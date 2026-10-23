"""Yılbaşı süsü baskı dosyaları (K-30): yuvarlak seramik süs, iki yüz (Printify 1632, SwiftPOD; UV baskı, alan 900x900).

Ön yüz: tişört tasarımının açık zemin sürümü (koyu mürekkep + vurgu) dairenin içine sığdırılır, alt yayda "CHRISTMAS <yıl>".
Arka yüz: üst yayda "MERRY CHRISTMAS", ortada büyük yıl (tasarımın ana fontu), altında nişin çizimi. Etsy'de süs pazarı yıllı
hatıra üzerine kurulu (2026-10-14 ölçümü: örgüde en çok görülen süs "2025 Christmas Ornament"); yıl hediyeyi o Noel'e bağlar.
Tuval 1800x1800 (baskı alanının iki katı); her şey kenardan pay bırakılarak çizilir (askı deliği üstte, seramik kenarı yuvarlak).
"""

from __future__ import annotations

import io
import json
import math
import re
from pathlib import Path

import resvg_py
from PIL import Image

from . import ikon as ikonlar
from .sablonlar import _kavisli, _kavisli_alt
from .sec import KOYU_MUREKKEP
from .yazi import font

KENAR = 1800
M = KENAR / 2  # merkez ve yarıçap
GUVENLI = 0.86  # içerik bu yarıçap kesrinin dışına taşmaz
TASARIM_R = 0.80  # ön yüzde tasarımın köşeleri bu yarıçapın içinde kalır (askı deliği ve seramik kenarı)
TASARIM_ALT = 0.46  # tasarımın alt kenarı merkezden bu kadar aşağıda biter: altındaki yay yazısına yer
ISIMLI_TASARIM_R, ISIMLI_TASARIM_ALT = 0.78, 0.16  # isimli süste tasarım biraz küçük ve yukarıda: altında isme yer
ISIM_FONT = "Pacifico-Regular.ttf"  # el yazısı; HarfBuzz harfleri birleştirir
ISIM_MAKS = 14  # Etsy kişiselleştirme sorusunun karakter sınırı da bu
YAY_FONT = "BebasNeue-Regular.ttf"
YIL_FONT_YEDEK = "AlfaSlabOne-Regular.ttf"


def vurgu_rengi(svg_yolu: str | Path) -> str:
    """Tasarımın ikinci rengi (koyu.svg'deki mürekkep dışı `<g fill>`); tek renkli tasarımda mürekkebin kendisi."""
    renkler = re.findall(r'<g fill="(#[0-9a-fA-F]{6})" color=', Path(svg_yolu).read_text(encoding="utf-8"))
    diger = [r for r in renkler if r.lower() not in (KOYU_MUREKKEP, "#000000", "#ffffff")]
    return diger[0] if diger else KOYU_MUREKKEP


def tasarim_vurgu(koyu_png: Path, svg: Path) -> str:
    """Yay ve yıldızların rengi: yazılı tasarımda SVG'nin vurgusu; çizimli tasarımda (SVG yok, K-37) çizimin dış çizgi
    rengi, yazı da o renkle kontürlü olduğu için süs aynı elden çıkmış görünür."""
    if svg.exists():
        return vurgu_rengi(svg)
    from matbaa.cizim import koyu_renk

    return koyu_renk(Image.open(koyu_png).convert("RGBA"))


def _png(parcalar: list[str]) -> Image.Image:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{KENAR}" height="{KENAR}" viewBox="0 0 {KENAR} {KENAR}">{"".join(parcalar)}</svg>'
    return Image.open(
        io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=KENAR, height=KENAR, skip_system_fonts=True)))
    ).convert("RGBA")


