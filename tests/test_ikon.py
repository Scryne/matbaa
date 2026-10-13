"""Çizimli şablonlar (2026-10-13): her niş çizimi baskı kapılarından geçer; çizimli şablonlar kapılardan geçer ve önce denenir."""

from __future__ import annotations

import random

import numpy as np
import pytest
from scipy import ndimage

from matbaa.tasarim import ikon, kapilar, render, sec
from matbaa.tasarim.sablonlar import IKON_MIN, Yazi, gunes, ikon_yigin, kavis_ikon

KOYU, VURGU = "#1d1d1f", "#9a3a2b"
KUMAS = ["#ffffff", "#f0e8d6"]


@pytest.mark.parametrize("ad", ikon.IKONLAR)
def test_cizim_en_kucuk_boyunda_ince_cizgi_kapisindan_gecer(ad):
    """Çizim en küçük kullanım boyunda (IKON_MIN) basıldığında hiçbir parçası DTG'nin kopardığı incelikte değil."""
    parca, g, h = ikon.yerlestir(ad, 500, 40, IKON_MIN)
    assert h == pytest.approx(IKON_MIN, rel=0.01) and g > 0
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{IKON_MIN + 80:.0f}"><g fill="#000" color="#000">{parca}</g></svg>'
    import io

    import resvg_py
    from PIL import Image

    png = bytes(resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True))
    govde = np.asarray(Image.open(io.BytesIO(png)).getchannel("A")) >= 128
    r = kapilar.INCE_YARICAP
    disk = np.hypot(*np.mgrid[-r : r + 1, -r : r + 1]) <= r
    kayip = (govde & ~ndimage.binary_opening(govde, structure=disk)).sum() / govde.sum()
    assert kayip <= kapilar.INCE_KAYIP_MAKS, f"{ad}: ince parça kaybı {kayip:.4f}"


def test_her_nisin_cizimi_var_ve_mevsim_kelimesi_once_gelir():
    for nis in ("fishing", "pickleball", "knitting", "running", "aunt", "milestone", "senior_mom"):
        assert ikon.adaylar(nis, "ANY TEXT"), nis
    assert ikon.adaylar("running", "MERRY MILEAGE")[0] in ikon.MEVSIM_IKONLARI
    assert not set(ikon.adaylar("running", "PACE: SNAIL")) & set(ikon.MEVSIM_IKONLARI)
    assert ikon.adaylar("bilinmeyen", "X") == []


ORNEKLER = {
    "ikon_yigin": lambda: ikon_yigin(
        "balik", [Yazi("THE BIGGER", "Anton-Regular.ttf", 0.02), Yazi("ONE GOT AWAY", "Anton-Regular.ttf", 0.02, vurgu=True)]
    ),
    "gunes": lambda: gunes(
        "dag",
        [
            Yazi("GRANDPA'S OFFICE", "AlfaSlabOne-Regular.ttf", 0.02),
            Yazi("BACK BY DINNER", "Staatliches-Regular.ttf", 0.08, 0.6, kucuk=True),
        ],
    ),
    "kavis_ikon": lambda: kavis_ikon(
        "yumak",
        Yazi("ONE MORE ROW", "Bungee-Regular.ttf", 0.06),
        Yazi("THEN BED", "ArchivoBlack-Regular.ttf"),
        Yazi("I'M LYING", "BebasNeue-Regular.ttf", 0.12),
    ),
}


@pytest.mark.parametrize(("ad", "vurgu"), [("ikon_yigin", VURGU), ("gunes", VURGU), ("gunes", None), ("kavis_ikon", VURGU)])
def test_cizimli_sablon_kapilardan_gecer(ad, vurgu):
    """İki renkte ve tek renkte (vurgu = mürekkep: güneşle çizim aynı renk, aradaki boşluk okunurluğu taşır)."""
    c = ORNEKLER[ad]()
    img = render.goruntu(c.svg(KOYU, vurgu))
    sonuc = kapilar.denetle(img, KOYU, KUMAS, c.okunacak, c.en_kucuk_yazi, vurgu=vurgu)
    assert kapilar.gecti(sonuc), [str(s) for s in sonuc if not s.gecti]


def test_gunes_cizimi_gunesten_bosluklu_ayrilir():
    """Tek renkte çizim güneşe yapışırsa siluet kaybolur: güneşin içinde çizim pikselleriyle güneş pikselleri arasında boşluk olmalı."""
    from matbaa.tasarim.sablonlar import ICERIK_G, UST_PAY

    c = ORNEKLER["gunes"]()
    rgba = np.asarray(render.goruntu(c.svg("#000000", "#ff0000")))
    taban = int(UST_PAY + ICERIK_G * 0.30)
    dolu = rgba[:taban, :, 3] > 200
    gunes_ = dolu & (rgba[:taban, :, 0] > 200)
    cizim = dolu & (rgba[:taban, :, 0] < 50)
    mesafe = ndimage.distance_transform_edt(~gunes_)
    assert cizim.any() and gunes_.any()
    assert mesafe[cizim].min() >= 25, f"çizim güneşe {mesafe[cizim].min():.0f} px yakın"


def test_cizimli_sablonlar_nis_varken_once_denenir():
    adaylar = sec._adaylar("", ["THE BIGGER", "ONE GOT AWAY"], "", random.Random(5), [], nis="fishing")
    assert adaylar[0][0] in sec.IKONLU
    yazili = sec._adaylar("", ["THE BIGGER", "ONE GOT AWAY"], "", random.Random(5), [])
    assert not {a[0] for a in yazili} & sec.IKONLU
