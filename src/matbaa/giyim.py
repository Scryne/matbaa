"""Giyilmiş ürün videosu (K-35 denemesi, 2026-10-15): tişörtü bir insanın üzerinde gösteren kısa TikTok videosu.

Scryne: ürünü insan üstünde görmek alıcıya daha güvenli hissettiriyor. Zincir (araştırma 2026-10-15, kie.ai tek anahtar):
1. GPT Image 2 (görselden görsele): Etsy ilanındaki vitrin mockup'ı + kendi baskı dosyamız referans → "bu tişörtü giyen insan".
2. OCR kapısı: fotoğraftaki sloganın kelimeleri birebir okunmuyorsa fotoğraf atılır, yeniden üretilir (`DENEME_FOTO`).
   Bağımsız bir ölçümde hiçbir model "giysideki yazıyı korur" diye doğrulanmadı: güvence yalnız bu kapı.
3. Veo 3.1 Fast (ilk kareden video, 9:16, 8 sn): yalnız hafif hareket istenir, yazıdan söz edilmez.
4. Video kapısı: örnek kareler OCR'dan geçer; slogan bozulan klip kullanılmaz.
5. Klibin sonuna markanın kapanış kartı eklenir (`tiktok.kapanis`).

Gerçekçi yapay zekâ insanı içeren video TikTok'ta "AI ile oluşturulmuş içerik" etiketiyle paylaşılır. Etsy ilanına girmez
(ilk görsel gerçek ürün kuralı). Maliyet (kie.ai, 2026-10): fotoğraf ~$0,05, video ~$0,30.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import time
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from matbaa.ayar import KOK
from matbaa.entegrasyon.http import KULLANICI, istek

TABAN = "https://api.kie.ai"
YUKLEME = "https://kieai.redpandaai.co/api/file-stream-upload"
CIKTI = KOK / "calisma" / "giyim"
DENEME_FOTO = 4
DENEME_VIDEO = 2
TAM_ESIK = 0.85  # fotoğraf: slogan kelimelerinin en az bu kadarı birebir okunmalı, gerisi en az %80 benzer
VIDEO_ESIK = 0.7  # video: örnek karelerin en az bu kadarında fotoğraf eşiği tutmalı (hareket bulanıklığı payı)

SAHNE = {  # niş → kim, nerede (gerçekçi, hediye alıcısının kendini göreceği an)
    "fishing": "a cheerful grandfather in his late 60s on a wooden lake dock at golden hour, fishing rod leaning nearby",
    "knitting": "a smiling woman in her 40s on a cozy living-room couch in the evening, a basket of yarn beside her",
    "running": "a friendly woman in her 30s at a park trailhead after a morning run, sneakers and a water bottle",
    "pickleball": "a happy woman in her 50s on an outdoor pickleball court holding a paddle",
    "bowling": "a cheerful man in his 50s at a bowling alley lane, bowling balls in the background",
    "band_mom": "a proud mother in her 40s in high school football stadium bleachers on a fall evening",
    "aunt": "a laughing woman in her 30s in a bright kitchen, birthday balloons in the background",
    "milestone": "a smiling man in his 50s at a backyard birthday party with string lights",
    "senior_mom": "a proud mother in her 40s outside a high school on a sunny spring day",
}


class KieHatasi(RuntimeError):
    pass


class Kie:
    """kie.ai istemcisi: dosya yükleme, görev açma, görev bekleme. Hata kodu HTTP 200 gövdesinde gelir (docs.kie.ai): `code`
    denetlenir."""

    def __init__(self, anahtar: str | None = None, http: httpx.Client | None = None, uyu=time.sleep):
        anahtar = anahtar or os.environ.get("KIE_API_KEY")
        if not anahtar:
            raise KieHatasi("KIE_API_KEY yok: kie.ai/api-key'den alınıp .env'e yazılmalı")
        self.http = http or httpx.Client(timeout=120)
        self.http.headers.update({"Authorization": f"Bearer {anahtar}", "User-Agent": KULLANICI})
        self.uyu = uyu

    @staticmethod
    def _veri(r: httpx.Response) -> dict:
        j = r.json()
        if j.get("code") != 200:
            raise KieHatasi(f"kie.ai {j.get('code')}: {j.get('msg')}")
        return j.get("data") or {}

    def yukle(self, veri: bytes, ad: str) -> str:
        """Yerel dosya → geçici herkese açık adres (kie.ai'nin model girdisi URL ister)."""
        r = istek(self.http, "POST", YUKLEME, tekrar_5xx=False, files={"file": (ad, veri)},
                  data={"uploadPath": "matbaa", "fileName": ad})  # fmt: skip
        return self._veri(r)["downloadUrl"]

    def gorev(self, model: str, girdi: dict) -> str:
        r = istek(self.http, "POST", f"{TABAN}/api/v1/jobs/createTask", tekrar_5xx=False, json={"model": model, "input": girdi})
        return self._veri(r)["taskId"]

    def bekle(self, gorev_id: str, sure: float = 900, aralik: float = 8) -> list[str]:
        """Görev bitene kadar sorar; sonuç adresleri (`resultJson.resultUrls`)."""
        son = time.monotonic() + sure
        while True:
            d = self._veri(istek(self.http, "GET", f"{TABAN}/api/v1/jobs/recordInfo", params={"taskId": gorev_id}))
            durum = str(d.get("state") or "").lower()
            if durum == "success":
                return list(json.loads(d.get("resultJson") or "{}").get("resultUrls") or [])
            if durum == "fail":
                raise KieHatasi(f"görev {gorev_id} düştü: {d.get('failMsg') or d.get('failCode')}")
            if time.monotonic() > son:
                raise KieHatasi(f"görev {gorev_id} {sure:.0f} sn'de bitmedi (durum {durum})")
            self.uyu(aralik)

    def indir(self, url: str) -> bytes:
        return istek(self.http, "GET", url, follow_redirects=True).content


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
        kucuk = rgb.resize((round(rgb.width * k), round(rgb.height * k)), Image.LANCZOS) if k < 1 else rgb
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


# --- istemler ---


def foto_istemi(satirlar: list[str], nis: str, renk: str) -> str:
    sahne = SAHNE.get(nis, "a smiling adult outdoors on a sunny day")
    slogan = " / ".join(satirlar)
    return (
        f"Photorealistic vertical lifestyle photo for a short social video: {sahne}, wearing the exact {renk.lower()} "
        "garment-dyed t-shirt from the first image. The chest print must be identical to the second image: same layout, same "
        f'illustration, same colors, and exactly this text spelled letter for letter: "{slogan}". The print is centered on the '
        "chest, flat and fully visible, facing the camera, not covered by arms, hair or objects, not cropped. Waist-up framing, "
        "natural light, candid smartphone photo look, shallow depth of field. No other text, logos or watermarks anywhere."
    )


VIDEO_ISTEMI = (
    "Subtle natural motion: the person smiles, breathes and shifts slightly while staying facing the camera; the camera "
    "slowly pushes in. The t-shirt and its printed design stay front-facing, flat and unchanged the whole time. Gentle ambient "
    "background sound, no speech, no music with lyrics, no on-screen text."
)


# --- hat ---


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def video_kareleri(mp4: Path, aralik: float = 0.5) -> list[Image.Image]:
    """Videodan her `aralik` saniyede bir kare (OCR kapısı için)."""
    p = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", str(mp4), "-vf", f"fps={1 / aralik}", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    )  # fmt: skip
    kareler, b = [], p.stdout
    imza = b"\x89PNG\r\n\x1a\n"
    for parca in [x for x in b.split(imza) if x]:
        kareler.append(Image.open(io.BytesIO(imza + parca)).convert("RGB"))
    return kareler


def kapanisla_birlestir(klip: Path, kapanis_png: Path, hedef: Path, kapanis_sn: float = 2.4) -> Path:
    """Klibi 1080x1920'ye getirir, sonuna sessiz kapanış kartı ekler (klibin sesi korunur, kart boyunca sessizlik)."""
    f = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,format=yuv420p,setsar=1[v0];"
        f"[1:v]scale=1080:1920,fps=30,format=yuv420p,setsar=1,trim=duration={kapanis_sn}[v1];"
        f"anullsrc=r=48000:cl=stereo,atrim=duration={kapanis_sn}[a1];"
        "[0:a]aresample=48000,aformat=channel_layouts=stereo[a0];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    subprocess.run(
        [_ffmpeg(), "-v", "error", "-y", "-i", str(klip), "-loop", "1", "-t", str(kapanis_sn), "-i", str(kapanis_png),
         "-filter_complex", f, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-c:a", "aac",
         "-movflags", "+faststart", str(hedef)],
        check=True, capture_output=True,
    )  # fmt: skip
    return hedef


