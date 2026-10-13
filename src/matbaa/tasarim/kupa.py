"""Kupa baskı dosyası (Faz 14): tişört tasarımının açık zemin (koyu mürekkep) sürümünden yatay sarma görseli.

Kupa baskı alanı 2475x1155 (11oz/15oz, SwiftPOD; 2026-10-13 Printify kataloğu), kupanın çevresini sarar. Tasarım iki kopya basılır
(çeyrek ve üç çeyrek noktalarında): sağ ya da sol elle tutan, karşıdaki kişi de tasarımı görür (Etsy'de yaygın kupa düzeni).
Kupa beyaz seramik: tişörtün açık kumaş sürümü (koyu mürekkep + açık kumaş vurgusu) olduğu gibi kullanılır.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

KUPA_G, KUPA_Y = 2475, 1155
DOLULUK_G, DOLULUK_Y = 0.40, 0.84  # bir kopyanın en çok alan kesri: sapa ve kupa kenarına pay


def kupa_gorseli(koyu_png: str | Path) -> Image.Image:
    tasarim = Image.open(koyu_png).convert("RGBA")
    kutu = tasarim.getchannel("A").getbbox()
    if kutu is None:
        raise ValueError(f"{koyu_png}: boş tasarım")
    icerik = tasarim.crop(kutu)
    k = min(KUPA_G * DOLULUK_G / icerik.width, KUPA_Y * DOLULUK_Y / icerik.height)
    kopya = icerik.resize((max(1, round(icerik.width * k)), max(1, round(icerik.height * k))), Image.LANCZOS)
    tuval = Image.new("RGBA", (KUPA_G, KUPA_Y), (0, 0, 0, 0))
    for merkez in (0.25, 0.75):
        tuval.alpha_composite(kopya, (round(KUPA_G * merkez - kopya.width / 2), round((KUPA_Y - kopya.height) / 2)))
    return tuval


def kaydet(koyu_png: str | Path, hedef: str | Path) -> Path:
    hedef = Path(hedef)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    kupa_gorseli(koyu_png).save(hedef, dpi=(300, 300), optimize=True)
    return hedef
