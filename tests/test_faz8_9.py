"""Faz 8–9: harcama tavanları, kur, aylık özet, haftalık rapor. Her test geçici veritabanında koşar (gerçek kuyruğa dokunmaz)."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_entegrasyon import SahtePrintify, ortam  # noqa: F401  (fixture)

from matbaa import db, fiyat, rapor, siparis, tavan, yayin

SIMDI = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)


def _olay(c, zaman: datetime, varlik: str, yeni: str, n: int = 1) -> None:
    for _ in range(n):
        c.execute(
            "INSERT INTO olay (zaman, varlik, varlik_id, eski, yeni) VALUES (?, ?, 1, NULL, ?)",
            (zaman.isoformat(timespec="seconds"), varlik, yeni),
        )
    c.commit()


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "t.db")
    monkeypatch.setattr(tavan, "tavanlar", lambda: {"aylik_ilan_ucreti_usd": 1.0, "gunluk_ip_denetim": 3})
    return db.baglan()


def test_ilan_tavani_ay_icinde_sayar_onceki_ayi_saymaz(c):
    _olay(c, SIMDI.replace(month=10), "urun", "tisort:printify", 20)  # geçen ay: sayılmaz
    _olay(c, SIMDI, "urun", "tisort:printify", 4)  # bu ay $0,80
    tavan.ilan_kontrol(c, SIMDI)  # 5. ilan = $1,00, tavanda: izinli
    _olay(c, SIMDI, "urun", "hoodie:printify")
    with pytest.raises(tavan.TavanAsildi, match="aylık ilan"):
        tavan.ilan_kontrol(c, SIMDI)


def test_ip_tavani_gunluk(c):
    _olay(c, SIMDI - timedelta(days=1), "ifade", "kapi:temiz", 10)
    _olay(c, SIMDI, "ifade", "kapi:ret", 2)
    tavan.ip_kontrol(c, SIMDI)
    _olay(c, SIMDI, "ifade", "kapi:temiz")
    with pytest.raises(tavan.TavanAsildi, match="IP"):
        tavan.ip_kontrol(c, SIMDI)


def test_yayin_tavanda_para_harcamadan_durur(ortam, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tavan, "tavanlar", lambda: {"aylik_ilan_ucreti_usd": 0.40, "gunluk_ip_denetim": 100})
    p = SahtePrintify()
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert len(p.olusturulan) == 2 and "tavan" in s  # $0,20 × 2 = tavan; üçüncü ürün açılmadı
    assert ortam.execute("SELECT count(*) FROM urun WHERE durum = 'hata'").fetchone()[0] == 0  # tavan hata değil, bekleme


def test_kur_tcmb_ayrisir_ve_bayatsa_configa_duser(tmp_path, monkeypatch):
    xml = '<Currency Kod="EUR"><ForexSelling>55.1</ForexSelling></Currency><Currency Kod="USD"><ForexSelling>49.3358</ForexSelling></Currency>'
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=xml)))
    monkeypatch.setattr(fiyat, "KUR_DOSYASI", tmp_path / "kur.json")
    monkeypatch.setattr(fiyat, "VERI", tmp_path)
    assert fiyat.kur_guncelle(http) == 49.3358  # EUR değil USD
    assert fiyat.try_usd() == 49.3358
    k = json.loads((tmp_path / "kur.json").read_text())
    k["zaman"] = int(time.time()) - 8 * 86400
    (tmp_path / "kur.json").write_text(json.dumps(k))
    assert fiyat.try_usd() == fiyat.ucretler()["try_usd"]


def _siparis(c, makbuz: str, olusma: datetime, net: float, takip: str | None = None, durum: str = "paid") -> None:
    c.execute(
        "INSERT INTO siparis (etsy_receipt_id, brut, net, durum, takip, olusturma) VALUES (?, ?, ?, ?, ?, ?)",
        (makbuz, net * 3, net, durum, takip, olusma.isoformat()),
    )
    c.commit()


def test_aylik_ozet_ilan_ucretini_dusur(c):
    _siparis(c, "1", SIMDI.replace(day=2), 9.0)
    _siparis(c, "2", SIMDI.replace(day=30), 10.0)
    _siparis(c, "3", SIMDI.replace(month=12, day=1), 99.0)  # sonraki ay
    _olay(c, SIMDI.replace(day=3), "urun", "tisort:printify", 10)
    o = siparis.aylik(c, "2026-11")
    assert (o["siparis"], o["siparis_net_usd"], o["ilan_ucreti_usd"], o["net_usd"]) == (2, 19.0, 2.0, 17.0)
    assert siparis.aylik(c, "2026-12")["siparis"] == 1  # aralık → ocak sınırı


class SahteEtsy:
    def __init__(self, ilanlar):
        self.ilanlar = ilanlar

    def aktif_ilanlar(self):
        return self.ilanlar


def test_haftalik_rapor_goruntulenme_farki_ve_gecikme(c, tmp_path, monkeypatch):
    monkeypatch.setattr(rapor, "RAPOR_DIZINI", tmp_path / "rapor")
    once = SIMDI - timedelta(days=7)
    rapor.goruntu_al(c, SahteEtsy([{"listing_id": 1, "views": 40, "num_favorers": 1}]), once)
    _siparis(c, "geciken", SIMDI - timedelta(days=10), 9.0)  # 6 iş günü, takip yok
    _siparis(c, "kargoda", SIMDI - timedelta(days=10), 9.0, takip="1Z")
    _siparis(c, "tamam", SIMDI - timedelta(days=12), 9.0, durum="completed")
    etsy = SahteEtsy([{"listing_id": 1, "views": 55, "num_favorers": 3}, {"listing_id": 2, "views": 7, "num_favorers": 0}])
    veri, metin = rapor.haftalik(c, etsy, SIMDI)
    g = veri["goruntulenme"]
    assert (g["toplam"], g["hafta"], g["favori_hafta"]) == (62, 22, 2)  # 15 + 7 (yeni ilan), 2 favori
    assert [x.split(":")[0] for x in veri["dikkat"]["gecikme"]] == ["makbuz geciken"]
    assert veri["hafta"] == "2026-H47" and metin.startswith("# Matbaa haftalık rapor — 2026-H47")
    assert "## Dikkat" in metin.split("## İlan")[0]  # dikkat isteyen en üstte
    yol = rapor.yaz(veri, metin)
    assert os.path.basename(yol) == "2026-H47.md" and rapor.bu_hafta_var_mi(SIMDI)
