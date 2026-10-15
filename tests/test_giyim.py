"""Giyilmiş ürün videosu (K-35 denemesi): kie.ai istemcisi (gövdedeki hata kodu, görev bekleme) ve sloganın OCR kapısı."""

from __future__ import annotations

import json

import httpx
import pytest
from PIL import Image

from matbaa import giyim
from matbaa.tasarim import render
from matbaa.tasarim.sablonlar import Yazi, yigin


def _kie(isle):
    return giyim.Kie("anahtar", http=httpx.Client(transport=httpx.MockTransport(isle)), uyu=lambda s: None)


def test_kie_gorev_bekler_sonuc_adreslerini_doner_govdedeki_hatayi_yukseltir():
    durumlar = iter(["waiting", "generating", "success"])

    def isle(r: httpx.Request):
        assert r.headers["authorization"] == "Bearer anahtar"
        if r.url.path.endswith("createTask"):
            assert json.loads(r.content)["model"] == "veo-3-1"
            return httpx.Response(200, json={"code": 200, "data": {"taskId": "t1"}})
        d = {"state": next(durumlar), "resultJson": json.dumps({"resultUrls": ["https://x/v.mp4"]})}
        return httpx.Response(200, json={"code": 200, "data": d})

    k = _kie(isle)
    assert k.bekle(k.gorev("veo-3-1", {"prompt": "p"})) == ["https://x/v.mp4"]
    k = _kie(lambda r: httpx.Response(200, json={"code": 402, "msg": "Credits insufficient"}))  # hata HTTP 200 gövdesinde
    with pytest.raises(giyim.KieHatasi, match="402"):
        k.gorev("veo-3-1", {})
    k = _kie(lambda r: httpx.Response(200, json={"code": 200, "data": {"state": "fail", "failMsg": "nsfw"}}))
    with pytest.raises(giyim.KieHatasi, match="nsfw"):
        k.bekle("t2")
    with pytest.raises(giyim.KieHatasi, match="KIE_API_KEY"):
        giyim.Kie(anahtar="")


def test_ocr_kapisi_birebir_slogani_gecirir_bozuk_slogani_durdurur():
    def gorsel(metin: str) -> Image.Image:
        c = yigin([Yazi(metin, "Anton-Regular.ttf", 0.02)])
        img = render.goruntu(c.svg("#1d1d1f", None))
        zemin = Image.new("RGBA", img.size, "#f3dfa2")
        zemin.alpha_composite(img)
        return zemin.crop((0, 0, 4500, 1600))

    assert giyim.gecer(giyim.slogan_puani(gorsel("GONE FISHING"), ["GONE FISHING"]))
    bozuk = giyim.slogan_puani(gorsel("GONF FISHNG"), ["GONE FISHING"])  # modelin tipik harf kayması
    assert not giyim.gecer(bozuk) and bozuk[0] < giyim.TAM_ESIK
