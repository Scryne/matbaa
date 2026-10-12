"""Printify API v1 istemcisi (developers.printify.com, 2026-10-13 okundu).

Sınırlar: genel 600/dk, katalog 100/dk, yayın 200/30 dk; hatalı istek oranı toplamın %5'ini aşmamalı.
Görsel base64 yüklenir (genel bir URL'imiz yok); baskı dosyası önce içerik kutusuna kırpılır.
"""

from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from PIL import Image

from .http import KULLANICI, istek

TABAN = "https://api.printify.com/v1"
YAYIN_ALANLARI = {
    "title": True,
    "description": True,
    "images": True,
    "variants": True,
    "tags": True,
    "keyFeatures": True,
    "shipping_template": True,
}


@dataclass(frozen=True)
class Yerlesim:
    x: float
    y: float
    scale: float


def yerlesim(kutu: tuple[int, int, int, int], tuval: tuple[int, int], alan: tuple[int, int]) -> Yerlesim:
    """Tuvaldeki içerik kutusunu, tuvalin tamamı yer tutucunun genişliğine oturacak şekilde yer tutucuya taşır.

    Printify koordinatı: yer tutucunun merkezi (0,5; 0,5); `scale` = görsel genişliği / yer tutucu genişliği.
    Tuval 4500x5400, tasarım üste hizalı: aynı oranla taşınınca göğüs hizası korunur.
    """
    x0, y0, x1, y1 = kutu
    tg, _ = tuval
    ag, ay = alan
    birim = ag / tg  # tuval pikseli → yer tutucu pikseli
    return Yerlesim(
        x=round(((x0 + x1) / 2) / tg, 5),
        y=round(((y0 + y1) / 2) * birim / ay, 5),
        scale=round((x1 - x0) / tg, 5),
    )


def kirp(png: Path) -> tuple[bytes, tuple[int, int, int, int], tuple[int, int]]:
    img = Image.open(png).convert("RGBA")
    kutu = img.getchannel("A").getbbox()
    if kutu is None:
        raise ValueError(f"{png}: boş baskı dosyası")
    b = io.BytesIO()
    img.crop(kutu).save(b, "PNG", optimize=True, dpi=(300, 300))
    return b.getvalue(), kutu, img.size


class Printify:
    def __init__(self, token: str | None = None, shop_id: str | None = None, http: httpx.Client | None = None, bekle=None):
        token = token or os.environ["PRINTIFY_TOKEN"]
        self.shop_id = shop_id or os.environ.get("PRINTIFY_SHOP_ID")
        self.http = http or httpx.Client(timeout=60)
        self.http.headers.update({"Authorization": f"Bearer {token}", "User-Agent": KULLANICI})
        self._bekle = bekle

    def _i(self, yontem: str, yol: str, **kw):
        ek = {"bekle": self._bekle} if self._bekle else {}
        return istek(self.http, yontem, f"{TABAN}{yol}", **ek, **kw).json()

    # --- keşif ---
    def dukkanlar(self) -> list[dict]:
        return self._i("GET", "/shops.json")

    def blueprint_bul(self, aranan: str) -> list[dict]:
        a = aranan.lower()
        return [
            b
            for b in self._i("GET", "/catalog/blueprints.json")
            if a in f"{b.get('brand', '')} {b.get('model', '')} {b.get('title', '')}".lower()
        ]

    def saglayicilar(self, blueprint_id: int) -> list[dict]:
        return self._i("GET", f"/catalog/blueprints/{blueprint_id}/print_providers.json")

    def varyantlar(self, blueprint_id: int, saglayici_id: int) -> list[dict]:
        return self._i("GET", f"/catalog/blueprints/{blueprint_id}/print_providers/{saglayici_id}/variants.json")["variants"]

    def kargo(self, blueprint_id: int, saglayici_id: int) -> dict:
        return self._i("GET", f"/catalog/blueprints/{blueprint_id}/print_providers/{saglayici_id}/shipping.json")

    # --- ürün ---
    def gorsel_yukle(self, png: Path, ad: str) -> tuple[str, tuple[int, int, int, int], tuple[int, int]]:
        veri, kutu, tuval = kirp(png)
        r = self._i("POST", "/uploads/images.json", json={"file_name": ad, "contents": base64.b64encode(veri).decode()})
        return r["id"], kutu, tuval

    def urun_olustur(self, govde: dict) -> dict:
        return self._i("POST", f"/shops/{self.shop_id}/products.json", json=govde)

    def yayinla(self, urun_id: str) -> dict:
        return self._i("POST", f"/shops/{self.shop_id}/products/{urun_id}/publish.json", json=YAYIN_ALANLARI)

    def urun(self, urun_id: str) -> dict:
        return self._i("GET", f"/shops/{self.shop_id}/products/{urun_id}.json")

    def siparisler(self, sayfa: int = 1) -> dict:
        return self._i("GET", f"/shops/{self.shop_id}/orders.json", params={"page": sayfa, "limit": 10})


