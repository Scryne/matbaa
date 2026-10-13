"""Niş çizimleri: retro tişört tasarımlarının yazıya eşlik eden tek renkli, kalın vektör simgeleri.

Her simge 1000x1000 birim kutuda geometrik parçalarla kurulur (dolgu ya da `currentColor` çizgi); baskıda en ince
çizgi simge yüksekliğinin ~%4'ü, ~700 px yükseklikte 28 px'in üstünde kalır (CIZGI_MIN). Sınır kutusu bir kez
render edilip ölçülür; yerleştirme gerçek mürekkep kutusuna göre yapılır, birim kutudaki boşluk tasarıma taşmaz.
Çizimler Aria'nın kendi inşasıdır (stok/ikon seti değil): lisans ve marka sorusu yok.
"""

from __future__ import annotations

import io
import itertools
import math
from functools import cache

import numpy as np
from PIL import Image

_SAYAC = itertools.count()
C = 'stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"'


def _daire(cx: float, cy: float, r: float) -> str:
    return f"M{cx - r:.1f},{cy:.1f} a{r:.1f},{r:.1f} 0 1 0 {2 * r:.1f},0 a{r:.1f},{r:.1f} 0 1 0 {-2 * r:.1f},0 Z"


def _yildiz(cx: float, cy: float, r_dis: float, r_ic: float, uc: int = 5, aci: float = -90) -> str:
    noktalar = []
    for i in range(uc * 2):
        r = r_dis if i % 2 == 0 else r_ic
        t = math.radians(aci + i * 180 / uc)
        noktalar.append(f"{cx + r * math.cos(t):.1f},{cy + r * math.sin(t):.1f}")
    return "M" + " L".join(noktalar) + " Z"


def _kesik_cizgi(x0: float, y0: float, cx: float, cy: float, r: float) -> tuple[float, float]:
    """(x0,y0)'dan (cx,cy) merkezli r yarıçaplı dairenin kenarına kadar giden doğrunun bitiş noktası."""
    dx, dy = cx - x0, cy - y0
    d = math.hypot(dx, dy)
    return x0 + dx * (d - r) / d, y0 + dy * (d - r) / d


def balik(_: str) -> str:
    govde = "M300,520 C390,330 700,300 905,505 C700,700 390,690 300,520 Z"
    kuyruk = "M345,520 L95,330 Q175,520 95,710 Z"
    sirt = "M500,368 Q590,235 700,352 Z"
    karin = "M560,640 Q610,735 680,642 Z"
    goz = _daire(790, 470, 30)
    # Solungaç: gövdeden kesilmiş ince hilal (negatif alan), baskıda 40 birim.
    solungac = "M700,400 Q650,505 700,610 L660,610 Q610,505 660,400 Z"
    return f'<path fill-rule="evenodd" d="{govde} {goz} {solungac}"/><path d="{kuyruk} {sirt} {karin}"/>'


def igne(_: str) -> str:
    return (
        f'<path {C} stroke-width="72" d="M600,215 V640 A180,180 0 0 1 240,640 V575"/>'
        f'<path fill-rule="evenodd" d="{_daire(600, 150, 95)} {_daire(600, 150, 42)}"/>'
        '<path d="M178,600 L302,600 L240,430 Z"/>'
    )


def mantar(_: str) -> str:
    """Olta şamandırası: üst yarı dolu, alt yarı halka, tepede çubuk ve kıvrılan misina."""
    cx, cy, r = 450, 640, 270
    return (
        f'<path d="M{cx - r},{cy} A{r},{r} 0 0 1 {cx + r},{cy} Z"/>'
        f'<path {C} stroke-width="62" d="M{cx - r + 31},{cy} A{r - 31},{r - 31} 0 0 0 {cx + r - 31},{cy}"/>'
        f'<path {C} stroke-width="40" d="M{cx - r + 31},{cy} H{cx + r - 31}"/>'
        f'<rect x="{cx - 34}" y="{cy - r - 150}" width="68" height="170" rx="28"/>'
        f'<path {C} stroke-width="34" d="M{cx},{cy - r - 140} C{cx + 30},{cy - r - 260} {cx + 230},{cy - r - 230} {cx + 300},{cy - r - 330}"/>'
    )


