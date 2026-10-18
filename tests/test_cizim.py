"""Çizimli hat (K-37): dekupe, aday elemesi, kompozisyon, ürün kümesi, ilan istemi ve uçtan uca `uret` (sahte ComfyUI)."""

from __future__ import annotations

import io
import json
from datetime import date

import pytest
from PIL import Image, ImageDraw

from matbaa import cizim, db, fiyat
from matbaa.ilan import metin as ilan_metin
from matbaa.ip import kapi

KAVRAM = {
    "ad": "deneme",
    "konu": "A round snowman",
    "ust": "COLD OUTSIDE",
    "alt": "ICED COFFEE INSIDE",
    "dolgu": "#c4772f",
    "font_ust": "LilitaOne-Regular.ttf",
    "font_alt": "TitanOne-Regular.ttf",
}


def _cizim(kenara_degsin: bool = False) -> Image.Image:
    """Beyaz zeminde kalın kahverengi çizgili beyaz gövde (kardan adam gibi) ve turuncu burun."""
    im = Image.new("RGB", (768, 768), "white")
    d = ImageDraw.Draw(im)
    kutu = (-40, 200, 500, 740) if kenara_degsin else (234, 200, 534, 620)
    d.ellipse(kutu, fill="white", outline="#4a2c1d", width=14)
    d.polygon([(384, 380), (450, 400), (384, 420)], fill="#e8823a", outline="#4a2c1d")
    return im


