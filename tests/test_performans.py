"""Faz 13: niş sırası mağaza verisinden; veri azken dengeli büyüme; satan ifadeler Claude istemine örnek olur."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from matbaa import db, performans
from matbaa.ifade import uret as ifade_uret

SIMDI = datetime(2026, 12, 1, 9, 0, tzinfo=UTC)


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "p.db")
    return db.baglan()


def _ilanlar(c, nis: str, adet: int, ilk_listing: int, slogan: str = "S") -> list[int]:
    """`adet` tasarım × 1 aktif ürün; dönen: tasarım kimlikleri."""
    tasarimlar = []
    for k in range(adet):
        i = db.ifade_ekle(c, nis, [f"{slogan} {nis} {k}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        t = db.tasarim_ekle(c, i, "yigin", [])
        c.execute(
            "INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (?, 'tisort', 'aktif', ?)",
            (t, str(ilk_listing + k)),
        )
        tasarimlar.append(t)
    c.commit()
    return tasarimlar


def _goruntu(c, tarih: datetime, listing: int, views: int, fav: int = 0) -> None:
    c.execute(
        "INSERT OR REPLACE INTO goruntulenme (tarih, etsy_listing_id, views, favori) VALUES (?, ?, ?, ?)",
        (tarih.date().isoformat(), str(listing), views, fav),
    )


def test_veri_azken_kuyruk_dengesi(c):
    _ilanlar(c, "fishing", 5, 100)
    sira = performans.uretim_sirasi(c, ["fishing", "knitting", "garden"], {"fishing": 9, "knitting": 1, "garden": 4}, SIMDI)
    assert sira == ["knitting", "garden", "fishing"]  # 5 aktif ilan < eşik: veri gürültü


def test_ilan_basina_puan_cok_ilanli_olu_nisi_gecer(c):
    fishing = _ilanlar(c, "fishing", 25, 100)  # çok ilan, hiç ilgi yok
    _ilanlar(c, "knitting", 8, 500)  # az ilan, ilgi var
    once = SIMDI - timedelta(days=performans.PENCERE_GUN + 1)
    for n in range(8):
        _goruntu(c, once, 500 + n, 10)
        _goruntu(c, SIMDI, 500 + n, 70, fav=2)  # +60 görüntülenme, +2 favori / ilan
    for n in range(25):
        _goruntu(c, SIMDI, 100 + n, 3)
    c.execute(
        "INSERT INTO siparis (etsy_receipt_id, tasarim_id, net, durum, olusturma) VALUES ('x', ?, 9, 'canceled', ?)",
        (fishing[0], SIMDI.isoformat()),
    )  # iptal satış sayılmaz
    c.commit()
    p = performans.nis_puanlari(c, SIMDI)
    assert p["knitting"]["goruntulenme"] == 480 and p["knitting"]["favori"] == 16 and p["fishing"]["satis"] == 0
    assert p["knitting"]["puan"] > 10 * p["fishing"]["puan"]
    sira = performans.uretim_sirasi(c, ["fishing", "knitting", "garden"], {}, SIMDI)
    assert sira == ["garden", "knitting", "fishing"]  # hiç ilanı olmayan niş keşfedilir; ilgi gören, görmeyenin önünde


def test_satis_siralamayi_cevirir_ve_satanlar_isteme_girer(c):
    fishing = _ilanlar(c, "fishing", 20, 100, slogan="REEL")
    _ilanlar(c, "knitting", 20, 500)
    for n in range(20):
        _goruntu(c, SIMDI, 500 + n, 40)  # knitting 800 görüntülenme, satış yok
        _goruntu(c, SIMDI, 100 + n, 20)  # fishing 400 görüntülenme, 3 satış
    for k in range(3):
        c.execute(
            "INSERT INTO siparis (etsy_receipt_id, tasarim_id, net, durum, olusturma) VALUES (?, ?, 9, 'paid', ?)",
            (f"r{k}", fishing[0], (SIMDI - timedelta(days=2)).isoformat()),
        )
    c.commit()
    # Çok görülüp satmayan niş, az görülüp satanın önüne geçmez: 20 × 5/500 = 0,2 > 40 × 2/900 ≈ 0,09
    assert performans.uretim_sirasi(c, ["knitting", "fishing"], {}, SIMDI)[0] == "fishing"
    satan = performans.satanlar(c, "fishing")
    assert satan == ["REEL fishing 0"]
    istem = ifade_uret.istem("fishing", 12, [], satanlar=satan)
    assert "REEL fishing 0" in istem and "never reuse their key phrase" in istem
