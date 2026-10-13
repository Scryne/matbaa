"""İlan fotoğrafları: Printify'ın renk mockup'larına eklenen kendi görsellerimiz (beden tablosu, baskı yakın planı, güven kartı, renkler).

Vitrin ve ilan metni "beden tablosu fotoğraflarda" diyor; Printify Comfort Colors/Gildan ilanına tablo koymuyor (2026-10-13, ilk ilanın
6 görseli yalnız renk mockup'ı). Görseller marka dilinde (krem/lacivert/mercan, vitrin kapağıyla aynı fontlar), yazılar fonttan yola
çevrilir: her makinede aynı çıkar. Ölçüler `config/urunler.toml` `olculer`den (kaynaklı); tablo yoksa görsel üretilmez.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image, ImageFilter

from matbaa.fiyat import urunler
from matbaa.tasarim import ikon
from matbaa.tasarim.yazi import font

KENAR = 2000  # kare: Printify mockup'larıyla (2048) aynı oran, galeride kırpılmaz
KREM, LACIVERT, MERCAN, ACIK_CIZGI = "#F4EDE1", "#2B3A55", "#E07A5F", "#D9CDB8"
BASLIK_F, GOVDE_F, RAKAM_F = "AlfaSlabOne-Regular.ttf", "ArchivoBlack-Regular.ttf", "BebasNeue-Regular.ttf"


def _yazi(
    metin: str,
    dosya: str,
    x: float,
    y_ust: float,
    yukseklik: float,
    renk: str,
    hiza: str = "orta",
    ara: float = 0.0,
    maks_g: float | None = None,
) -> tuple[str, float]:
    """Büyük harf yüksekliği `yukseklik` (`maks_g`'yi aşarsa küçülür); `hiza` orta/sol/sag x'e göre. (svg, genişlik)"""
    s = font(dosya).satir(metin, ara)
    k = yukseklik / s.yukseklik
    if maks_g:
        k = min(k, maks_g / s.genislik)
    g = s.genislik * k
    sol = {"orta": x - g / 2, "sol": x, "sag": x - g}[hiza]
    tx, ty = sol - s.x0 * k, y_ust - s.y0 * k
    return f'<path fill="{renk}" d="{s.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})"/>', g


def _svg(parcalar: list[str], zemin: str = KREM) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{KENAR}" height="{KENAR}" viewBox="0 0 {KENAR} {KENAR}">'
        f'<rect width="{KENAR}" height="{KENAR}" fill="{zemin}"/>{"".join(parcalar)}</svg>'
    )


def _png(svg: str) -> Image.Image:
    return Image.open(
        io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=KENAR, height=KENAR, skip_system_fonts=True)))
    ).convert("RGB")


def beden_tablosu(urun: str) -> Image.Image | None:
    """Beden tablosu: Size / Width / Length (inç, düz yatırılmış). Kupa için boy ve çap."""
    u = urunler()[urun]
    olcu = u.get("olculer")
    if not olcu:
        return None
    p: list[str] = []
    p.append(_yazi("SIZE GUIDE", BASLIK_F, KENAR / 2, 170, 110, LACIVERT, ara=0.04)[0])
    p.append(
        _yazi(
            u["blank"].upper() + "  ·  " + olcu.get("kesim", "UNISEX FIT").upper(), RAKAM_F, KENAR / 2, 340, 62, MERCAN, ara=0.08
        )[0]
    )
    sutunlar = olcu["sutunlar"]  # ["SIZE", "WIDTH", "LENGTH"]
    satirlar = olcu["satirlar"]  # [["S", "20", "28"], ...]
    sol, sag, ust = 260, KENAR - 260, 520
    satir_y = min(150, (KENAR - 330 - ust) / (len(satirlar) + 1))
    xs = [sol + (sag - sol) * (i + 0.5) / len(sutunlar) for i in range(len(sutunlar))]
    p.append(f'<rect x="{sol}" y="{ust}" width="{sag - sol}" height="{satir_y}" rx="22" fill="{LACIVERT}"/>')
    for x, s in zip(xs, sutunlar, strict=True):
        p.append(_yazi(s, GOVDE_F, x, ust + satir_y * 0.32, satir_y * 0.34, KREM, ara=0.06)[0])
    for i, satir in enumerate(satirlar):
        y = ust + satir_y * (i + 1)
        if i % 2:
            p.append(f'<rect x="{sol}" y="{y}" width="{sag - sol}" height="{satir_y}" fill="{ACIK_CIZGI}" opacity="0.45"/>')
        for j, (x, v) in enumerate(zip(xs, satir, strict=True)):
            p.append(
                _yazi(v, GOVDE_F if j == 0 else RAKAM_F, x, y + satir_y * 0.3, satir_y * (0.36 if j == 0 else 0.42), LACIVERT)[0]
            )
    alt = ust + satir_y * (len(satirlar) + 1) + 70
    for k, not_ in enumerate(olcu.get("notlar", [])):
        p.append(_yazi(not_, RAKAM_F, KENAR / 2, alt + k * 80, 50, LACIVERT, ara=0.04)[0])
    return _png(_svg(p))


def _doku(g: int, y: int, renk: str, tohum: int) -> Image.Image:
    """Kumaş zemini: renk + ince örgü dokusu (yatay/dikey hafif gürültü), baskı yakın planına gerçekçilik."""
    rnd = np.random.default_rng(tohum)
    taban = np.array(Image.new("RGB", (1, 1), renk).getpixel((0, 0)), dtype=np.float32)
    gurultu = rnd.normal(0, 1, (y, g)).astype(np.float32)
    orgu = (np.sin(np.arange(g) * 1.9)[None, :] + np.sin(np.arange(y) * 2.3)[:, None]) * 0.6
    ton = (gurultu * 3.2 + orgu * 2.0)[..., None]
    return Image.fromarray(np.clip(taban + ton, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(0.6))


def yakin_plan(tasarim_png: str | Path, kumas_hex: str, tohum: int = 0) -> Image.Image:
    """Baskının yakın planı: tasarım kumaş dokusunda, kadrajı dolduracak kadar büyük."""
    t = Image.open(tasarim_png).convert("RGBA")
    t = t.crop(t.getchannel("A").getbbox())
    k = min(KENAR * 0.82 / t.width, KENAR * 0.82 / t.height)
    t = t.resize((round(t.width * k), round(t.height * k)), Image.LANCZOS)
    zemin = _doku(KENAR, KENAR, kumas_hex, tohum).convert("RGBA")
    zemin.alpha_composite(t, ((KENAR - t.width) // 2, (KENAR - t.height) // 2))
    return zemin.convert("RGB")


GUVEN = [
    ("parilti", "PRINTED TO ORDER", "Made just for you by our US production partner"),
    ("kamyon", "FREE US SHIPPING", "Ships with tracking after 3 to 5 business days"),
    ("hediye", "READY TO GIFT", "Ships straight to them with their address at checkout"),
    ("kalp", "WE'VE GOT YOU", "Damaged or misprinted? We replace or refund it"),
]


def guven_karti() -> Image.Image:
    p: list[str] = [_yazi("WHY SHOP WITH US", BASLIK_F, KENAR / 2, 170, 100, LACIVERT, ara=0.04)[0]]
    ust, adim = 420, 380
    for i, (ik, baslik, alt) in enumerate(GUVEN):
        y = ust + i * adim
        p.append(f'<circle cx="330" cy="{y + 120}" r="130" fill="{LACIVERT}"/>')
        svg, _, _ = ikon.yerlestir(ik, 330, y + 50, 140, genislik_maks=150)
        p.append(f'<g fill="{KREM}" color="{KREM}">{svg}</g>')
        p.append(_yazi(baslik, GOVDE_F, 540, y + 40, 78, LACIVERT, hiza="sol", ara=0.03, maks_g=KENAR - 540 - 150)[0])
        p.append(_yazi(alt.upper(), RAKAM_F, 540, y + 165, 56, MERCAN, hiza="sol", ara=0.05, maks_g=KENAR - 540 - 150)[0])
    return _png(_svg(p))


def renk_karti(urun: str) -> Image.Image:
    u = urunler()[urun]
    renkler = u["renkler"]
    p: list[str] = [_yazi("AVAILABLE COLORS", BASLIK_F, KENAR / 2, 170, 100, LACIVERT, ara=0.04)[0]]
    p.append(_yazi(u["blank"].upper(), RAKAM_F, KENAR / 2, 330, 60, MERCAN, ara=0.08)[0])
    sutun = 3 if len(renkler) > 4 else 2
    satir_n = (len(renkler) + sutun - 1) // sutun
    ust, alt_pay, ara_g, etiket = 500, 140, 130, 150  # etiket: kutu altı yazı payı
    kutu = min(400.0, (KENAR - ust - alt_pay - satir_n * etiket) / (satir_n * 0.72))
    kutu_y = kutu * 0.72
    toplam_g, toplam_y = sutun * kutu + (sutun - 1) * ara_g, satir_n * (kutu_y + etiket)
    y0 = ust + (KENAR - ust - alt_pay - toplam_y) / 2
    for i, r in enumerate(renkler):
        satir, sira = divmod(i, sutun)
        n_bu = min(sutun, len(renkler) - satir * sutun)  # son satır eksikse ortalanır
        x0 = (KENAR - (n_bu * kutu + (n_bu - 1) * ara_g)) / 2
        x, y = x0 + sira * (kutu + ara_g), y0 + satir * (kutu_y + etiket)
        p.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{kutu:.1f}" height="{kutu_y:.1f}" rx="40" fill="{r["hex"]}" stroke="{ACIK_CIZGI}" stroke-width="8"/>'
        )
        p.append(
            _yazi(r["ad"].upper(), GOVDE_F, x + kutu / 2, y + kutu_y + 45, 50, LACIVERT, ara=0.03, maks_g=kutu + ara_g * 0.8)[0]
        )
    _ = toplam_g
    return _png(_svg(p))


def _jpeg(img: Image.Image) -> bytes:
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=90, optimize=True)
    return b.getvalue()


def _kumas_rengi(img: Image.Image) -> tuple[float, float, float]:
    """Mockup'ta baskının altındaki düz kumaş: görselin ortası, yüksekliğin ~%78'i (Printify ön mockup düzeni)."""
    g, y = img.size
    parca = np.asarray(img.convert("RGB").crop((int(g * 0.44), int(y * 0.74), int(g * 0.56), int(y * 0.82))), dtype=np.float32)
    return tuple(parca.reshape(-1, 3).mean(axis=0))


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def vitrin_sec(gorseller: list[tuple[dict, Image.Image]], hedef_hex: str) -> dict | None:
    """Mevcut ilan görsellerinden kumaşı `hedef_hex`'e en yakın olanı (Printify görselleri renk adı taşımaz)."""
    hedef = np.array(_hex_rgb(hedef_hex), dtype=np.float32)
    if not gorseller:
        return None
    return min(gorseller, key=lambda gi: float(np.linalg.norm(np.array(_kumas_rengi(gi[1])) - hedef)))[0]


def ilan_gorselleri(urun: str, dosyalar: dict[str, Path], tohum: int = 0) -> list[tuple[str, Image.Image, str]]:
    """(ad, görsel, alt metin) — ilana eklenecek kendi görsellerimiz, sırasıyla. `dosyalar`: {"koyu_png", "acik_png", ("kupa_png")}.

    Yakın plan vitrin rengindeki kumaşta (o rengin mürekkebiyle): ilk iki görsel aynı ürünü gösterir.
    """
    u = urunler()[urun]
    renk = next((r for r in u["renkler"] if r["ad"] == u.get("vitrin_rengi")), u["renkler"][0])
    png = dosyalar.get("kupa_png") if urun == "kupa" else dosyalar[f"{renk['murekkep']}_png"]
    tur = u["etsy_turu"].lower()
    sonuc = [("yakin-plan", yakin_plan(png, renk["hex"], tohum), f"Close-up of the printed design on a {tur}")]
    if (b := beden_tablosu(urun)) is not None:
        sonuc.append(("beden", b, f"Size guide for the {u['blank']} with measurements in inches"))
    if len(u["renkler"]) > 1:
        sonuc.append(("renkler", renk_karti(urun), f"Available colors for this {u['etsy_turu'].lower()}"))
    sonuc.append(("guven", guven_karti(), "Printed to order in the USA with free US shipping"))
    return sonuc


def sira_kur(etsy, listing_id: int, sira: list[int]) -> None:
    """Görselleri verilen sırayla 1..n'e yazar. Etsy tek görselin rank'ini değiştirince diğerlerini kaydırmıyor (aynı rank'te iki
    görsel kalıyordu, 2026-10-13 canlı ilan): sıra her seferinde baştan sona açıkça kurulur."""
    for rank, gid in enumerate(sira, start=1):
        etsy.gorsel_sirala(listing_id, gid, rank)


def ilana_ekle(etsy, listing_id: int, urun: str, dosyalar: dict[str, Path], tohum: int = 0, maks: int = 20, indir=None) -> dict:
    """Kendi görsellerimizi ekler ve galeriyi kurar: vitrin rengindeki mockup, yakın plan, diğer mockup'lar, beden/renk/güven kartları.

    Etsy 11. görseli kabul etti (2026-10-13): sınır 10 değil (araştırma: 20). Görseller önce sona yüklenir, sonra sıra tek seferde kurulur.
    """
    import httpx

    indir = indir or (lambda url: Image.open(io.BytesIO(httpx.get(url, timeout=60).content)))
    u = urunler()[urun]
    mevcut = etsy.ilan_gorselleri(listing_id)
    sonuc: dict = {"vitrin": None, "eklenen": []}
    vitrin = None
    if (renk := u.get("vitrin_rengi")) and len(mevcut) > 1:
        hedef = next((r["hex"] for r in u["renkler"] if r["ad"] == renk), None)
        if hedef:
            vitrin = vitrin_sec([(g, indir(g["url_570xN"])) for g in mevcut], hedef)
    kendi: dict[str, int] = {}
    for ad, img, alt in ilan_gorselleri(urun, dosyalar, tohum)[: max(maks - len(mevcut), 0)]:
        y = etsy.gorsel_yukle(listing_id, _jpeg(img), len(mevcut) + len(kendi) + 1, f"{ad}.jpg", alt)
        kendi[ad] = (y or {}).get("listing_image_id")
        sonuc["eklenen"].append(ad)
    mockuplar = [g["listing_image_id"] for g in mevcut if not vitrin or g["listing_image_id"] != vitrin["listing_image_id"]]
    bas = ([vitrin["listing_image_id"]] if vitrin else mockuplar[:1]) + ([kendi["yakin-plan"]] if kendi.get("yakin-plan") else [])
    sira = bas + [g for g in mockuplar if g not in bas] + [gid for ad, gid in kendi.items() if gid and ad != "yakin-plan"]
    sira_kur(etsy, listing_id, sira)
    sonuc["vitrin"] = vitrin["listing_image_id"] if vitrin else None
    return sonuc
