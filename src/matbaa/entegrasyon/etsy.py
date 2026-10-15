"""Etsy Open API v3 istemcisi — yalnız kendi mağazamız (Seller App).

Şemadan doğrulandı (etsy.com/openapi/generated/oas/3.0.0.json, 2026-10-13): `x-api-key` = `keystring:shared_secret`;
token adresi `https://api.etsy.com/v3/public/oauth/token` (developers.etsy.com authentication, 2026-10-13; 9 Şubat 2026'dan beri
shared secret'sız istek reddediliyor); `updateListing` gövdesi form-urlencoded ve
`production_partner_ids`, `state`, `tags` alanlarını taşır. Erişim token'ı 1 saat, yenileme token'ı 90 gün ve
her yenilemede değişir: yeni yenileme token'ı (ve geçerli erişim token'ı) `TOKEN_DOSYASI`na atomik yazılır.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from matbaa.ayar import KOK

from .http import KULLANICI, ApiHatasi, istek

TABAN = "https://openapi.etsy.com/v3/application"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
TOKEN_DOSYASI = KOK / ".etsy_token.json"  # git dışı


class Etsy:
    def __init__(
        self,
        keystring: str | None = None,
        shared_secret: str | None = None,
        shop_id: str | None = None,
        http: httpx.Client | None = None,
        token_dosyasi: Path = TOKEN_DOSYASI,
        bekle=None,
    ):
        self.keystring = keystring or os.environ["ETSY_KEYSTRING"]
        self.secret = shared_secret or os.environ["ETSY_SHARED_SECRET"]
        self.shop_id = shop_id or os.environ.get("ETSY_SHOP_ID")
        self.http = http or httpx.Client(timeout=60)
        self.http.headers.update({"x-api-key": f"{self.keystring}:{self.secret}", "User-Agent": KULLANICI})
        self.token_dosyasi = token_dosyasi
        self._bekle = bekle
        self._erisim: str | None = None
        self._bitis = 0.0
        self._taksonomi: dict[int, list[dict]] = {}
        self._bolumler: dict[str, int] | None = None

    def _kayit(self) -> dict:
        try:
            return json.loads(self.token_dosyasi.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _kaydet(self, kayit: dict) -> None:
        """Atomik yazım: yenileme token'ı her yenilemede değişir, yarım yazılmış dosya mağazayı yeniden yetkilendirmeye düşürür."""
        gecici = self.token_dosyasi.with_name(self.token_dosyasi.name + ".tmp")
        gecici.write_text(json.dumps(kayit), encoding="utf-8")
        gecici.replace(self.token_dosyasi)

    def _yenile(self, zorla: bool = False) -> None:
        """`zorla`: kayıttaki erişim token'ı süresi dolmamış görünse de kullanılmaz (Etsy 401 döndü: token geçersiz)."""
        kayit = self._kayit()
        # Aynı koşudaki başka bir istemcinin aldığı erişim token'ı hâlâ geçerliyse kullanılır: her `Etsy()` yeni yenileme yapmaz.
        if not zorla and kayit.get("access_token") and kayit.get("bitis", 0) > time.time():
            self._erisim, self._bitis = kayit["access_token"], kayit["bitis"]
            return
        yenileme = kayit.get("refresh_token") or os.environ.get("ETSY_REFRESH_TOKEN")
        if not yenileme:
            raise RuntimeError("Etsy yenileme token'ı yok: önce `uv run python scripts/etsy_yetki.py`")
        try:
            r = istek(
                self.http,
                "POST",
                TOKEN_URL,
                data={"grant_type": "refresh_token", "client_id": self.keystring, "refresh_token": yenileme},
            )
        except ApiHatasi as e:
            if e.durum in (400, 401):
                raise RuntimeError(
                    f"Etsy yenileme token'ı reddedildi ({e.durum}): yeniden yetkilendir → `uv run python scripts/etsy_yetki.py`"
                ) from e
            raise
        d = r.json()
        self._erisim, self._bitis = d["access_token"], time.time() + d.get("expires_in", 3600) - 120
        self._kaydet(
            {
                "refresh_token": d["refresh_token"],
                "yenilendi": int(time.time()),
                "access_token": self._erisim,
                "bitis": self._bitis,
            }
        )

    def _i(self, yontem: str, yol: str, **kw) -> dict:
        if not self._erisim or time.time() > self._bitis:
            self._yenile()
        ek = {"bekle": self._bekle} if self._bekle else {}
        try:
            r = istek(self.http, yontem, f"{TABAN}{yol}", headers={"Authorization": f"Bearer {self._erisim}"}, **ek, **kw)
        except ApiHatasi as e:
            # Süresi dolmamış görünen erişim token'ı Etsy'de geçersiz olabilir (yeniden yetki, Etsy tarafında iptal): bir kez
            # zorla yenilenip istek yinelenir. 401'de istek işlenmemiştir, yinelemek mükerrer kaynak açmaz.
            if e.durum != 401:
                raise
            self._yenile(zorla=True)
            r = istek(self.http, yontem, f"{TABAN}{yol}", headers={"Authorization": f"Bearer {self._erisim}"}, **ek, **kw)
        return r.json() if r.content else {}

    def uretim_ortaklari(self) -> list[dict]:
        return self._i("GET", f"/shops/{self.shop_id}/production-partners")["results"]

    def ilan(self, listing_id: int) -> dict:
        return self._i("GET", f"/listings/{listing_id}")

    def ilan_guncelle(self, listing_id: int, **alanlar) -> dict:
        # Form gövdesinde dizi alanları virgülle birleşir (şema: "A comma-separated list").
        form = {k: ",".join(map(str, v)) if isinstance(v, list | tuple) else v for k, v in alanlar.items()}
        return self._i("PATCH", f"/shops/{self.shop_id}/listings/{listing_id}", data=form)

    def hazirlama_ayarla(self, listing_id: int, readiness_state_id: int) -> bool:
        """İşlem süresi profili ilanda değil, her varyantın teklifinde durur (`updateListing` alanı yok sayar, 2026-10-14
        canlı denendi). Printify ilanı kendi "2-5 days" profiline bağlıyor; mağaza vaadi 3-5 gün. Envanter (SKU, fiyat, adet
        aynen; Printify siparişi SKU'dan eşler) yalnız profil farklıysa `updateListingInventory` (JSON, şema 2026-10-14) ile
        yazılır. Değiştiyse True."""
        env = self._i("GET", f"/listings/{listing_id}/inventory")
        urunler = [
            p | {"offerings": [o for o in p["offerings"] if not o.get("is_deleted")]}
            for p in env["products"]
            if not p.get("is_deleted")
        ]
        if all(o.get("readiness_state_id") == readiness_state_id for p in urunler for o in p["offerings"]):
            return False
        alanlar = ("property_id", "value_ids", "scale_id", "property_name", "values")
        govde = {
            "products": [
                {
                    "sku": p.get("sku"),
                    "property_values": [{k: v.get(k) for k in alanlar} for v in p.get("property_values", [])],
                    "offerings": [
                        {
                            "price": o["price"]["amount"] / o["price"]["divisor"],
                            "quantity": o["quantity"],
                            "is_enabled": o["is_enabled"],
                            "readiness_state_id": readiness_state_id,
                        }
                        for o in p["offerings"]
                    ],
                }
                for p in urunler
            ],
            **{
                k: env.get(k, [])
                for k in ("price_on_property", "quantity_on_property", "sku_on_property", "readiness_state_on_property")
            },
        }
        self._i("PUT", f"/listings/{listing_id}/inventory", json=govde)
        return True

    def taksonomi_ozellikleri(self, taxonomy_id: int) -> list[dict]:
        """getPropertiesByTaxonomyId: kategorinin öznitelikleri (`property_id`, `name`, `display_name`, `possible_values`,
        `is_multivalued`, `supports_attributes`). Kategori başına bir kez okunur."""
        if taxonomy_id not in self._taksonomi:
            self._taksonomi[taxonomy_id] = self._i("GET", f"/seller-taxonomy/nodes/{taxonomy_id}/properties")["results"]
        return self._taksonomi[taxonomy_id]

    def ozellik_yaz(self, listing_id: int, property_id: int, value_ids: list[int], values: list[str]) -> dict:
        """updateListingProperty (form; dizi virgülle, 2026-10-14 canlı denendi: "102,210" → Cotton, Polyester)."""
        return self._i(
            "PUT",
            f"/shops/{self.shop_id}/listings/{listing_id}/properties/{property_id}",
            data={"value_ids": ",".join(map(str, value_ids)), "values": ",".join(values)},
        )

    def ozellik_sil(self, listing_id: int, property_id: int) -> dict:
        return self._i("DELETE", f"/shops/{self.shop_id}/listings/{listing_id}/properties/{property_id}")

    def bolum_kimligi(self, baslik: str) -> int:
        """Mağaza bölümü (Shop section) kimliği; yoksa açılır (createShopSection, form `title`). Liste koşu başına bir kez okunur."""
        if self._bolumler is None:
            self._bolumler = {
                b["title"]: int(b["shop_section_id"]) for b in self._i("GET", f"/shops/{self.shop_id}/sections")["results"]
            }
        if baslik not in self._bolumler:
            b = self._i("POST", f"/shops/{self.shop_id}/sections", data={"title": baslik})
            self._bolumler[baslik] = int(b["shop_section_id"])
        return self._bolumler[baslik]

    def kargo_profilleri(self) -> list[dict]:
        return self._i("GET", f"/shops/{self.shop_id}/shipping-profiles")["results"]

    def kargo_profili_olustur(self, **alanlar) -> dict:
        """createShopShippingProfile (form): zorunlu title, origin_country_iso, primary_cost, secondary_cost (şema 2026-10-13)."""
        return self._i("POST", f"/shops/{self.shop_id}/shipping-profiles", data=alanlar)

    def makbuzlar(self, min_son_degisim: int | None = None, limit: int = 100, sayfa_maks: int = 20) -> list[dict]:
        """Ödenmiş makbuzlar (yeniden eskiye), sayfalı: ilk koşuda ya da uzun aradan sonra 100'den fazlası kaybolmaz."""
        params: dict = {"limit": limit, "was_paid": "true"}
        if min_son_degisim:
            params["min_last_modified"] = min_son_degisim
        sonuc: list[dict] = []
        for n in range(sayfa_maks):
            sayfa = self._i("GET", f"/shops/{self.shop_id}/receipts", params=params | {"offset": n * limit})
            sonuc += sayfa.get("results", [])
            if len(sonuc) >= sayfa.get("count", 0) or len(sayfa.get("results", [])) < limit:
                break
        return sonuc

    def aktif_ilanlar(self) -> list[dict]:
        """Mağazanın aktif ilanları; `views` günde bir kez sayılan toplam görüntülenme, `num_favorers` favori (şema 2026-10-13)."""
        sonuc, ofset = [], 0
        while True:
            sayfa = self._i("GET", f"/shops/{self.shop_id}/listings", params={"state": "active", "limit": 100, "offset": ofset})
            sonuc += sayfa["results"]
            ofset += 100
            if ofset >= sayfa.get("count", 0) or not sayfa["results"]:
                return sonuc

    def ilan_gorselleri(self, listing_id: int) -> list[dict]:
        """getListingImages: rank sıralı görseller (`listing_image_id`, `rank`, `url_570xN`)."""
        return sorted(self._i("GET", f"/listings/{listing_id}/images")["results"], key=lambda g: g["rank"])

    def gorsel_yukle(self, listing_id: int, png: bytes, rank: int, ad: str = "gorsel.jpg", alt_metin: str = "") -> dict:
        """uploadListingImage (multipart `image`): yeni görsel `rank` sırasına girer, sonrakiler kayar."""
        veri = {"rank": str(rank)} | ({"alt_text": alt_metin[:500]} if alt_metin else {})
        return self._i(
            "POST", f"/shops/{self.shop_id}/listings/{listing_id}/images", files={"image": (ad, png, "image/jpeg")}, data=veri
        )

    def gorsel_sirala(self, listing_id: int, listing_image_id: int, rank: int, alt_metin: str = "") -> dict:
        """Var olan görseli yeniden yüklemeden sıraya taşır (uploadListingImage + `listing_image_id`).

        Etsy bu istekte gelmeyen `alt_text`'i boşaltır (2026-10-15 canlı ölçüm: sıralanan her görselin alt metni silinmişti):
        kendi görselimizin alt metni her sıralamada yeniden gönderilir."""
        veri = {"listing_image_id": str(listing_image_id), "rank": str(rank)} | (
            {"alt_text": alt_metin[:500]} if alt_metin else {}
        )
        return self._i("POST", f"/shops/{self.shop_id}/listings/{listing_id}/images", data=veri)

    # --- isimli süs (Faz 11): Printify'a bağlı olmayan, doğrudan açılan ilan ---
    def taslak_ilan(self, **alanlar) -> dict:
        """createDraftListing (form; dizi alanları virgülle). Taslak ücretsiz; listeleme ücreti aktifleşince."""
        form = {k: ",".join(map(str, v)) if isinstance(v, list | tuple) else v for k, v in alanlar.items()}
        return self._i("POST", f"/shops/{self.shop_id}/listings", data=form)

    def envanter_yaz(self, listing_id: int, govde: dict) -> dict:
        return self._i("PUT", f"/listings/{listing_id}/inventory", json=govde)

    def kisisellestirme_yaz(self, listing_id: int, sorular: list[dict]) -> dict:
        """updateListingPersonalization: soruların tamamını değiştirir. Eski `personalization_*` ilan alanları 2026'da kalktı
        (migration guide); alıcının cevabı makbuzda `transactions[].variations[]`, `property_id == 54`."""
        return self._i(
            "POST", f"/shops/{self.shop_id}/listings/{listing_id}/personalization", json={"personalization_questions": sorular}
        )

    def kisisellestirme(self, listing_id: int) -> dict:
        return self._i("GET", f"/listings/{listing_id}/personalization")

    def takip_yaz(self, receipt_id: int, takip: str, tasiyici: str) -> dict:
        """createReceiptShipment: alıcıya Etsy'den kargo e-postası gider. 2026-10-15 denendi: uygulamamız erişebiliyor (403 değil)."""
        return self._i(
            "POST",
            f"/shops/{self.shop_id}/receipts/{receipt_id}/tracking",
            data={"tracking_code": takip, "carrier_name": tasiyici},
        )

    def gorsel_sil(self, listing_id: int, listing_image_id: int) -> dict:
        return self._i("DELETE", f"/shops/{self.shop_id}/listings/{listing_id}/images/{listing_image_id}")
