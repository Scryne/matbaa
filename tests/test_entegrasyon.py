"""Printify/Etsy entegrasyonu sahte HTTP ve sahte istemcilerle: gerçek hesap gerektirmez (Faz 0 öncesi)."""

from __future__ import annotations

import json

import httpx
import pytest
from PIL import Image

from matbaa import db, yayin
from matbaa.entegrasyon import etsy as etsy_mod
from matbaa.entegrasyon import printify as pf
from matbaa.entegrasyon.http import ApiHatasi, istek


def test_yerlesim_ustten_hizali_tasarim():
    # 4500x5400 tuvalde x 225–4275, y 150–1350 kutu; yer tutucu 4500x5400 → tuval ile birebir
    y = pf.yerlesim((225, 150, 4275, 1350), (4500, 5400), (4500, 5400))
    assert y.x == pytest.approx(0.5) and y.scale == pytest.approx(0.9)
    assert y.y == pytest.approx(750 / 5400, abs=1e-4)
    # Yer tutucu daha basık (3600x4800): tuval genişliği yer tutucuya oturur, oran korunur
    y2 = pf.yerlesim((225, 150, 4275, 1350), (4500, 5400), (3600, 4800))
    assert y2.y == pytest.approx(750 * 0.8 / 4800, abs=1e-4)


def test_kirp_bos_dosyayi_reddeder(tmp_path):
    p = tmp_path / "bos.png"
    Image.new("RGBA", (100, 100)).save(p)
    with pytest.raises(ValueError):
        pf.kirp(p)


VARYANTLAR = [
    {
        "id": 1,
        "options": {"color": "Solid Black", "size": "M"},
        "placeholders": [{"position": "front", "decoration_method": "dtg", "width": 4500, "height": 5400}],
    },
    {
        "id": 2,
        "options": {"color": "White", "size": "M"},
        "placeholders": [{"position": "front", "decoration_method": "dtg", "width": 4500, "height": 5400}],
    },
    {"id": 3, "options": {"color": "White", "size": "XS"}, "placeholders": []},
    {"id": 4, "options": {"color": "Orange", "size": "M"}, "placeholders": []},
    {
        "id": 5,
        "options": {"color": "White", "size": "2XL"},
        "placeholders": [{"position": "front", "decoration_method": "dtg", "width": 4500, "height": 5400}],
    },
]
RENKLER = [{"ad": "White", "murekkep": "koyu"}, {"ad": "Black", "murekkep": "acik"}]


def test_varyant_sec_ad_eslesmesi_ve_beden():
    g = pf.varyant_sec(VARYANTLAR, RENKLER, ["S", "M", "L", "XL", "2XL"])
    assert [v["id"] for v in g["koyu"]] == [2, 5]  # XS katalogda yok, Orange katalogda yok
    assert [v["id"] for v in g["acik"]] == [1]  # "Solid Black" ↔ "Black"


def test_urun_govdesi_fiyat_ve_baski_alanlari():
    g = pf.varyant_sec(VARYANTLAR, RENKLER, ["M", "2XL"])
    gorseller = {"koyu": ("img-k", (225, 150, 4275, 1350), (4500, 5400)), "acik": ("img-a", (225, 150, 4275, 1350), (4500, 5400))}
    govde = pf.urun_govdesi("Başlık", "a\n\nb", ["t"], 706, 99, g, gorseller, 28.99, {"2XL": 2.0})
    fiyatlar = {v["id"]: v["price"] for v in govde["variants"]}
    assert fiyatlar == {2: 2899, 5: 3099, 1: 2899}
    alanlar = {a["placeholders"][0]["images"][0]["id"]: a["variant_ids"] for a in govde["print_areas"]}
    assert alanlar == {"img-k": [2, 5], "img-a": [1]}  # açık kumaşa koyu mürekkep
    assert govde["description"] == "a<br><br>b"


def test_eslesmeyen_katalog_hatasi():
    with pytest.raises(ValueError):
        pf.urun_govdesi("b", "a", [], 1, 1, {"koyu": [], "acik": []}, {}, 10, {})


def test_429_retry_after_ve_5xx_geri_cekilme():
    sira = iter([httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(502), httpx.Response(200, json={"ok": 1})])
    beklenen = []
    http = httpx.Client(transport=httpx.MockTransport(lambda r: next(sira)))
    r = istek(http, "GET", "https://x/y", bekle=beklenen.append)
    assert r.json() == {"ok": 1} and beklenen == [3.0, 4.0]


def test_4xx_hemen_hata():
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(400, json={"error": "low dpi"})))
    with pytest.raises(ApiHatasi, match="low dpi"):
        istek(http, "POST", "https://x/y", bekle=lambda s: None)


