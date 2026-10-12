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
ACIK_KUMAS = ["#ffffff", "#efe6d2", "#c9d6c3", "#d9c7b0"]  # beyaz, ivory, sage, sand (Comfort Colors tonları)
KOYU_KUMAS = ["#141414", "#1f2a44", "#2f4a3a", "#5a2e2e"]  # siyah, lacivert, orman, bordo
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
        satirlar += [Yazi(s, f, 0.02) for s in dengeli_bol(ana, f, 0.02)]
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
        for etiket, murekkep, kumaslar in (("koyu", KOYU_MUREKKEP, ACIK_KUMAS), ("acik", ACIK_MUREKKEP, KOYU_KUMAS)):
            img = render.goruntu(cizim.svg(murekkep))
            s = kapilar.denetle(img, murekkep, kumaslar, cizim.okunacak, cizim.en_kucuk_yazi)
            kalite[etiket] = [str(x) for x in s]
            goruntuler[etiket] = img
            if not kapilar.gecti(s):
                gecti = False
                nedenler.append(f"{sablon}/{fontlar[0]}: " + "; ".join(str(x) for x in s if not x.gecti))
                break
        if gecti:
            return Secim(sablon, fontlar, cizim, goruntuler["koyu"], goruntuler["acik"], kalite), nedenler
    return None, nedenler
