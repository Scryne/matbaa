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

    return TestClient(app, base_url="http://127.0.0.1:8766")


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


def test_yerel_olmayan_host_ve_baska_kokenden_yazma_reddedilir(istemci):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    assert TestClient(app, base_url="http://kotu.example").get("/api/kuyruk").status_code == 403  # DNS rebinding
    r = istemci.post("/api/geri-al/1", headers={"Origin": "https://kotu.example"})
    assert r.status_code == 403  # siteler arası POST
    assert istemci.post("/api/karar/1", json={"karar": "onay"}, headers={"Origin": "http://127.0.0.1:8766"}).status_code == 200


def test_eksik_baski_dosyasi_404(istemci):
    assert istemci.get("/tam/1/koyu").status_code == 404
    assert istemci.get("/onizleme/1/acik").status_code == 404


def test_ilan_duzeltilir_kurala_ve_markaya_uymayan_kaydedilmez(istemci, monkeypatch):
    from matbaa.ilan.metin import AI_BEYANI, URETIM_ORTAGI
    from matbaa.ip import marka

    monkeypatch.setattr(marka, "dizin", lambda: marka.MarkaDizini([("REEL COOL DAD", "1")]))
    c = db.baglan()
    c.execute("UPDATE ilan SET aciklama = ? WHERE tasarim_id = 1", (f"x\n\n{URETIM_ORTAGI}\n\n{AI_BEYANI}",))
    c.commit()
    etiketler = [f"fishing gift {i}" for i in range(13)]
    r = istemci.post("/api/ilan/1/tisort", json={"baslik": "Funny Fishing Grandpa Shirt", "etiketler": etiketler})
    assert r.status_code == 200 and r.json()["baslik"] == "Funny Fishing Grandpa Shirt"
    assert db.baglan().execute("SELECT baslik FROM ilan WHERE tasarim_id = 1").fetchone()[0] == "Funny Fishing Grandpa Shirt"
    assert istemci.post("/api/ilan/1/tisort", json={"baslik": "X", "etiketler": etiketler[:5]}).status_code == 422
    r = istemci.post("/api/ilan/1/tisort", json={"baslik": "Fishing Shirt", "etiketler": ["reel cool dad", *etiketler[:12]]})
    assert r.status_code == 422 and "markaya" in r.json()["detail"]
    c.execute("INSERT INTO urun (tasarim_id, urun, durum) VALUES (1, 'tisort', 'olusturuldu')")
    c.commit()
    assert istemci.post("/api/ilan/1/tisort", json={"baslik": "Y", "etiketler": etiketler}).status_code == 409


def test_pano_acilis_sayfasi_ve_verisi(istemci, tmp_path, monkeypatch):
    """Takip panosu `/`, onay masası `/onay`; pano verisi yalnız yerelden okunur (son koşu raporu, roadmap, veritabanı)."""
    from matbaa import hat
    from matbaa.panel import pano

    monkeypatch.setattr(hat, "SON_KOSU", tmp_path / "son.json")
    (tmp_path / "son.json").write_text(
        json.dumps(
            {
                "basladi": "2026-11-20T07:30:00+00:00",
                "sure_sn": 300,
                "hatalar": [],
                "alarmlar": [],
                "yayin": {"urun": 4, "hata": 0},
            }
        )
    )
    monkeypatch.setattr(pano, "_sonraki_kosu", lambda: None)
    c = db.baglan()
    c.execute("UPDATE tasarim SET durum = 'yayinda' WHERE id = 1")
    c.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (1, 'tisort', 'aktif', '42')")
    c.execute("INSERT INTO urun (tasarim_id, urun, durum) VALUES (1, 'hoodie', 'bekliyor')")
    c.execute(
        "INSERT INTO goruntulenme (tarih, etsy_listing_id, views, favori) VALUES ('2026-11-19', '42', 3, 0), ('2026-11-20', '42', 10, 1)"
    )
    c.commit()
    assert "Matbaa · Pano" in istemci.get("/").text and "Onay masası" in istemci.get("/onay").text
    d = istemci.get("/api/pano").json()
    assert d["ozet"]["aktif_ilan"] == 1 and d["ozet"]["views"] == 10 and d["ozet"]["son_gun_artis"] == 7
    assert [x["urun"] for x in d["ilanlar"]] == ["tisort"]  # sırada bekleyen ürün ilan sayılmaz
    assert d["ilanlar"][0]["url"].endswith("/42") and d["son_kosu"]["adimlar"]["yayin"] == {"urun": 4, "hata": 0}
    assert len(d["roadmap"]) >= 10 and d["hat"]["urun"]["bekliyor"] == 1
