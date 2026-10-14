"""Etsy öznitelikleri: istenen değerler (ürün sabiti, metin, mevsim), kategori tablosuna çözümleme, günlük eşitleme."""

from __future__ import annotations

import json
from datetime import date

import httpx

from matbaa import db, yayin
from matbaa.entegrasyon import etsy as etsy_mod
from matbaa.entegrasyon.http import ApiHatasi
from matbaa.ilan import oznitelik

EKIM, TEMMUZ = date(2026, 10, 14), date(2026, 7, 10)


def test_istenen_urun_sabitleri_ve_hediye_mevsimi():
    o = oznitelik.istenen("hoodie", "fishing", ["Grandpa's Fishing Crew"], "Funny Fishing Grandpa Hoodie", EKIM)
    assert o["Clothing closure"] == ["Pullover"]  # hoodie kategorisinde zorunlu
    assert o["Sleeve length"] == ["Long sleeve"] and o["Materials"] == ["Cotton", "Polyester"]
    assert o["Clothing graphic"] == ["Humorous saying"]
    assert o["Holiday"] == ["Christmas"] and "Occasion" not in o
    assert "Holiday" not in oznitelik.istenen("tisort", "knitting", ["One More Row"], "", TEMMUZ)  # mevsim dışı


def test_metindeki_tatil_ve_vesile_mevsimden_once():
    assert oznitelik.istenen("tisort", "fishing", ["Gobble Gobble", "Gone Fishing"], "", EKIM)["Holiday"] == ["Thanksgiving"]
    # bowling'de "turkey" üç strike demek: Şükran Günü değil
    assert oznitelik.istenen("tisort", "bowling", ["Bowling Turkey Club"], "", EKIM)["Holiday"] == ["Christmas"]
    # başlıktaki genel hediye açısı mevsimi ezmez, mevsim dışında kullanılır
    baslik = "Funny Fishing Shirt, Father's Day Gift for Grandpa"
    assert oznitelik.istenen("tisort", "fishing", ["Gone Fishing"], baslik, EKIM)["Holiday"] == ["Christmas"]
    assert oznitelik.istenen("tisort", "fishing", ["Gone Fishing"], baslik, TEMMUZ)["Holiday"] == ["Father's Day"]
    assert oznitelik.istenen("tisort", "fishing", ["Retired", "Gone Fishing"], "", TEMMUZ)["Occasion"] == ["Retirement"]
    assert oznitelik.istenen("tisort", "milestone", ["Classic Model"], "", TEMMUZ)["Occasion"] == ["Birthday"]  # niş kartı


def _ozellik(pid, ad, degerler, coklu=False, gorunen=None, attr=True):
    return {
        "property_id": pid,
        "name": ad,
        "display_name": gorunen or ad,
        "is_multivalued": coklu,
        "supports_attributes": attr,
        "possible_values": [{"value_id": pid * 100 + i, "name": d} for i, d in enumerate(degerler)],
    }


TAKSONOMI = [
    _ozellik(1, "Material multi", ["Cotton", "Polyester", "Ceramic"], coklu=True, gorunen="Materials"),
    _ozellik(2, "Primary color", ["Yellow", "Beige", "White"]),
    _ozellik(3, "Sleeve length", ["Short sleeve", "Long sleeve"]),
    _ozellik(4, "Clothing closure", ["Pullover", "Full zip"], coklu=True),
    _ozellik(5, "Holiday", ["Christmas", "Thanksgiving", "Father's Day"]),
    _ozellik(6, "Occasion", ["Birthday", "Retirement"]),
    _ozellik(7, "Clothing graphic", ["Humorous saying", "Phrase & saying"]),
    _ozellik(513, "Custom1", [], attr=False),
]


