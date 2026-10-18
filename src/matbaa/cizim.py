"""Çizimli tasarım hattı (K-37, 2026-10-18): kavram → IP kapısı → yerel çizim (FLUX.2 klein) → dekupe → vektör yazıyla kompozisyon.

Neden: Etsy trend ölçümünde hızlı büyüyen giyim ilanları sevimli çizimli karakter + kış/Noel + kahve/kitap/evcil hayvan/meslek
esprisi; yazılı tasarımlar bunlarla yarışmıyordu (Scryne: "kimse almaz"). Yerel model yazıyı harf harf koruyamıyor ("MERY
BRIGCUT"): çizim yazısız üretilir, yazıyı motor fonttan yol olarak dizer (yazım hatası imkânsız, OCR kapısı yerleşimi denetler).

Akış: `config/cizim.toml` kavramı → `kapi.denetle` (USPTO + Jev) → `ifade` (yapi: ust, alt, cizim) → ComfyUI'de `ADAY` çizim →
her aday: kenara bağlı beyaz zemin silinir (kalın dış çizgi içerideki beyazı korur), yazı/kırpık/parçalı aday elenir → üst
kavisli + alt düz yazıyla 4500x5400 baskı PNG'si → boyut/kenar/OCR kapısı → `tasarim` (`kalite_ok`). Geçen adayların hepsi
`calisma/cizim/<ifade>/`'da kalır; `sec` başka adayı baskı dosyası yapar. Sonrası mevcut hat: ilan metni, onay, yayın.
Baskı dosyası koyu ve açık anahtarlarında aynı dosyadır: çizimli ürünler (`tur = "cizim"`) yalnız açık kumaşlarda.
"""

from __future__ import annotations

import base64
import io
import json
import math
import random
import tomllib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

from matbaa import db
from matbaa.ayar import CONFIG, KOK, modeller
from matbaa.giyim import Comfy, ComfyHatasi, comfy_ac, comfy_kapat
from matbaa.tasarim import kapilar, render
from matbaa.tasarim.sablonlar import TUVAL_G, TUVAL_Y, _kavisli, _yol
from matbaa.tasarim.yazi import font

NIS = "cozy_christmas"
FONTLAR = KOK / "varliklar" / "fontlar"
CIKTI = KOK / "calisma" / "cizim"
URETIM = KOK / "uretim"
ADAY = 4
STIL = (
    "{konu}. Cute retro cartoon illustration for a t-shirt print, thick clean dark brown outlines, flat colors, limited warm "
    "vintage palette, subtle screen-print grain, single centered subject, isolated on a plain pure white background. "
    "Absolutely no text, no letters, no words, no shirt, no frame, no border."
)
BEYAZ_MIN, BEYAZ_RENK_FARKI = 232, 18  # zemin pikseli: en koyu kanal > 232 ve kanallar arası fark < 18
KENAR_PAYI = 60  # px, baskı kapısıyla aynı (kapilar)
OKUNURLUK_ESIK = 0.8


def kavramlar() -> dict[str, dict]:
    return {k["ad"]: k for k in tomllib.loads((CONFIG / "cizim.toml").read_text(encoding="utf-8"))["kavram"]}


def akis(konu: str, tohum: int) -> dict:
    """ComfyUI API iş akışı: FLUX.2 klein 4B distilled (şablon `image_flux2_klein_text_to_image`, distilled alt grafiği)."""
    m = modeller()["cizim"]
    g = m["boyut"]
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["metin_kodlayici"], "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": STIL.format(konu=konu)}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1.0}},
        "7": {"class_type": "RandomNoise", "inputs": {"noise_seed": tohum}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": m["adim"], "width": g, "height": g}},
        "10": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": g, "height": g, "batch_size": 1}},
        "11": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {"noise": ["7", 0], "guider": ["6", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["10", 0]},
        },
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "matbaa_cizim"}},
    }


# --- çizim adayı ---