def kurek(_: str) -> str:
    """Pickleball raketi (eğik, köşeli-yuvarlak yüz, kısa sap) ve ayrı duran delikli top."""
    yuz = "M250,215 Q250,90 375,90 H555 Q680,90 680,215 V470 Q680,600 560,620 H370 Q250,600 250,470 Z"
    raket = f'<g transform="rotate(-30 465 520)"><path d="{yuz}"/><rect x="410" y="590" width="110" height="330" rx="36"/></g>'
    cx, cy, r = 800, 230, 150
    delikler = " ".join(
        _daire(cx + 78 * math.cos(math.radians(a)), cy + 78 * math.sin(math.radians(a)), 22) for a in range(0, 360, 60)
    )
    return raket + f'<path fill-rule="evenodd" d="{_daire(cx, cy, r)} {_daire(cx, cy, 22)} {delikler}"/>'


def top(_: str) -> str:
    """Pickleball topu: sık, eşit delikler (film makarası gibi durmasın diye iki halka + merkez, delikler küçük)."""
    halkalar = [(0, 0, 1)] + [(170, 0, 6), (320, 30, 12)]
    delikler = " ".join(
        _daire(500 + rr * math.cos(math.radians(a0 + i * 360 / n)), 500 + rr * math.sin(math.radians(a0 + i * 360 / n)), 42)
        for rr, a0, n in halkalar
        for i in range(n)
    )
    return f'<path fill-rule="evenodd" d="{_daire(500, 500, 420)} {delikler}"/>'


def yumak(_: str) -> str:
    """Yün yumağı: halka, içinde kırpılmış iplik kavisleri; iki şiş yumağın kenarında durur."""
    cx, cy, r = 470, 600, 300
    kid = f"yumak{next(_SAYAC)}"
    kavisler = " ".join(
        f"M{cx - r - 50},{cy + dy} Q{cx},{cy + dy - egri} {cx + r + 50},{cy + dy}"
        for dy, egri in ((-170, 160), (-40, 190), (90, 200), (215, 170))
    )
    sis = []
    for x0, y0 in ((220, 110), (830, 150)):
        x1, y1 = _kesik_cizgi(x0, y0, cx, cy, r + 55)
        sis.append(f'<path {C} stroke-width="44" d="M{x0},{y0} L{x1:.1f},{y1:.1f}"/><path d="{_daire(x0, y0, 52)}"/>')
    return (
        f'<defs><clipPath id="{kid}"><path d="{_daire(cx, cy, r - 30)}"/></clipPath></defs>'
        + "".join(sis)
        + f'<path {C} stroke-width="60" d="{_daire(cx, cy, r - 30)}"/>'
        + f'<path {C} stroke-width="44" clip-path="url(#{kid})" d="{kavisler}"/>'
        + f'<path {C} stroke-width="44" d="M{cx + r - 40},{cy + 120} C{cx + r + 80},{cy + 220} {cx + r + 40},{cy + 330} {cx + r + 200},{cy + 330}"/>'
    )


def kronometre(_: str) -> str:
    cx, cy, r = 500, 590, 300
    a = math.radians(-50)
    isaretler = " ".join(
        f"M{cx + (r - 95) * math.cos(t):.1f},{cy + (r - 95) * math.sin(t):.1f} L{cx + (r - 55) * math.cos(t):.1f},{cy + (r - 55) * math.sin(t):.1f}"
        for t in (math.radians(d) for d in (-90, 0, 90, 180))
    )
    return (
        f'<path {C} stroke-width="66" d="{_daire(cx, cy, r)}"/>'
        f'<rect x="{cx - 80}" y="{cy - r - 175}" width="160" height="85" rx="30"/>'
        f'<rect x="{cx - 34}" y="{cy - r - 110}" width="68" height="120"/>'
        f'<path {C} stroke-width="54" d="M{cx + r * 0.78 * math.cos(math.radians(-45)):.1f},{cy + r * 0.78 * math.sin(math.radians(-45)):.1f} l85,-85"/>'
        f'<path {C} stroke-width="40" d="{isaretler}"/>'
        f'<path {C} stroke-width="52" d="M{cx},{cy} L{cx + (r - 120) * math.cos(a):.1f},{cy + (r - 120) * math.sin(a):.1f}"/>'
        f'<path d="{_daire(cx, cy, 50)}"/>'
    )


