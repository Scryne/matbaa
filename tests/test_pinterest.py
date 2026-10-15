"""Pinterest toplu pin CSV'si: kuyruk, sınırlar, takvim (günde 3, 14 gün), indirme. Geçici veritabanı, sahte Etsy."""

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
                "url_570xN": f"https://i.etsystatic.com/{listing_id}/il_570xN.jpg",
                "url_fullxfull": f"https://i.etsystatic.com/{listing_id}/full.jpg",
            }
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
                    "Funny Fishing Shirt " * 10,
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


def test_kuyruk_ilan_basina_bir_pin_ve_sinirlar(c):
    assert pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)["eklenen"] == 6  # bekleyen ürün pinlenmez
    assert pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)["eklenen"] == 0  # ikinci koşu mükerrer açmaz
    p = c.execute("SELECT * FROM pin WHERE urun = 'tisort' ORDER BY id").fetchone()
    assert len(p["baslik"]) <= pinterest.BASLIK_MAKS and p["baslik"].endswith("…")
    assert len(p["aciklama"]) <= pinterest.ACIKLAMA_MAKS and "Care:" not in p["aciklama"]
    assert p["gorsel_url"].endswith("full.jpg") and p["pano"] == "Fishing Gifts" and p["anahtar"].count(",") == 7
    assert c.execute("SELECT pano FROM pin WHERE urun = 'susleme'").fetchone()[0] == "Christmas Ornaments"


def test_csv_takvimi_gunde_uc_tasarimlar_ardisik_degil_ve_ikinci_dosya_devam_eder(c, monkeypatch):
    pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)
    monkeypatch.setattr(pinterest, "GUN", 2)  # takvim 2 gün (yarın, öbür gün) × 2 = 4 yer; 6 pinin 4ü sığar
    monkeypatch.setattr(pinterest, "GUNLUK", 2)
    dosya, veri, n = pinterest.csv_uret(c, SIMDI)
    satirlar = _oku(veri)
    assert list(satirlar[0]) == pinterest.SUTUNLAR and n == len(satirlar) == 4
    assert [s["Publish date"] for s in satirlar] == [
        "2026-10-21T13:00:00",
        "2026-10-21T18:00:00",
        "2026-10-22T13:00:00",
        "2026-10-22T18:00:00",
    ]
    tasarim = {r["etsy_listing_id"]: r["tasarim_id"] for r in c.execute("SELECT etsy_listing_id, tasarim_id FROM pin")}
    sira = [tasarim[s["Link"].rsplit("/", 1)[1]] for s in satirlar]
    assert all(a != b for a, b in zip(sira, sira[1:], strict=False))  # aynı tasarım art arda yok
    assert pinterest.bekleyen(c) == 2 and pinterest.son_csv(c)[1] == veri  # yeniden indirme aynı dosya
    _, veri2, n2 = pinterest.csv_uret(c, SIMDI)
    assert n2 == 0  # takvim dolu: yeni pin eklenmez, ertesi gün eklenir
    _, veri2, n2 = pinterest.csv_uret(c, SIMDI.replace(day=22))
    assert n2 == 2 and _oku(veri2)[0]["Publish date"] == "2026-10-23T13:00:00"  # önceki takvimin ardından


def test_panodan_indirme(c, monkeypatch):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    pinterest.kuyruga_ekle(c, SahteEtsy(), yazdir=lambda *_: None)
    t = TestClient(app, base_url="http://127.0.0.1:8766")
    assert t.get("/pinterest/son").status_code == 404
    r = t.post("/pinterest/indir")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and len(_oku(r.content)) == 6
    assert t.post("/pinterest/indir").status_code == 409  # bekleyen kalmadı
    assert _oku(t.get("/pinterest/son").content) == _oku(r.content)
    assert t.get("/api/pano").json()["pinterest"]["verilen"] == 6
