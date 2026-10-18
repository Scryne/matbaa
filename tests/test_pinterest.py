"""Pinterest toplu pin CSV'si: kuyruk (ilan başına 3 görsel), sınırlar, takvim, indirme. Geçici veritabanı, sahte Etsy."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

import pytest

from matbaa import db, pinterest

SIMDI = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


class SahteEtsy:
    def ilan_gorselleri(self, listing_id):
        return [
            {
                "url_570xN": f"https://i.etsystatic.com/{listing_id}/il_570xN_{k}.jpg",
                "url_fullxfull": f"https://i.etsystatic.com/{listing_id}/full_{k}.jpg",
            }
            for k in range(4)
        ]


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "p.db")
    c = db.baglan()
    lid = 100
    for n, nis in enumerate(["fishing", "knitting"]):
        i = db.ifade_ekle(c, nis, [f"SLOGAN {n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        t = db.tasarim_ekle(c, i, "yigin", [])
        for u in ("tisort", "hoodie", "susleme"):
            lid += 1
            c.execute(
                "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (?, ?, ?, ?, ?, 33.99, 0)",
                (
                    t,
                    u,
                    "Funny Fishing Shirt, " * 10,
                    json.dumps([f"tag {k}" for k in range(13)]),
                    "Satış cümlesi. " * 60 + "\n\nCare: wash cold.",
                ),
            )
            c.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (?, ?, 'aktif', ?)", (t, u, str(lid)))
    c.execute("INSERT INTO urun (tasarim_id, urun, durum) VALUES (1, 'sweatshirt', 'bekliyor')")
    c.commit()
    return c


def _oku(veri: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(veri.decode("utf-8"))))


def test_kuyruk_ilan_basina_uc_gorsel_ve_sinirlar(c):
    assert pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)["eklenen"] == 18  # 6 ilan × 3; bekleyen ürün pinlenmez
    assert pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)["eklenen"] == 0  # ikinci koşu mükerrer açmaz
    p = c.execute("SELECT * FROM pin WHERE urun = 'tisort' ORDER BY id").fetchone()
    assert len(p["baslik"]) <= pinterest.BASLIK_MAKS and p["baslik"].endswith("…")
    assert len(p["aciklama"]) <= pinterest.ACIKLAMA_MAKS and "Care:" not in p["aciklama"]
    assert p["gorsel_url"].endswith("full_0.jpg") and p["pano"] == "Fishing Gifts" and p["anahtar"].count(",") == 7
    ayni = c.execute(
        "SELECT gorsel_sira, gorsel_url FROM pin WHERE etsy_listing_id = ? ORDER BY gorsel_sira", (p["etsy_listing_id"],)
    )
    assert [(s, u.rsplit("/", 1)[1]) for s, u in ayni] == [(0, "full_0.jpg"), (1, "full_1.jpg"), (2, "full_2.jpg")]
    assert c.execute("SELECT pano FROM pin WHERE urun = 'susleme'").fetchone()[0] == "Christmas Ornaments"


def test_csv_takvimi_tasarimlar_ardisik_degil_ve_ikinci_dosya_devam_eder(c, monkeypatch):
    pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)
    monkeypatch.setattr(pinterest, "GUN", 2)  # takvim 2 gün (yarın, öbür gün) × 2 = 4 yer; 18 pinin 4ü sığar
    monkeypatch.setattr(pinterest, "GUNLUK", 2)
    dosya, veri, n = pinterest.csv_uret(c, SIMDI)
    satirlar = _oku(veri)
    assert list(satirlar[0]) == pinterest.SUTUNLAR and n == len(satirlar) == 4
    assert [s["Publish date"] for s in satirlar] == [
        "2026-10-21T12:00:00",
        "2026-10-21T14:00:00",
        "2026-10-22T12:00:00",
        "2026-10-22T14:00:00",
    ]
    tasarim = {r["etsy_listing_id"]: r["tasarim_id"] for r in c.execute("SELECT etsy_listing_id, tasarim_id FROM pin")}
    sira = [tasarim[s["Link"].rsplit("/", 1)[1]] for s in satirlar]
    assert all(a != b for a, b in zip(sira, sira[1:], strict=False))  # aynı tasarım art arda yok
    assert {s["Media URL"].rsplit("/", 1)[1] for s in satirlar} == {"full_0.jpg"}  # önce ilanların ilk pinleri
    assert pinterest.bekleyen(c) == 14 and pinterest.son_csv(c)[1] == veri  # yeniden indirme aynı dosya
    _, veri2, n2 = pinterest.csv_uret(c, SIMDI)
    assert n2 == 0  # takvim dolu: yeni pin eklenmez, ertesi gün eklenir
    _, veri2, n2 = pinterest.csv_uret(c, SIMDI.replace(day=22))
    assert n2 == 4 and _oku(veri2)[0]["Publish date"] == "2026-10-23T12:00:00"  # önceki takvimin ardından


def test_panodan_indirme(c, monkeypatch):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)
    t = TestClient(app, base_url="http://127.0.0.1:8766")
    assert t.get("/pinterest/son").status_code == 404
    r = t.post("/pinterest/indir")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and len(_oku(r.content)) == 18
    assert t.post("/pinterest/indir").status_code == 409  # bekleyen kalmadı
    assert _oku(t.get("/pinterest/son").content) == _oku(r.content)
    assert t.get("/api/pano").json()["pinterest"]["verilen"] == 18


def test_yayindan_kalkan_ilanin_pini_dosyaya_girmez(c):
    pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)
    c.execute("UPDATE urun SET durum = 'kaldirildi' WHERE urun = 'susleme'")  # mevsim bitti (K-30)
    _, veri, n = pinterest.csv_uret(c, SIMDI)
    assert n == 12 and not [s for s in _oku(veri) if s["Pinterest board"] == "Christmas Ornaments"]
    assert c.execute("SELECT count(*) FROM pin WHERE durum = 'atlandi'").fetchone()[0] == 6
    assert pinterest.bekleyen(c) == 0


def test_ayni_ilanin_pinleri_farkli_baslik():
    b = "Funny Fishing Grandpa T-Shirt, Grandpa's Fishing Crew Tee, Fishing Gift for Dad"
    assert pinterest.baslik(b, 0) == b
    assert pinterest.baslik(b, 1) == "Grandpa's Fishing Crew Tee, Fishing Gift for Dad, Funny Fishing Grandpa T-Shirt"
    assert len({pinterest.baslik(b, k) for k in pinterest.PIN_GORSELLERI}) == 3
    assert pinterest.baslik("Tek parça", 2) == "Tek parça"


def test_eski_pin_tablosu_tasinir(tmp_path):
    import sqlite3

    yol = tmp_path / "eski.db"
    e = sqlite3.connect(yol)
    e.execute(
        """CREATE TABLE pin (id INTEGER PRIMARY KEY, etsy_listing_id TEXT NOT NULL UNIQUE, tasarim_id INTEGER, urun TEXT,
           gorsel_url TEXT NOT NULL, baslik TEXT NOT NULL, aciklama TEXT, pano TEXT NOT NULL, anahtar TEXT, durum TEXT NOT NULL,
           yayin TEXT, dosya TEXT, olusturma TEXT)"""
    )
    e.execute("INSERT INTO pin (etsy_listing_id, gorsel_url, baslik, pano, durum) VALUES ('7', 'u', 'b', 'p', 'verildi')")
    e.commit()
    e.close()
    c = db.baglan(yol)
    assert [tuple(r) for r in c.execute("SELECT etsy_listing_id, gorsel_sira, durum FROM pin")] == [("7", 0, "verildi")]
    c.execute(
        "INSERT INTO pin (etsy_listing_id, gorsel_sira, gorsel_url, baslik, pano, durum) VALUES ('7', 1, 'u', 'b', 'p', 'x')"
    )
