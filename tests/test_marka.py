"""Marka eşleştiricisi küçük, elle kurulmuş bir dizinle sınanır (gerçek USPTO dosyasına bağlı değil)."""

from __future__ import annotations

import pytest

from matbaa.ip.marka import MarkaDizini

MARKALAR = [
    ("BOYMOM", "1"),
    ("MAMA BEAR", "2"),
    ("GIRL DAD", "3"),
    ("REEL COOL", "4"),
    ("PICKLEBALL", "5"),
    ("IN MY", "6"),
    ("JUST DO IT", "7"),
    ("PEARL JAM", "8"),
    ("NIKE", "9"),
    ("BASKETBALL IS MY THERAPY", "10"),
]


@pytest.fixture(scope="module")
def d() -> MarkaDizini:
    return MarkaDizini(MARKALAR)


@pytest.mark.parametrize(
    ("ifade", "neden"),
    [
        ("Mama Bear", "ifadenin tamamı canlı marka"),
        ("Boy Mom", "ifade bitişik yazılınca canlı marka"),
        ("Proud Boymom Club", "uydurma tek kelime canlı marka"),
        ("Girl Dad Energy", "çok kelimeli canlı marka ifadenin baskın kısmı"),
        ("Reel Cool Grandpa", "çok kelimeli canlı marka ifadenin baskın kısmı"),
    ],
)
def test_kesin_ret(d, ifade, neden):
    s = d.kontrol(ifade)
    assert not s.temiz
    assert neden in {r[1] for r in s.reddet}


def test_yaygin_kelime_markasi_reddetmez_aday_yapar(d):
    s = d.kontrol("Pickleball Is My Therapy")
    assert s.temiz
    assert "PICKLEBALL" in s.adaylar


def test_yalniz_baglactan_marka_sayilmaz(d):
    s = d.kontrol("Knitting Is In My Blood Forever")
    assert s.temiz and "IN MY" not in s.adaylar


def test_satir_tek_yaygin_kelime_marka_ise_dusurmez(d):
    assert d.satir_kontrol("Mama").temiz  # "MAMA BEAR" var ama satır "MAMA": slogan düzeyinde bakılır
    assert d.satir_kontrol("Pickleball").temiz


def test_satirin_kendisi_cok_kelimeli_marka(d):
    s = d.satir_kontrol("Mama Bear")
    assert not s.temiz and s.reddet[0][1] == "satırın kendisi canlı marka"


def test_satirda_uydurma_marka_kelimesi(d):
    assert not d.satir_kontrol("Proud Boymom").temiz


def test_tek_kelime_takasi_benzer_doner(d):
    assert "JUST DO IT" in d.kontrol("Just Dink It").benzerler
    assert "BASKETBALL IS MY THERAPY" in d.kontrol("Pickleball Is My Therapy").benzerler


def test_iki_kelimede_yalniz_sestes_takas(d):
    assert "PEARL JAM" in d.kontrol("Purl Jam").benzerler
    assert d.kontrol("Toast Jam").benzerler == []  # PEARL→TOAST sesteş değil


def test_temiz_ifade(d):
    s = d.kontrol("Knit Happens")
    assert s.temiz and not s.benzerler


def test_noktalama_ve_ve_isareti(d):
    assert not d.kontrol("MAMA-BEAR!").temiz
