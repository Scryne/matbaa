"""Onay paneli API'si geçici veritabanıyla: gerçek kuyruğa dokunmaz."""

from __future__ import annotations

import json
import re
from pathlib import Path

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
    assert d["tasarimlar"][0]["ip"] == {"karar": "temiz", "nedenler": []}


def test_dikkat_seridi_geciken_siparis_ve_takilan_urun(istemci, tmp_path, monkeypatch):
    from matbaa import hat, yayin

    monkeypatch.setattr(hat, "SON_KOSU", tmp_path / "son.json")
    (tmp_path / "son.json").write_text(
        json.dumps({"basladi": "2026-11-20T07:30:00+00:00", "hatalar": ["yayin: ApiHatasi: 401"], "alarmlar": ["makbuz 9: eski"]})
    )
    c = db.baglan()
    c.execute("INSERT INTO siparis (etsy_receipt_id, durum, olusturma) VALUES ('77', 'paid', '2000-01-03T00:00:00+00:00')")
    c.execute("UPDATE urun SET durum = 'hata', hata = ? WHERE tasarim_id = 1", (f"Printify panelinde {yayin.ELLE}",))
    c.execute("INSERT INTO urun (tasarim_id, urun, durum, hata) VALUES (2, 'hoodie', 'hata', ?)", (f"x {yayin.ELLE}",))
    c.commit()
    d = istemci.get("/api/kuyruk").json()
    assert d["son_kosu"] == {"zaman": "2026-11-20T07:30:00+00:00", "hata": 1}
    assert d["dikkat"][0] == "son koşu: yayin: ApiHatasi: 401"
    assert any(x.startswith("makbuz 77:") for x in d["dikkat"]) and not any("makbuz 9" in x for x in d["dikkat"])
    assert any(x.startswith("#2 hoodie") for x in d["dikkat"])


def test_sayfanin_okudugu_her_alan_apide_var(istemci):
    """Sayfa `veri.<alan>` okur; API'de olmayan alan sayfayı "yükleniyor…"da dondurur (02c149c'de `kar` böyle kaldı)."""
    import matbaa.panel.app as panel

    alanlar = set(re.findall(r"\bveri\.(\w+)", Path(panel.SAYFA).read_text(encoding="utf-8")))
    d = istemci.get("/api/kuyruk").json()
    assert alanlar and alanlar <= set(d), alanlar - set(d)
    assert {"siparis", "net_usd"} <= set(d["kar"])


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