def madalya(_: str) -> str:
    """Bitiriş madalyası: iki şerit madalyanın üstünde birleşir (boşlukla), madalyada halka ve yıldız."""
    cx, cy, r = 500, 660, 240
    return (
        f'<path d="M290,60 H420 L492,385 H430 Z M710,60 H580 L508,385 H570 Z"/>'
        f'<path fill-rule="evenodd" d="{_daire(cx, cy, r)} {_daire(cx, cy, r - 50)} {_yildiz(cx, cy + 8, 125, 55)}"/>'
    )


def kalp(_: str) -> str:
    return '<path d="M500,880 L190,570 A155,155 0 0 1 500,300 A155,155 0 0 1 810,570 Z" transform="translate(-155 -155) scale(1.31)"/>'


def parilti(_: str) -> str:
    buyuk = "M430,90 Q470,420 800,470 Q470,520 430,860 Q390,520 60,470 Q390,420 430,90 Z"
    kucuk = "M800,90 Q815,215 935,235 Q815,255 800,380 Q785,255 665,235 Q785,215 800,90 Z"
    return f'<path d="{buyuk} {kucuk}"/>'


def hediye(_: str) -> str:
    """Hediye kutusu: kapak ve gövde arası boşluk, şerit negatif alan, üstte fiyonk."""
    kutu = "M175,515 H825 V905 H175 Z M120,360 H880 V480 H120 Z"
    serit = "M458,350 H542 V915 H458 Z"
    fiyonk = "M500,350 C410,160 240,190 300,290 C335,345 430,350 500,350 C570,350 665,345 700,290 C760,190 590,160 500,350 Z"
    return f'<path fill-rule="evenodd" d="{kutu} {serit}"/><path {C} stroke-width="56" d="{fiyonk}"/>'


def agac(_: str) -> str:
    katlar = "M500,170 L705,440 H295 Z M500,330 L770,640 H230 Z M500,500 L840,840 H160 Z"
    return f'<path d="{katlar}"/><rect x="445" y="830" width="110" height="120" rx="14"/><path d="{_yildiz(500, 120, 95, 40)}"/>'


def kar(_: str) -> str:
    kollar = []
    for d in range(0, 360, 60):
        t = math.radians(d)
        ux, uy = math.cos(t), math.sin(t)
        x1, y1 = 500 + 400 * ux, 500 + 400 * uy
        kollar.append(f"M500,500 L{x1:.1f},{y1:.1f}")
        for k, uz in ((0.55, 120), (0.8, 85)):
            bx, by = 500 + 400 * k * ux, 500 + 400 * k * uy
            for s in (-1, 1):
                t2 = t + s * math.radians(45)
                kollar.append(f"M{bx:.1f},{by:.1f} L{bx + uz * math.cos(t2):.1f},{by + uz * math.sin(t2):.1f}")
    return f'<path {C} stroke-width="54" d="{" ".join(kollar)}"/><path d="{_daire(500, 500, 70)}"/>'


def kep(_: str) -> str:
    """Mezuniyet kepi: eşkenar dörtgen tepe, altında başlık bandı, sarkan püskül."""
    tepe = "M500,180 L920,370 L500,560 L80,370 Z"
    bant = "M250,500 V700 Q500,820 750,700 V500 L500,612 Z"
    return (
        f'<path d="{tepe}"/><path d="{bant}"/>'
        f'<path {C} stroke-width="34" d="M500,370 L800,470 V700"/>'
        '<path d="M760,690 H840 L870,840 H730 Z"/>'
    )


def tac(_: str) -> str:
    govde = "M150,760 L110,330 L330,560 L500,250 L670,560 L890,330 L850,760 Z"
    bant = "M150,800 H850 V890 H150 Z"
    toplar = " ".join(_daire(x, y, 55) for x, y in ((110, 300), (500, 215), (890, 300)))
    return f'<path d="{govde} {bant} {toplar}"/>'