def test_cozumle_ad_esler_tek_degerliye_ilkini_yazar_bilinmeyeni_atlar():
    hedef, atlanan = oznitelik.cozumle(
        {
            "Materials": ["Cotton", "Polyester"],
            "Holiday": ["Christmas", "Thanksgiving"],
            "Neckline": ["Crew"],
            "Occasion": ["Moving"],
        },
        TAKSONOMI,
    )
    assert hedef == {1: ([100, 101], ["Cotton", "Polyester"]), 5: ([500], ["Christmas"])}
    assert atlanan == ["Neckline", "Occasion=['Moving']"]
    assert oznitelik.cozumle({"Custom1": ["x"]}, TAKSONOMI)[0] == {}  # öznitelik olmayan (varyant) özellik yazılmaz


def test_etsy_ozellik_yaz_form_dizisi_virgullu(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps({"access_token": "a", "bitis": 9e12}))
    istekler = []

    def isle(r: httpx.Request):
        istekler.append(r)
        return httpx.Response(200, json={"results": TAKSONOMI} if r.method == "GET" else {})

    e = etsy_mod.Etsy(
        "ks", "sec", "777", http=httpx.Client(transport=httpx.MockTransport(isle)), token_dosyasi=tmp_path / "t.json"
    )
    e.ozellik_yaz(9, 1, [100, 101], ["Cotton", "Polyester"])
    r = istekler[0]
    assert r.method == "PUT" and r.url.path.endswith("/shops/777/listings/9/properties/1")
    assert dict(httpx.QueryParams(r.content.decode())) == {"value_ids": "100,101", "values": "Cotton,Polyester"}
    e.taksonomi_ozellikleri(482)
    e.taksonomi_ozellikleri(482)
    assert [x.url.path for x in istekler[1:]] == ["/v3/application/seller-taxonomy/nodes/482/properties"]  # bir kez okunur


class SahteEtsy:
    def __init__(self, dus: set[int] = frozenset()):
        self.yazilan, self.silinen, self.dus = [], [], dus

    def ilan(self, lid):
        if lid in self.dus:
            raise RuntimeError("etsy düştü")
        return {"taxonomy_id": 482}

    def taksonomi_ozellikleri(self, tax):
        return TAKSONOMI

    def ozellik_yaz(self, lid, pid, ids, adlar):
        self.yazilan.append((lid, pid, adlar))

    def ozellik_sil(self, lid, pid):
        self.silinen.append((lid, pid))


def _aktif(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "o.db")
    c = db.baglan()
    for n, nis in enumerate(["fishing", "knitting"]):
        i = db.ifade_ekle(c, nis, [f"S{n}"])
        db.kapi_yaz(c, i, "temiz", [], [])
        t = db.tasarim_ekle(c, i, "yigin", [])
        c.execute("INSERT INTO urun (tasarim_id, urun, durum, etsy_listing_id) VALUES (?, 'hoodie', 'aktif', ?)", (t, 100 + n))
    c.execute("INSERT INTO urun (tasarim_id, urun, durum) VALUES (1, 'tisort', 'printify')")  # Etsy'de değil: dokunulmaz
    c.commit()
    return c


def test_esitleme_bir_kez_yazar_mevsim_bitince_siler(tmp_path, monkeypatch):
    c, e = _aktif(tmp_path, monkeypatch), SahteEtsy()
    sessiz = lambda *_: None  # noqa: E731
    assert yayin.oznitelikleri_esitle(c, e, gun=EKIM, yazdir=sessiz) == {"yazilan": 2, "hata": 0}
    assert {(lid, pid) for lid, pid, _ in e.yazilan} >= {(100, 4), (100, 5), (101, 5)}  # kapanış + Christmas
    assert (100, 5, ["Christmas"]) in e.yazilan
    n = len(e.yazilan)
    assert yayin.oznitelikleri_esitle(c, e, gun=EKIM, yazdir=sessiz)["yazilan"] == 0 and len(e.yazilan) == n  # değişmedi
    assert yayin.oznitelikleri_esitle(c, e, gun=TEMMUZ, yazdir=sessiz)["yazilan"] == 2
    assert sorted(e.silinen) == [(100, 5), (101, 5)]  # Christmas kalkar


