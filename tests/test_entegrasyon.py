"""Printify/Etsy entegrasyonu sahte HTTP ve sahte istemcilerle: gerçek hesap gerektirmez (Faz 0 öncesi)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from PIL import Image

from matbaa import db, fiyat, yayin
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


def test_etsy_hazirlama_profili_envanterde_sku_fiyat_korunarak_yazilir(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps({"access_token": "a", "bitis": 9e12}))
    teklif = {"offering_id": 1, "quantity": 999, "is_enabled": True, "is_deleted": False, "readiness_state_id": 2}
    deger = {"property_id": 513, "property_name": "Clothing sizes", "scale_id": None, "scale_name": None}
    env = {
        "products": [
            {
                "product_id": 7,
                "sku": "S1",
                "is_deleted": False,
                "offerings": [teklif | {"price": {"amount": 3399, "divisor": 100}}],
                "property_values": [deger | {"value_ids": [11], "values": ["S"]}],
            },
            {
                "product_id": 8,
                "sku": "S2",
                "is_deleted": True,
                "offerings": [teklif | {"price": {"amount": 1, "divisor": 1}}],
                "property_values": [],
            },
        ],
        "price_on_property": [513],
        "quantity_on_property": [],
        "sku_on_property": [513],
        "readiness_state_on_property": [],
    }
    yazilan = []

    def isle(r: httpx.Request):
        if r.method == "PUT":
            yazilan.append(json.loads(r.content))
            env["products"][0]["offerings"][0]["readiness_state_id"] = 3
            return httpx.Response(200, json={})
        return httpx.Response(200, json=env)

    e = etsy_mod.Etsy(
        "ks", "sec", "777", http=httpx.Client(transport=httpx.MockTransport(isle)), token_dosyasi=tmp_path / "t.json"
    )
    assert e.hazirlama_ayarla(9, 3) is True
    g = yazilan[0]
    assert g["products"] == [
        {
            "sku": "S1",
            "property_values": [
                {"property_id": 513, "value_ids": [11], "scale_id": None, "property_name": "Clothing sizes", "values": ["S"]}
            ],
            "offerings": [{"price": 33.99, "quantity": 999, "is_enabled": True, "readiness_state_id": 3}],
        }
    ]
    assert g["price_on_property"] == [513] and g["sku_on_property"] == [513]
    assert e.hazirlama_ayarla(9, 3) is False and len(yazilan) == 1  # profil zaten doğruysa envantere dokunulmaz


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

    def yayinla(self, urun_id, kargo_sablonu=True):
        self.kargo_sablonu = kargo_sablonu
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

    def hazirlama_ayarla(self, listing_id, readiness_state_id):
        self.hazirlama = getattr(self, "hazirlama", []) + [(listing_id, readiness_state_id)]
        return True


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
        "etsy": {"uretim_ortagi_id": 55, "kargo_profili_id": 66, "hazirlama_profili_id": 35},
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


@pytest.mark.parametrize("alan", ["uretim_ortagi_id", "kargo_profili_id"])
def test_etsy_hazir_degilken_yayin_printifya_dokunmaz(ortam, monkeypatch, alan):
    cfg = yayin.ayar()
    monkeypatch.setitem(cfg["etsy"], alan, 0)
    p = SahtePrintify()
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert alan in s["bekliyor"] and not p.olusturulan and s["urun"] == 0
    assert ortam.execute("SELECT count(*) FROM urun WHERE durum != 'bekliyor'").fetchone()[0] == 0


def test_elle_mod_kargo_hazir_olmadan_yayinlamaz_hazirsa_yayinlar(ortam, monkeypatch):  # K-27
    cfg = yayin.ayar()
    monkeypatch.setitem(cfg, "etsy", {"mod": "elle", "elle_kargo_hazir": False})
    p = SahtePrintify()
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert "elle_kargo_hazir" in s["bekliyor"] and not p.olusturulan
    monkeypatch.setitem(cfg["etsy"], "elle_kargo_hazir", True)  # API kimlikleri yokken de yayınlar
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert s["urun"] == 3 and p.kargo_sablonu is True


class KargoluPrintify(SahtePrintify):
    def __init__(self, profil):
        super().__init__()
        self.profil = profil

    def urun(self, urun_id):
        return {"external": {"id": f"L{urun_id}", "shipping_template_id": self.profil}}


@pytest.mark.parametrize(("profil", "alarm"), [("777", 0), ("123", 3)])
def test_elle_denetim_ilani_kaydeder_yanlis_kargoda_bir_kez_alarm_verir(ortam, monkeypatch, profil, alarm):  # K-27
    monkeypatch.setitem(yayin.ayar(), "etsy", {"mod": "elle", "elle_kargo_hazir": True, "kargo_profili_id": 777})
    p = KargoluPrintify(profil)
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    s = yayin.elle_denetle(ortam, p, yazdir=lambda *_: None)
    assert s["etsy"] == 3 and len(s["alarm"]) == alarm
    durumlar = ortam.execute("SELECT durum, etsy_listing_id FROM urun WHERE printify_id IS NOT NULL").fetchall()
    assert {d[0] for d in durumlar} == {"aktif"} and all(d[1].startswith("L") for d in durumlar)
    assert ortam.execute("SELECT durum FROM tasarim WHERE id = 1").fetchone()[0] == "yayinda"
    assert yayin.elle_denetle(ortam, p, yazdir=lambda *_: None)["alarm"] == []  # ikinci gün aynı alarm tekrar etmez


class SiparisliPrintify(SahtePrintify):
    def __init__(self, siparisler):
        super().__init__()
        self.siparisler_ = siparisler

    def son_siparisler(self, sayfa_maks: int = 10):
        return self.siparisler_


def _pf_siparis(i, urun_id, durum, gun_once, takip=None, fiyat_sent=None):
    from datetime import UTC, datetime, timedelta

    return {
        "id": f"o{i}", "status": durum, "metadata": {"shop_order_id": 5000 + i},
        "created_at": (datetime(2026, 10, 20, tzinfo=UTC) - timedelta(days=gun_once)).isoformat(),
        "total_price": 1304, "total_shipping": 449, "total_tax": 0,
        "line_items": [{"product_id": urun_id, "quantity": 1, "metadata": {"price": fiyat_sent} if fiyat_sent else {}}],
        "shipments": [{"number": takip}] if takip else [],
    }  # fmt: skip


def test_printify_siparis_defteri_net_iptal_ve_gecikme(ortam):  # K-27, Faz 8-9 API'siz
    from datetime import UTC, datetime

    from matbaa import siparis

    yayin.yayinla(ortam, SahtePrintify(), yazdir=lambda *_: None)  # p1..p3 tasarım 1'in ürünleri
    p = SiparisliPrintify(
        [
            _pf_siparis(1, "p1", "fulfilled", 3, takip="9400TRACK", fiyat_sent=3399),
            _pf_siparis(2, "p2", "in-production", 9),  # takipsiz, 9 gün önce: alarm
            _pf_siparis(3, "p3", "canceled", 2),
        ]
    )
    s = siparis.izle_printify(ortam, p, simdi=datetime(2026, 10, 20, tzinfo=UTC), yazdir=lambda *_: None)
    assert s["yeni"] == 3 and len(s["alarm"]) == 1 and "5002" in s["alarm"][0]
    r = ortam.execute("SELECT brut, net, takip, tasarim_id FROM siparis WHERE etsy_receipt_id = '5001'").fetchone()
    assert r[0] == 33.99 and 0 < r[1] < 33.99 - 17.53 and r[2] == "9400TRACK" and r[3] == 1  # metadata fiyatı, maliyet düşülmüş
    # metadata fiyatı yoksa yayınlanan ilan fiyatı (yayında güncel katalogdan yazılır)
    assert (
        ortam.execute("SELECT brut FROM siparis WHERE etsy_receipt_id = '5002'").fetchone()[0]
        == fiyat.urunler()["sweatshirt"]["fiyat"]
    )
    s2 = siparis.izle_printify(ortam, p, simdi=datetime(2026, 10, 20, tzinfo=UTC), yazdir=lambda *_: None)
    assert s2["yeni"] == 0 and s2["guncel"] == 3
    toplam = ortam.execute(f"SELECT count(*) FROM siparis WHERE {siparis.GECERLI}").fetchone()[0]
    assert toplam == 2  # iptal gelirden düşer


def test_kupa_yalniz_satan_tasarima_acilir(ortam):  # Faz 14
    from matbaa.entegrasyon.printify import varyant_sec
    from matbaa.ilan.metin import Ilan

    assert [
        v["id"]
        for v in varyant_sec([{"id": 1, "options": {"size": "11oz"}}], [{"ad": "White", "murekkep": "koyu"}], ["11oz"])["koyu"]
    ] == [1]
    yaz = lambda s, n, u: Ilan("Funny Fishing Mug", [f"fishing mug {i}" for i in range(13)], "a", "alt")  # noqa: E731
    assert yayin.kupa_ac(ortam, yaz, yazdir=lambda *_: None)["acilan"] == 0  # satış yok
    ortam.execute("UPDATE tasarim SET durum = 'yayinda' WHERE id = 1")
    ortam.execute("INSERT INTO siparis (etsy_receipt_id, tasarim_id, brut, net, durum) VALUES ('r1', 1, 33.99, 9, 'paid')")
    ortam.execute("INSERT INTO siparis (etsy_receipt_id, tasarim_id, brut, net, durum) VALUES ('r2', 2, 33.99, 9, 'canceled')")
    assert yayin.kupa_ac(ortam, yaz, yazdir=lambda *_: None)["acilan"] == 1  # iptal edilen tasarım 2'ye açılmaz
    assert ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 1 AND urun = 'kupa'").fetchone()[0] == "bekliyor"
    assert yayin.kupa_ac(ortam, yaz, yazdir=lambda *_: None)["acilan"] == 0  # ikinci kez açılmaz


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
    assert alanlar["should_auto_renew"] == "true"  # Printify kapalı açıyor: 4 ayda ilan sona ererdi
    assert [r for _, r in e.hazirlama] == [35, 35]  # Printify'ın 2-5 gün profili mağazanın 3-5 gün profiline çekilir
    assert ortam.execute("SELECT durum FROM tasarim WHERE id = 1").fetchone()[0] == "yayinda"


def _dun(c) -> None:
    """Ürün olaylarını bir gün geriye al: günlük sınır sıfırlanır, geçmiş (hata_oncesi) korunur."""
    dun = (datetime.now(UTC) - timedelta(days=1)).isoformat(timespec="seconds")
    c.execute("UPDATE olay SET zaman = ? WHERE varlik = 'urun'", (dun,))  # mağaza yaşı 1 gün: sınır hâlâ 1 tasarım
    c.commit()


def test_printify_urunu_olan_hata_yeniden_printifya_gitmez(ortam):
    p = SahtePrintify(dus={2})
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)  # tasarım 1: tişört + hoodie printify, sweatshirt hata (ürün açılmadı)
    db.urun_gecis(ortam, 1, "tisort", "hata", "etsy: 500")  # Etsy adımında düşmüş
    pid = ortam.execute("SELECT printify_id FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()[0]
    _dun(ortam)
    once = list(p.olusturulan)
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert p.olusturulan == once and s["hata"] == 1  # tişört yeniden açılmadı; yalnız sweatshirt denendi, yine düştü
    r = ortam.execute("SELECT durum, printify_id FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()
    assert tuple(r) == ("hata", pid) and pid
    assert yayin.etsy_esle(ortam, p, SahteEtsy(), yazdir=lambda *_: None)["aktif"] == 2  # tişört Etsy adımından sürer


class YayiniDusenPrintify(SahtePrintify):
    def __init__(self):
        super().__init__()
        self.yayin_istekleri, self.dusur = [], True

    def yayinla(self, urun_id, kargo_sablonu=True):
        self.kargo_sablonu = kargo_sablonu
        self.yayin_istekleri.append(urun_id)
        if self.dusur:
            raise ApiHatasi(500, "publish", "POST")
        return {}


def test_yayin_duserse_ayni_urun_yeniden_yayinlanir_ikinci_urun_acilmaz(ortam):
    p = YayiniDusenPrintify()
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert p.olusturulan == [1, 2, 3]
    assert {r[0] for r in ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 1")} == {"hata"}
    _dun(ortam)
    p.dusur = False
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert p.olusturulan == [1, 2, 3] and s["urun"] == 3  # aynı üç ürün yayınlandı, yenisi açılmadı
    assert p.yayin_istekleri[-3:] == ["p1", "p2", "p3"]
    assert {r[0] for r in ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 1")} == {"printify"}


def test_etsy_eslemesi_bekleyen_tasarim_gunluk_siniri_harcamaz(ortam):
    p = SahtePrintify()
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)  # tasarım 1'in üç ürünü printify'da, Etsy eşlemesi bekliyor
    _dun(ortam)
    s = yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert s["tasarim"] == 1 and p.olusturulan[-3:] == [1, 2, 3] and len(p.olusturulan) == 6  # sıradaki tasarım 2 açıldı
    assert {r[0] for r in ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 2")} == {"printify"}


class EtsyyeDusmeyenPrintify(SahtePrintify):
    def urun(self, urun_id):
        return {"external": []}


def test_etsy_ilani_olusmazsa_yeniden_yayin_sonra_elle(ortam):
    p = EtsyyeDusmeyenPrintify()
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert yayin.etsy_esle(ortam, p, SahteEtsy(), yazdir=lambda *_: None)["bekleyen"] == 3  # henüz süre dolmadı
    eski = lambda: ortam.execute("UPDATE urun SET guncelleme = '2000-01-01T00:00:00+00:00' WHERE tasarim_id = 1")  # noqa: E731
    for _ in range(yayin.YENIDEN_YAYIN_MAKS):
        eski()
        assert yayin.etsy_esle(ortam, p, SahteEtsy(), yazdir=lambda *_: None)["yeniden_yayin"] == 3
        _dun(ortam)
        yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    assert len(p.olusturulan) == 3  # yeniden yayın aynı ürünleri kullandı
    eski()
    yayin.etsy_esle(ortam, p, SahteEtsy(), yazdir=lambda *_: None)
    hatalar = [r[0] for r in ortam.execute("SELECT hata FROM urun WHERE tasarim_id = 1")]
    assert all(yayin.ELLE in h for h in hatalar)
    assert yayin.etsy_esle(ortam, p, SahteEtsy(), yazdir=lambda *_: None)["bekleyen"] == 0  # elle bakılacaklar döngüye girmez


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
    def __init__(self, siparisler=None):
        self.s = (
            siparisler
            if siparisler is not None
            else [
                {
                    "id": "po1",
                    "metadata": {"shop_order_id": 111},
                    "total_price": 1265,
                    "total_shipping": 429,
                    "total_tax": 0,
                    "shipments": [{"number": "1Z999"}],
                }
            ]
        )

    def son_siparisler(self):
        return self.s


def _para(x):
    return {"amount": round(x * 100), "divisor": 100}


def _makbuz(no, gun, toplam=33.98, **ek):
    from datetime import UTC, datetime

    return {
        "receipt_id": no, "grandtotal": _para(toplam), "total_tax_cost": _para(0), "total_vat_cost": _para(0),
        "total_shipping_cost": _para(4.99), "create_timestamp": int(datetime(2026, 11, gun, tzinfo=UTC).timestamp()),
        "status": "Paid", "is_shipped": False, **ek,
    }  # fmt: skip


def test_siparis_net_ve_gecikme_alarmi(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from matbaa import siparis

    monkeypatch.setattr(db, "DB", tmp_path / "s.db")
    c = db.baglan()
    simdi = datetime(2026, 11, 20, tzinfo=UTC)
    makbuzlar = [_makbuz(111, 18, 35.98, total_tax_cost=_para(2.0)), _makbuz(222, 9)]
    s = siparis.izle(c, SahteEtsyMakbuz(makbuzlar), SahtePrintifySiparis(), simdi, yazdir=lambda *_: None)
    assert s["yeni"] == 2
    assert s["alarm"] == ["makbuz 222: 9 iş günü, takip yok"]  # 111'in takibi var ve yeni
    r = c.execute("SELECT printify_order_id, brut, net, takip, durum FROM siparis WHERE etsy_receipt_id = '111'").fetchone()
    assert tuple(r)[:2] == ("po1", 33.98) and r[3] == "1Z999" and r[4] == "paid"
    assert 5 < r[2] < 12
    assert siparis.izle(c, SahteEtsyMakbuz(makbuzlar), SahtePrintifySiparis(), simdi, yazdir=lambda *_: None)["guncel"] == 2
    assert siparis.ozet(c, gun=100000)["siparis"] == 2
    # Ertesi gün Etsy 222'yi döndürmese de (değişmedi) alarm sürer: alarm veritabanının tamamından.
    s = siparis.izle(c, SahteEtsyMakbuz([]), SahtePrintifySiparis(), simdi, yazdir=lambda *_: None)
    assert s["alarm"] == ["makbuz 222: 9 iş günü, takip yok"]


def test_siparis_urunden_eslesir_tasarima_baglanir_iptal_gelirden_duser(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from matbaa import siparis

    monkeypatch.setattr(db, "DB", tmp_path / "s.db")
    c = db.baglan()
    i = db.ifade_ekle(c, "fishing", ["REEL COOL"])
    db.kapi_yaz(c, i, "temiz", [], [])
    t = db.tasarim_ekle(c, i, "yigin", [])
    c.execute("INSERT INTO urun (tasarim_id, urun, printify_id, etsy_listing_id) VALUES (?, 'hoodie', 'pp-h', '7001')", (t,))
    c.commit()
    printify = SahtePrintifySiparis(
        [
            # Makbuz kimliği taşımayan iki sipariş: aynı ürün, biri çok geç (başka makbuzun) → yakın olan seçilir
            {"id": "geç", "metadata": {}, "line_items": [{"product_id": "pp-h"}], "created_at": "2026-11-15 10:00:00+00:00",
             "total_price": 9999, "total_shipping": 0, "total_tax": 0},
            {"id": "po-h", "metadata": {}, "line_items": [{"product_id": "pp-h"}], "created_at": "2026-11-03 12:00:00+00:00",
             "total_price": 2311, "total_shipping": 879, "total_tax": 0, "shipments": []},
        ]
    )  # fmt: skip
    makbuzlar = [
        _makbuz(333, 3, 55.98, transactions=[{"listing_id": 7001, "quantity": 1}], shipments=[{"tracking_code": "9400ETSY"}]),
        _makbuz(444, 4, 55.98, status="Canceled", transactions=[{"listing_id": 1, "quantity": 1}]),
    ]
    simdi = datetime(2026, 11, 20, tzinfo=UTC)
    s = siparis.izle(c, SahteEtsyMakbuz(makbuzlar), printify, simdi, yazdir=lambda *_: None)
    r = c.execute("SELECT printify_order_id, tasarim_id, takip FROM siparis WHERE etsy_receipt_id = '333'").fetchone()
    assert tuple(r) == ("po-h", t, "9400ETSY")  # ürünle eşleşti, tasarıma bağlandı, takip Etsy'den
    assert s["alarm"] == [] and s["printify_eslesmedi"] == 1  # iptal makbuz alarm vermez
    o = siparis.ozet(c, gun=100000)
    assert o["siparis"] == 1  # iptal gelire girmez
    # Printify eşleşmeyen sipariş katalog tahmini ürün türünden: tişört değil hoodie maliyeti
    hoodie = fiyat.urun_hesap("hoodie").uretim
    c.execute("DELETE FROM siparis")
    siparis.izle(c, SahteEtsyMakbuz(makbuzlar[:1]), SahtePrintifySiparis([]), simdi, yazdir=lambda *_: None)
    net = c.execute("SELECT net FROM siparis WHERE etsy_receipt_id = '333'").fetchone()[0]
    assert net == fiyat.hesap(55.98 - 4.99, 4.99, hoodie).net


def test_printify_siparis_sayfalari():
    sayfalar = {1: {"data": [{"id": 1}] * 10, "last_page": 2}, 2: {"data": [{"id": 2}] * 3, "last_page": 2}}
    gorulen = []

    def isle(r: httpx.Request):
        n = int(r.url.params["page"])
        gorulen.append((n, r.url.params["limit"]))
        return httpx.Response(200, json=sayfalar[n])

    p = pf.Printify("tok", "s1", http=httpx.Client(transport=httpx.MockTransport(isle)))
    assert len(p.son_siparisler()) == 13 and gorulen == [(1, "10"), (2, "10")]


def test_urun_olusturma_5xxte_yinelenmez():
    n = []

    def isle(r):
        n.append(r)
        return httpx.Response(502)

    p = pf.Printify("tok", "s1", http=httpx.Client(transport=httpx.MockTransport(isle)), bekle=lambda s: None)
    with pytest.raises(ApiHatasi):
        p.urun_olustur({})
    assert len(n) == 1  # sunucu ürünü açıp yanıtı düşürmüş olabilir: ikinci POST mükerrer ürün açar


def test_is_gunu_farki():
    from datetime import datetime

    from matbaa.siparis import is_gunu_farki

    assert is_gunu_farki(datetime(2026, 11, 13), datetime(2026, 11, 16)) == 1  # Cuma → Pazartesi


class KargoEtsy(SahteEtsy):
    def __init__(self, profiller=()):
        super().__init__()
        self.profiller, self.olusturulan = list(profiller), []

    def kargo_profilleri(self):
        return self.profiller

    def kargo_profili_olustur(self, **alanlar):
        self.olusturulan.append(alanlar)
        return {"shipping_profile_id": 555}


class KonumluPrintify(SahtePrintify):
    def saglayici(self, sid):
        return {"id": sid, "location": {"country": "US", "zip": "92614"}}


def test_kargo_profili_kurulur_config_yazilir_ilana_baglanir(ortam, tmp_path, monkeypatch):
    from matbaa.ayar import CONFIG

    (tmp_path / "yayin.toml").write_text((CONFIG / "yayin.toml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(yayin, "CONFIG", tmp_path)
    cfg = yayin.ayar()
    monkeypatch.setattr(yayin.ayar, "cache_clear", lambda: None, raising=False)  # fikstürün ayar'ı önbelleksiz
    e = KargoEtsy()
    assert yayin.kargo_profili_kur(KonumluPrintify(), e, yazdir=lambda *_: None) == 555
    a = e.olusturulan[0]
    assert (a["primary_cost"], a["destination_country_iso"], a["origin_postal_code"]) == (0, "US", "92614")
    assert "kargo_profili_id = 555" in (tmp_path / "yayin.toml").read_text(encoding="utf-8")
    # Aynı adlı profil varsa yenisi açılmaz
    e2 = KargoEtsy([{"title": "Free US shipping", "shipping_profile_id": 777}])
    assert yayin.kargo_profili_kur(KonumluPrintify(), e2, yazdir=lambda *_: None) == 777 and not e2.olusturulan
    # Eşleme her ilana profili bağlar
    cfg["etsy"]["kargo_profili_id"] = 777
    p = SahtePrintify()
    yayin.yayinla(ortam, p, yazdir=lambda *_: None)
    e3 = SahteEtsy()
    yayin.etsy_esle(ortam, p, e3, yazdir=lambda *_: None)
    assert all(al["shipping_profile_id"] == 777 for _, al in e3.guncellenen) and e3.guncellenen


def test_varyant_sec_benzer_adli_baska_rengi_almaz():
    vs = [
        {"id": 1, "options": {"color": "Navy", "size": "M"}},
        {"id": 2, "options": {"color": "Heather Sport Dark Navy", "size": "M"}},
        {"id": 3, "options": {"color": "Heather Navy", "size": "M"}},
        {"id": 4, "options": {"color": "Solid Navy", "size": "L"}},
    ]
    g = pf.varyant_sec(vs, [{"ad": "Navy", "murekkep": "acik"}], ["M", "L"])
    assert [v["id"] for v in g["acik"]] == [1, 4]


def test_blueprint_bul_marka_isareti_ve_tam_model():
    katalog = [
        {"id": 706, "brand": "Comfort Colors®", "model": "1717", "title": "Unisex Garment-Dyed T-shirt"},
        {"id": 2743, "brand": "Comfort Colors®", "model": "1745Y", "title": "Youth"},
        {"id": 49, "brand": "Gildan", "model": "18000", "title": "Unisex Heavy Blend™ Crewneck Sweatshirt"},
        {"id": 1256, "brand": "Gildan", "model": "18000B", "title": "Youth Crewneck Sweatshirt"},
    ]
    p = pf.Printify("tok", "s", http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=katalog))))
    assert [b["id"] for b in p.blueprint_bul("Comfort Colors 1717")] == [706]
    assert [b["id"] for b in p.blueprint_bul("Gildan 18000")] == [49]


def test_onayli_kuyruk_azalinca_onay_bekleyen_varsa_alarm(ortam):
    assert yayin.onay_pisti(ortam) is None  # 3 onaylı < 5 gün ama onay bekleyen yok: üretim kuyruğu doldurur
    i = db.ifade_ekle(ortam, "fishing", ["Bekleyen"])
    db.kapi_yaz(ortam, i, "temiz", [], [])
    t = db.tasarim_ekle(ortam, i, "yigin", [])
    for d in ("kalite_ok", "metin_ok", "onay_bekliyor"):
        db.gecis(ortam, t, d)
    assert "panelde 1 tasarım onay bekliyor" in yayin.onay_pisti(ortam)
    for n in range(2):  # 3 + 2 onaylı = 5 günlük yayın
        j = db.ifade_ekle(ortam, "fishing", [f"Ek{n}"])
        db.kapi_yaz(ortam, j, "temiz", [], [])
        ortam.execute("UPDATE tasarim SET durum = 'onaylandi' WHERE id = ?", (db.tasarim_ekle(ortam, j, "yigin", []),))
    assert yayin.onay_pisti(ortam) is None  # 5 günlük yayına yetiyor


# --- K-30: yılbaşı süsü (mevsimlik ürün) ---

SUS_VARYANTLAR = [
    {
        "id": 11,
        "options": {"shape": "Round", "size": "One size"},
        "placeholders": [
            {"position": "front", "decoration_method": "uv", "width": 900, "height": 900},
            {"position": "back", "decoration_method": "uv", "width": 900, "height": 900},
        ],
    },
    {"id": 12, "options": {"shape": "Heart", "size": "One size"}, "placeholders": []},
    {
        "id": 13,
        "options": {"shape": "Round + White Gift Packaging", "size": "One size"},
        "placeholders": [
            {"position": "front", "decoration_method": "uv", "width": 900, "height": 900},
            {"position": "back", "decoration_method": "uv", "width": 900, "height": 900},
        ],
    },
]


def test_susleme_govdesi_iki_yuz_ve_sekil_secenegi():
    k = fiyat.urunler()["susleme"]
    g = pf.varyant_sec(SUS_VARYANTLAR, k["renkler"], k["bedenler"], k["beden_anahtari"])
    assert [v["id"] for v in g["koyu"]] == [11, 13]  # kalp şekli katalogda yok
    gorseller = {"koyu": ("on", (100, 100, 1700, 1500), (1800, 1800)), "arka": ("arka", (300, 200, 1500, 1400), (1800, 1800))}
    govde = pf.urun_govdesi("B", "A", [], 1632, 39, g, gorseller, k["fiyat"], k["buyuk_beden_ek"], k["beden_anahtari"])
    assert {v["id"]: v["price"] for v in govde["variants"]} == {11: 2199, 13: 2499}  # hediye kutusu +$3
    yerler = {y["position"]: y["images"][0]["id"] for y in govde["print_areas"][0]["placeholders"]}
    assert yerler == {"front": "on", "back": "arka"}
    yalniz_on = [{**SUS_VARYANTLAR[0], "placeholders": SUS_VARYANTLAR[0]["placeholders"][:1]}]
    with pytest.raises(ValueError):  # arka alanı olmayan varyanta arka yüz istenirse sessizce tek yüz basılmaz
        pf.urun_govdesi("B", "A", [], 1, 1, {"koyu": yalniz_on, "acik": []}, gorseller, 20, {})


def test_susleme_uygunlugu_nis_noel_kelimesi_ve_pencere():
    from datetime import date

    ekim, aralik_sonu = date(2026, 10, 14), date(2026, 12, 20)
    assert "susleme" in fiyat.tasarim_urunleri("fishing", ["REEL COOL"], ekim)
    assert "susleme" not in fiyat.tasarim_urunleri("bowling", ["SPARE ME"], ekim)  # süs talebi tişörtün altında olan niş
    assert "susleme" in fiyat.tasarim_urunleri("bowling", ["Merry Christmas, 7-10"], ekim)  # Noel kelimesi her nişte açar
    assert "susleme" not in fiyat.tasarim_urunleri("fishing", ["REEL COOL"], aralik_sonu)  # pencere 12-10'da kapanır
    assert "kupa" not in fiyat.tasarim_urunleri("fishing", ["REEL COOL"], ekim)  # kupa satışa bağlı
    assert not fiyat.mevsim_bitti("susleme", ekim) and fiyat.mevsim_bitti("susleme", date(2026, 12, 27))
    assert fiyat.mevsim_bitti("susleme", date(2027, 2, 1)) and not fiyat.mevsim_bitti("tisort", date(2027, 2, 1))


@pytest.fixture
def sus_ortam(ortam, monkeypatch, tmp_path):
    cfg = yayin.ayar()
    cfg["printify"]["susleme"] = {"blueprint_id": 1632, "saglayici_id": 39}
    monkeypatch.setattr(yayin, "susleme_dosyalari", lambda *a, **k: {"on": tmp_path / "on.png", "arka": tmp_path / "arka.png"})
    monkeypatch.setattr(yayin, "mevsimde", lambda u, gun=None: True)
    return ortam


class SahteSusPrintify(SahtePrintify):
    def varyantlar(self, bp, sg):
        return SUS_VARYANTLAR if bp == 1632 else VARYANTLAR


def _sus_ilan(s, n, u):
    from matbaa.ilan.metin import Ilan

    return Ilan("Fishing Christmas Ornament 2026", [f"fishing ornament {i}" for i in range(13)], "a", "alt")


def test_mevsimlik_ac_uygun_tasarimlara_bir_kez_acar(sus_ortam):
    from datetime import date

    sessiz = lambda *_: None  # noqa: E731
    sus_ortam.execute("UPDATE ifade SET nis = 'bowling' WHERE id = 3")  # bowling, Noel kelimesi yok: açılmaz
    assert yayin.mevsimlik_ac(sus_ortam, _sus_ilan, gun=date(2026, 10, 14), yazdir=sessiz)["acilan"] == 4  # süs + isimli süs
    for urun in ("susleme", "isimli_susleme"):
        n = sus_ortam.execute("SELECT count(*) FROM urun WHERE urun = ? AND durum = 'bekliyor'", (urun,)).fetchone()[0]
        assert n == 2
    assert yayin.mevsimlik_ac(sus_ortam, _sus_ilan, gun=date(2026, 10, 14), yazdir=sessiz)["acilan"] == 0
    assert yayin.mevsimlik_ac(sus_ortam, _sus_ilan, gun=date(2026, 12, 20), yazdir=sessiz)["acilan"] == 0


def test_susu_olan_tasarim_once_ve_yayindakine_ek_urun_siniri_yemez(sus_ortam):
    # Tasarım 3'ün süsü var (sırada öne geçer); tasarım 1 zaten yayında, yalnız süsü bekliyor (tasarım sınırını yemez).
    for t in (1, 3):
        sus_ortam.execute("INSERT INTO urun (tasarim_id, urun) VALUES (?, 'susleme')", (t,))
        sus_ortam.execute(
            "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (?, 'susleme', 'B', '[]', 'A', 21.99, 0)",
            (t,),
        )
    sus_ortam.execute("UPDATE urun SET durum = 'aktif' WHERE tasarim_id = 1 AND urun != 'susleme'")
    db.olay(sus_ortam, "urun", 1, "olusturuldu", "tisort:printify", "ilk yayın")
    sus_ortam.execute("UPDATE olay SET zaman = '2026-01-01T00:00:00+00:00' WHERE yeni = 'tisort:printify'")
    sus_ortam.execute("UPDATE tasarim SET durum = 'yayinda' WHERE id = 1")
    sus_ortam.commit()
    p = SahteSusPrintify()
    s = yayin.yayinla(sus_ortam, p, yazdir=lambda *_: None)
    assert s["sinir"] == 5 and s.get("ek_urun") == 1 and s["tasarim"] == 2
    durum = dict(sus_ortam.execute("SELECT tasarim_id || '/' || urun, durum FROM urun").fetchall())
    assert durum["1/susleme"] == "printify" and durum["3/susleme"] == "printify"
    assert p.olusturulan.count(1632) == 2


def test_susu_olan_onayli_tasarim_sirada_one_gecer(sus_ortam):
    sus_ortam.execute("INSERT INTO urun (tasarim_id, urun) VALUES (3, 'susleme')")
    sus_ortam.execute(
        "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (3, 'susleme', 'B', '[]', 'A', 21.99, 0)"
    )
    sus_ortam.commit()
    s = yayin.yayinla(sus_ortam, SahteSusPrintify(), yazdir=lambda *_: None)
    assert s["sinir"] == 1 and s["tasarim"] == 1 and s["urun"] == 4
    assert sus_ortam.execute("SELECT count(*) FROM urun WHERE tasarim_id = 3 AND durum = 'printify'").fetchone()[0] == 4


def test_mevsim_bitince_aktif_sus_ilani_pasife_alinir(sus_ortam):
    from datetime import date

    sus_ortam.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (1, 'susleme', 'aktif', '777')")
    sus_ortam.commit()
    e = SahteEtsy()
    assert yayin.mevsim_kapat(sus_ortam, e, gun=date(2026, 12, 1), yazdir=lambda *_: None)["kapanan"] == 0
    assert yayin.mevsim_kapat(sus_ortam, e, gun=date(2026, 12, 27), yazdir=lambda *_: None)["kapanan"] == 1
    assert e.guncellenen == [(777, {"state": "inactive", "should_auto_renew": "false"})]
    assert sus_ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 1 AND urun = 'susleme'").fetchone()[0] == "kaldirildi"
    assert sus_ortam.execute("SELECT durum FROM urun WHERE tasarim_id = 1 AND urun = 'tisort'").fetchone()[0] == "bekliyor"


def test_gunluk_sinir_doluyken_de_yayindaki_tasarima_sus_acilir(sus_ortam):
    p = SahteSusPrintify()
    assert yayin.yayinla(sus_ortam, p, yazdir=lambda *_: None)["tasarim"] == 1  # bugünün tek tasarım hakkı
    yayinda = sus_ortam.execute("SELECT DISTINCT tasarim_id FROM urun WHERE durum = 'printify'").fetchone()[0]
    sus_ortam.execute("UPDATE tasarim SET durum = 'yayinda' WHERE id = ?", (yayinda,))
    bekleyen = [r[0] for r in sus_ortam.execute("SELECT id FROM tasarim WHERE durum = 'onaylandi'")]
    sus_ortam.execute("INSERT INTO urun (tasarim_id, urun) VALUES (?, 'susleme')", (yayinda,))
    sus_ortam.execute(
        "INSERT INTO ilan (tasarim_id, urun, baslik, etiketler, aciklama, fiyat, kargo) VALUES (?, 'susleme', 'B', '[]', 'A', 21.99, 0)",
        (yayinda,),
    )
    sus_ortam.commit()
    s = yayin.yayinla(sus_ortam, p, yazdir=lambda *_: None)
    assert s["tasarim"] == 0 and s.get("ek_urun") == 1 and s["urun"] == 1
    assert not sus_ortam.execute(
        f"SELECT count(*) FROM urun WHERE durum != 'bekliyor' AND tasarim_id IN ({','.join(map(str, bekleyen))})"
    ).fetchone()[0]  # yeni tasarım açılmadı
