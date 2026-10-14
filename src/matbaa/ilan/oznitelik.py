"""Etsy öznitelikleri (attributes): arama filtreleri (renk, kol boyu, tatil, vesile, baskı türü) ve kategori zorunluları.

Printify ilanı özniteliksiz açıyor (2026-10-14 canlı: 6 ilanın hepsi boş; hoodie kategorisinde "Clothing closure" zorunlu).
Varyantlar Custom1/Custom2 (513/514) üzerinde, renk ve kol boyu öznitelik olarak çakışmadan yazılır. Ürün sabitleri
`config/urunler.toml` `oznitelik`, baskı türü niş kartında (`etsy_grafik`). Tatil: basılı satır → açık hediye mevsimi
(`config/takvim.toml` `etsy_tatil`) → başlık → niş kartı; başlıktaki genel "Father's Day Gift" Ekim'de Christmas'ı ezmez (canlı
ilk denemede ezdi). Vesile: basılı satır ya da başlık → niş kartı (`etsy_vesile`). Adlar Etsy'nin değer adlarıdır; ilanın
kategorisinde olmayan özellik ya da değer yazımda atlanır (kupa kategorisinde kol boyu yok).
"""

from __future__ import annotations

import re
from datetime import date

from matbaa.fiyat import urunler
from matbaa.ifade.uret import aktif_mevsimler, nisler

# Metinde geçen tatil: mevsimden önce gelir ("Gobble Gobble" Kasım'da da Thanksgiving'dir). "turkey" yok: bowling'de üç strike.
METIN_TATIL = [
    (r"thanksgiving|gobble|pilgrim", "Thanksgiving"),
    (r"christmas|xmas|santa|stocking stuffer|holiday sweater", "Christmas"),
    (r"halloween|spooky|trick or treat", "Halloween"),
    (r"father'?s day", "Father's Day"),
    (r"mother'?s day", "Mother's Day"),
    (r"valentine", "Valentine's Day"),
    (r"st\.? patrick|shamrock|lucky charm", "St Patrick's Day"),
    (r"new year", "New Year's"),
]
METIN_VESILE = [
    (r"birthday|\bbday\b|\b[1-9]0th\b|over the hill", "Birthday"),
    (r"retire", "Retirement"),
    (r"graduat|\bgrad\b|class of 20\d\d|senior night", "Graduation"),
]
VARSAYILAN_GRAFIK = "Humorous saying"


def _ilk(desenler: list[tuple[str, str]], metin: str) -> str | None:
    return next((deger for desen, deger in desenler if re.search(desen, metin, re.I)), None)


def istenen(urun: str, nis: str, satirlar: list[str], baslik: str = "", gun: date | None = None) -> dict[str, list[str]]:
    """İlanın olması gereken öznitelikleri {Etsy özellik adı: [değer adları]}. Gün değişince tatil değişebilir (mevsim)."""
    k = nisler().get(nis, {})
    o = {ad: list(d) for ad, d in urunler()[urun].get("oznitelik", {}).items()}
    o["Clothing graphic"] = [k.get("etsy_grafik", VARSAYILAN_GRAFIK)]
    basili = " ".join(satirlar)
    mevsim = next((m["etsy_tatil"] for m in aktif_mevsimler(nis, gun) if m.get("etsy_tatil")), None)
    if tatil := _ilk(METIN_TATIL, basili) or mevsim or _ilk(METIN_TATIL, baslik) or k.get("etsy_tatil"):
        o["Holiday"] = [tatil]
    if vesile := _ilk(METIN_VESILE, f"{basili} {baslik}") or k.get("etsy_vesile"):
        o["Occasion"] = [vesile]
    return o


def cozumle(istek: dict[str, list[str]], ozellikler: list[dict]) -> tuple[dict[int, tuple[list[int], list[str]]], list[str]]:
    """İstenen adları kategorinin özellik tablosuna (getPropertiesByTaxonomyId) eşler: {property_id: (value_ids, values)}.

    Ad `name` ya da `display_name` ile eşleşir ("Materials" ↔ "Material multi"). Tek değerli özelliğe ilk değer yazılır.
    İkinci dönüş: kategoride bulunmayan ya da değeri tanınmayan istekler (kayıt için)."""
    tablo = {}
    for p in ozellikler:
        if p.get("supports_attributes"):
            for ad in {p.get("name"), p.get("display_name")} - {None}:
                tablo.setdefault(ad.lower(), p)
    sonuc, atlanan = {}, []
    for ad, degerler in istek.items():
        p = tablo.get(ad.lower())
        if not p:
            atlanan.append(ad)
            continue
        olasi = {v["name"].lower(): v for v in p.get("possible_values", [])}
        bulunan = [olasi[d.lower()] for d in degerler if d.lower() in olasi]
        if not bulunan:
            atlanan.append(f"{ad}={degerler}")
            continue
        if not p.get("is_multivalued"):
            bulunan = bulunan[:1]
        sonuc[int(p["property_id"])] = ([int(v["value_id"]) for v in bulunan], [v["name"] for v in bulunan])
    return sonuc, atlanan