def test_esitleme_hatasi_digerlerini_durdurmaz_ve_siniri_uyar(tmp_path, monkeypatch):
    c = _aktif(tmp_path, monkeypatch)
    s = yayin.oznitelikleri_esitle(c, SahteEtsy(dus={100}), gun=EKIM, yazdir=lambda *_: None)
    assert s == {"yazilan": 1, "hata": 1}
    assert yayin.oznitelikleri_esitle(c, SahteEtsy(), gun=EKIM, sinir=0, yazdir=lambda *_: None) == {
        "yazilan": 0,
        "hata": 0,
        "kalan": 1,  # düşen ilan ertesi koşuya kalır
    }


class SahteEtsyVitrin:
    def __init__(self, bolumler=None):
        self.guncellenen, self.bolumler = [], bolumler or {"Fishing": 1, "Knitting & Crochet": 2}

    def bolum_kimligi(self, baslik):
        if baslik not in self.bolumler:  # bölüm açmak shops_w ister
            raise ApiHatasi(403, "Access token lacks scope for this request (requires scope: shops_w)", "POST")
        return self.bolumler[baslik]

    def ilan_guncelle(self, lid, **alanlar):
        self.guncellenen.append((lid, alanlar))


def test_vitrin_nis_bolumu_ve_otomatik_yenileme_bir_kez(tmp_path, monkeypatch):
    c, e = _aktif(tmp_path, monkeypatch), SahteEtsyVitrin()
    assert yayin.vitrin_esitle(c, e, yazdir=lambda *_: None) == {"yazilan": 2, "hata": 0}
    assert e.guncellenen == [
        (100, {"shop_section_id": 1, "should_auto_renew": "true"}),
        (101, {"shop_section_id": 2, "should_auto_renew": "true"}),
    ]
    assert yayin.vitrin_esitle(c, e, yazdir=lambda *_: None)["yazilan"] == 0 and len(e.guncellenen) == 2


def test_etsy_bolum_yoksa_acilir_varsa_kullanilir(tmp_path):
    (tmp_path / "t.json").write_text(json.dumps({"access_token": "a", "bitis": 9e12}))
    istekler = []

    def isle(r: httpx.Request):
        istekler.append((r.method, r.content.decode()))
        if r.method == "GET":
            return httpx.Response(200, json={"count": 1, "results": [{"shop_section_id": 7, "title": "Fishing"}]})
        return httpx.Response(201, json={"shop_section_id": 8, "title": "Bowling"})

    e = etsy_mod.Etsy(
        "ks", "sec", "777", http=httpx.Client(transport=httpx.MockTransport(isle)), token_dosyasi=tmp_path / "t.json"
    )
    assert [e.bolum_kimligi("Fishing"), e.bolum_kimligi("Bowling"), e.bolum_kimligi("Bowling")] == [7, 8, 8]
    assert istekler == [("GET", ""), ("POST", "title=Bowling")]  # liste bir kez, bölüm bir kez açılır


def test_vitrin_bolum_yetkisi_yoksa_yalniz_yenileme_sonra_bolum(tmp_path, monkeypatch):
    c, e = _aktif(tmp_path, monkeypatch), SahteEtsyVitrin({"Fishing": 1})
    s = yayin.vitrin_esitle(c, e, yazdir=lambda *_: None)
    assert s["yazilan"] == 2 and s["hata"] == 0 and "shops_w" in s["bolum_yok"]
    assert e.guncellenen == [
        (100, {"should_auto_renew": "true", "shop_section_id": 1}),
        (101, {"should_auto_renew": "true"}),  # yenileme bölümü beklemez
    ]
    assert yayin.vitrin_esitle(c, e, yazdir=lambda *_: None)["yazilan"] == 0 and len(e.guncellenen) == 2  # yinelenmez
    e.bolumler["Knitting & Crochet"] = 2  # yetki geldi ya da bölüm elle açıldı
    assert yayin.vitrin_esitle(c, e, yazdir=lambda *_: None)["yazilan"] == 1
    assert e.guncellenen[-1] == (101, {"should_auto_renew": "true", "shop_section_id": 2})
