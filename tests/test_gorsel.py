"""İlan fotoğrafları: vitrin mockup'ı renkle seçilir ve başa alınır, kendi görsellerimiz doğru sıraya ve sınır içinde eklenir."""

from __future__ import annotations

from PIL import Image

from matbaa.ilan import gorsel
from matbaa.tasarim import render
from matbaa.tasarim.sablonlar import Yazi, yigin


def _mockup(renk: str) -> Image.Image:
    img = Image.new("RGB", (570, 570), "#ffffff")
    img.paste(Image.new("RGB", (300, 420), renk), (135, 100))  # tişört gövdesi
    return img


class SahteEtsy:
    def __init__(self, renkler):
        self.gorseller = [{"listing_image_id": 100 + i, "rank": i + 1, "url_570xN": r} for i, r in enumerate(renkler)]
        self.siralanan, self.yuklenen, self.silinen, self.altlar = [], [], [], {}

    def ilan_gorselleri(self, listing_id):
        return list(self.gorseller)

    def gorsel_sil(self, listing_id, image_id):
        self.silinen.append(image_id)
        self.gorseller = [g for g in self.gorseller if g["listing_image_id"] != image_id]

    def gorsel_sirala(self, listing_id, image_id, rank, alt=""):
        self.siralanan.append((image_id, rank))
        self.altlar[image_id] = alt

    def gorsel_yukle(self, listing_id, png, rank, ad, alt):
        assert png[:2] == b"\xff\xd8" and alt  # JPEG ve alt metin
        self.yuklenen.append((ad.removesuffix(".jpg"), rank))
        return {"listing_image_id": 900 + len(self.yuklenen)}


def _tasarim(tmp_path):
    yol = tmp_path / "koyu.png"
    render.goruntu(yigin([Yazi("GONE FISHING", "Anton-Regular.ttf")]).svg("#1d1d1f")).save(yol)
    return yol


def _dosyalar(tmp_path):
    p = _tasarim(tmp_path)
    return {"koyu_png": p, "acik_png": p}


def test_vitrin_rengi_basa_alinir_kendi_gorseller_sona(tmp_path):
    renkler = ["#ffffff", "#f0e8d6", "#f3dfa2", "#4a4a48", "#1b1b1b", "#1f2a44"]  # White, Ivory, Butter, Pepper, Black, Navy
    e = SahteEtsy(renkler)
    s = gorsel.ilana_ekle(e, 1, "tisort", _dosyalar(tmp_path), indir=_mockup)
    vitrin = (
        100
        + {"White": 0, "Ivory": 1, "Butter": 2, "Pepper": 3, "Black": 4, "Navy": 5}[gorsel.urunler()["tisort"]["vitrin_rengi"]]
    )
    sira = [gid for gid, _ in e.siralanan]
    assert [r for _, r in e.siralanan] == list(range(1, 11))  # her görsel tek ve ardışık rank alır
    assert sira[0] == vitrin and sira[1] == 901  # vitrin mockup'ı, sonra yakın plan
    assert sira[2:7] == [g for g in range(100, 106) if g != vitrin] and sira[7:] == [902, 903, 904]
    assert s["eklenen"] == ["yakin-plan", "beden", "renkler", "guven"]


def test_kopya_mockuplar_silinir_kartlar_eklenir(tmp_path):
    e = SahteEtsy(["#ffffff", "#1b1b1b"] * 9)  # Printify her varyantın setini ayrı yükler
    s = gorsel.ilana_ekle(e, 1, "tisort", _dosyalar(tmp_path), indir=_mockup)
    assert s["silinen"] == list(range(102, 118)) and e.silinen == s["silinen"]
    assert s["eklenen"] == ["yakin-plan", "beden", "renkler", "guven"]
    assert len(e.siralanan) == 6 and not {gid for gid, _ in e.siralanan} & set(s["silinen"])


def test_alt_metni_silinmis_kart_goruntusunden_taninir(tmp_path):
    dos = _dosyalar(tmp_path)
    kart = {f"kart:{ad}": img for ad, img, _ in gorsel.ilan_gorselleri("tisort", dos)}
    e = SahteEtsy(["#ffffff", "#1b1b1b", "kart:guven", "kart:guven"])  # Etsy sıralamada alt metni sildi; kart iki kez yüklenmiş
    s = gorsel.ilana_ekle(e, 1, "tisort", dos, indir=lambda u: kart.get(u) or _mockup(u))
    assert s["onceden"] == ["guven"] and s["silinen"] == [103] and s["eklenen"] == ["yakin-plan", "beden", "renkler"]
    assert e.altlar[102] == "Printed to order in the USA with free US shipping"  # sıralama alt metni yeniden yazar
    assert e.altlar[100] == "" and all(e.altlar[900 + i] for i in (1, 2, 3))


def test_yer_yoksa_sondaki_mockuplar_kartlara_yer_acar(tmp_path):
    e = SahteEtsy([f"#{v:02x}{v:02x}{v:02x}" for v in range(16, 244, 12)])  # 19 farklı mockup
    s = gorsel.ilana_ekle(e, 1, "tisort", _dosyalar(tmp_path), indir=_mockup)
    assert len(s["silinen"]) == 3 and s["vitrin"] not in s["silinen"] and 100 not in s["silinen"]
    assert s["eklenen"] == ["yakin-plan", "beden", "renkler", "guven"] and len(e.siralanan) == 20
