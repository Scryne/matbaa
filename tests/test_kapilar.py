"""Kalite kapıları bozuk girdiyle sınanır: her kapı kendi hatasını yakalamalı, sağlam tasarımı geçirmeli.

Yeşil test ancak sorduğu soru kadar değerlidir (Kokpit v2.7 dersi): her bozuk örnek tek bir kusuru
taşır ve yalnız ilgili kapının düşmesi beklenir.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFilter

from matbaa.tasarim import kapilar, render
from matbaa.tasarim.sablonlar import TUVAL_G, TUVAL_Y, Yazi, kavis, yigin

KOYU = "#1d1d1f"
ACIK_KUMAS = ["#ffffff"]


@pytest.fixture(scope="module")
def saglam() -> tuple[Image.Image, list[str], float]:
    c = yigin(
        [
            Yazi("JUST ONE", "Anton-Regular.ttf", 0.04, 0.62),
            Yazi("MORE", "Anton-Regular.ttf"),
            Yazi("PLANT", "Anton-Regular.ttf"),
        ]
    )
    return render.goruntu(c.svg(KOYU)), c.okunacak, c.en_kucuk_yazi


def _dusenler(
    img, murekkep=KOYU, kumaslar=ACIK_KUMAS, beklenen=None, en_kucuk=None
) -> set[str]:
    return {
        s.kapi.split()[0]
        for s in kapilar.denetle(img, murekkep, kumaslar, beklenen, en_kucuk)
        if not s.gecti
    }


def test_saglam_tasarim_gecer(saglam):
    img, metin, kucuk = saglam
    assert _dusenler(img, beklenen=metin, en_kucuk=kucuk) == set()


def test_yumusak_golge_yari_saydam_kapisina_takilir(saglam):
    img = saglam[0]
    golge = img.filter(ImageFilter.GaussianBlur(40))
    a = np.asarray(golge.getchannel("A")).astype(float) * 0.45
    golge.putalpha(Image.fromarray(a.astype(np.uint8)))
    bozuk = Image.new("RGBA", img.size)
    bozuk.alpha_composite(golge, (40, 40))
    bozuk.alpha_composite(img)
    assert _dusenler(bozuk) == {"yari_saydam"}


def test_ince_cizgi_kapisina_takilir(saglam):
    bozuk = saglam[0].copy()
    d = ImageDraw.Draw(bozuk)
    for i in range(60):  # 4 px genişliğinde çizgiler: ~0,3 mm
        y = 3800 + i * 20
        d.rectangle((300, y, 4200, y + 3), fill=KOYU)
    assert _dusenler(bozuk) == {"ince_cizgi"}


def test_kenara_dayanan_tasarim_kenar_payina_takilir(saglam):
    bozuk = Image.new("RGBA", (TUVAL_G, TUVAL_Y))
    bozuk.alpha_composite(saglam[0], (-200, 0))
    assert "kenar_payi" in _dusenler(bozuk)


def test_dusuk_kontrast_kapisi():
    img = render.goruntu(yigin([Yazi("NIGHT", "Anton-Regular.ttf")]).svg("#2b2b2b"))
    assert _dusenler(img, murekkep="#2b2b2b", kumaslar=["#141414"]) == {"kontrast"}


def test_kucuk_yazi_kapisi(saglam):
    assert _dusenler(saglam[0], en_kucuk=90.0) == {"en_kucuk_yazi"}


def test_okunurluk_ust_uste_binen_yaziyi_yakalar():
    a = yigin([Yazi("GARDEN", "Anton-Regular.ttf")])
    b = yigin([Yazi("PLANTS", "AlfaSlabOne-Regular.ttf")])
    svg = a.svg(KOYU).replace(
        "</g></svg>", "".join(b.parcalar) + "</g></svg>"
    )  # iki satır aynı yerde
    img = render.goruntu(svg)
    assert "okunurluk" in _dusenler(img, beklenen=["GARDEN", "PLANTS"])


def test_bos_tuval():
    assert _dusenler(Image.new("RGBA", (TUVAL_G, TUVAL_Y))) == {"bos_degil"}


def test_kavis_ortasi_yay_uclarinin_altinda():
    c = kavis(
        Yazi("BOOK CLUB", "AlfaSlabOne-Regular.ttf", 0.06),
        Yazi("Chapter Lover", "Lobster-Regular.ttf"),
    )
    img = render.goruntu(c.svg(KOYU))
    assert kapilar.gecti(
        kapilar.denetle(img, KOYU, ACIK_KUMAS, c.okunacak, c.en_kucuk_yazi)
    )
