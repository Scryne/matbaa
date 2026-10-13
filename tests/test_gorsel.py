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
        self.siralanan, self.yuklenen = [], []

    def ilan_gorselleri(self, listing_id):
        return list(self.gorseller)

    def gorsel_sirala(self, listing_id, image_id, rank):
        self.siralanan.append((image_id, rank))

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


def test_yer_yoksa_fazlasi_eklenmez(tmp_path):
    e = SahteEtsy(["#ffffff"] * 19)
    gorsel.ilana_ekle(e, 1, "tisort", _dosyalar(tmp_path), indir=_mockup)
    assert [a for a, _ in e.yuklenen] == ["yakin-plan"]
