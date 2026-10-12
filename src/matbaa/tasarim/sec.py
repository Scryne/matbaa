"""Slogan yapısından (üst / ana / alt) şablon ve font seçimi, kalite kapılarıyla birlikte.

Aynı mağazada aynı şablon + ana font çifti art arda tekrar etmesin (toplu üretim görünümüne karşı, K-4):
son `CESITLILIK_PENCERE` tasarımda kullanılan çiftler sona atılır.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

from . import kapilar, render
from .sablonlar import Cizim, Yazi, dengeli_bol, kavis, rozet, yigin

KOYU_MUREKKEP, ACIK_MUREKKEP = "#1d1d1f", "#f3ead8"


def _kumaslar(murekkep: str) -> list[str]:
    """Katalogdaki, bu mürekkeple basılacak tüm kumaş renkleri: kontrast kapısı satılacak her renge karşı ölçülür."""
    from matbaa.fiyat import urunler

    return sorted({r["hex"] for u in urunler().values() for r in u["renkler"] if r["murekkep"] == murekkep})


ACIK_KUMAS = _kumaslar("koyu")  # koyu mürekkep → açık kumaşlar
KOYU_KUMAS = _kumaslar("acik")

# Vurgu paletleri: (açık kumaşta vurgu, koyu kumaşta vurgu). Küçük satırlar, yay yazısı ve çizgiler bu renge geçer.
# Kontrast kapısından geçmeyen palet (ör. hardal adaçayı yeşilinde) aday olmaz; None = tek renk.
PALETLER: dict[str, tuple[str, str] | None] = {
    "tek": None,
    "kiremit": ("#9a3a2b", "#e8826a"),
    "orman": ("#2f5d46", "#9cc4a2"),
    "lacivert": ("#23395b", "#8fb8d8"),
    "hardal": ("#76510c", "#e3b448"),
}


def gecerli_paletler() -> list[str]:
    ok = []
    for ad, p in PALETLER.items():
        if p is None or (
            min(kapilar.kontrast(p[0], k) for k in ACIK_KUMAS) >= kapilar.KONTRAST_MIN
            and min(kapilar.kontrast(p[1], k) for k in KOYU_KUMAS) >= kapilar.KONTRAST_MIN
        ):
            ok.append(ad)
    return ok


CESITLILIK_PENCERE = 5

ANA_FONTLAR = [
    "Anton-Regular.ttf",
    "AlfaSlabOne-Regular.ttf",
    "ArchivoBlack-Regular.ttf",
    "Shrikhand-Regular.ttf",
    "AbrilFatface-Regular.ttf",
    "DMSerifDisplay-Regular.ttf",
    "Righteous-Regular.ttf",
    "BebasNeue-Regular.ttf",
]
KUCUK_FONTLAR = ["BebasNeue-Regular.ttf", "Righteous-Regular.ttf", "ArchivoBlack-Regular.ttf"]
KAVIS_FONTLAR = ["AlfaSlabOne-Regular.ttf", "ArchivoBlack-Regular.ttf", "Righteous-Regular.ttf", "BebasNeue-Regular.ttf"]


@dataclass
class Secim:
    sablon: str
    fontlar: list[str]
    palet: str
    cizim: Cizim
    koyu: Image.Image
    acik: Image.Image
    kalite: dict[str, list[str]]


def _adaylar(ust: str, ana: list[str], alt: str, rnd: random.Random) -> list[tuple[str, list[str], Callable[[], Cizim]]]:
    sonuc = []
    for f in rnd.sample(ANA_FONTLAR, len(ANA_FONTLAR)):
        k = rnd.choice(KUCUK_FONTLAR)
        if len(ana) == 1 and ust:
            kf = rnd.choice(KAVIS_FONTLAR)
            sonuc.append(
                (
                    "kavis",
                    [kf, f, k],
                    lambda kf=kf, f=f, k=k: kavis(
                        Yazi(ust.upper(), kf, 0.06), Yazi(ana[0], f), Yazi(alt.upper(), k, 0.12) if alt else None
                    ),
                )
            )
            sonuc.append(
                (
                    "rozet",
                    [k, f, k],
                    lambda f=f, k=k: rozet(
                        Yazi(ust.upper(), k, 0.15), Yazi(ana[0], f), Yazi(alt.upper(), k, 0.08) if alt else None
                    ),
                )
            )
        satirlar = []
        if ust:
            satirlar.append(Yazi(ust.upper(), k, 0.12, 0.45, kucuk=True))
        bolum = dengeli_bol(ana, f, 0.02)
        # Küçük satır yoksa vurgu rengi bir ana satıra geçer: 2 satırda ikincisi, 3 satırda ortadaki.
        vurgu_i = (len(bolum) // 2 if len(bolum) == 3 else 1) if (not ust and not alt and len(bolum) >= 2) else -1
        satirlar += [Yazi(s, f, 0.02, vurgu=(j == vurgu_i)) for j, s in enumerate(bolum)]
        if alt:
            satirlar.append(Yazi(alt.upper(), k, 0.08, 0.6, kucuk=True))
        sonuc.append(("yigin", [f, k], lambda satirlar=satirlar: yigin(satirlar)))
    return sonuc


def sec(
    ust: str, ana: list[str], alt: str, son_kullanilan: list[tuple[str, str]], tohum: int, deneme: int = 6
) -> tuple[Secim | None, list[str]]:
    """İlk kapılardan geçen tasarımı döner; geçemezse (None, ret nedenleri)."""
    rnd = random.Random(tohum)
    adaylar = _adaylar(ust, ana, alt, rnd)
    paletler = gecerli_paletler()
    palet = paletler[tohum % len(paletler)]  # deterministik: aynı ifade aynı paleti alır
    vurgu = PALETLER[palet]
    yakin = set(son_kullanilan[-CESITLILIK_PENCERE:])
    adaylar.sort(key=lambda a: (a[0], a[1][0 if a[0] == "yigin" else 1]) in yakin)
    nedenler: list[str] = []
    for sablon, fontlar, kur in adaylar[:deneme]:
        try:
            cizim = kur()
        except ValueError as e:  # EksikGlif, boş satır
            nedenler.append(f"{sablon}/{fontlar}: {e}")
            continue
        kalite, gecti = {}, True
        goruntuler = {}
        for etiket, murekkep, kumaslar, v in (
            ("koyu", KOYU_MUREKKEP, ACIK_KUMAS, vurgu[0] if vurgu else None),
            ("acik", ACIK_MUREKKEP, KOYU_KUMAS, vurgu[1] if vurgu else None),
        ):
            img = render.goruntu(cizim.svg(murekkep, v))
            s = kapilar.denetle(img, murekkep, kumaslar, cizim.okunacak, cizim.en_kucuk_yazi, vurgu=v)
            kalite[etiket] = [str(x) for x in s]
            goruntuler[etiket] = img
            if not kapilar.gecti(s):
                gecti = False
                nedenler.append(f"{sablon}/{fontlar[0]}: " + "; ".join(str(x) for x in s if not x.gecti))
                break
        if gecti:
            return Secim(sablon, fontlar, palet, cizim, goruntuler["koyu"], goruntuler["acik"], kalite), nedenler
    return None, nedenler