def test_dekupe_dis_zemini_siler_ic_beyazi_korur():
    k = cizim.dekupe(_cizim())
    assert k.mode == "RGBA" and 280 <= k.width <= 320  # çizim kutusuna kırpıldı
    a = k.getchannel("A")
    assert a.getpixel((k.width // 2, k.height // 2)) == 255  # gövdenin içindeki beyaz kaldı
    assert a.getpixel((2, 2)) == 0  # köşedeki zemin gitti


def test_aday_sorunlari_kirpik_ve_temiz():
    temiz = _cizim()
    assert cizim.aday_sorunlari(temiz, cizim.dekupe(temiz)) == []
    kirpik = _cizim(kenara_degsin=True)
    assert any("kenara" in s for s in cizim.aday_sorunlari(kirpik, cizim.dekupe(kirpik)))
    yazili = _cizim()
    ImageDraw.Draw(yazili).text((60, 60), "MERY BRIGCUT", fill="black", font_size=72)
    assert any("yazı" in s for s in cizim.aday_sorunlari(yazili, cizim.dekupe(yazili)))


def test_birlestir_baski_kapisindan_gecer():
    img = cizim.birlestir(cizim.dekupe(_cizim()), KAVRAM)
    assert img.size == (4500, 5400) and img.mode == "RGBA"
    assert cizim.baski_sorunlari(img, KAVRAM) == []
    assert cizim.koyu_renk(cizim.dekupe(_cizim())).startswith("#4")  # yazının kontürü çizimin çizgi rengi


def test_urun_kumesi_cizimli_nise_yalniz_cizim_urunleri():
    assert fiyat.tasarim_urunleri("cozy_christmas", ["MERRY", "WOOFMAS"], gun=date(2026, 11, 1)) == [
        "tisort_cizim",
        "sweatshirt_cizim",
    ]
    eski = fiyat.tasarim_urunleri("fishing", ["CHRISTMAS CREW"], gun=date(2026, 11, 1))
    assert "tisort_cizim" not in eski and "tisort" in eski and "susleme" in eski
    assert all(u["murekkep"] == "koyu" for k in ("tisort_cizim", "sweatshirt_cizim") for u in fiyat.urunler()[k]["renkler"])


def test_ilan_istemi_cizimi_anlatir_beyan_cizime_gore():
    i = ilan_metin.istem(["MERRY LITTLE", "TRASH PANDA"], "cozy_christmas", "sweatshirt_cizim", "A raccoon in a Santa hat")
    assert "A raccoon in a Santa hat" in i and "Cute Christmas Raccoon Sweatshirt" in i
    assert "Illustration" not in ilan_metin.istem(["ONE MORE ROW"], "knitting", "tisort")


class SahteComfy:
    def __init__(self, gorseller):
        self.gorseller, self.akislar = gorseller, []

    def calistir(self, akis, sure=0):
        self.akislar.append(akis)
        return [{"filename": str(len(self.akislar) - 1)}]

    def indir(self, f):
        b = io.BytesIO()
        self.gorseller[int(f["filename"])].save(b, "PNG")
        return b.getvalue()


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "c.db")
    monkeypatch.setattr(cizim, "CIKTI", tmp_path / "cizim")
    monkeypatch.setattr(cizim, "URETIM", tmp_path / "uretim")
    monkeypatch.setattr(cizim, "KOK", tmp_path)
    monkeypatch.setattr(kapi, "denetle", lambda satirlar, nis, ana=None: kapi.Karar("temiz"))
    return db.baglan()


def test_uret_eleyip_tasarim_acar_ve_aday_secilir(c):
    comfy = SahteComfy([_cizim(kenara_degsin=True), _cizim(), _cizim()])
    r = cizim.uret(c, KAVRAM, comfy, adet=3, tohum=7, yazdir=lambda *_: None)
    assert r["sonuc"] == "tasarim" and r["gecen"] == [1, 2]
    assert [a["7"]["inputs"]["noise_seed"] for a in comfy.akislar] == [7, 8, 9]  # aday başına bir iş, ardışık tohum
    t = c.execute("SELECT * FROM tasarim WHERE id = ?", (r["tasarim"],)).fetchone()
    d = json.loads(t["dosyalar"])
    assert t["durum"] == "kalite_ok" and t["sablon"] == "cizim" and d["koyu_png"] == d["acik_png"]
    i = c.execute("SELECT nis, yapi, kaynak FROM ifade WHERE id = ?", (t["ifade_id"],)).fetchone()
    assert i["nis"] == "cozy_christmas" and json.loads(i["yapi"])["cizim"] == "A round snowman"
    assert json.loads(t["kalite"])["elenen"]["0"]  # kırpık aday nedeniyle kayıtta
    # ikinci koşu aynı kavramı yeniden üretmez
    assert cizim.uret(c, KAVRAM, comfy, adet=3, yazdir=lambda *_: None)["sonuc"] == "zaten_var"
    cizim.sec(c, r["tasarim"], 2)
    assert json.loads(c.execute("SELECT kalite FROM tasarim WHERE id = ?", (r["tasarim"],)).fetchone()[0])["aday"] == 2
    with pytest.raises(ValueError):
        cizim.sec(c, r["tasarim"], 0)  # elenen aday seçilemez


def test_ip_reddi_tasarim_acmaz(c, monkeypatch):
    monkeypatch.setattr(kapi, "denetle", lambda satirlar, nis, ana=None: kapi.Karar("ret", ["USPTO: tescilli"]))
    comfy = SahteComfy([_cizim()])
    assert cizim.uret(c, KAVRAM, comfy, adet=1, yazdir=lambda *_: None)["sonuc"] == "ip_ret"
    assert comfy.akislar == [] and c.execute("SELECT count(*) FROM tasarim").fetchone()[0] == 0


def test_cizimli_ilan_aciklamasi_dogrulayicidan_gecer(monkeypatch):
    from matbaa import llm

    ham = {
        "title": "Cute Christmas Raccoon Sweatshirt, Hot Cocoa Bandit Holiday Crewneck, Christmas Gift for Her",
        "tags": [
            "raccoon sweatshirt",
            "christmas raccoon",
            "hot cocoa shirt",
            "cute xmas sweater",
            "holiday crewneck",
            "christmas gift her",
            "raccoon lover gift",
            "winter sweatshirt",
            "cozy christmas",
            "funny xmas shirt",
            "animal christmas",
            "cocoa lover gift",
            "xmas crewneck",
            "trash panda gift",
            "holiday sweater",
            "cute raccoon",
        ],
        "intro": "A chubby raccoon in a Santa hat guards its hot cocoa. A cozy gift for anyone who loves cute holiday sweaters.",
        "alt_text": "Sand sweatshirt with a cartoon raccoon in a Santa hat holding hot cocoa and the words HOT COCOA BANDIT",
    }
    monkeypatch.setattr(llm, "yapilandirilmis", lambda *a, **k: ham)
    i = ilan_metin.olustur(["HOT COCOA", "BANDIT"], "cozy_christmas", "sweatshirt_cizim", "A raccoon in a Santa hat")
    assert not [s for s in i.sorunlar if "AI" in s] and ilan_metin.AI_BEYANI_CIZIM in i.aciklama
    assert "Illustration: A raccoon in a Santa hat." in i.aciklama


def test_baski_dosyasi_printify_sinirinin_altinda_ve_kirpmada_paletli_kalir(tmp_path):
    """Baskı dokulu (grenli) çizim: tam renkli ~10 MB, paletli ~1 MB; Printify'a giden kırpılmış dosya da paletli kalmalı."""
    import numpy as np

    from matbaa.entegrasyon.printify import BASE64_MAKS, kirp

    k = cizim.dekupe(_cizim()).resize((1500, 2100))
    a = np.asarray(k).astype(int)
    a[..., :3] = np.clip(a[..., :3] + np.random.default_rng(0).normal(0, 10, a[..., :3].shape), 0, 255)
    img = cizim.birlestir(Image.fromarray(a.astype(np.uint8), "RGBA"), KAVRAM)
    tam = io.BytesIO()
    img.save(tam, "PNG")
    assert len(tam.getvalue()) * 4 / 3 > BASE64_MAKS  # paletsiz hali sınırı aşar (sınamanın anlamı)
    veri, _, tuval = kirp(cizim.baski_kaydet(img, tmp_path / "cizim.png"))
    assert Image.open(io.BytesIO(veri)).mode == "P" and len(veri) * 4 / 3 < BASE64_MAKS and tuval == (4500, 5400)