def test_etsy_token_yenilenir_ve_yeni_yenileme_tokeni_kaydedilir(tmp_path, monkeypatch):
    monkeypatch.setenv("ETSY_REFRESH_TOKEN", "eski")
    gorulen = []

    def isle(r: httpx.Request):
        gorulen.append((r.method, r.url.path, r.headers.get("x-api-key"), r.headers.get("authorization")))
        if r.url.path.endswith("/oauth/token"):
            assert b"refresh_token=eski" in r.content
            return httpx.Response(200, json={"access_token": "123.erisim", "refresh_token": "yeni", "expires_in": 3600})
        if r.method == "PATCH":
            assert r.headers["content-type"].startswith("application/x-www-form-urlencoded")
            assert b"production_partner_ids=55%2C66" in r.content
            return httpx.Response(200, json={"listing_id": 9})
        return httpx.Response(200, json={"results": [{"production_partner_id": 55}]})

    e = etsy_mod.Etsy(
        "ks", "sec", "777", http=httpx.Client(transport=httpx.MockTransport(isle)), token_dosyasi=tmp_path / "t.json"
    )
    assert e.uretim_ortaklari() == [{"production_partner_id": 55}]
    e.ilan_guncelle(9, production_partner_ids=[55, 66], state="active")
    assert json.loads((tmp_path / "t.json").read_text())["refresh_token"] == "yeni"
    assert gorulen[1][2] == "ks:sec" and gorulen[1][3] == "Bearer 123.erisim"
    assert sum(1 for g in gorulen if g[1].endswith("/oauth/token")) == 1  # token önbellekte


# --- yayın akışı sahte istemcilerle ---


class SahtePrintify:
    def __init__(self, dus: set[str] | None = None):
        self.olusturulan, self.dus = [], dus or set()

    def gorsel_yukle(self, png, ad):
        return f"img-{ad}", (225, 150, 4275, 1350), (4500, 5400)

    def varyantlar(self, bp, sg):
        return VARYANTLAR

    def urun_olustur(self, govde):
        if govde["blueprint_id"] in self.dus:
            raise ApiHatasi(400, "low dpi", "POST")
        self.olusturulan.append(govde["blueprint_id"])
        return {"id": f"p{len(self.olusturulan)}"}

    def yayinla(self, urun_id):
        return {}

    def urun(self, urun_id):
        return {"external": [{"id": "9001", "handle": "x"}]}