def _yay(metin: str, ustte: bool, r_taban: float, yukseklik: float, renk: str, aci_maks: float) -> tuple[str, float]:
    """Yay yazısı: üstte taban çizgisi yayda (harfler dışa), altta dik okunur (harflerin tepesi merkeze). (svg, yarım açı)"""
    f = font(YAY_FONT)
    s = f.satir(metin, 0.08)
    olcek = min(yukseklik / f.buyuk_harf, aci_maks * r_taban / s.ilerleme)
    parcalar = (_kavisli if ustte else _kavisli_alt)(s, olcek, M, M, r_taban)
    return f'<g fill="{renk}">{"".join(parcalar)}</g>', s.ilerleme * olcek / r_taban / 2


def _yildizlar(r: float, yarim_aci: float, boy: float, renk: str, ustte: bool) -> str:
    """Yay yazısının iki ucunda, yazıdan bir yıldız boyu açıkta küçük yıldız (Noel süsü dili)."""
    p = []
    for isaret in (-1, 1):
        t = (yarim_aci + 2.2 * boy / r) * isaret
        x = M + r * math.sin(t)
        y = M - r * math.cos(t) if ustte else M + r * math.cos(t)
        p.append(f'<path d="{ikonlar._yildiz(x, y, boy, boy * 0.42)}"/>')
    return f'<g fill="{renk}">{"".join(p)}</g>'


def on_yuz(koyu_png: str | Path, vurgu: str, yil: int, isim: str | None = None) -> Image.Image:
    """`isim` verilirse (isimli süs, Faz 11): tasarım küçülüp yukarı çıkar, ortada el yazısı isim, altta daha dar yıl yayı."""
    tasarim = Image.open(koyu_png).convert("RGBA")
    kutu = tasarim.getchannel("A").getbbox()
    if kutu is None:
        raise ValueError(f"{koyu_png}: boş tasarım")
    icerik = tasarim.crop(kutu)
    alt_kesir, r_kesir = (ISIMLI_TASARIM_ALT, ISIMLI_TASARIM_R) if isim else (TASARIM_ALT, TASARIM_R)
    g, h = _sigdir(icerik.width / icerik.height, r_kesir, alt_kesir)
    icerik = icerik.resize((round(g), round(h)), Image.LANCZOS)
    r_taban, boy = 0.82 * M, (0.085 if isim else 0.10) * M
    yay, yarim = _yay(f"CHRISTMAS {yil}", False, r_taban, boy, vurgu, math.radians(90 if isim else 100))
    parcalar = [yay, _yildizlar(r_taban - boy / 2, yarim, boy * 0.42, vurgu, ustte=False)]
    if isim:
        parcalar.append(_isim(isim))
    tuval = _png(parcalar)
    alt = M + alt_kesir * M
    tuval.alpha_composite(icerik, (round(M - g / 2), round(alt - h)))
    return tuval


def isim_temizle(metin: str) -> str:
    """Alıcının yazdığı isim → basılacak metin: boşluklar sadeleşir, uzunluk `ISIM_MAKS`. Fontta glifi olmayan karakter
    `EksikGlif` yükseltir (sipariş insana düşer; sessizce kutu basılmaz)."""
    # Alıcılar soruyu cevap kalıbıyla yazabiliyor ("Name: Emma", "\"Emma\""): etiket ve dış tırnak basılmaz.
    metin = re.sub(r"^\s*(?:name|names)\s*[:=\-]\s*", "", metin, flags=re.I).strip().strip('"“”«»').strip()
    temiz = " ".join(metin.split())[:ISIM_MAKS].strip()
    if not temiz:
        raise ValueError("boş isim")
    if temiz == temiz.lower():  # "grandpa joe" → "Grandpa Joe"; "McKenzie" yazıldığı gibi kalır
        temiz = " ".join(p[:1].upper() + p[1:] for p in temiz.split(" "))
    font(ISIM_FONT).satir(temiz)
    return temiz


