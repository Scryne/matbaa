"""Faz 2: her şablon kalite kapılarından geçer, font tablosu tutarlı, çeşitlilik kuralı seçim sırasını gerçekten değiştirir."""

from __future__ import annotations

import random

import pytest

from matbaa.tasarim import kapilar, render, sec
from matbaa.tasarim.sablonlar import Yazi, ayirici, cerceve, egik, el_yazisi, madalyon, yigin
from matbaa.tasarim.yazi import FONT_DIZINI

KOYU, VURGU = "#1d1d1f", "#9a3a2b"
KUMAS = ["#ffffff", "#f0e8d6"]

ORNEKLER = {
    "cerceve": lambda: cerceve(
        [Yazi("REEL COOL", "Anton-Regular.ttf"), Yazi("GRANDPA", "Anton-Regular.ttf")],
        Yazi("EST. 2026", "BebasNeue-Regular.ttf", 0.15),
        Yazi("CATCH AND RELEASE", "BebasNeue-Regular.ttf", 0.1),
    ),
    "ayirici": lambda: ayirici(
        Yazi("PICKLEBALL", "Graduate-Regular.ttf", 0.12, 0.5, kucuk=True),
        [Yazi("DINK", "Bevan-Regular.ttf"), Yazi("RESPONSIBLY", "Bevan-Regular.ttf")],
    ),
    "egik": lambda: egik([Yazi("KNIT", "Knewave-Regular.ttf"), Yazi("HAPPENS", "Knewave-Regular.ttf", vurgu=True)]),
    "madalyon": lambda: madalyon(
        Yazi("PAPA'S FISHING CLUB", "Graduate-Regular.ttf", 0.08),
        Yazi("REEL", "Rye-Regular.ttf"),
        Yazi("EST. 2026", "Graduate-Regular.ttf", 0.12),
    ),
    "el_yazisi": lambda: el_yazisi(
        [Yazi("CROCHET", "PassionOne-Regular.ttf"), Yazi("QUEEN", "PassionOne-Regular.ttf")],
        Yazi("Hooked on", "Pacifico-Regular.ttf"),
        ustte=True,
    ),
}


@pytest.mark.parametrize("ad", ORNEKLER)
def test_yeni_sablon_kapilardan_gecer(ad):
    c = ORNEKLER[ad]()
    img = render.goruntu(c.svg(KOYU, VURGU))
    sonuc = kapilar.denetle(img, KOYU, KUMAS, c.okunacak, c.en_kucuk_yazi, vurgu=VURGU)
    assert kapilar.gecti(sonuc), [str(s) for s in sonuc if not s.gecti]
    assert c.vurgu_parcalar, "şablonun ikinci renkte öğesi olmalı (K-18)"


def test_madalyon_uzun_orta_satiri_reddeder():
    with pytest.raises(ValueError, match="madalyon"):
        madalyon(
            Yazi("CLUB", "Graduate-Regular.ttf"),
            Yazi("PROFESSIONAL OVERTHINKER", "Anton-Regular.ttf"),
            Yazi("EST", "Graduate-Regular.ttf"),
        )


def _bloklar(c) -> list[tuple[int, int]]:
    """Render edilen tasarımda dikey dolu bantlar (satır/çizgi), yukarıdan aşağı."""
    satirlar = (render.alfa(render.goruntu(c.svg(KOYU, VURGU))) > 0).any(axis=1)
    bloklar, bas = [], None
    for y, dolu in enumerate(satirlar):
        if dolu and bas is None:
            bas = y
        elif not dolu and bas is not None:
            bloklar.append((bas, y))
            bas = None
    return bloklar


def test_kisa_kucuk_satir_ana_satir_boyuna_cikmaz():
    f = "Anton-Regular.ttf"
    c = yigin([Yazi("PROMOTED", f), Yazi("TO AUNTIE", f), Yazi("EST. 2027", "BebasNeue-Regular.ttf", 0.08, 0.6, kucuk=True)])
    *ana, kucuk = [b - a for a, b in _bloklar(c)]
    assert kucuk <= 0.5 * min(ana)