def dekupe(img: Image.Image) -> Image.Image:
    """Kenara bağlı beyaz zemin saydamlaşır; dış çizginin içindeki beyaz (kardan adam gövdesi) kalır. Çizim kutusuna kırpılır."""
    rgb = img.convert("RGB")
    a = np.asarray(rgb).astype(int)
    beyaz = (a.min(axis=2) > BEYAZ_MIN) & (a.max(axis=2) - a.min(axis=2) < BEYAZ_RENK_FARKI)
    lab, _ = ndimage.label(beyaz)
    kenar = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    zemin = ndimage.binary_opening(np.isin(lab, list(kenar)), iterations=1)
    dolu = ~zemin
    lab2, n = ndimage.label(dolu)
    if n:  # zeminde kalan kırıntılar (gölge lekesi, kar tanesi tozu) atılır: alanın %0,2'sinden küçük bileşenler
        boy = ndimage.sum(np.ones_like(lab2), lab2, range(1, n + 1))
        dolu = np.isin(lab2, [i + 1 for i, b in enumerate(boy) if b > dolu.size * 0.002])
    alfa = Image.fromarray((dolu * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    rgba = rgb.convert("RGBA")
    rgba.putalpha(alfa)
    kutu = rgba.getbbox()
    return rgba.crop(kutu) if kutu else rgba


def aday_sorunlari(ham: Image.Image, kesik: Image.Image) -> list[str]:
    """Çizim adayının elenme nedenleri: kenara değen (kırpık) konu, çok küçük/çok büyük konu, parçalı konu, içinde yazı."""
    sorun = []
    a = np.asarray(ham.convert("RGB")).astype(int)
    zemin_degil = ~((a.min(axis=2) > BEYAZ_MIN) & (a.max(axis=2) - a.min(axis=2) < BEYAZ_RENK_FARKI))
    kenar = np.concatenate(
        [zemin_degil[:4].ravel(), zemin_degil[-4:].ravel(), zemin_degil[:, :4].ravel(), zemin_degil[:, -4:].ravel()]
    )
    if kenar.mean() > 0.01:
        sorun.append(f"konu kenara değiyor (%{kenar.mean() * 100:.1f})")
    alfa = np.asarray(kesik.getchannel("A")) > 128
    oran = alfa.sum() / (ham.width * ham.height)
    if not 0.08 <= oran <= 0.6:
        sorun.append(f"konu alanı %{oran * 100:.0f} (beklenen %8-60)")
    lab, n = ndimage.label(alfa)
    if n > 1:
        boy = sorted(ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)), reverse=True)
        if boy[1] > 0.08 * boy[0]:
            sorun.append(f"konu parçalı ({n} bileşen, ikincisi %{boy[1] / boy[0] * 100:.0f})")
    yazi = _yazi_var(ham)
    if yazi:
        sorun.append(f"çizimde yazı var: {yazi}")
    return sorun


def _yazi_var(ham: Image.Image) -> list[str]:
    """Model "no text" dese de harf çizebilir; 2+ harfli, güvenli okunan kelime baskıya giremez (yazım hatası, marka)."""
    sonuc, _ = kapilar._ocr()(np.asarray(ham.convert("RGB").resize((1024, 1024))), use_cls=False)
    return [r[1] for r in (sonuc or []) if r[2] >= 0.6 and sum(ch.isalpha() for ch in r[1]) >= 2]


def koyu_renk(rgba: Image.Image) -> str:
    """Çizimin dış çizgi rengi (en koyu %8'in medyanı): yazının dış çizgisi çizimle aynı elden çıkmış görünür."""
    a = np.asarray(rgba).reshape(-1, 4)
    a = a[a[:, 3] > 200][:, :3].astype(float)
    parlak = a.mean(axis=1)
    k = a[parlak <= np.percentile(parlak, 8)]
    return "#" + "".join(f"{int(x):02x}" for x in np.median(k, axis=0))


# --- kompozisyon ---


def birlestir(cizim: Image.Image, kavram: dict) -> Image.Image:
    """4500x5400 baskı: üstte kavisli satır, ortada çizim, altta düz satır; yazı dolgu renginde, çizimin çizgi rengiyle kontürlü."""
    cizgi = koyu_renk(cizim)
    fu = font(str(FONTLAR / kavram["font_ust"]))
    su = fu.satir(kavram["ust"], 0.02)
    yay = math.radians(min(75, 18 + 7 * len(kavram["ust"])))  # kısa satır az, uzun satır çok kavis
    # Kiriş %80, alt satır %86: kontur (her yanda ~90 px) ve yay ucundaki glifin dışa dönüşü kenar payını yemesin.
    olcek = min(TUVAL_G * 0.80 * yay / (2 * math.sin(yay / 2) * su.ilerleme), 560 / fu.buyuk_harf)
    r = su.ilerleme * olcek / yay
    buyuk = fu.buyuk_harf * olcek
    cy = 150 + r + buyuk
    parcalar = _kavisli(su, olcek, TUVAL_G / 2, cy, r)
    ust_alt = cy - r * math.cos(yay / 2) + buyuk * 0.25  # kavisli satırın uçlarının altı

    s = min(TUVAL_G * 0.7 / cizim.width, 2750 / cizim.height)
    cg, cy_ = int(cizim.width * s), int(cizim.height * s)
    c2 = cizim.resize((cg, cy_), Image.LANCZOS)
    b = io.BytesIO()
    c2.save(b, "PNG")
    cizim_y = max(150 + buyuk * 1.16 + 180, ust_alt - 200)
    resim = (
        f'<image x="{(TUVAL_G - cg) / 2:.0f}" y="{cizim_y:.0f}" width="{cg}" height="{cy_}" '
        f'href="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}"/>'
    )
    fa = font(str(FONTLAR / kavram["font_alt"]))
    sa = fa.satir(kavram["alt"], 0.01)
    olcek_a = min(TUVAL_G * 0.86 / sa.genislik, 760 / sa.yukseklik)
    pa, ha = _yol(sa, olcek_a, TUVAL_G / 2, cizim_y + cy_ + 110)
    parcalar.append(pa)
    kontur = 2 * max(buyuk * 0.16, ha * 0.11)
    stil = f'fill="{kavram["dolgu"]}" stroke="{cizgi}" stroke-width="{kontur:.0f}" stroke-linejoin="round" paint-order="stroke"'
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{TUVAL_G}" height="{TUVAL_Y}" viewBox="0 0 {TUVAL_G} {TUVAL_Y}">'
        f"{resim}<g {stil}>{''.join(parcalar)}</g></svg>"
    )
    return render.goruntu(svg)