def dag(_: str) -> str:
    """Göl manzarası: arkada güneş, iki dağ (karlı tepe negatif), önde su çizgileri."""
    gunes = _daire(640, 330, 150)
    daglar = "M60,700 L380,250 L560,500 L660,380 L940,700 Z"
    kar_ = "M380,250 L455,355 L415,330 L380,370 L345,330 L305,355 Z"
    su = " ".join(f"M{x0},{y} H{x1}" for x0, x1, y in ((90, 910, 780), (210, 790, 865), (330, 670, 945)))
    kid = f"dag{next(_SAYAC)}"
    return (
        f'<defs><mask id="{kid}" maskUnits="userSpaceOnUse" x="0" y="0" width="1000" height="1000">'
        f'<rect width="1000" height="1000" fill="#fff"/><path d="{daglar}" fill="#000" stroke="#000" stroke-width="70"/></mask></defs>'
        f'<path d="{gunes}" mask="url(#{kid})"/>'
        f'<path fill-rule="evenodd" d="{daglar} {kar_}"/>'
        f'<path {C} stroke-width="44" d="{su}"/>'
    )


IKONLAR = {
    "balik": balik, "igne": igne, "mantar": mantar, "kurek": kurek, "top": top, "yumak": yumak,
    "kronometre": kronometre, "madalya": madalya, "kalp": kalp, "parilti": parilti, "hediye": hediye,
    "agac": agac, "kar": kar, "kep": kep, "tac": tac, "dag": dag,
}  # fmt: skip

NIS_IKONLARI = {
    "fishing": ["balik", "igne", "mantar", "dag"],
    "pickleball": ["kurek", "top"],
    "knitting": ["yumak"],
    "running": ["kronometre", "madalya", "dag"],
    "aunt": ["kalp", "parilti"],
    "milestone": ["tac", "parilti"],
    "senior_mom": ["kep", "kalp"],
}
MEVSIM_IKONLARI = ["agac", "kar", "hediye"]
GUNESSIZ = {"dag"}  # kendi güneşi olan manzara: güneş amblemine konursa iç içe güneş olur
MEVSIM_KELIMELERI = {
    "CHRISTMAS",
    "XMAS",
    "SANTA",
    "MERRY",
    "SNOW",
    "HOLIDAY",
    "HOLIDAYS",
    "ELF",
    "JINGLE",
    "SLEIGH",
    "NOEL",
    "GIFTS",
    "WINTER",
}


def adaylar(nis: str, metin: str) -> list[str]:
    """İfadeye uyan simgeler: Noel kelimesi geçiyorsa önce mevsim simgeleri, sonra nişinkiler."""
    kelimeler = {k.strip(".,!?'’\"") for k in metin.upper().split()}
    mevsim = MEVSIM_IKONLARI if kelimeler & MEVSIM_KELIMELERI else []
    return mevsim + NIS_IKONLARI.get(nis, [])


def birim_svg(ad: str, renk: str = "#000") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000" viewBox="0 0 1000 1000">'
        f'<g fill="{renk}" color="{renk}">{IKONLAR[ad](ad)}</g></svg>'
    )


@cache
def kutu(ad: str) -> tuple[float, float, float, float]:
    """Simgenin 1000 birimlik kutudaki gerçek mürekkep sınırı (x0, y0, x1, y1): render edilip ölçülür."""
    import resvg_py

    png = bytes(resvg_py.svg_to_bytes(svg_string=birim_svg(ad), width=1000, height=1000, skip_system_fonts=True))
    a = np.asarray(Image.open(io.BytesIO(png)).getchannel("A"))
    ys, xs = np.nonzero(a > 8)
    return float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)


def yerlestir(ad: str, cx: float, ust: float, yukseklik: float, genislik_maks: float | None = None) -> tuple[str, float, float]:
    """Simgeyi mürekkep kutusu (cx merkezli, `ust`ten başlayan) `yukseklik` boyunda yerleştirir: (svg, gerçek genişlik, gerçek yükseklik)."""
    x0, y0, x1, y1 = kutu(ad)
    k = yukseklik / (y1 - y0)
    if genislik_maks is not None:
        k = min(k, genislik_maks / (x1 - x0))
    tx, ty = cx - (x0 + x1) / 2 * k, ust - y0 * k
    return f'<g transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})">{IKONLAR[ad](ad)}</g>', (x1 - x0) * k, (y1 - y0) * k
