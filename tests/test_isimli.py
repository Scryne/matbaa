"""Faz 11 isimli süs: makbuz → Printify API siparişi → üretim → takip; ilan doğrudan Etsy'de. Sahte istemciler, geçici veritabanı."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest
from PIL import Image

from matbaa import db, isimli, yayin

SIMDI = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
VARYANTLAR = [
    {
        "id": 112959,
        "options": {"shape": "Round", "size": "One size"},
        "placeholders": [{"position": "front", "width": 900, "height": 900}],
    },
    {
        "id": 244846,
        "options": {"shape": "Round + White Gift Packaging", "size": "One size"},
        "placeholders": [{"position": "front", "width": 900, "height": 900}],
    },
]


def _jpeg(renk: str) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (570, 570), renk).save(b, "JPEG")
    return b.getvalue()


class SahtePrintify:
    def __init__(self, var_olan=None):
        self.urunler, self.siparisler, self.silinen, self.uretim, self.iptal = [], {}, [], [], []
        self.var_olan = var_olan or []

    def varyantlar(self, bp, sg):
        return VARYANTLAR

    def gorsel_yukle(self, png, ad):
        assert png.exists()
        return f"img-{ad}", (0, 0, 1800, 1800), (1800, 1800)

    def urun_olustur(self, govde):
        self.urunler.append(govde)
        kameralar = [
            ("1_front", "#ffffff"),
            ("1_back", "#eeeeee"),
            ("1_context", "#203040"),
            ("2_front", "#ffffff"),
            ("2_giftbox", "#ffffff"),
        ]
        return {"id": f"u{len(self.urunler)}", "images": [{"src": r, "mockup_id": f"x_{k}"} for k, r in kameralar]}

    def urun_sil(self, urun_id):
        self.silinen.append(urun_id)

    def son_siparisler(self, sayfa_maks=10):
        return self.var_olan + [
            {"id": k, "status": v["status"], "metadata": {"shop_order_id": v["external_id"]}} for k, v in self.siparisler.items()
        ]

    def siparis_ac(self, govde):
        oid = f"o{len(self.siparisler) + 1}"
        self.siparisler[oid] = govde | {"status": "on-hold", "shipments": []}
        return {"id": oid}

    def siparis(self, oid):
        return self.siparisler[oid]

    def uretime_gonder(self, oid):
        self.uretim.append(oid)
        self.siparisler[oid]["status"] = "in-production"

    def siparis_iptal(self, oid):
        self.iptal.append(oid)
        self.siparisler[oid]["status"] = "canceled"


class SahteEtsy:
    def __init__(self, makbuzlar=None):
        self.makbuz_listesi = makbuzlar or []
        self.takipler, self.taslaklar, self.envanter, self.sorular = [], [], [], []
        self.gorseller, self.siralanan = [], []

    def makbuzlar(self, min_son_degisim=None):
        return self.makbuz_listesi

    def takip_yaz(self, receipt_id, takip, tasiyici):
        self.takipler.append((receipt_id, takip, tasiyici))

    # ilan
    def taslak_ilan(self, **alanlar):
        self.taslaklar.append(alanlar)
        return {"listing_id": 777}

    def envanter_yaz(self, listing_id, govde):
        self.envanter.append(govde)

    def kisisellestirme_yaz(self, listing_id, sorular):
        self.sorular.append(sorular)

    def ilan_gorselleri(self, listing_id):
        return list(self.gorseller)

    def gorsel_yukle(self, listing_id, b, rank, ad="", alt=""):
        gid = 500 + len(self.gorseller)
        renk = ad
        if ad.startswith("mockup"):  # yüklenen mockup'ın rengi: ilana_ekle kopya denetimi gerçek görsel görsün
            renk = "#{:02x}{:02x}{:02x}".format(*Image.open(io.BytesIO(b)).convert("RGB").getpixel((5, 5)))
        self.gorseller.append({"listing_image_id": gid, "rank": rank, "url_570xN": renk, "alt_text": alt, "ad": ad})
        return {"listing_image_id": gid}

    def gorsel_sirala(self, listing_id, gid, rank, alt=""):
        self.siralanan.append((gid, rank))

    def gorsel_sil(self, listing_id, gid):
        self.gorseller = [g for g in self.gorseller if g["listing_image_id"] != gid]


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "i.db")
    monkeypatch.setattr(isimli, "KOK", tmp_path)
    monkeypatch.setattr(isimli, "CIKTI", tmp_path / "isimli")
    cfg = {
        "isinma": [[0, 100000, 5]],
        "printify": {u: {"blueprint_id": 1632, "saglayici_id": 39} for u in ("tisort", "sweatshirt", "hoodie", "isimli_susleme")},
        "etsy": {"uretim_ortagi_id": 55, "kargo_profili_id": 66, "hazirlama_profili_id": 35, "iade_politikasi_id": 77},
    }
    monkeypatch.setattr(yayin, "ayar", lambda: cfg)
    (tmp_path / "uretim").mkdir()
    t = Image.new("RGBA", (4500, 5400), (0, 0, 0, 0))
    t.paste(Image.new("RGBA", (4000, 2000), (29, 29, 31, 255)), (250, 150))
    t.save(tmp_path / "uretim" / "koyu.png")
    c = db.baglan()
    i = db.ifade_ekle(c, "fishing", ["GONE FISHING"])
    db.kapi_yaz(c, i, "temiz", [], [])
    tid = db.tasarim_ekle(c, i, "yigin", [])
    c.execute("UPDATE tasarim SET dosyalar = ? WHERE id = ?", (json.dumps({"koyu_png": "uretim/koyu.png"}), tid))
    c.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (?, 'isimli_susleme', 'aktif', '4600')", (tid,))
    c.commit()
    return c


def _makbuz(mid=91, isim="grandpa joe", durum="paid", sku="MATBAA-ISIM-1-244846", adet=1):
    return {
        "receipt_id": mid,
        "status": durum,
        "name": "Jane Q Doe",
        "first_line": "1 Elm St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "country_iso": "US",
        "create_timestamp": int(SIMDI.timestamp()),
        "transactions": [
            {
                "transaction_id": 5,
                "listing_id": 4600,
                "quantity": adet,
                "sku": sku,
                "variations": [
                    {"property_id": 513, "formatted_name": "Ornament shapes", "formatted_value": "Round + White Gift Packaging"},
                    {"property_id": 54, "formatted_name": "Name", "formatted_value": isim},
                ],
            },
            {"transaction_id": 6, "listing_id": 1234, "quantity": 1, "sku": "29091835815138805137", "variations": []},
        ],
    }


def test_kalem_ve_adres_ayristirma():
    ks = isimli.kalemler(_makbuz(), {"4600": 1})
    assert ks == [
        {"transaction_id": "5", "tasarim_id": 1, "isim": "grandpa joe", "varyant_id": 244846, "adet": 1}
    ]  # Printify kalemi atlanır
    a = isimli.adres(_makbuz())
    assert (a["first_name"], a["last_name"], a["country"], a["region"]) == ("Jane Q", "Doe", "US", "TX")
    assert isimli.adres({"name": "Cher"})["first_name"] == "Cher"


def test_siparis_acilir_uretime_gider_takip_yazilir_ve_tekrarlanmaz(c):
    e, p = SahteEtsy([_makbuz()]), SahtePrintify()
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["yeni"] == 1 and s["uretimde"] == 1 and not s["alarm"]
    o = p.siparisler["o1"]
    assert o["external_id"] == "91" and o["line_items"] == [{"product_id": "u1", "variant_id": 244846, "quantity": 1}]
    assert p.urunler[0]["title"] == "Order 91 - Grandpa Joe"  # isim temizlenip baskıya girdi
    assert (isimli.CIKTI / "91-5.png").exists() and p.uretim == ["o1"]
    # ikinci koşu: aynı makbuz için yeni sipariş yok; kargo gelince takip Etsy'ye
    o["shipments"] = [{"carrier": "USPS", "number": "9400111"}]
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["yeni"] == 0 and s["takip"] == 1 and len(p.siparisler) == 1
    assert e.takipler == [(91, "9400111", "usps")]
    r = c.execute("SELECT durum, takip FROM isimli_siparis").fetchone()
    assert tuple(r) == ("takip_yazildi", "9400111")


def test_printifyda_ayni_makbuz_varsa_ikinci_siparis_acilmaz(c):
    p = SahtePrintify()
    p.siparisler["eski"] = {"status": "on-hold", "shipments": [], "external_id": "91"}
    s = isimli.siparisleri_isle(c, SahteEtsy([_makbuz()]), p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["yeni"] == 1 and not p.urunler and p.uretim == ["eski"]  # kimliği kaydedemeden düşen koşunun siparişi kullanıldı


def test_isimsiz_ya_da_basilamaz_isim_alarm_verir_siparis_acmaz(c):
    p = SahtePrintify()
    s = isimli.siparisleri_isle(c, SahteEtsy([_makbuz(isim="李")]), p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["hata"] == 1 and "91" in s["alarm"][0] and not p.siparisler
    s = isimli.siparisleri_isle(c, SahteEtsy([_makbuz(isim="")]), p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["hata"] == 1 and not p.siparisler  # hata satırı her koşu yeniden denenir, alarm sürer


def test_iptal_edilen_makbuzun_printify_siparisi_iptal_edilir(c):
    p = SahtePrintify()
    p.siparisler["o1"] = {"status": "on-hold", "shipments": [], "external_id": "91"}
    c.execute("INSERT INTO isimli_siparis (etsy_receipt_id, durum, printify_order_id) VALUES ('91', 'acildi', 'o1')")
    c.commit()
    s = isimli.siparisleri_isle(c, SahteEtsy([_makbuz(durum="canceled")]), p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert p.iptal == ["o1"] and s["iptal"] == 1 and not p.uretim


def test_ilan_dogrudan_etsyde_acilir_ve_etsy_eslemeye_birakilir(c):
    c.execute("UPDATE urun SET durum = 'bekliyor', etsy_listing_id = NULL")
    c.execute(
        "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (1, 'isimli_susleme', 'Personalized', '[\"a\"]', 'A', 24.99, 0)"
    )
    c.commit()
    e, p = SahteEtsy(), SahtePrintify()
    t = c.execute("SELECT t.id, t.dosyalar FROM tasarim t").fetchone()
    il = c.execute("SELECT * FROM ilan").fetchone()
    lid = isimli.ilan_ac(
        c, e, p, t, il, yazdir=lambda *_: None, indir=_jpeg, gorsel_indir=lambda u: Image.new("RGB", (570, 570), u)
    )
    assert lid == "777" and e.taslaklar[0]["production_partner_ids"] == [55] and e.taslaklar[0]["taxonomy_id"] == 1857
    g = e.envanter[0]
    assert [x["sku"] for x in g["products"]] == ["MATBAA-ISIM-1-112959", "MATBAA-ISIM-1-244846"]
    assert [x["offerings"][0]["price"] for x in g["products"]] == [24.99, 27.99]
    assert e.sorular[0][0]["max_allowed_characters"] == 14 and e.sorular[0][0]["required"] is True
    assert p.silinen == ["u1"]  # geçici mockup ürünü silindi
    adlar = [g["ad"] for g in e.gorseller]
    assert adlar[:2] == ["mockup-1.jpg", "mockup-2.jpg"] and "isim.jpg" in adlar  # kopya mockup yüklenmedi, kart eklendi
    r = c.execute("SELECT durum, etsy_listing_id FROM urun").fetchone()
    assert tuple(r) == ("etsy_taslak", "777")
    assert c.execute("SELECT count(*) FROM olay WHERE yeni = 'isimli_susleme:printify'").fetchone()[0] == 1  # ilan ücreti sayılır


def test_yayinla_isimliyi_printifya_degil_etsye_acar(c, monkeypatch):
    for d in ("kalite_ok", "metin_ok", "onay_bekliyor", "onaylandi"):
        db.gecis(c, 1, d)
    c.execute("UPDATE urun SET durum = 'bekliyor', etsy_listing_id = NULL")
    c.execute(
        "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (1, 'isimli_susleme', 'B', '[]', 'A', 24.99, 0)"
    )
    c.commit()
    monkeypatch.setattr(yayin, "mevsimde", lambda u, gun=None: True)
    acilan = []
    monkeypatch.setattr(isimli, "ilan_ac", lambda c_, e, p, t, il, yazdir: acilan.append((t["id"], il["urun"])))
    p = SahtePrintify()
    s = yayin.yayinla(c, p, yazdir=lambda *_: None)  # Etsy istemcisi yok: isimli bekler
    assert not acilan and s["urun"] == 0
    s = yayin.yayinla(c, p, yazdir=lambda *_: None, etsy=SahteEtsy())
    assert acilan == [(1, "isimli_susleme")] and s["urun"] == 1 and not p.urunler  # Printify ürünü açılmadı


def test_cevap_kalibi_ve_tirnak_basilmaz():
    from matbaa.tasarim import susleme

    assert susleme.isim_temizle("Name: emma") == "Emma"
    assert susleme.isim_temizle('  "Grandpa Joe" ') == "Grandpa Joe"
    assert susleme.isim_temizle("O'Neil") == "O'Neil"  # isim içindeki kesme işareti kalır


def test_basilamayan_isim_panelden_duzeltilir_sonra_acilir(c):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    p, e = SahtePrintify(), SahteEtsy([_makbuz(isim="李")])
    isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    t = TestClient(app, base_url="http://127.0.0.1:8766")
    assert t.post("/api/isimli/91/isim", json={"isimler": {"5": "李"}}).status_code == 422  # yine basılamaz: kaydedilmez
    assert t.post("/api/isimli/404/isim", json={"isimler": {"5": "Li"}}).status_code == 404
    r = t.post("/api/isimli/91/isim", json={"isimler": {"5": "li wei"}})
    assert r.status_code == 200 and r.json()["isimler"] == {"5": "Li Wei"}
    kalem = t.get("/api/pano").json()["siparisler"]["isimli"][0]["kalemler"]
    assert kalem == [{"transaction_id": "5", "isim": "Li Wei"}]  # panel elle verilen ismi gösterir
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert s["yeni"] == 1 and p.urunler[0]["title"] == "Order 91 - Li Wei"
    assert t.post("/api/isimli/91/isim", json={"isimler": {"5": "Bo"}}).status_code == 409  # açılmış siparişin ismi değişmez


def test_printify_iptal_ederse_elle_ve_her_gun_alarm_kapatinca_susar(c):
    from fastapi.testclient import TestClient

    from matbaa.panel.app import app

    p, e = SahtePrintify(), SahteEtsy([_makbuz()])
    isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    p.siparisler["o1"]["status"] = "canceled"  # Printify üretimdeki siparişi iptal etti
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert c.execute("SELECT durum FROM isimli_siparis").fetchone()[0] == "elle" and len(s["alarm"]) == 1
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert len(s["alarm"]) == 1 and len(p.siparisler) == 1  # otomatik yeniden açılmaz, alarm sürer
    assert TestClient(app, base_url="http://127.0.0.1:8766").post("/api/isimli/91/kapat").status_code == 200
    s = isimli.siparisleri_isle(c, e, p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    assert not s["alarm"] and len(p.siparisler) == 1


def test_uretimdeyken_iade_edilen_makbuz_elle_kargodan_sonra_sessiz(c):
    c.execute("INSERT INTO isimli_siparis (etsy_receipt_id, durum, printify_order_id) VALUES ('91', 'uretimde', 'o1')")
    c.execute("INSERT INTO isimli_siparis (etsy_receipt_id, durum, printify_order_id) VALUES ('92', 'takip_yazildi', 'o2')")
    c.commit()
    p = SahtePrintify()
    p.siparisler.update({"o1": {"status": "in-production", "shipments": []}, "o2": {"status": "fulfilled", "shipments": []}})
    m = [_makbuz(durum="fully refunded"), _makbuz(mid=92, durum="fully refunded")]
    s = isimli.siparisleri_isle(c, SahteEtsy(m), p, SIMDI, yazdir=lambda *_: None, bekle_sn=0)
    durum = dict(c.execute("SELECT etsy_receipt_id, durum FROM isimli_siparis").fetchall())
    assert durum == {"91": "elle", "92": "iptal"} and len(s["alarm"]) == 1 and not p.iptal
