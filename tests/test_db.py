from __future__ import annotations

import pytest

from matbaa import db


@pytest.fixture
def c(tmp_path):
    baglanti = db.baglan(tmp_path / "t.db")
    yield baglanti
    baglanti.close()


def _temiz_ifade(c) -> int:
    i = db.ifade_ekle(c, "fishing", ["REEL GOOD", "GRANDPA"])
    db.kapi_yaz(c, i, "temiz", [], [{"ifade": "REEL GOOD GRANDPA"}])
    return i


def test_ayni_ifade_iki_kez_eklenmez(c):
    assert db.ifade_ekle(c, "fishing", ["A", "B"]) is not None
    assert db.ifade_ekle(c, "fishing", ["A", "B"]) is None
    assert db.ifade_ekle(c, "knitting", ["A", "B"]) is not None


@pytest.mark.parametrize("karar", [None, "ret"])
def test_temiz_olmayan_ifadeden_tasarim_dogmaz(c, karar):
    i = db.ifade_ekle(c, "fishing", ["X"])
    if karar:
        db.kapi_yaz(c, i, karar, ["neden"], [])
    with pytest.raises(db.GecersizGecis):
        db.tasarim_ekle(c, i, "kavis", ["Anton-Regular.ttf"])


def test_insan_karari_tasarima_girer_panelde_isaretli(c):
    """K-13: "insan" sonucu reddedilmez, onay kuyruğunda işaretli gider; kararı Scryne'ın onayı verir."""
    i = db.ifade_ekle(c, "fishing", ["X"])
    db.kapi_yaz(c, i, "insan", ["benzer marka, ünlülük belirsiz"], [])
    assert db.tasarim_ekle(c, i, "kavis", [])


def test_mutlu_yol_ve_olay_gunlugu(c):
    t = db.tasarim_ekle(c, _temiz_ifade(c), "kavis", ["Anton-Regular.ttf"])
    for d in ("kalite_ok", "metin_ok", "onay_bekliyor", "onaylandi", "yayinda"):
        db.gecis(c, t, d)
    assert c.execute("SELECT durum FROM tasarim WHERE id = ?", (t,)).fetchone()[0] == "yayinda"
    yeniler = [r[0] for r in c.execute("SELECT yeni FROM olay WHERE varlik = 'tasarim' ORDER BY id")]
    assert yeniler == ["aday", "kalite_ok", "metin_ok", "onay_bekliyor", "onaylandi", "yayinda"]


def test_urun_durumu_ayri_izlenir(c):
    t = db.tasarim_ekle(c, _temiz_ifade(c), "kavis", [])
    c.execute("INSERT INTO urun (tasarim_id, urun) VALUES (?, 'tisort'), (?, 'hoodie')", (t, t))
    db.urun_gecis(c, t, "tisort", "olusturuldu", printify_id="p1")
    db.urun_gecis(c, t, "tisort", "printify")
    db.urun_gecis(c, t, "hoodie", "hata", "429")
    r = dict(c.execute("SELECT urun, durum FROM urun WHERE tasarim_id = ?", (t,)).fetchall())
    assert r == {"tisort": "printify", "hoodie": "hata"}
    assert db.hata_oncesi(c, t, "hoodie") == "bekliyor" and db.hata_oncesi(c, t, "tisort") is None
    assert c.execute("SELECT printify_id FROM urun WHERE urun = 'tisort'").fetchone()[0] == "p1"
    with pytest.raises(db.GecersizGecis):
        db.urun_gecis(c, t, "tisort", "aktif")  # Etsy taslağı atlanamaz


def test_onaysiz_yayin_yok(c):
    t = db.tasarim_ekle(c, _temiz_ifade(c), "kavis", [])
    db.gecis(c, t, "kalite_ok")
    db.gecis(c, t, "metin_ok")
    with pytest.raises(db.GecersizGecis):
        db.gecis(c, t, "yayinda")  # onay atlanamaz


def test_ret_son_durumdur_ve_neden_saklanir(c):
    t = db.tasarim_ekle(c, _temiz_ifade(c), "kavis", [])
    db.gecis(c, t, "ret", "okunurluk 0.33")
    assert c.execute("SELECT ret_nedeni FROM tasarim WHERE id = ?", (t,)).fetchone()[0] == "okunurluk 0.33"
    with pytest.raises(db.GecersizGecis):
        db.gecis(c, t, "kalite_ok")


def test_duzeltme_istegi_adaya_doner(c):
    t = db.tasarim_ekle(c, _temiz_ifade(c), "kavis", [])
    for d in ("kalite_ok", "metin_ok", "onay_bekliyor", "aday"):
        db.gecis(c, t, d)
    assert [r["id"] for r in db.durumdakiler(c, "aday")] == [t]
