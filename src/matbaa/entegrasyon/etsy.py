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

    def _yenile(self) -> None:
        kayit = self._kayit()
        # Aynı koşudaki başka bir istemcinin aldığı erişim token'ı hâlâ geçerliyse kullanılır: her `Etsy()` yeni yenileme yapmaz.
        if kayit.get("access_token") and kayit.get("bitis", 0) > time.time():
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

    def gorsel_sirala(self, listing_id: int, listing_image_id: int, rank: int) -> dict:
        """Var olan görseli yeniden yüklemeden sıraya taşır (uploadListingImage + `listing_image_id`)."""
        return self._i(
            "POST",
            f"/shops/{self.shop_id}/listings/{listing_id}/images",
            data={"listing_image_id": str(listing_image_id), "rank": str(rank)},
        )

    def gorsel_sil(self, listing_id: int, listing_image_id: int) -> dict:
        return self._i("DELETE", f"/shops/{self.shop_id}/listings/{listing_id}/images/{listing_image_id}")
