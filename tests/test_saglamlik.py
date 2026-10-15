"""Denetim turu (2026-10-14): eşzamanlılık, yeniden deneme, kalıcılık ve panel güvenliği. Her test geçici dizinde koşar."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from test_entegrasyon import VARYANTLAR, SahteEtsy, SahtePrintify, ortam  # noqa: F401  (fixture)

from matbaa import db, fiyat, kilit, radar, yayin
from matbaa.entegrasyon import etsy as etsy_mod
from matbaa.entegrasyon.http import ApiHatasi
from matbaa.ilan import dogrula, gorsel
from matbaa.ilan.metin import AI_BEYANI, URETIM_ORTAGI, Ilan

_ = VARYANTLAR


# --- veritabanı ---


def test_yedek_tutarli_kopya_ve_eskiler_silinir(tmp_path):
    c = db.baglan(tmp_path / "m.db")
    db.ifade_ekle(c, "fishing", ["A"])
    c.commit()
    for g in range(1, 5):
        db.yedekle(c, tmp_path / "yedek", gun=f"2026-10-0{g}", sakla=2)
    kalan = sorted(f.name for f in (tmp_path / "yedek").iterdir())
    assert kalan == ["matbaa-2026-10-03.db", "matbaa-2026-10-04.db"]
    assert sqlite3.connect(tmp_path / "yedek" / kalan[-1]).execute("SELECT count(*) FROM ifade").fetchone()[0] == 1


def test_wal_okuyucu_yazani_beklemez(tmp_path):
    yazan, okuyan = db.baglan(tmp_path / "m.db"), db.baglan(tmp_path / "m.db")
    db.ifade_ekle(yazan, "fishing", ["A"])  # yazma işlemi açık, commit yok
    assert okuyan.execute("SELECT count(*) FROM ifade").fetchone()[0] == 0
    yazan.commit()


def test_ikinci_kosu_kilide_takilir_ilk_bitince_acilir(tmp_path):
    yol = tmp_path / "k.kilit"
    with kilit.tek_kosu(yol):
        with pytest.raises(kilit.Kilitli), kilit.tek_kosu(yol):
            pass
    with kilit.tek_kosu(yol):  # bırakıldı
        pass


def test_gunluk_kilitliyse_atlanir(tmp_path):
    from matbaa import hat

    yol = tmp_path / "k.kilit"
    with kilit.tek_kosu(yol):
        r = hat.gunluk(kilit=yol, yazdir=lambda *_: None)
    assert "atlandi" in r


# --- Etsy istemcisi ---


def _etsy(tmp_path, isle):
    return etsy_mod.Etsy(
        "ks", "sec", "777", http=httpx.Client(transport=httpx.MockTransport(isle)), token_dosyasi=tmp_path / "t.json"
    )


def test_erisim_tokeni_istemciler_arasinda_paylasilir(tmp_path, monkeypatch):
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "eski")
    yenileme = []

    def isle(r):
        if r.url.path.endswith("/oauth/token"):
            yenileme.append(1)
            return httpx.Response(200, json={"access_token": "1.a", "refresh_token": "yeni", "expires_in": 3600})
        return httpx.Response(200, json={"results": []})

    _etsy(tmp_path, isle).uretim_ortaklari()
    _etsy(tmp_path, isle).uretim_ortaklari()  # günlük koşu Etsy()'yi birkaç kez kurar
    assert len(yenileme) == 1
    assert not (tmp_path / "t.json.tmp").exists() and json.loads((tmp_path / "t.json").read_text())["refresh_token"] == "yeni"


def test_reddedilen_yenileme_tokeni_yol_gosterir(tmp_path, monkeypatch):
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "bayat")
    e = _etsy(tmp_path, lambda r: httpx.Response(400, json={"error": "invalid_grant"}))
    with pytest.raises(RuntimeError, match="etsy_yetki"):
        e.uretim_ortaklari()


def test_makbuzlar_sayfalanir(tmp_path, monkeypatch):
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "x")

    def isle(r):
        if r.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "1.a", "refresh_token": "y"})
        ofset = int(r.url.params["offset"])
        return httpx.Response(
            200, json={"count": 250, "results": [{"receipt_id": i} for i in range(ofset, min(ofset + 100, 250))]}
        )

    assert len(_etsy(tmp_path, isle).makbuzlar()) == 250


# --- yayın ---


def test_yayin_fiyati_guncel_katalogdan(ortam):  # noqa: F811
    p = SahtePrintify()
    govdeler = []
    asil = p.urun_olustur
    p.urun_olustur = lambda g: govdeler.append(g) or asil(g)
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    beklenen = round(fiyat.urunler()["tisort"]["fiyat"] * 100)
    assert min(v["price"] for v in govdeler[0]["variants"]) == beklenen  # ilan satırındaki eski 28.99 değil
    assert ortam.execute("SELECT fiyat FROM ilan WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()[0] == beklenen / 100


class BozukEtsy(SahteEtsy):
    def ilan_guncelle(self, listing_id, **alanlar):
        raise ApiHatasi(400, "listing is invalid", "PATCH")


def test_kalici_etsy_hatasi_ucuncu_denemede_elle_bakilir(ortam):  # noqa: F811
    yayin.yayinla(ortam, SahtePrintify(), yazdir=lambda *_: None)
    for _ in range(yayin.ETSY_DENEME_MAKS):
        yayin.etsy_esle(ortam, SahtePrintify(), BozukEtsy(), yazdir=lambda *_: None)
    hata = ortam.execute("SELECT hata FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()[0]
    assert yayin.ELLE in hata
    s = yayin.etsy_esle(ortam, SahtePrintify(), BozukEtsy(), yazdir=lambda *_: None)
    assert s["hata"] == 0  # artık her gün yinelenmez; alarm günlük koşuda


def test_elle_denetim_bir_urun_okunamazsa_digerleri_surer(ortam, monkeypatch):  # noqa: F811
    yayin.yayinla(ortam, SahtePrintify(), yazdir=lambda *_: None)

    class YarimPrintify(SahtePrintify):
        def urun(self, urun_id):
            if urun_id == "p1":
                raise httpx.ConnectError("ağ")
            return super().urun(urun_id)

    s = yayin.elle_denetle(ortam, YarimPrintify(), yazdir=lambda *_: None)
    assert s["hata"] == 1 and s["etsy"] == 2


def test_yayindan_sonra_ilan_dusene_kadar_eslenir(ortam):  # noqa: F811
    from matbaa import hat

    yayin.yayinla(ortam, SahtePrintify(), yazdir=lambda *_: None)

    class GecPrintify(SahtePrintify):
        def __init__(self):
            super().__init__()
            self.sorgu = 0

        def urun(self, urun_id):
            self.sorgu += 1
            return super().urun(urun_id) if self.sorgu > 3 else {"external": []}  # ilk turda Etsy ilanı yok

    beklenen = []
    s = hat._esle_bekle(ortam, GecPrintify(), SahteEtsy(), lambda *_: None, bekle=beklenen.append, saat=lambda: 0)
    assert s["tur"] == 2 and s["aktif"] == 3 and s["bekleyen"] == 0 and beklenen == [hat.ESLEME_ARALIK_SN]


# --- ilan metni ---


def _ilan(baslik: str) -> Ilan:
    return Ilan(baslik, [f"fishing tag {i}" for i in range(13)], f"x\n\n{URETIM_ORTAGI}\n\n{AI_BEYANI}", "alt")


def test_baslikta_ozel_karakter_bir_kez():
    s = dogrula.dogrula(_ilan("Fishing & Hunting & Camping Dad Shirt: Gift: Tee"))
    assert s.baslik.count("&") == 1 and s.baslik.count(":") == 1 and "and Camping" in s.baslik and not s.sorunlar


def test_metin_llm_hatasi_kuyrugu_durdurmaz(tmp_path, monkeypatch):
    from matbaa import hat

    monkeypatch.setattr(db, "DB", tmp_path / "m.db")
    c = db.baglan()
    for n in range(2):
        i = db.ifade_ekle(c, "fishing", [f"S{n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        db.gecis(c, db.tasarim_ekle(c, i, "yigin", []), "kalite_ok")
    c.commit()

    def yaz(satirlar, nis, urun):
        if satirlar == ["S0"]:
            raise TimeoutError("claude 240 sn'de bitmedi")
        return _ilan("Funny Fishing Shirt")

    monkeypatch.setattr(hat, "_ilan_yaz", yaz)
    s = hat.metin(c, yazdir=lambda *_: None)
    assert s["tasarim"] == 1  # ikinci tasarım yine onaya gitti
    assert c.execute("SELECT durum FROM tasarim WHERE id = 1").fetchone()[0] == "kalite_ok"  # ilk tasarım yarın yeniden denenir


# --- ilan görselleri ---


def test_yarim_kalan_gorsel_yuklemesi_tekrarlanmaz(tmp_path):
    from test_gorsel import SahteEtsy as GorselEtsy
    from test_gorsel import _dosyalar, _mockup

    e = GorselEtsy(["#ffffff", "#f3dfa2"])
    plan = gorsel.ilan_gorselleri("tisort", _dosyalar(tmp_path))
    # önceki koşu yakın planı ve beden tablosunu yükleyip düştü
    for k, (_ad, _, alt) in enumerate(plan[:2]):
        e.gorseller.append({"listing_image_id": 500 + k, "rank": 3 + k, "url_570xN": "#ffffff", "alt_text": alt})
    s = gorsel.ilana_ekle(e, 1, "tisort", _dosyalar(tmp_path), indir=_mockup)
    assert s["onceden"] == ["beden", "yakin-plan"] and s["eklenen"] == ["renkler", "guven"]
    sira = [gid for gid, _ in e.siralanan]
    assert sira[1] == 500 and len(sira) == len(set(sira)) == 6  # yakın plan ikinci, mükerrer yok


# --- radar, fiyat ---


def test_radar_haftada_bir(tmp_path, monkeypatch):
    monkeypatch.setattr(radar, "CIKTI", tmp_path)
    simdi = datetime(2026, 10, 20, tzinfo=UTC)
    assert not radar.son_tarama_taze(simdi=simdi)
    (tmp_path / f"{(simdi - timedelta(days=6)).date()}.json").write_text("{}")
    assert radar.son_tarama_taze(simdi=simdi)
    assert not radar.son_tarama_taze(simdi=simdi + timedelta(days=1))


def test_iki_adet_iki_yenileme_ucreti():
    tek, cift = fiyat.hesap(60.0, 0.0, 20.0), fiyat.hesap(60.0, 0.0, 20.0, adet=2)
    assert round(tek.etsy_ucret - cift.etsy_ucret, 2) == -fiyat.ucretler()["listeleme_usd"]


def test_panel_baglantisi_baska_is_parcaciginda_kapanir(tmp_path, monkeypatch):
    """FastAPI eşzamanlı bağımlılığı açar ve kapatırken iş parçacığı değişebiliyor (görsel doğrulamada aralıklı 500)."""
    import threading

    from matbaa.panel import app as panel

    monkeypatch.setattr(db, "DB", tmp_path / "p.db")
    gen = panel._c()
    next(gen)
    hata = []

    def kapat():
        try:
            next(gen, None)
        except Exception as e:
            hata.append(e)

    t = threading.Thread(target=kapat)
    t.start()
    t.join()
    assert hata == []


def test_bekleme_turlari_hatali_urunu_yeniden_denemez(ortam):  # noqa: F811
    yayin.yayinla(ortam, SahtePrintify(), yazdir=lambda *_: None)
    yayin.etsy_esle(ortam, SahtePrintify(), BozukEtsy(), yazdir=lambda *_: None)  # 3 ürün hata (1. deneme)
    for _ in range(5):  # aynı koşunun 90 sn'lik turları
        assert yayin.etsy_esle(ortam, SahtePrintify(), BozukEtsy(), yazdir=lambda *_: None, hata_dene=False)["hata"] == 0
    assert all(yayin.ELLE not in h for (h,) in ortam.execute("SELECT hata FROM urun WHERE durum = 'hata'"))


def test_adim_disinda_dusen_gunluk_kosu_son_kosuya_ve_bildirime_yazilir(tmp_path, monkeypatch):
    from matbaa import bildirim, hat

    monkeypatch.setattr(hat, "SON_KOSU", tmp_path / "son.json")
    monkeypatch.setattr(hat, "_gunluk", lambda *a: (_ for _ in ()).throw(RuntimeError("config bozuk")))
    gosterilen = []
    monkeypatch.setattr(bildirim, "goster", lambda baslik, metin, yazdir=print: gosterilen.append(baslik))
    r = hat.gunluk(kilit=tmp_path / "k.kilit", yazdir=lambda *_: None)
    assert "config bozuk" in r["hatalar"][0] and gosterilen
    assert json.loads((tmp_path / "son.json").read_text(encoding="utf-8"))["hatalar"] == r["hatalar"]