def baski_sorunlari(img: Image.Image, kavram: dict) -> list[str]:
    """Baskı dosyası kapısı: tuval boyutu, kenar payı (yazı ya da çizim taşmadı), OCR ile düz alt satırın okunması. Kavisli
    üst satır OCR'a girmez (`sablonlar.kavis` ile aynı: OCR kavisli yazıyı güvenilir okumuyor, geometrisi çakışmayı önlüyor)."""
    sorun = []
    if img.size != (TUVAL_G, TUVAL_Y) or img.mode != "RGBA":
        return [f"tuval {img.size} {img.mode}"]
    kutu = img.getchannel("A").getbbox()
    if not kutu:
        return ["boş baskı"]
    x0, y0, x1, y1 = kutu
    if min(x0, y0, TUVAL_G - x1, TUVAL_Y - y1) < KENAR_PAYI:
        sorun.append(f"kenar payı < {KENAR_PAYI} px: {kutu}")
    oran, eksik = kapilar.okunurluk(img, "#3a2418", [kavram["alt"]])
    if oran < OKUNURLUK_ESIK:
        sorun.append(f"okunurluk {oran:.2f}, eksik {eksik}")
    return sorun


# --- hat ---


def _ifade(c, kavram: dict, yazdir) -> int | None:
    """Kavramın ifadesi (varsa mevcut); IP kapısı yalnız ilk kez. Kapıdan geçmezse None."""
    from matbaa.ip import kapi

    satirlar = [kavram["ust"], kavram["alt"]]
    r = c.execute(
        "SELECT id, kapi_karar FROM ifade WHERE nis = ? AND satirlar = ?", (NIS, json.dumps(satirlar, ensure_ascii=False))
    ).fetchone()
    if r and r["kapi_karar"]:
        return r["id"] if r["kapi_karar"] in ("temiz", "insan") else None
    i = (
        r["id"]
        if r
        else db.ifade_ekle(
            c, NIS, satirlar, kaynak="elle", yapi={"ust": kavram["ust"], "alt": kavram["alt"], "cizim": kavram["konu"]}
        )
    )
    k = kapi.denetle(satirlar, NIS, ana=[kavram["alt"]])
    db.kapi_yaz(c, i, k.karar, k.nedenler, k.kayit)
    c.commit()
    yazdir(f"  IP kapısı {kavram['ad']}: {k.karar} {k.nedenler[:2]}")
    return i if k.karar in ("temiz", "insan") else None