def test_ayirici_cizgisi_yaziya_degmez():
    """Çizgi ile üstündeki satır arasında satır yüksekliğinin belirgin bir kesri kadar boşluk kalır (pano: "MOM SERVES")."""
    c = ayirici(None, [Yazi("MOM SERVES", "ArchivoBlack-Regular.ttf"), Yazi("SNACKS & ACES", "ArchivoBlack-Regular.ttf")])
    bloklar = _bloklar(c)
    assert len(bloklar) == 3  # satır, çizgi, satır
    (u0, u1), (c0, _), _ = bloklar
    assert c0 - u1 >= 0.3 * (u1 - u0)


def test_font_tablosu():
    dosyalar = {p.name for p in FONT_DIZINI.glob("*.ttf")}
    assert set(sec.FONTLAR) == dosyalar, "tablo ile klasör aynı olmalı (kullanılmayan font taşınmaz)"
    assert len(sec.FONTLAR) >= 20
    for f in sec.FONTLAR:
        lisans = FONT_DIZINI / f"{f.split('-')[0].lower()}-OFL.txt"
        assert lisans.exists() and "SIL Open Font License" in lisans.read_text(encoding="utf-8"), f
    assert not set(sec.EL_FONTLAR) & set(
        sec.ANA_FONTLAR + sec.KUCUK_FONTLAR + sec.KAVIS_FONTLAR
    )  # el yazısı yalnız ikincil satır


def test_el_yazisi_buyuk_harfli_satira_uygulanmaz():
    kur = sec._kurucular("", ["GARDEN THERAPY"], "SO MANY PROJECTS")["el_yazisi"]
    assert kur("Anton-Regular.ttf", random.Random(1)) is None
    kur = sec._kurucular("", ["GARDEN THERAPY"], "so many projects")["el_yazisi"]
    assert kur("Anton-Regular.ttf", random.Random(1)) is not None


def test_cesitlilik_az_kullanilan_sablon_once_yakin_cift_sona():
    son = [("yigin", "Anton-Regular.ttf")] * 6 + [("cerceve", "Bevan-Regular.ttf")] * 5
    adaylar = sec._adaylar("Papa's Rules", ["REEL COOL"], "Catch and release", random.Random(3), son)
    sira = [a[0] for a in adaylar]
    ilk_tur = sira[: len(set(sira))]
    assert ilk_tur.index("yigin") == len(ilk_tur) - 1 and ilk_tur.index("cerceve") == len(ilk_tur) - 2
    assert all(sec.ana_font(s, f) != "Bevan-Regular.ttf" for s, f, _ in adaylar if s == "cerceve")
    # Başlık + tek ana + alt: el yazısı dışında hepsi uygun (el yazısı tam bir ikincil satır ister).
    assert set(sira) == {"yigin", "egik", "ayirici", "cerceve", "kavis", "rozet", "madalyon"}


def test_sablon_yapiya_uymazsa_aday_olmaz():
    sira = {a[0] for a in sec._adaylar("", ["DINK RESPONSIBLY"], "", random.Random(1), [])}
    assert not sira & {"kavis", "rozet", "madalyon", "el_yazisi"}  # başlık/alt satır gerektirenler


def test_bes_tasarimlik_pencerede_ayni_cift_tekrar_etmez(monkeypatch):
    """Ardışık seçimlerde (şablon, ana font) çifti 5'lik pencerede bir kez (K-4). Kapılar burada ölçülmüyor: hızlı sahte."""
    monkeypatch.setattr(sec.kapilar, "denetle", lambda *a, **k: [])
    monkeypatch.setattr(sec.render, "goruntu", lambda svg: None)
    son: list[tuple[str, str]] = []
    for n in range(30):
        s, _ = sec.sec("", ["FISH", "TALES"], "", son, tohum=n)
        cift = (s.sablon, sec.ana_font(s.sablon, s.fontlar))
        assert cift not in son[-sec.CESITLILIK_PENCERE :]
        son.append(cift)
    assert len({s for s, _ in son}) >= 4  # tek şablona yığılma yok
