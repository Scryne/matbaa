"""Mağaza vitrini görselleri: Etsy kapak görseli (banner), TikTok profil fotoğrafı, logo ile aynı dil (pul + kalp, krem/lacivert/mercan).

Yazılar fonttan yola çevrilir (tasarım motorunun `yazi` modülü, OFL fontlar), çizimler `tasarim.ikon`'dan gelir:
görsel her makinede aynı çıkar, ölçü değişirse yeniden üretilir.

    uv run python scripts/marka_varliklari.py
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import resvg_py
from PIL import Image

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "src"))

from matbaa.tasarim import ikon  # noqa: E402
from matbaa.tasarim.yazi import font  # noqa: E402

KREM, LACIVERT, MERCAN = "#F4EDE1", "#2B3A55", "#E07A5F"
CIKTI = KOK / "varliklar" / "marka"


def yazi(
    metin: str, dosya: str, x_merkez: float, y_ust: float, yukseklik: float, renk: str, harf_araligi: float = 0.0
) -> tuple[str, float]:
    """Metni büyük harf yüksekliği `yukseklik` olacak şekilde ortalı yerleştirir: (svg, genişlik)."""
    s = font(dosya).satir(metin, harf_araligi)
    k = yukseklik / s.yukseklik
    tx, ty = x_merkez - (s.x0 + s.genislik / 2) * k, y_ust - s.y0 * k
    return f'<path fill="{renk}" d="{s.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})"/>', s.genislik * k


def pul(x: float, y: float, boy: float) -> str:
    """Logodaki pul + kalp (etsy-shop-icon.svg ile aynı geometri), sol üst köşesi (x, y), kenar `boy`."""
    k = boy / 176
    delik = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="8"/>'
        for i in range(9)
        for cx, cy in ((40 + i * 22, 40), (40 + i * 22, 216), (40, 40 + i * 22), (216, 40 + i * 22))
    )
    return (
        f'<g transform="translate({x - 40 * k:.2f} {y - 40 * k:.2f}) scale({k:.5f})">'
        f'<rect x="40" y="40" width="176" height="176" fill="{LACIVERT}"/><g fill="{KREM}">{delik}</g>'
        f'<path fill="{MERCAN}" d="M128 164.9 L89.1 126 A27.5 27.5 0 0 1 128 87.1 A27.5 27.5 0 0 1 166.9 126 Z"/></g>'
    )


def kapak(g: int = 3360, y: int = 840) -> str:
    """Etsy kapak görseli: ortada pul + mağaza adı + slogan + niş çizimleri sırası; kenarlar boş (mobil kırpma payı)."""
    parcalar = [f'<rect width="{g}" height="{y}" fill="{KREM}"/>']
    boy = y * 0.50
    ad, ad_g = yazi("HobbyHeartPrints", "AlfaSlabOne-Regular.ttf", 0, 0, y * 0.17, LACIVERT, 0.01)
    blok_g = boy + y * 0.08 + ad_g
    x0 = (g - blok_g) / 2
    ust = (y - boy) / 2
    parcalar.append(pul(x0, ust, boy))
    metin_x = x0 + boy + y * 0.08 + ad_g / 2
    ad_svg, _ = yazi("HobbyHeartPrints", "AlfaSlabOne-Regular.ttf", metin_x, ust + boy * 0.04, y * 0.17, LACIVERT, 0.01)
    parcalar.append(ad_svg)
    slogan, sl_g = yazi(
        "RETRO TEES FOR THE HOBBIES YOU LOVE", "BebasNeue-Regular.ttf", metin_x, ust + boy * 0.47, y * 0.075, MERCAN, 0.06
    )
    parcalar.append(slogan)
    # Niş çizimleri sırası: sloganın genişliğine eşit aralıklı, lacivert.
    adlar = ["balik", "yumak", "kurek", "kronometre", "kalp"]
    h_i = y * 0.11
    for i, a in enumerate(adlar):
        cx = metin_x - sl_g / 2 + sl_g * (i + 0.5) / len(adlar)
        svg, _, h = ikon.yerlestir(a, cx, ust + boy - h_i, h_i, genislik_maks=h_i * 1.15)
        if h < h_i:  # genişlikten küçülen çizim (balık) satırın tabanına otursun
            svg, _, _ = ikon.yerlestir(a, cx, ust + boy - h, h, genislik_maks=h_i * 1.15)
        parcalar.append(f'<g fill="{LACIVERT}" color="{LACIVERT}">{svg}</g>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{g}" height="{y}" viewBox="0 0 {g} {y}">{"".join(parcalar)}</svg>'


def profil(boy: int = 1000) -> str:
    """Yuvarlak kırpılan profil fotoğrafı (TikTok): pulun köşeleri daireye sığar (kenar <= çap/sqrt2, payla %60)."""
    k = boy * 0.6
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{boy}" height="{boy}" viewBox="0 0 {boy} {boy}">'
        f'<rect width="{boy}" height="{boy}" fill="{KREM}"/>{pul((boy - k) / 2, (boy - k) / 2, k)}</svg>'
    )


def kaydet(svg: str, ad: str, g: int, y: int) -> Path:
    CIKTI.mkdir(parents=True, exist_ok=True)
    (CIKTI / f"{ad}.svg").write_text(svg, encoding="utf-8")
    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, width=g, height=y, skip_system_fonts=True))
    yol = CIKTI / f"{ad}.png"
    Image.open(io.BytesIO(png)).convert("RGB").save(yol, optimize=True)
    return yol


if __name__ == "__main__":
    # Etsy önerisi 1600x400 (4:1, en az 1200x300); mobilde kenarlar kırpılır, içerik ortadaki ~%56 genişlikte (araştırma 2026-10-13).
    print(kaydet(kapak(1600, 400), "etsy-kapak", 1600, 400))
    print(kaydet(profil(1000), "tiktok-profil", 1000, 1000))