def uret(c, kavram: dict, comfy: Comfy, adet: int = ADAY, tohum: int | None = None, yazdir=print) -> dict:
    """Bir kavramdan tasarım: geçen adaylar `calisma/cizim/<ifade>/aday_N.png`, ilki baskı dosyası olur (`kalite_ok`)."""
    ifade_id = _ifade(c, kavram, yazdir)
    if ifade_id is None:
        return {"kavram": kavram["ad"], "sonuc": "ip_ret"}
    var = c.execute("SELECT id FROM tasarim WHERE ifade_id = ? AND durum != 'ret'", (ifade_id,)).fetchone()
    if var:
        return {"kavram": kavram["ad"], "sonuc": "zaten_var", "tasarim": var[0]}
    tohum = tohum if tohum is not None else random.randint(1, 2**31)
    klasor = CIKTI / f"{ifade_id:05d}"
    klasor.mkdir(parents=True, exist_ok=True)
    gecen, elenen = [], {}
    # Adaylar tek tek (tohum, tohum+1, ...): 8 GB ekran kartında 1536 px'lik toplu iş belleği taşırıp dakikalarca sürüyor.
    for n in range(adet):
        f = comfy.calistir(akis(kavram["konu"], tohum + n), sure=600)[0]
        ham = Image.open(io.BytesIO(comfy.indir(f))).convert("RGB")
        ham.save(klasor / f"ham_{n}.png")
        kesik = dekupe(ham)
        sorun = aday_sorunlari(ham, kesik)
        if not sorun:
            baski = birlestir(kesik, kavram)
            sorun = baski_sorunlari(baski, kavram)
        if sorun:
            elenen[n] = sorun
            continue
        render.kaydet(baski, klasor / f"aday_{n}.png")
        gecen.append(n)
    (klasor / "kayit.json").write_text(
        json.dumps(
            {"kavram": kavram, "tohum": tohum, "model": modeller()["cizim"], "gecen": gecen, "elenen": elenen},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    if not gecen:
        yazdir(f"  {kavram['ad']}: {adet} adayın hiçbiri geçmedi {elenen}")
        return {"kavram": kavram["ad"], "sonuc": "aday_yok", "elenen": elenen}
    t = db.tasarim_ekle(c, ifade_id, "cizim", [kavram["font_ust"], kavram["font_alt"]])
    _baski_yaz(c, t, klasor / f"aday_{gecen[0]}.png", {"aday": gecen[0], "gecen": gecen, "elenen": elenen, "tohum": tohum})
    db.gecis(c, t, "kalite_ok", f"çizim adayı {gecen[0]} ({len(gecen)}/{adet} geçti)")
    c.commit()
    yazdir(f"  {kavram['ad']}: tasarım {t}, aday {gecen} geçti, elenen {list(elenen)}")
    return {"kavram": kavram["ad"], "sonuc": "tasarim", "tasarim": t, "gecen": gecen}


def baski_kaydet(img: Image.Image, yol: Path) -> Path:
    """Baskı dosyası 256 renkli paletle: tam renkli 4500x5400 çizim ~5 MB, base64'te Printify'ın 5 MB yükleme sınırını aşıyordu
    (ilk yayında 12 tasarımın hepsi düştü). Düz renkli çizimde fark gözle seçilmiyor (ışık parıltısı hafif azalır), dosya ~1 MB."""
    img.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(yol, optimize=True)
    return yol


def _baski_yaz(c, t: int, aday: Path, kalite: dict) -> None:
    hedef = URETIM / f"{t:05d}"
    hedef.mkdir(parents=True, exist_ok=True)
    baski_kaydet(Image.open(aday), hedef / "cizim.png")
    yol = str((hedef / "cizim.png").relative_to(KOK))
    # Çizimli ürünler yalnız açık kumaşta (koyu mürekkep grubu); açık anahtarı da aynı dosya: okuyan her yer bir yol bulur.
    dosyalar = {"koyu_png": yol, "acik_png": yol}
    c.execute("UPDATE tasarim SET dosyalar = ?, kalite = ? WHERE id = ?", (json.dumps(dosyalar), json.dumps(kalite), t))


def sec(c, tasarim_id: int, aday: int) -> None:
    """Onaydan önce başka bir geçen adayı baskı dosyası yapar (ilan metni değişmez: çizim konusu ve yazı aynı)."""
    t = c.execute(
        "SELECT t.durum, t.kalite, t.ifade_id FROM tasarim t WHERE t.id = ?",
        (tasarim_id,),
    ).fetchone()
    if t is None or t["durum"] not in ("kalite_ok", "metin_ok", "onay_bekliyor"):
        raise ValueError(f"tasarım {tasarim_id} seçim için uygun değil ({t and t['durum']})")
    kalite = json.loads(t["kalite"] or "{}")
    if aday not in kalite.get("gecen", []):
        raise ValueError(f"aday {aday} geçenler arasında değil: {kalite.get('gecen')}")
    kalite["aday"] = aday
    _baski_yaz(c, tasarim_id, CIKTI / f"{t['ifade_id']:05d}" / f"aday_{aday}.png", kalite)
    db.olay(c, "tasarim", tasarim_id, None, "cizim_sec", f"aday {aday}")
    c.commit()


def hazirla(c, adlar: list[str] | None = None, adet: int = ADAY, comfy: Comfy | None = None, yazdir=print) -> list[dict]:
    """Verilen (ya da tasarımı olmayan bütün) kavramlar; ComfyUI'yi gerekirse açar, iş bitince kapatır."""
    hepsi = kavramlar()
    secilen = [hepsi[a] for a in adlar] if adlar else list(hepsi.values())
    comfy = comfy or Comfy()
    actik = comfy_ac(comfy)
    sonuc = []
    try:
        for k in secilen:
            try:
                sonuc.append(uret(c, k, comfy, adet, yazdir=yazdir))
            except (ComfyHatasi, OSError) as e:
                yazdir(f"  {k['ad']}: {type(e).__name__}: {str(e)[:200]}")
                sonuc.append({"kavram": k["ad"], "sonuc": "hata", "hata": str(e)[:200]})
    finally:
        if actik:
            comfy_kapat()
    return sonuc
