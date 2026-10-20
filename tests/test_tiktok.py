"""TikTok videoları (K-34): kare düzeni, metin süzgeci, video dosyası, paylaşım takvimi, pano uçları. Sahte Etsy, Claude yok."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from matbaa import db, tiktok
from matbaa.ip import marka

SIMDI = datetime(2026, 10, 20, 15, 0, tzinfo=UTC)  # ABD doğu 11:00 (EDT)


def _mockup(renk) -> Image.Image:
    img = Image.new("RGB", (2000, 2000), "#ffffff")
    img.paste(Image.new("RGB", (900, 1100), renk), (550, 450))  # stüdyo zemininde ürün
    return img


class SahteEtsy:
    def ilan_gorselleri(self, listing_id):
        return [
            {"listing_image_id": 1, "url_570xN": f"{listing_id}-a", "alt_text": ""},
            {"listing_image_id": 2, "url_570xN": f"{listing_id}-b", "alt_text": None},
            {"listing_image_id": 3, "url_570xN": f"{listing_id}-kart", "alt_text": "Size guide for the tee"},  # kendi kartımız
        ]


def _yazar(istem, sistem, sema):
    return {
        "hook": "POV: your dad found a new lake",
        "caption": "Find HobbyHeartPrints on Etsy.",
        "hashtags": ["#Fishing Gifts", "dadlife", "!!"],
    }


@pytest.fixture(autouse=True)
def marka_dizini(monkeypatch):
    """Gerçek USPTO dosyası git dışı (CI'de yok): tek tescilli hashtag'li küçük dizin."""
    monkeypatch.setattr(marka, "dizin", lambda: marka.MarkaDizini([("DADLIFE", "88000001")]))


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "t.db")
    monkeypatch.setattr(tiktok, "CIKTI", tmp_path / "tiktok")
    monkeypatch.setattr(tiktok, "FPS", 2)  # test hızı: kare düzeni aynı, kare sayısı az
    c = db.baglan()
    t = Image.new("RGBA", (4500, 5400), (0, 0, 0, 0))
    t.paste(Image.new("RGBA", (4000, 2000), (29, 29, 31, 255)), (250, 150))
    (tmp_path / "u").mkdir()
    t.save(tmp_path / "u" / "koyu.png")
    t.save(tmp_path / "u" / "acik.png")
    monkeypatch.setattr(tiktok, "KOK", tmp_path)
    for n in range(2):
        i = db.ifade_ekle(c, "fishing", [f"GONE FISHING {n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        tid = db.tasarim_ekle(c, i, "yigin", [])
        c.execute(
            "UPDATE tasarim SET dosyalar = ? WHERE id = ?",
            (json.dumps({"koyu_png": "u/koyu.png", "acik_png": "u/acik.png"}), tid),
        )
        for k, u in enumerate(("tisort", "hoodie", "susleme")):
            c.execute(
                "INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id, guncelleme) VALUES (?, ?, 'aktif', ?, ?)",
                (tid, u, str(100 * tid + k), f"2026-10-1{n}T10:00:00+00:00"),
            )
    c.commit()
    return c


def test_urun_kenar_bosluklarindan_kirpilir_yazi_urune_binmez():
    foto = _mockup("#f3dfa2")
    katman, alt = tiktok.etiket_katmani("Gift idea for the angler who never comes home on time", tiktok.GUVENLI[1] + 30, 60)
    kare = np.asarray(tiktok._sigdir(foto, alt + 10))
    urun = np.all(np.abs(kare.astype(int) - (0xF3, 0xDF, 0xA2)) < 6, axis=2)
    ys, xs = np.nonzero(urun)
    assert ys.min() > alt and ys.max() <= tiktok.FOTO_ALT  # yazının altında, TikTok açıklama alanının üstünde
    assert xs.max() - xs.min() > 0.6 * tiktok.G  # boş stüdyo zemini kırpıldı: ürün büyük
    assert tuple(kare[5, 5]) == (255, 255, 255)  # zemin mockup'ın kendi rengi
    a = np.asarray(katman)[..., 3]
    assert not a[:, tiktok.GUVENLI[2] + 1 :].any()  # sağdaki düğme şeridine yazı taşmaz


def test_etiket_kutusu_zemine_gore_renk_degistirir():
    acik, _ = tiktok.etiket_katmani("Also a hoodie", 200, koyu_zemin=False)
    koyu, _ = tiktok.etiket_katmani("Also a hoodie", 200, koyu_zemin=True)
    renk = lambda k: tuple(np.asarray(k)[205, tiktok.G // 2 - 160][:3])  # noqa: E731
    assert renk(acik) != renk(koyu) and tiktok.koyu_mu((20, 20, 30)) and not tiktok.koyu_mu((250, 250, 250))


def test_metin_hashtagleri_temizlenir_claude_dusunce_kalip_metin():
    m = tiktok.metin_yaz(["GONE FISHING"], "fishing", ["T-shirt"], yazar=_yazar)
    assert m.etiketler[0] == "fishinggifts" and "" not in m.etiketler  # "#Fishing Gifts" temizlendi, "!!" düştü
    assert not marka.dizin().kontrol("dadlife").temiz and "dadlife" not in m.etiketler  # tescilli marka hashtag olmaz
    assert m.gonderi().endswith("#" + m.etiketler[-1]) and m.gonderi().startswith("Find HobbyHeartPrints")

    def dusen(*a):
        raise TimeoutError("claude -p")

    y = tiktok.metin_yaz(["GONE FISHING"], "fishing", ["T-shirt"], yazar=dusen)
    assert y.hook and "HobbyHeartPrints" in y.aciklama and len(y.etiketler) >= 3


def test_gunluk_adim_video_uretir_tekrar_uretmez_takvim_ve_pano(c):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    indir = lambda url: _mockup("#1f2a44" if url.endswith("b") else "#f3dfa2")  # noqa: E731
    s = tiktok.hazirla(c, SahteEtsy(), sinir=1, yazdir=lambda *_: None, indir=indir, yazar=_yazar)
    assert s == {"hazir": 1, "hata": 0}
    v = c.execute("SELECT * FROM tiktok_video").fetchone()
    assert v["tasarim_id"] == 1 and v["durum"] == "hazir" and v["tur"] == "urun" and not v["ai"]  # en eski yayın önce
    mp4 = tiktok.CIKTI / "00001" / "video.mp4"
    assert mp4.stat().st_size > 10_000 and mp4.read_bytes()[4:8] == b"ftyp"
    assert tiktok.hazirla(c, SahteEtsy(), sinir=5, yazdir=lambda *_: None, indir=indir, yazar=_yazar)["hazir"] == 1  # yalnız #2
    o = tiktok.ozet(c, SIMDI)
    assert [h["plan"] for h in o["hazir"]] == ["2026-10-20T16:00+00:00", "2026-10-20T23:00+00:00"]  # ABD 12:00 ve 19:00
    assert o["hazir"][1]["plan_tr"] == "2026-10-21T02:00"  # Studio Türkiye saatiyle zamanlar
    t = TestClient(app, base_url="http://127.0.0.1:8766")
    r = t.get("/tiktok/1/video.mp4")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and "attachment" in r.headers["content-disposition"]
    assert t.get("/tiktok/1/../../matbaa.db").status_code == 404 and t.get("/tiktok/9/video.mp4").status_code == 404
    assert t.post("/api/tiktok/1/paylasildi").status_code == 200
    assert t.post("/api/tiktok/1/paylasildi").status_code == 409  # iki kez sayılmaz
    pano = t.get("/api/pano").json()["tiktok"]
    assert pano["paylasilan"] == 1 and [h["tasarim_id"] for h in pano["hazir"]] == [2]


def test_yalniz_cizimli_urunu_olan_tasarim_da_video_alir(c):
    """K-37 çizimli ürünler (`tisort_cizim`, `sweatshirt_cizim`) ayrı ürün anahtarı: 2026-10-20'ye kadar günlük adım onları
    seçmiyordu, 24 çizimli ilan videosuz kaldı."""
    c.execute("DELETE FROM urun")
    for k, u in enumerate(("tisort_cizim", "sweatshirt_cizim")):
        c.execute(
            "INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id, guncelleme) VALUES (1, ?, 'aktif', ?, '2026-10-19')",
            (u, str(500 + k)),
        )
    c.commit()
    indir = lambda url: _mockup("#f3dfa2")  # noqa: E731
    assert tiktok.hazirla(c, SahteEtsy(), sinir=5, yazdir=lambda *_: None, indir=indir, yazar=_yazar) == {"hazir": 1, "hata": 0}
    assert c.execute("SELECT tasarim_id FROM tiktok_video").fetchone()[0] == 1


def test_takvim_gunde_iki_saat_aksam_gecince_ertesi_gun_ve_dolu_saat_atlanir(c):
    gec = datetime(2026, 10, 20, 23, 30, tzinfo=UTC)  # ABD 19:30: bugünkü iki saat de geçti
    assert tiktok.plan(c, 1, gec)[0].isoformat() == "2026-10-21T16:00:00+00:00"
    c.execute(
        "INSERT INTO tiktok_video (tasarim_id, tur, durum, plan) VALUES (1, 'urun', 'paylasildi', '2026-10-20T23:00+00:00')"
    )
    assert [z.isoformat() for z in tiktok.plan(c, 2, SIMDI)] == ["2026-10-20T16:00:00+00:00", "2026-10-21T16:00:00+00:00"]
    kis = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)  # yaz saati bitti (EST): 12:00 = 17:00 UTC
    c.execute("DELETE FROM tiktok_video")
    assert tiktok.plan(c, 1, kis)[0].isoformat() == "2026-11-03T17:00:00+00:00"


def test_yeniden_uretim_metni_korur(c):
    indir = lambda url: _mockup("#f3dfa2")  # noqa: E731
    tiktok.uret(c, SahteEtsy(), 1, indir=indir, yazar=_yazar)
    baska = lambda *a: {"hook": "Yepyeni kanca", "caption": "Başka.", "hashtags": ["x", "y", "z"]}  # noqa: E731
    tiktok.uret(c, SahteEtsy(), 1, indir=indir, yazar=baska)
    assert c.execute("SELECT hook FROM tiktok_video WHERE tasarim_id = 1").fetchone()[0] == "POV: your dad found a new lake"


def test_eski_video_tablosu_tasinir(c):
    c.execute("CREATE TABLE video (tasarim_id INTEGER PRIMARY KEY, durum TEXT, klasor TEXT, hook TEXT, aciklama TEXT, "
              "etiketler TEXT, sure REAL, olusturma TEXT, paylasim TEXT, plan TEXT)")  # fmt: skip
    c.execute("INSERT INTO video (tasarim_id, durum, hook) VALUES (2, 'hazir', 'POV: 1 a.m.')")
    c.commit()
    c2 = db.baglan()
    assert tuple(c2.execute("SELECT tasarim_id, tur, durum, hook FROM tiktok_video").fetchone()) == (
        2,
        "urun",
        "hazir",
        "POV: 1 a.m.",
    )
    assert not c2.execute("SELECT 1 FROM sqlite_master WHERE name = 'video'").fetchone()
    db.baglan().close()  # ikinci bağlantı: taşıma yinelenmez


def test_sirasiz_isaretleme_kart_saatini_korur(c):
    for tid, tur, zaman in [(1, "urun", "a"), (2, "urun", "b"), (1, "giyim", "c")]:
        c.execute(
            "INSERT INTO tiktok_video (tasarim_id, tur, durum, hook, olusturma) VALUES (?, ?, 'hazir', 'h', ?)", (tid, tur, zaman)
        )
    c.commit()
    kart = {h["id"]: h["plan"] for h in tiktok.ozet(c, SIMDI)["hazir"]}
    for vid in (3, 1, 2):  # önce sonuncu işaretlenir
        tiktok.paylasildi(c, vid, SIMDI)
        assert c.execute("SELECT plan FROM tiktok_video WHERE id = ?", (vid,)).fetchone()[0] == kart[vid]
        assert {h["id"]: h["plan"] for h in tiktok.ozet(c, SIMDI)["hazir"]} == {
            k: v for k, v in kart.items() if k in {r[0] for r in c.execute("SELECT id FROM tiktok_video WHERE durum = 'hazir'")}
        }  # kalan kartlar kaymaz
