"""Giyilmiş ürün videosu (K-35 denemesi, 2026-10-15): tişörtü bir insanın üzerinde gösteren kısa TikTok videosu, yerel ComfyUI.

Scryne: ürünü insan üstünde görmek alıcıya daha güvenli hissettiriyor; üretim ücretsiz ve yerel olsun (ComfyUI, RTX 4060 8 GB).

Neden baskıyı model çizmiyor: yerel modeller giysideki yazıyı harf harf koruyamıyor, ücretli modeller için de bağımsız ölçüm yok
(araştırma 2026-10-15). Zincir bu yüzden ters kurulu, slogan her zaman birebir:
1. Fotoğraf (RealVisXL V5, SDXL): nişe uygun sahnede **baskısız** vitrin renginde tişört giyen, kameraya dönük insan. Birkaç
   aday üretilir; tişörtü en geniş ve en simetrik görünen seçilir.
2. Baskı yerleştirme (kod): tişört SAM 2 ile bölütlenir, göğüs bölgesine kendi baskı dosyamız oturur; kumaşın ışığı çarpımla, kırışıklığı
   parlaklık eğiminden küçük bir bükmeyle baskıya geçer (mockup tekniği). OCR kapısı sloganın okunduğunu doğrular.
3. Hareket (Wan 2.2 TI2V 5B, ilk kareden video): yalnız hafif hareket istenir; örnek kareler OCR'dan geçer. Baskı bozulursa
   video yerine fotoğrafın üstünde kamera yakınlaşması kullanılır (her zaman güvenli).
4. Sonuna markanın kapanış kartı (`tiktok.kapanis`).

Model lisansları: RealVisXL OpenRAIL++, Wan 2.2 Apache-2.0 (ikisi de ticari kullanıma açık). Gerçekçi yapay zekâ insanı içeren
video TikTok'ta "AI ile oluşturulmuş içerik" etiketiyle paylaşılır; Etsy ilanına girmez (ilk görsel gerçek ürün kuralı).
"""

from __future__ import annotations

import io
import json
import random
import re
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
from PIL import Image
from scipy import ndimage

from matbaa.ayar import KOK

COMFY = "http://127.0.0.1:8188"
CIKTI = KOK / "calisma" / "giyim"
FOTO_MODEL = "RealVisXL_V5.0_fp16.safetensors"
VIDEO_MODEL, VIDEO_TE, VIDEO_VAE = (
    "wan2.2_ti2v_5B_fp16.safetensors",
    "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "wan2.2_vae.safetensors",
)
FOTO_G, FOTO_Y = 768, 1344  # SDXL'in dikey kovası (~9:16)
VIDEO_G, VIDEO_Y, VIDEO_KARE, VIDEO_FPS = 704, 1280, 81, 24  # Wan 2.2 5B'nin 720p dikey çözünürlüğü, ~3,4 sn
ADAY = 4
TAM_ESIK = 0.85  # slogan kelimelerinin en az bu kadarı birebir okunmalı, gerisi en az %80 benzer
TASMA_MAKS = 0.03  # baskının en çok bu kadarı tişört dışına düşebilir (kol/el önündeyse aday elenir)
VIDEO_ESIK = 0.7  # örnek karelerin en az bu kadarında fotoğraf eşiği tutmalı (hareket bulanıklığı payı)

SAHNE = {  # niş → kim, nerede (hediye alıcısının kendini göreceği an)
    "fishing": "a cheerful grandfather in his late 60s standing on a wooden lake dock at golden hour",
    "knitting": "a smiling woman in her 40s standing in a cozy living room with yarn baskets on shelves",
    "running": "a friendly woman in her 30s standing at a park trailhead on a sunny morning",
    "pickleball": "a happy woman in her 50s standing on an outdoor pickleball court",
    "bowling": "a cheerful man in his 50s standing in a bowling alley, lanes blurred behind him",
    "band_mom": "a proud mother in her 40s standing in high school stadium bleachers on a fall evening",
    "aunt": "a laughing woman in her 30s standing in a bright kitchen",
    "milestone": "a smiling man in his 50s standing in a backyard with string lights",
    "senior_mom": "a proud mother in her 40s standing outside a high school on a sunny spring day",
}
NEGATIF = (
    "text, letters, words, logo, print, graphic, pattern, stripes, embroidery, pocket, jacket, open shirt, crossed arms, "
    "hands on chest, holding objects in front of the body, side view, back view, cropped head, blurry, deformed hands, "
    "extra fingers, cartoon, illustration, render, watermark"
)
VIDEO_ISTEMI = (
    "The person smiles, breathes and sways very slightly while standing facing the camera, natural candid moment, the camera "
    "slowly pushes in. The t-shirt and the print on the chest stay front-facing, flat and unchanged. Realistic, stable, smooth."
)
VIDEO_NEGATIF = (
    "fast motion, turning around, walking away, arms crossing, covering the chest, morphing, distorted text, blurry, flicker"
)


