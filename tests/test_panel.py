"""Onay paneli API'si geçici veritabanıyla: gerçek kuyruğa dokunmaz."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from matbaa import db


@pytest.fixture
def istemci(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "panel.db")
    c = db.baglan()
    for n in range(2):
        i = db.ifade_ekle(c, "fishing", [f"SLOGAN {n}"])
        db.kapi_yaz(c, i, "temiz", [], [{"ifade": f"SLOGAN {n}", "adaylar": ["SLOGAN"], "benzerler": []}])
        t = db.tasarim_ekle(c, i, "yigin", ["Anton-Regular.ttf"])
        for d in ("kalite_ok", "metin_ok", "onay_bekliyor"):
            db.gecis(c, t, d)
        c.execute(
            "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (?, 'tisort', 'Başlık', ?, 'açıklama', 28.99, 4.99)",
            (t, json.dumps(["a b"] * 13)),
        )
    c.commit()
    from matbaa.panel.app import app

    return TestClient(app)


def test_kuyruk(istemci):
    d = istemci.get("/api/kuyruk").json()
    assert [t["id"] for t in d["tasarimlar"]] == [1, 2]
    assert d["tasarimlar"][0]["ilanlar"]["tisort"]["net"] > 0
    assert d["tasarimlar"][0]["kanit"]["aday_markalar"] == ["SLOGAN"]


def test_onay_ret_ve_cifte_karar(istemci):
    assert istemci.post("/api/karar/1", json={"karar": "onay"}).json()["durum"] == "onaylandi"
    assert istemci.post("/api/karar/1", json={"karar": "ret"}).status_code == 409  # karar bir kez
    assert istemci.post("/api/karar/2", json={"karar": "ret", "neden": "espri zayıf"}).json()["durum"] == "ret"
    assert istemci.get("/api/kuyruk").json()["tasarimlar"] == []
    neden = db.baglan().execute("SELECT ret_nedeni FROM tasarim WHERE id = 2").fetchone()[0]
    assert neden == "Scryne: espri zayıf"


def test_gecersiz_karar(istemci):
    assert istemci.post("/api/karar/1", json={"karar": "belki"}).status_code == 422


def test_onay_geri_alinir_ret_alinmaz(istemci):
    istemci.post("/api/karar/1", json={"karar": "onay"})
    assert istemci.post("/api/geri-al/1").json()["durum"] == "onay_bekliyor"
    istemci.post("/api/karar/2", json={"karar": "ret"})
    assert istemci.post("/api/geri-al/2").status_code == 409