def _isim(isim: str) -> str:
    """Ortada, tasarımla yıl yayı arasında el yazısı isim: kutuya (genişlik 1.2M, yükseklik 0.26M) orantılı sığar."""
    s = font(ISIM_FONT).satir(isim_temizle(isim))
    k = min(0.26 * M / s.yukseklik, 1.20 * M / s.genislik)
    yc = M + 0.40 * M
    tx, ty = M - (s.x0 + s.genislik / 2) * k, yc - (s.y0 + s.yukseklik / 2) * k
    return f'<path fill="{KOYU_MUREKKEP}" d="{s.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})"/>'


def _sigdir(oran: float, r_kesir: float = TASARIM_R, alt_kesir: float = TASARIM_ALT) -> tuple[float, float]:
    """Alt kenarı merkezden `alt_kesir` aşağıda biten, dört köşesi `r_kesir` dairesinde kalan en büyük dikdörtgen (genişlik, yükseklik)."""
    r, alt = r_kesir * M, alt_kesir * M
    g_maks = 2 * math.sqrt(r**2 - alt**2)  # alt köşeler
    lo, hi = 0.0, 2 * r
    for _ in range(40):
        h = (lo + hi) / 2
        g = h * oran
        if g <= g_maks and (g / 2) ** 2 + (h - alt) ** 2 <= r**2:
            lo = h
        else:
            hi = h
    return lo * oran, lo


def arka_yuz(ana_font: str, vurgu: str, yil: int, nis_ikonu: str | None) -> Image.Image:
    r_taban, boy = 0.66 * M, 0.11 * M
    yay, yarim = _yay("MERRY CHRISTMAS", True, r_taban, boy, vurgu, math.radians(110))
    p = [yay, _yildizlar(r_taban + boy / 2, yarim, boy * 0.42, vurgu, ustte=True)]
    try:
        s = font(ana_font).satir(str(yil))
    except Exception:  # fontta rakam glifi yoksa (EksikGlif) yedek font
        s = font(YIL_FONT_YEDEK).satir(str(yil))
    hedef_h = 0.40 * M
    k = min(hedef_h / s.yukseklik, 1.15 * M / s.genislik)
    y_ust = M - 0.14 * M
    tx, ty = M - (s.x0 + s.genislik / 2) * k, y_ust - s.y0 * k
    p.append(f'<path fill="{KOYU_MUREKKEP}" d="{s.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})"/>')
    if nis_ikonu:
        ust = y_ust + s.yukseklik * k + 0.07 * M
        alt_sinir = M + GUVENLI * M * 0.72
        h_i = min(0.24 * M, alt_sinir - ust)
        parca, _, _ = ikonlar.yerlestir(nis_ikonu, M, ust, h_i, genislik_maks=0.5 * M)
        p.append(f'<g fill="{vurgu}" color="{vurgu}">{parca}</g>')
    return _png(p)


def kaydet(dosyalar: dict, fontlar: list[str], nis: str, yil: int, kok: Path) -> dict[str, Path]:
    """Ön ve arka yüzü tasarım klasörüne yazar (`susleme_on_<yıl>.png`, `susleme_arka_<yıl>.png`); varsa yeniden çizmez."""
    koyu = kok / dosyalar["koyu_png"]
    klasor = koyu.parent
    hedef = {"on": klasor / f"susleme_on_{yil}.png", "arka": klasor / f"susleme_arka_{yil}.png"}
    if all(p.exists() for p in hedef.values()):
        return hedef
    svg = kok / dosyalar.get("koyu_svg", str(Path(dosyalar["koyu_png"]).with_suffix(".svg")))
    vurgu = tasarim_vurgu(koyu, svg)
    ikon_adi = (ikonlar.NIS_IKONLARI.get(nis) or [None])[0]
    on_yuz(koyu, vurgu, yil).save(hedef["on"], dpi=(600, 600), optimize=True)
    ana = fontlar[0] if fontlar else YIL_FONT_YEDEK
    arka_yuz(ana, vurgu, yil, ikon_adi).save(hedef["arka"], dpi=(600, 600), optimize=True)
    return hedef


def fontlar_json(ham: str | None) -> list[str]:
    try:
        return list(json.loads(ham or "[]"))
    except ValueError:
        return []