# --- ComfyUI ---


class ComfyHatasi(RuntimeError):
    pass


class Comfy:
    """Yerel ComfyUI API'si: iş akışı (API biçimi) kuyruğa girer, geçmişten çıktı dosyası okunur."""

    def __init__(self, adres: str = COMFY, http: httpx.Client | None = None, uyu=time.sleep):
        self.adres = adres.rstrip("/")
        self.http = http or httpx.Client(timeout=60)
        self.uyu = uyu
        self.kimlik = uuid.uuid4().hex

    def hazir_mi(self) -> bool:
        try:
            return self.http.get(f"{self.adres}/system_stats", timeout=5).status_code == 200
        except httpx.HTTPError:
            return False

    def yukle(self, img: Image.Image, ad: str) -> str:
        b = io.BytesIO()
        img.save(b, "PNG")
        r = self.http.post(
            f"{self.adres}/upload/image", files={"image": (ad, b.getvalue(), "image/png")}, data={"overwrite": "true"}
        )
        r.raise_for_status()
        return r.json()["name"]

    def calistir(self, akis: dict, sure: float = 3600, aralik: float = 3) -> list[dict]:
        """İş akışını kuyruğa koyar, bitince çıktı dosyalarını ({filename, subfolder, type}) döner."""
        r = self.http.post(f"{self.adres}/prompt", json={"prompt": akis, "client_id": self.kimlik})
        if r.status_code != 200:
            raise ComfyHatasi(f"iş akışı reddedildi: {r.text[:500]}")
        pid = r.json()["prompt_id"]
        son = time.monotonic() + sure
        while True:
            g = self.http.get(f"{self.adres}/history/{pid}").json().get(pid)
            if g:
                durum = g.get("status") or {}
                if durum.get("status_str") == "error":
                    mesaj = next(
                        (m[1].get("exception_message") for m in durum.get("messages", []) if m[0] == "execution_error"), ""
                    )
                    raise ComfyHatasi(f"ComfyUI hatası: {mesaj}")
                if durum.get("completed"):
                    return [
                        f
                        for cikti in g.get("outputs", {}).values()
                        for k in ("images", "gifs", "videos")
                        for f in cikti.get(k, [])
                    ]
            if time.monotonic() > son:
                raise ComfyHatasi(f"iş akışı {sure:.0f} sn'de bitmedi")
            self.uyu(aralik)

    def indir(self, f: dict) -> bytes:
        r = self.http.get(
            f"{self.adres}/view",
            params={"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f.get("type", "output")},
        )
        r.raise_for_status()
        return r.content


def foto_akisi(olumlu: str, tohum: int, adet: int = ADAY) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": FOTO_MODEL}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": olumlu, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIF, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": FOTO_G, "height": FOTO_Y, "batch_size": adet}},
        "5": {"class_type": "KSampler", "inputs": {
            "model": ["1", 0], "seed": tohum, "steps": 30, "cfg": 5.0, "sampler_name": "dpmpp_2m_sde", "scheduler": "karras",
            "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "matbaa/foto"}},
    }  # fmt: skip


def video_akisi(goruntu: str, tohum: int) -> dict:
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": VIDEO_MODEL, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": VIDEO_TE, "type": "wan", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": VIDEO_ISTEMI, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": VIDEO_NEGATIF, "clip": ["2", 0]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": goruntu}},
        "8": {"class_type": "Wan22ImageToVideoLatent", "inputs": {
            "vae": ["3", 0], "width": VIDEO_G, "height": VIDEO_Y, "length": VIDEO_KARE, "batch_size": 1, "start_image": ["7", 0]}},
        "9": {"class_type": "KSampler", "inputs": {
            "model": ["4", 0], "seed": tohum, "steps": 20, "cfg": 5.0, "sampler_name": "uni_pc", "scheduler": "simple",
            "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["8", 0], "denoise": 1.0}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "matbaa/video_kare"}},
    }  # fmt: skip


def foto_istemi(nis: str, renk: str) -> str:
    sahne = SAHNE.get(nis, "a smiling adult standing outdoors on a sunny day")
    return (
        f"candid smartphone photo, {sahne}, wearing a plain solid {renk} crew neck t-shirt with nothing printed on it, "
        "standing straight and facing the camera, arms relaxed at the sides, the whole chest clearly visible, waist-up framing "
        "with some headroom above the head, "
        "natural light, realistic skin texture, shallow depth of field, photorealistic"
    )


# --- tişört ve baskı yerleştirme ---


def _comfy_python() -> Path:
    import os

    kok = Path(os.environ.get("MATBAA_COMFY") or Path.home() / "ComfyUI")
    return kok / ".venv" / "Scripts" / "python.exe"


def tisort_maskesi(foto_yolu: Path) -> np.ndarray:
    """SAM 2.1 (Apache-2.0) ile tişört: göğüs ve karın noktasından bölütleme, ComfyUI'nin Python ortamında (`scripts/tisort_bolutle.py`).

    Renk eşiği yetmedi (2026-10-15 ilk deneme): gün batımında gökyüzü ve yüz tişört rengine kaydı, baskı yüze oturdu; kumaşın rengi
    de göğüsten bele ışıkla değişiyor. SAM dört adayın dördünde tişörtü gökyüzü, yüz ve kollar olmadan ayırdı."""
    cikis = foto_yolu.with_name(foto_yolu.stem + "_maske.png")
    subprocess.run(
        [str(_comfy_python()), str(KOK / "scripts" / "tisort_bolutle.py"), str(foto_yolu), str(cikis)],
        check=True, capture_output=True, env={**__import__("os").environ, "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"},
    )  # fmt: skip
    return np.asarray(Image.open(cikis)) > 127


def _orta_serit(satir: np.ndarray, x: int, bosluk: int = 6) -> tuple[int, int] | None:
    """`x`'i içeren kesintisiz True şeridi (en çok `bosluk` px'lik kopukluğa izin verir)."""
    if not satir[max(0, x - bosluk) : x + bosluk + 1].any():
        return None
    sol = sag = x
    while sol > 0 and satir[max(0, sol - bosluk) : sol].any():
        sol -= 1
    while sag < len(satir) - 1 and satir[sag + 1 : sag + 1 + bosluk].any():
        sag += 1
    return sol, sag


def gogus(maske: np.ndarray) -> tuple[float, float, float] | None:
    """Baskının yeri (merkez x, üst y, genişlik) ya da uygun değilse None: yaka = orta şeritte tişörtün başladığı satır; göğüs
    hizasında ortadan geçen kesintisiz şeridin %56'sı genişlik. Kadrajın ortasında değilse ya da gövde dar (yan duruş) elenir."""
    y_, g_ = maske.shape
    band = slice(int(g_ * 0.42), int(g_ * 0.58))
    satirlar = np.nonzero(maske[:, band].mean(axis=1) > 0.5)[0]
    if not len(satirlar):
        return None
    ust = int(satirlar.min())
    satir = min(y_ - 1, ust + int(0.14 * y_))  # göğüs hizası
    serit = _orta_serit(maske[satir], g_ // 2)
    if serit is None:
        return None
    sol, sag = serit
    gen, cx = sag - sol, (sol + sag) / 2
    if gen < g_ * 0.3 or abs(cx - g_ / 2) > g_ * 0.18:
        return None
    return cx, ust + 0.055 * y_, gen * 0.56


def baski_yerlestir(
    foto: Image.Image, maske: np.ndarray, baski: Image.Image, yer: tuple[float, float, float]
) -> tuple[Image.Image, float]:
    """Baskıyı kumaşa oturtur: ışık (çarpım) + kırışıklık bükmesi (parlaklık eğimi) + kenarlar tişört maskesiyle kırpılır.
    İkinci dönüş: baskının tişört dışına düşen (kırpılan) payı; kol ya da el göğsün önündeyse büyür, aday elenir."""
    cx, ust, gen = yer
    b = baski.convert("RGBA").crop(baski.getchannel("A").getbbox())
    k = gen / b.width
    b = b.resize((max(1, round(b.width * k)), max(1, round(b.height * k))), Image.LANCZOS)
    x0, y0 = round(cx - b.width / 2), round(ust)
    tuval = Image.new("RGBA", foto.size, (0, 0, 0, 0))
    tuval.alpha_composite(b, (max(0, x0), max(0, y0)), (max(0, -x0), max(0, -y0)))
    t = np.asarray(tuval, dtype=np.float32) / 255
    rgb = np.asarray(foto.convert("RGB"), dtype=np.float32) / 255
    parlak = ndimage.gaussian_filter(rgb.mean(axis=2), 2.0)
    ort = float(np.median(parlak[maske])) if maske.any() else 0.5
    isik = np.clip(parlak / max(ort, 1e-3), 0.55, 1.2)
    gy, gx = np.gradient(ndimage.gaussian_filter(parlak, 6.0))
    yy, xx = np.mgrid[0 : t.shape[0], 0 : t.shape[1]].astype(np.float32)
    kuvvet = 18.0  # px: kumaş kırışığı baskıyı en çok bu kadar büker
    bukul = np.stack(
        [ndimage.map_coordinates(t[..., i], [yy - gy * kuvvet * 10, xx - gx * kuvvet * 10], order=1) for i in range(4)], -1
    )
    alfa = (
        bukul[..., 3] * ndimage.gaussian_filter(maske.astype(np.float32), 1.0) * 0.96
    )  # mürekkep kumaşın dokusunu hafif gösterir
    renk = np.clip(bukul[..., :3] * isik[..., None], 0, 1)
    sonuc = rgb * (1 - alfa[..., None]) + renk * alfa[..., None]
    toplam = float(bukul[..., 3].sum())
    tasma = 1 - float((bukul[..., 3] * maske).sum()) / toplam if toplam else 1.0
    return Image.fromarray((sonuc * 255).round().astype(np.uint8)), tasma


# --- OCR kapısı ---


def _kelimeler(metin: str) -> list[str]:
    return re.findall(r"[A-Z0-9]+", metin.upper())


def slogan_puani(img: Image.Image, satirlar: list[str], olcekler=(1600, 1100)) -> tuple[float, float, list[str]]:
    """(birebir okunan kelime oranı, en az %80 benzer okunan oranı, okunmayanlar). Kapılardaki OCR ile aynı motor."""
    import difflib

    from matbaa.tasarim.kapilar import _ocr

    okunan: list[str] = []
    rgb = img.convert("RGB")
    for g in olcekler:
        k = g / max(rgb.size)
        kucuk = rgb.resize((round(rgb.width * k), round(rgb.height * k)), Image.LANCZOS) if k != 1 else rgb
        sonuc, _ = _ocr()(np.asarray(kucuk), use_cls=False)
        okunan += _kelimeler(" ".join(r[1] for r in (sonuc or [])))
    beklenen = [k for s in satirlar for k in _kelimeler(s)]
    if not beklenen:
        return 1.0, 1.0, []
    birlesik = "".join(okunan)
    tam = sum(1 for k in beklenen if k in okunan or (len(k) > 3 and k in birlesik))
    eksik = [k for k in beklenen if not (k in okunan or k in birlesik
             or any(difflib.SequenceMatcher(None, k, o).ratio() >= 0.8 for o in okunan))]  # fmt: skip
    return tam / len(beklenen), 1 - len(eksik) / len(beklenen), eksik


def gecer(puan: tuple[float, float, list[str]]) -> bool:
    return puan[0] >= TAM_ESIK and not puan[2]


# --- video ---


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def kareden_video(kareler: list[Image.Image], hedef: Path, fps: int) -> Path:
    import imageio_ffmpeg

    g, y = kareler[0].size
    yazici = imageio_ffmpeg.write_frames(str(hedef), (g, y), fps=fps, codec="libx264", pix_fmt_out="yuv420p", quality=8,
                                         macro_block_size=8)  # fmt: skip
    yazici.send(None)
    for k in kareler:
        yazici.send(np.ascontiguousarray(np.asarray(k.convert("RGB"))))
    yazici.close()
    return hedef


def kamera_hareketi(foto: Image.Image, sure: float = 5.0, fps: int = 30) -> list[Image.Image]:
    """Video modeli baskıyı bozduğunda güvenli yedek: fotoğrafın üstünde yavaş yakınlaşma (baskı piksel piksel aynı kalır)."""
    g, y = foto.size
    n = round(sure * fps)
    kareler = []
    for i in range(n):
        z = 1.0 + 0.08 * i / n
        w, h = g / z, y / z
        kareler.append(foto.resize((g, y), Image.BICUBIC, box=((g - w) / 2, (y - h) * 0.4, (g + w) / 2, (y - h) * 0.4 + h)))
    return kareler


def kapanisla_birlestir(
    klip: Path, kapanis_png: Path, hedef: Path, kanca_png: Path | None = None, yavas: float = 1.25, kapanis_sn: float = 2.4
) -> Path:
    """Klibi 1080x1920'ye getirir (`yavas` kat ağırlaştırarak: model klibi ~3,4 sn, hafif hareket yavaşta doğal durur), üstüne
    kanca yazısını (`tiktok.etiket_katmani`, şeffaf PNG) koyar, sonuna kapanış kartı ekler. Ses yok: TikTok'ta eklenir."""
    girdiler = ["-i", str(klip), "-loop", "1", "-t", str(kapanis_sn), "-i", str(kapanis_png)]
    f = f"[0:v]setpts={yavas}*PTS,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1[k];"
    if kanca_png:
        girdiler += ["-loop", "1", "-i", str(kanca_png)]
        f += "[k][2:v]overlay=0:0:shortest=1,format=yuv420p[v0];"
    else:
        f += "[k]format=yuv420p[v0];"
    f += f"[1:v]scale=1080:1920,fps=30,format=yuv420p,setsar=1,trim=duration={kapanis_sn}[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
    subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", *girdiler, "-filter_complex", f, "-map", "[v]", "-c:v", "libx264", "-crf", "20",
         "-movflags", "+faststart", str(hedef)],
        check=True, capture_output=True,
    )  # fmt: skip
    return hedef


# --- hat ---


def uret(c, comfy: Comfy, tasarim_id: int, tohum: int | None = None, video: bool = True, yazdir=print) -> dict:
    """Tek tasarımın giyilmiş videosu → `calisma/giyim/<id>/video.mp4`; adaylar, seçim ve OCR puanları `rapor.json`."""
    from matbaa import tiktok
    from matbaa.fiyat import urunler

    if not comfy.hazir_mi():
        raise ComfyHatasi(f"ComfyUI {comfy.adres} adresinde çalışmıyor: scripts/comfy_baslat.ps1")
    t = c.execute(
        "SELECT t.id, t.dosyalar, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.id = ?",
        (tasarim_id,),
    ).fetchone()
    if t is None:
        raise ValueError(f"tasarım {tasarim_id} yok")
    satirlar, dos = json.loads(t["satirlar"]), json.loads(t["dosyalar"])
    u = urunler()["tisort"]
    vitrin = next((r for r in u["renkler"] if r["ad"] == u.get("vitrin_rengi")), u["renkler"][0])
    renk_adi = {"Butter": "pale butter yellow"}.get(vitrin["ad"], vitrin["ad"].lower())
    baski = Image.open(KOK / dos[f"{vitrin['murekkep']}_png"])
    klasor = CIKTI / f"{tasarim_id:05d}"
    klasor.mkdir(parents=True, exist_ok=True)
    tohum = tohum if tohum is not None else random.randrange(2**31)
    rapor: dict = {"tasarim": tasarim_id, "slogan": satirlar, "tohum": tohum, "adaylar": []}

    bas = time.time()
    dosyalar = comfy.calistir(foto_akisi(foto_istemi(t["nis"], renk_adi), tohum))
    rapor["foto_sn"] = round(time.time() - bas)
    secilen = None
    for i, f in enumerate(dosyalar):
        foto = Image.open(io.BytesIO(comfy.indir(f))).convert("RGB")
        foto.save(klasor / f"aday_{i + 1}.jpg", quality=92)
        yol = klasor / f"aday_{i + 1}.jpg"
        maske = tisort_maskesi(yol)
        yer = gogus(maske)
        kayit: dict = {"aday": i + 1, "tisort": round(float(maske.mean()), 3), "yer": yer and [round(v) for v in yer]}
        if yer:
            sonuc, tasma = baski_yerlestir(foto, maske, baski, yer)
            p = slogan_puani(sonuc, satirlar, olcekler=(1344, 1000))
            kayit |= {"tasma": round(tasma, 3), "tam": round(p[0], 3), "eksik": p[2]}
            sonuc.save(klasor / f"giyilmis_{i + 1}.jpg", quality=92)
            if gecer(p) and tasma <= TASMA_MAKS and (secilen is None or yer[2] > secilen[1]):
                secilen = (sonuc, yer[2], i + 1)  # en geniş göğüs: kameraya en dönük, en yakın
        rapor["adaylar"].append(kayit)
        yazdir(f"  aday {i + 1}: {kayit}")
    if secilen is None:
        (klasor / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
        raise ComfyHatasi(f"{len(dosyalar)} adayın hiçbirinde tişört kameraya dönük bulunamadı ya da baskı okunmadı")
    foto, _, rapor["secilen"] = secilen
    foto.save(klasor / "foto.png")

    klip = klasor / "klip.mp4"
    rapor["hareket"] = "kamera"
    if video:
        bas = time.time()
        ad = comfy.yukle(foto.resize((VIDEO_G, VIDEO_Y), Image.LANCZOS), f"matbaa-giyim-{tasarim_id:05d}.png")
        kareler = [
            Image.open(io.BytesIO(comfy.indir(f))).convert("RGB") for f in comfy.calistir(video_akisi(ad, tohum), sure=5400)
        ]
        rapor["video_sn"] = round(time.time() - bas)
        ornek = kareler[:: max(1, len(kareler) // 12)]
        puanlar = [slogan_puani(k, satirlar, olcekler=(1280,)) for k in ornek]
        rapor["video_gecen_kare"] = round(sum(gecer(p) for p in puanlar) / max(len(puanlar), 1), 3)
        kareden_video(kareler, klasor / "model_klip.mp4", VIDEO_FPS)
        yazdir(
            f"  video: {len(kareler)} kare, {rapor['video_sn']} sn, örnek karelerin %{rapor['video_gecen_kare'] * 100:.0f}'inde slogan birebir"
        )
        if rapor["video_gecen_kare"] >= VIDEO_ESIK:
            klip, rapor["hareket"] = klasor / "model_klip.mp4", "model"
    if rapor["hareket"] == "kamera":
        kareden_video(kamera_hareketi(foto), klip, 30)
    m = tiktok.kayitli_metin(c, tasarim_id, "giyim") or tiktok.metin_yaz(
        satirlar, t["nis"], ["T-shirt worn by a real-looking person"], onceki=tiktok.son_kancalar(c)
    )  # kendi kancası: aynı tasarımın ürün videosuyla aynı cümle iki kez paylaşılmasın
    rapor["kanca"] = m.hook
    sure = bitir(klasor, klip, KOK / dos["koyu_png"], m.hook)
    (klasor / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    tiktok.kaydet(c, tasarim_id, "giyim", klasor, m, sure, ai=True)
    return rapor


def kare_al(mp4: Path, saniye: float) -> Image.Image:
    p = subprocess.run(
        [_ffmpeg(), "-v", "error", "-ss", str(saniye), "-i", str(mp4), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    )  # fmt: skip
    return Image.open(io.BytesIO(p.stdout)).convert("RGB")


def bitir(klasor: Path, klip: Path, baski_png: Path, kanca: str) -> float:
    """Klip + kanca yazısı + kapanış kartı → `video.mp4`, ilk kareden `kapak.jpg`. Süre (sn) döner."""
    from matbaa import tiktok

    kapanis, kanca_png = klasor / "kapanis.png", klasor / "kanca.png"
    tiktok.kapanis(baski_png, "Free US shipping  ·  Made to order").save(kapanis)
    tiktok.etiket_katmani(kanca, tiktok.GUVENLI[1] + 30, 60, maks_satir=3)[0].save(kanca_png)
    hedef = kapanisla_birlestir(klip, kapanis, klasor / "video.mp4", kanca_png)
    kapak = kare_al(hedef, 1.0)
    kapak.thumbnail((360, 640))
    kapak.save(klasor / "kapak.jpg", "JPEG", quality=85)
    p = subprocess.run([_ffmpeg(), "-i", str(hedef)], capture_output=True, text=True, errors="replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", p.stderr)
    return round(int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]), 1) if m else 0.0


# --- günlük hat ---

GUNLUK = 1  # günde bir giyilmiş video: bu laptopta ~20 dk ekran kartı (fotoğraf ~1,5 dk, video ~18 dk)


def comfy_ac(comfy: Comfy) -> bool:
    """ComfyUI kapalıysa başlatır (`scripts/comfy_baslat.ps1`). Bu çağrı başlattıysa True: iş bitince `comfy_kapat`."""
    if comfy.hazir_mi():
        return False
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(KOK / "scripts" / "comfy_baslat.ps1")],
        check=True, capture_output=True, timeout=300,
    )  # fmt: skip
    if not comfy.hazir_mi():
        raise ComfyHatasi("ComfyUI başlatılamadı (bkz. ComfyUI/comfy.log)")
    return True


def comfy_kapat(port: int = 8188) -> None:
    """Bizim açtığımız ComfyUI'yi kapatır: ekran kartı ve ~10 GB bellek boşalır."""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         f"Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
         "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
        capture_output=True, timeout=60, check=False,
    )  # fmt: skip


def hazirla(c, comfy: Comfy | None = None, sinir: int = GUNLUK, yazdir=print, uretici=None) -> dict:
    """Günlük adım: giyilmiş videosu olmayan, tişörtü Etsy'de aktif tasarımlar (en eski yayın önce), en çok `sinir` tanesi.

    ComfyUI kurulu değilse adım atlanır. Üretilemeyen tasarım `hata` ile kaydedilir ve yeniden denenmez (her gün 20 dk boşa
    gitmesin); `matbaa giyim --tasarim N` elle yeniden dener."""
    if not _comfy_python().exists():
        return {"atlandi": f"ComfyUI kurulu değil ({_comfy_python().parent.parent.parent})"}
    adaylar = c.execute(
        """SELECT u.tasarim_id, min(u.guncelleme) AS ilk FROM urun u WHERE u.durum = 'aktif' AND u.urun = 'tisort'
             AND u.etsy_listing_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM tiktok_video v WHERE v.tasarim_id = u.tasarim_id AND v.tur = 'giyim')
           GROUP BY u.tasarim_id ORDER BY ilk LIMIT ?""",
        (sinir,),
    ).fetchall()
    sayac: dict = {"hazir": 0, "hata": 0}
    if not adaylar:
        return sayac
    comfy = comfy or Comfy()
    uretici = uretici or uret
    actik = comfy_ac(comfy)
    try:
        for r in adaylar:
            try:
                s = uretici(c, comfy, r["tasarim_id"], yazdir=yazdir)
            except Exception as e:
                c.execute(
                    """INSERT INTO tiktok_video (tasarim_id, tur, durum, hata, olusturma) VALUES (?, 'giyim', 'hata', ?, ?)
                       ON CONFLICT (tasarim_id, tur) DO UPDATE SET durum = 'hata', hata = excluded.hata""",
                    (r["tasarim_id"], f"{type(e).__name__}: {e}"[:500], time.strftime("%Y-%m-%dT%H:%M:%S")),
                )
                c.commit()
                sayac["hata"] += 1
                yazdir(f"  giyim hata {r['tasarim_id']}: {type(e).__name__}: {str(e)[:150]}")
                continue
            sayac["hazir"] += 1
            yazdir(f"  giyilmiş video: tasarım {r['tasarim_id']}: {s.get('kanca')}")
    finally:
        if actik:
            comfy_kapat()
    return sayac