def varyant_sec(varyantlar: list[dict], renkler: list[dict], bedenler: list[str]) -> dict[str, list[dict]]:
    """Katalog renk/beden listesine uyan varyantlar, mürekkep grubuna göre ("koyu" | "acik").

    Printify renk adları sağlayıcıya göre "Solid Black" gibi önek alabilir; ad bitişiyle eşlenir.
    """
    gruplar: dict[str, list[dict]] = {"koyu": [], "acik": []}
    for v in varyantlar:
        o = v.get("options", {})
        renk, beden = str(o.get("color", "")), str(o.get("size", ""))
        if beden not in bedenler:
            continue
        eslesen = next(
            (r for r in renkler if renk.lower() == r["ad"].lower() or renk.lower().endswith(" " + r["ad"].lower())), None
        )
        if eslesen:
            gruplar[eslesen["murekkep"]].append(v)
    return gruplar


def on_yer_tutucu(varyant: dict) -> tuple[str, int, int]:
    """Ön baskı alanı: DTG varsa o, yoksa ilk "front" ile başlayan."""
    on = [p for p in varyant.get("placeholders", []) if p["position"].startswith("front")]
    on.sort(key=lambda p: p.get("decoration_method") != "dtg")
    if not on:
        raise ValueError(f"varyant {varyant.get('id')}: ön baskı alanı yok")
    return on[0]["position"], on[0]["width"], on[0]["height"]


def urun_govdesi(
    baslik: str,
    aciklama: str,
    etiketler: list[str],
    blueprint_id: int,
    saglayici_id: int,
    gruplar: dict[str, list[dict]],
    gorseller: dict[str, tuple[str, tuple[int, int, int, int], tuple[int, int]]],
    fiyat_usd: float,
    buyuk_beden_ek: dict[str, float],
) -> dict:
    variants, print_areas = [], []
    for murekkep, vs in gruplar.items():
        if not vs:
            continue
        gorsel_id, kutu, tuval = gorseller[murekkep]
        pozisyon, ag, ay = on_yer_tutucu(vs[0])
        y = yerlesim(kutu, tuval, (ag, ay))
        for v in vs:
            ek = buyuk_beden_ek.get(str(v.get("options", {}).get("size")), 0.0)
            variants.append({"id": v["id"], "price": round((fiyat_usd + ek) * 100), "is_enabled": True})
        print_areas.append(
            {
                "variant_ids": [v["id"] for v in vs],
                "placeholders": [
                    {"position": pozisyon, "images": [{"id": gorsel_id, "x": y.x, "y": y.y, "scale": y.scale, "angle": 0}]}
                ],
            }
        )
    if not variants:
        raise ValueError("hiç varyant eşleşmedi: renk/beden adlarını Printify kataloğuyla karşılaştır")
    return {
        "title": baslik,
        "description": aciklama.replace("\n\n", "<br><br>"),
        "blueprint_id": blueprint_id,
        "print_provider_id": saglayici_id,
        "tags": etiketler,
        "variants": variants,
        "print_areas": print_areas,
    }
