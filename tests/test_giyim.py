"""Giyilmiş ürün videosu (K-35): ComfyUI istemcisi (kuyruk, geçmiş, hata), tişört bulma, baskı yerleştirme ve OCR kapısı.
Gerçek ComfyUI ya da model yok: sahte HTTP, sentetik "tişörtlü insan" görseli."""

from __future__ import annotations

import io
import json

import httpx
import numpy as np
import pytest
from PIL import Image, ImageDraw

from matbaa import giyim
from matbaa.tasarim import render
from matbaa.tasarim.sablonlar import Yazi, yigin

BUTTER = "#f3dfa2"


def _baski(metin: str) -> Image.Image:
    return render.goruntu(yigin([Yazi(metin, "Anton-Regular.ttf", 0.02)]).svg("#1d1d1f", None))


def _insan() -> tuple[Image.Image, np.ndarray]:
    """Sentetik kare + tişört maskesi (gerçekte SAM verir): koyu zemin, baş, ortada kameraya dönük düz tişört, kırışık gölgesi."""
    img = Image.new("RGB", (giyim.FOTO_G, giyim.FOTO_Y), "#3b4a3f")
    d = ImageDraw.Draw(img)
    d.ellipse((300, 120, 468, 330), fill="#c99a7a")
    govde = [
        (170, 420),
        (598, 420),
        (690, 640),
        (610, 680),
        (590, 600),
        (590, 1344),
        (178, 1344),
        (178, 600),
        (158, 680),
        (78, 640),
    ]
    d.polygon(govde, fill=BUTTER)
    d.line((300, 800, 470, 1100), fill="#e6d193", width=30)  # kumaş kırışığı (biraz daha koyu)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon(govde, fill=255)
    return img, np.asarray(m) > 0


def test_gogus_ortada_baski_yerlesir_tasmaz_ve_okunur():
    foto, maske = _insan()
    cx, ust, gen = giyim.gogus(maske)
    assert abs(cx - giyim.FOTO_G / 2) < 20 and 420 < ust < 700 and 150 < gen < 360
    sonuc, tasma = giyim.baski_yerlestir(foto, maske, _baski("GONE FISHING"), (cx, ust, gen))
    assert tasma < giyim.TASMA_MAKS
    a = np.asarray(sonuc).astype(int)
    assert (np.abs(a - np.asarray(foto).astype(int)).sum(axis=2) > 30)[~maske].mean() < 0.001  # baskı tişörtün dışına taşmaz
    buyuk = sonuc.crop((round(cx - gen), round(ust - 40), round(cx + gen), round(ust + gen))).resize((1200, 1200))
    assert giyim.gecer(giyim.slogan_puani(buyuk, ["GONE FISHING"], olcekler=(1200,)))
    # Kol göğsün önündeyse (maskede delik) baskının bir kısmı kumaşa düşmez: taşma büyür, aday elenir
    kollu = maske.copy()
    kollu[round(ust) : round(ust + gen * 0.5), round(cx - gen / 2) : round(cx)] = False
    assert giyim.baski_yerlestir(foto, kollu, _baski("GONE FISHING"), (cx, ust, gen))[1] > giyim.TASMA_MAKS


def test_kameraya_donuk_olmayan_ya_da_tisortsuz_aday_elenir():
    bos = np.zeros((giyim.FOTO_Y, giyim.FOTO_G), bool)
    assert giyim.gogus(bos) is None
    yan = np.zeros_like(bos)
    yan[500:1344, 20:260] = True  # kadrajın kenarında
    assert giyim.gogus(yan) is None


def test_ocr_kapisi_bozuk_slogani_durdurur():
    def gorsel(metin):
        z = Image.new("RGBA", (4500, 5400), BUTTER)
        z.alpha_composite(_baski(metin))
        return z.crop((0, 0, 4500, 1600))

    assert giyim.gecer(giyim.slogan_puani(gorsel("GONE FISHING"), ["GONE FISHING"]))
    assert not giyim.gecer(giyim.slogan_puani(gorsel("GONF FISHNG"), ["GONE FISHING"]))  # modelin tipik harf kayması


def test_comfy_kuyruga_koyar_bekler_ciktiyi_indirir_hatayi_yukseltir():
    png = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(png, "PNG")
    gecmis = iter(
        [
            {},
            {"p1": {"status": {"completed": False}}},
            {
                "p1": {
                    "status": {"completed": True},
                    "outputs": {"7": {"images": [{"filename": "a.png", "subfolder": "matbaa", "type": "output"}]}},
                }
            },
        ]
    )

    def isle(r: httpx.Request):
        if r.url.path == "/prompt":
            assert json.loads(r.content)["prompt"]["1"]["class_type"] == "CheckpointLoaderSimple"
            return httpx.Response(200, json={"prompt_id": "p1"})
        if r.url.path.startswith("/history/"):
            return httpx.Response(200, json=next(gecmis))
        if r.url.path == "/view":
            assert r.url.params["subfolder"] == "matbaa"
            return httpx.Response(200, content=png.getvalue())
        return httpx.Response(200, json={})

    c = giyim.Comfy(http=httpx.Client(transport=httpx.MockTransport(isle), base_url="http://127.0.0.1:8188"), uyu=lambda s: None)
    dosyalar = c.calistir(giyim.foto_akisi("p", 1))
    assert Image.open(io.BytesIO(c.indir(dosyalar[0]))).size == (8, 8)

    hata = {
        "p2": {"status": {"status_str": "error", "messages": [["execution_error", {"exception_message": "CUDA out of memory"}]]}}
    }

    def isle2(r):
        return httpx.Response(200, json={"prompt_id": "p2"} if r.url.path == "/prompt" else hata)

    c = giyim.Comfy(http=httpx.Client(transport=httpx.MockTransport(isle2)), uyu=lambda s: None)
    with pytest.raises(giyim.ComfyHatasi, match="out of memory"):
        c.calistir(giyim.video_akisi("x.png", 1))


def test_kamera_hareketi_baskiyi_bozmaz():
    foto, _ = _insan()
    kareler = giyim.kamera_hareketi(foto, sure=1.0, fps=10)
    assert len(kareler) == 10 and kareler[0].size == foto.size
    assert np.abs(np.asarray(kareler[0]).astype(int) - np.asarray(foto).astype(int)).mean() < 2  # ilk kare fotoğrafın kendisi