class SahteEtsy:
    def __init__(self):
        self.guncellenen = []

    def ilan(self, listing_id):
        return {"description": "AI beyanı yok"}

    def ilan_guncelle(self, listing_id, **alanlar):
        self.guncellenen.append((listing_id, alanlar))


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "y.db")
    monkeypatch.setattr(yayin, "KOK", tmp_path)
    cfg = {
        "isinma": [[0, 7, 1], [7, 100000, 5]],
        "printify": {
            u: {"blueprint_ara": u, "blueprint_id": i + 1, "saglayici_id": 9}
            for i, u in enumerate(["tisort", "sweatshirt", "hoodie"])
        },
        "etsy": {"uretim_ortagi_id": 55},
    }
    monkeypatch.setattr(yayin, "ayar", lambda: cfg)
    c = db.baglan()
    for n in range(3):
        i = db.ifade_ekle(c, "fishing", [f"S{n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        t = db.tasarim_ekle(c, i, "yigin", [])
        c.execute("UPDATE tasarim SET dosyalar = ? WHERE id = ?", (json.dumps({"koyu_png": "k.png", "acik_png": "a.png"}), t))
        for d in ("kalite_ok", "metin_ok", "onay_bekliyor", "onaylandi"):
            db.gecis(c, t, d)
        for u in ("tisort", "sweatshirt", "hoodie"):
            c.execute(
                "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (?, ?, 'B', '[]', 'A', 28.99, 4.99)",
                (t, u),
            )
            c.execute("INSERT INTO urun (tasarim_id, urun) VALUES (?, ?)", (t, u))
    c.commit()
    return c


def test_isinma_ilk_gun_bir_tasarim(ortam):
    p = SahtePrintify()
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert s["sinir"] == 1 and s["tasarim"] == 1 and s["urun"] == 3
    assert yayin.yayinla(ortam, p, yazdir=lambda *_: None)["tasarim"] == 0  # aynı gün ikinci koşu: sınır dolu


def test_urun_hatasi_digerlerini_durdurmaz_ve_mukerrer_acilmaz(ortam):
    p = SahtePrintify(dus={2})  # sweatshirt düşer
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    durum = dict(ortam.execute("SELECT urun, durum FROM urun WHERE tasarim_id = 1").fetchall())
    assert durum == {"tisort": "printify", "sweatshirt": "hata", "hoodie": "printify"}
    e = SahteEtsy()
    s = yayin.etsy_esle(ortam, p, e, yazdir=lambda *_: None)
    assert s["aktif"] == 2
    alanlar = e.guncellenen[0][1]
    assert alanlar["production_partner_ids"] == [55] and alanlar["state"] == "active" and alanlar["description"] == "A"
    assert ortam.execute("SELECT durum FROM tasarim WHERE id = 1").fetchone()[0] == "yayinda"


def test_printify_urunu_olan_hata_yeniden_printifya_gitmez(ortam):
    p = SahtePrintify(dus={2})
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)  # tasarım 1: tişört + hoodie printify, sweatshirt hata (printify_id yok)
    ortam.execute("UPDATE urun SET durum = 'hata' WHERE tasarim_id = 1 AND urun = 'tisort'")  # Etsy adımında düşmüş gibi
    pid = ortam.execute("SELECT printify_id FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()[0]
    ortam.execute("DELETE FROM olay WHERE varlik = 'urun'")  # yeni gün: günlük sınır sıfır
    ortam.execute("UPDATE tasarim SET durum = 'onaylandi', durum_zamani = '2000-01-01' WHERE id = 1")  # önce bu seçilsin
    once = list(p.olusturulan)
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert p.olusturulan == once  # tişört (printify_id var) yeniden oluşturulmadı; sweatshirt yine düştü
    r = ortam.execute("SELECT durum, printify_id FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()
    assert tuple(r) == ("hata", pid) and pid


def test_uretim_ortagi_yoksa_etsy_esle_durur(ortam, monkeypatch):
    monkeypatch.setattr(yayin, "ayar", lambda: {"isinma": [], "printify": {}, "etsy": {"uretim_ortagi_id": 0}})
    with pytest.raises(RuntimeError, match="uretim_ortagi_id"):
        yayin.etsy_esle(ortam, SahtePrintify(), SahteEtsy())


# --- sipariş defteri ---


class SahteEtsyMakbuz:
    def __init__(self, makbuzlar):
        self.m = makbuzlar

    def makbuzlar(self, min_son_degisim=None):
        return self.m


class SahtePrintifySiparis:
    def siparisler(self, sayfa):
        return {
            "data": [
                {
                    "id": "po1",
                    "metadata": {"shop_order_id": 111},
                    "total_price": 1265,
                    "total_shipping": 429,
                    "total_tax": 0,
                    "shipments": [{"number": "1Z999"}],
                }
            ]
        }


def test_siparis_net_ve_gecikme_alarmi(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from matbaa import siparis

    monkeypatch.setattr(db, "DB", tmp_path / "s.db")
    c = db.baglan()
    simdi = datetime(2026, 11, 20, tzinfo=UTC)
    para = lambda x: {"amount": round(x * 100), "divisor": 100}  # noqa: E731
    makbuzlar = [
        {"receipt_id": 111, "grandtotal": para(35.98), "total_tax_cost": para(2.0), "total_vat_cost": para(0), "total_shipping_cost": para(4.99),
         "create_timestamp": int(datetime(2026, 11, 18, tzinfo=UTC).timestamp()), "status": "Paid", "is_shipped": False},
        {"receipt_id": 222, "grandtotal": para(33.98), "total_tax_cost": para(0), "total_vat_cost": para(0), "total_shipping_cost": para(4.99),
         "create_timestamp": int(datetime(2026, 11, 9, tzinfo=UTC).timestamp()), "status": "Paid", "is_shipped": False},
    ]  # fmt: skip
    s = siparis.izle(c, SahteEtsyMakbuz(makbuzlar), SahtePrintifySiparis(), simdi, yazdir=lambda *_: None)
    assert s["yeni"] == 2
    assert s["alarm"] == ["makbuz 222: 9 iş günü, takip yok"]  # 111'in takibi var ve yeni
    r = c.execute("SELECT printify_order_id, brut, net, takip FROM siparis WHERE etsy_receipt_id = '111'").fetchone()
    assert tuple(r)[:2] == ("po1", 33.98) and r[3] == "1Z999"
    assert r[2] == pytest.approx(33.98 - 16.94 - (33.98 - 16.94 - r[2]), abs=0.01) and 5 < r[2] < 12
    assert siparis.izle(c, SahteEtsyMakbuz(makbuzlar), SahtePrintifySiparis(), simdi, yazdir=lambda *_: None)["guncel"] == 2
    assert siparis.ozet(c, gun=100000)["siparis"] == 2


def test_is_gunu_farki():
    from datetime import datetime

    from matbaa.siparis import is_gunu_farki

    assert is_gunu_farki(datetime(2026, 11, 13), datetime(2026, 11, 16)) == 1  # Cuma → Pazartesi
