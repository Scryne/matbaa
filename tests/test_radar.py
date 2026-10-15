"""Niş radarı (Faz 15): fırsat = talep / log(rekabet); marka riskli ve giysi olmayan (desen) adaylar öne çıkmaz."""

from __future__ import annotations

from matbaa import radar

SIMDI = 1_800_000_000


class SahteEtsy:
    def __init__(self, veri):
        self.veri = veri  # kelime -> (ilan sayısı, görüntülenme, fiyat)

    def _i(self, yontem, yol, params):
        kelime = params["keywords"].removesuffix(" shirt")
        sayi, gor, fiyat = self.veri[kelime]
        sonuc = [
            {"views": gor, "num_favorers": gor // 20, "original_creation_timestamp": SIMDI - 100 * 86400,
             "price": {"amount": int(fiyat * 100), "divisor": 100}, "tags": [f"{kelime} gift"]}
            for _ in range(20)
        ]  # fmt: skip
        return {"count": sayi, "results": sonuc}


class SahteMarka:
    def kontrol(self, metin):
        return type("K", (), {"temiz": "riskli" not in metin})()


def test_firsat_siralamasi_marka_ve_desen_suzgeci(monkeypatch):
    ayar = {"adaylar": ["kucuk", "buyuk", "riskli", "desen"], "mevcut": ["eski"], "ek": "shirt", "ust_ilan": 100,
            "min_yas_gun": 14, "min_medyan_fiyat": 12.0}  # fmt: skip
    monkeypatch.setattr(radar, "ayar", lambda: ayar)
    veri = {"eski": (90000, 10, 25.0), "kucuk": (5000, 100, 24.0), "buyuk": (200000, 100, 24.0), "riskli": (5000, 200, 24.0),
            "desen": (5000, 300, 5.99)}  # fmt: skip
    monkeypatch.setattr(radar.time, "time", lambda: SIMDI)
    s = radar.tara(SahteEtsy(veri), SahteMarka(), bekle=lambda _: None, yazdir=lambda *_: None)
    sira = [o["kelime"] for o in s["adaylar"]]
    assert sira.index("kucuk") < sira.index("buyuk")  # aynı talepte az rekabet önde
    assert s["one_cikan"] == ["kucuk", "buyuk"]  # riskli marka ve desen dışarıda
    k = next(o for o in s["adaylar"] if o["kelime"] == "kucuk")
    assert k["talep"] == 1.0 and k["rekabet"] == 5000 and k["medyan_fiyat"] == 24.0


def test_radar_her_mevcut_nisi_olcer():
    from matbaa.ifade.uret import nisler

    mevcut = radar.ayar()["mevcut"]
    assert len(mevcut) == len(nisler())  # yeni niş kartı eklenince radar kıyas listesi de güncellenmeli