def uret(c, etsy, kie: Kie, tasarim_id: int, yazdir=print) -> dict:
    """Tek tasarımın giyilmiş videosu → `calisma/giyim/<id>/video.mp4`. Her deneme ve OCR puanı `rapor.json`a yazılır."""
    from matbaa import tiktok
    from matbaa.fiyat import urunler

    t = c.execute(
        "SELECT t.id, t.dosyalar, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.id = ?",
        (tasarim_id,),
    ).fetchone()
    lid = c.execute(
        "SELECT etsy_listing_id FROM urun WHERE tasarim_id = ? AND urun = 'tisort' AND durum = 'aktif'", (tasarim_id,)
    ).fetchone()
    if t is None or lid is None:
        raise ValueError(f"tasarım {tasarim_id}: aktif tişört ilanı yok")
    satirlar, dos = json.loads(t["satirlar"]), json.loads(t["dosyalar"])
    klasor = CIKTI / f"{tasarim_id:05d}"
    klasor.mkdir(parents=True, exist_ok=True)
    rapor: dict = {"tasarim": tasarim_id, "slogan": satirlar, "foto": [], "video": []}

    # Referanslar: vitrin mockup'ı (kumaş rengi, kesim) + baskı dosyası beyaz zeminde (yazının birebir hâli)
    vitrin = tiktok._mockuplar(etsy, int(lid[0]), tiktok._indir)[0].convert("RGB")
    u = urunler()["tisort"]
    renk = u.get("vitrin_rengi", "white")
    baski = Image.open(KOK / dos["koyu_png"]).convert("RGBA")
    baski = baski.crop(baski.getchannel("A").getbbox())
    zemin = Image.new("RGBA", (baski.width + 200, baski.height + 200), "white")
    zemin.alpha_composite(baski, (100, 100))
    zemin.thumbnail((1600, 1600))
    refler = []
    for ad, img in (("vitrin.jpg", vitrin), ("baski.jpg", zemin.convert("RGB"))):
        b = io.BytesIO()
        img.save(b, "JPEG", quality=92)
        refler.append(kie.yukle(b.getvalue(), f"matbaa-{tasarim_id:05d}-{ad}"))

    foto_url = None
    for k in range(DENEME_FOTO):
        gid = kie.gorev(
            "gpt-image-2-image-to-image",
            {"prompt": foto_istemi(satirlar, t["nis"], renk), "input_urls": refler, "aspect_ratio": "9:16", "resolution": "2K"},
        )
        url = kie.bekle(gid, sure=600, aralik=5)[0]
        foto = Image.open(io.BytesIO(kie.indir(url))).convert("RGB")
        foto.save(klasor / f"foto_{k + 1}.jpg", "JPEG", quality=92)
        p = slogan_puani(foto, satirlar)
        rapor["foto"].append({"deneme": k + 1, "tam": round(p[0], 3), "benzer": round(p[1], 3), "eksik": p[2]})
        yazdir(f"  foto {k + 1}: birebir %{p[0] * 100:.0f}, eksik {p[2]}")
        if gecer(p):
            foto_url, rapor["secilen_foto"] = url, k + 1
            break
    if foto_url is None:
        (klasor / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
        raise KieHatasi(f"{DENEME_FOTO} fotoğrafta slogan birebir çıkmadı: {rapor['foto']}")

    for k in range(DENEME_VIDEO):
        gid = kie.gorev(
            "veo-3-1",
            {"prompt": VIDEO_ISTEMI, "image_urls": [foto_url], "model": "veo3_fast", "aspect_ratio": "9:16",
             "generation_type": "FIRST_AND_LAST_FRAMES_2_VIDEO", "resolution": "720p"},
        )  # fmt: skip
        url = kie.bekle(gid, sure=1200, aralik=15)[0]
        klip = klasor / f"klip_{k + 1}.mp4"
        klip.write_bytes(kie.indir(url))
        puanlar = [slogan_puani(kare, satirlar, olcekler=(1280,)) for kare in video_kareleri(klip)]
        oran = sum(gecer(p) for p in puanlar) / max(len(puanlar), 1)
        rapor["video"].append({"deneme": k + 1, "gecen_kare": round(oran, 3), "kare": len(puanlar)})
        yazdir(f"  video {k + 1}: karelerin %{oran * 100:.0f}'inde slogan birebir")
        if oran >= VIDEO_ESIK:
            kapanis = klasor / "kapanis.png"
            tiktok.kapanis(KOK / dos["koyu_png"], "Free US shipping  ·  Made to order").save(kapanis)
            kapanisla_birlestir(klip, kapanis, klasor / "video.mp4")
            rapor["secilen_video"] = k + 1
            break
    (klasor / "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    if "secilen_video" not in rapor:
        raise KieHatasi(f"{DENEME_VIDEO} videoda slogan hareket boyunca korunmadı: {rapor['video']} (fotoğraflar klasörde)")
    return rapor
