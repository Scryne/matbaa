"""Videoların bütün platformlara otomatik paylaşımı (K-38, 2026-10-20).

Scryne: "mağazamızdaki tüm ilanlar tüm platformlarda olmalı", her şey otomatik. Video tasarım başına bir tane (tiktok.py) ve o
tasarımın bütün ilanlarını gösterir (tişört, sweatshirt, süs): aynı tasarımın beş ilanına beş benzer video tekrar içerik sayılır.
İlanların kendisi doğrudan linkiyle Pinterest'te pin olarak durur (pinterest.py).

Yollar (docs/arastirma/08): Instagram ve Facebook Reels Meta'nın resmî API'si, YouTube Data API; TikTok onaylı aracı (Zernio):
kendi denetimsiz uygulamamız TikTok'ta yalnız "sadece ben" paylaşır. Şifre/çerez isteyen resmî olmayan araçlar elendi: hesap
kısıtlanma riski, tek trafik kaynağımız bu hesaplar.

Akış: `kuyruga_ekle` her videoyu her açık platforma bir `gonderi` satırı yapar → `planla` platformun günlük saatlerinden (ABD
doğu) boş saat verir; iki tasarım dili (çizimli/yazılı) sırayla gider, tanıtım tek hatta yığılıp Faz 18 kıyasını bozmasın →
`gonder`: platform zamanlamayı kendisi tutuyorsa (`ileri_gun`) saat yaklaşınca zamanlı gönderilir, tutmuyorsa saati gelince
yayınlanır (saatlik görev). Kaçırılan saat (bilgisayar kapalıydı) yeni saate kayar: gönderiler üst üste yığılmaz.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

from matbaa import db
from matbaa.ayar import CONFIG, KOK

ABD = ZoneInfo("America/New_York")
PLATFORMLAR = ("tiktok", "instagram", "facebook", "youtube", "pinterest")
MAKS_DENEME = 3
KACIRMA = timedelta(hours=3)  # saatinden bu kadar geç kalmış gönderi yayınlanmaz, yeni saate kayar
ONCE = timedelta(minutes=20)  # zamanlı gönderi için en yakın saat (aracılar ~10-15 dk ileri ister)
ILAN_URL = "https://www.etsy.com/listing/{}"
MAGAZA_URL = "https://hobbyheartprints.etsy.com"
YT_BASLIK_MAKS = 100


def ayar(dosya: Path | None = None) -> dict:
    return tomllib.loads((dosya or CONFIG / "paylasim.toml").read_text(encoding="utf-8"))


@dataclass
class Is:
    """Bir platforma gidecek tek gönderi: istemcinin bilmesi gereken her şey."""

    gonderi_id: int
    platform: str
    video: Path
    kapak: Path | None
    baslik: str  # YouTube başlığı; diğer platformlar kullanmaz
    metin: str  # platformun açıklama alanı
    link: str
    ai: bool  # gerçekçi AI insanı: platformların AI içerik işareti
    plan: datetime
    pano: str = ""  # Pinterest panosu (niş)


@dataclass
class Sonuc:
    durum: str  # zamanlandi | yayinda
    dis_id: str | None = None
    url: str | None = None


class Platform(Protocol):
    def gonder(self, is_: Is, zamanli: bool) -> Sonuc:
        """`zamanli`: `is_.plan`a zamanla; değilse hemen yayınla."""
        ...


# --- metin ---


def _kisalt(metin: str, maks: int) -> str:
    metin = " ".join(metin.split())
    return metin if len(metin) <= maks else metin[: maks - 1].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def metinler(aciklama: str, etiketler: list[str], link: str) -> dict[str, str]:
    """Aynı açıklama platformun link kuralına göre: TikTok'ta link yok (1.000 takipçiye kadar), Instagram'da açıklamadaki link
    tıklanmaz (bio'da), Facebook ve YouTube açıklamasında ilan adresi, Pinterest'te pinin kendisi ilana gider (açıklama 800)."""
    e = " ".join(f"#{x}" for x in etiketler)
    kargo = "" if "free us shipping" in aciklama.lower() else " Free US shipping."  # Claude'un açıklaması çoğu kez zaten söylüyor
    return {
        "tiktok": f"{aciklama} {e}",
        "instagram": f"{aciklama}\n\nShop it on Etsy: link in bio.{kargo}\n\n{e}",
        "facebook": f"{aciklama}\n\nShop it on Etsy: {link}{kargo}\n\n{e}",
        "youtube": f"{aciklama}\n\nShop it on Etsy: {link}{kargo}\n\n{e} #shorts",
        "pinterest": _kisalt(f"{aciklama} Printed to order in the USA.{kargo} Tap to see it on Etsy.", 800),
    }


def ilan_linki(c, tasarim_id: int) -> str:
    """Videonun ilk ürününün ilanı (videoda ilk görünen); yoksa mağaza."""
    from matbaa.tiktok import GIYSILER

    urunler = dict(
        c.execute(
            "SELECT urun, etsy_listing_id FROM urun WHERE tasarim_id = ? AND durum = 'aktif' AND etsy_listing_id IS NOT NULL",
            (tasarim_id,),
        ).fetchall()
    )
    for u in (*GIYSILER, *sorted(urunler)):
        if u in urunler:
            return ILAN_URL.format(urunler[u])
    return MAGAZA_URL


# --- kuyruk ve takvim ---


def kuyruga_ekle(c, platformlar: list[str]) -> int:
    """Her video × her açık platform bir satır. TikTok'a Scryne'ın elle yüklediği videolar (K-34, 10-15 → 10-19) `elle` girer:
    ikinci kez gitmez. AI insanlı video (K-35) yalnız TikTok'a: diğer platformların API'sinde AI işareti alanı yok. Yayındaki
    ilanı kalmamış tasarımın videosu kuyruğa girmez (ölü ilana trafik)."""
    n = 0
    for v in c.execute(
        """SELECT v.id, v.durum, v.plan, v.ai FROM tiktok_video v
           WHERE v.durum IN ('hazir', 'paylasildi') AND v.klasor IS NOT NULL
             AND EXISTS (SELECT 1 FROM urun u WHERE u.tasarim_id = v.tasarim_id AND u.durum = 'aktif')"""
    ).fetchall():
        for p in platformlar:
            if v["ai"] and p != "tiktok":
                continue
            elle = p == "tiktok" and v["durum"] == "paylasildi"
            k = c.execute(
                "INSERT OR IGNORE INTO gonderi (video_id, platform, durum, plan, guncelleme) VALUES (?, ?, ?, ?, ?)",
                (v["id"], p, "elle" if elle else "bekliyor", v["plan"] if elle else None, db.simdi()),
            )
            n += k.rowcount
    c.commit()
    return n


def _saat(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def slotlar(saatler: list[str], dolu: set[datetime], n: int, simdi: datetime) -> list[datetime]:
    """Şimdiden (`ONCE` sonrasından) itibaren sıradaki `n` boş saat (UTC), dolu saatler atlanır."""
    esik = simdi + ONCE
    sonuc, gun = [], esik.astimezone(ABD).date()
    while len(sonuc) < n:
        for s in saatler:
            z = datetime.combine(gun, _saat(s), ABD).astimezone(UTC)
            if z > esik and z not in dolu and len(sonuc) < n:
                sonuc.append(z)
        gun += timedelta(days=1)
    return sonuc


def _sira(satirlar: list) -> list:
    """Çizimli ve yazılı tasarımlar sırayla (çizimli önce); her dilin içinde video sırası."""
    hatlar: dict[bool, list] = {True: [], False: []}
    for r in satirlar:
        hatlar[r["sablon"] == "cizim"].append(r)
    sonuc = []
    while hatlar[True] or hatlar[False]:
        for h in (True, False):
            if hatlar[h]:
                sonuc.append(hatlar[h].pop(0))
    return sonuc


def planla(c, platformlar: list[str], simdi: datetime, ayarlar: dict) -> int:
    """Saati olmayan ve saatini kaçırmış bekleyen gönderilere boş saat. Elle/zamanlanmış/yayındaki gönderilerin saatleri dolu."""
    n = 0
    for p in platformlar:
        c.execute(
            "UPDATE gonderi SET plan = NULL WHERE platform = ? AND durum = 'bekliyor' AND plan < ?",
            (p, (simdi - KACIRMA).isoformat(timespec="minutes")),
        )
        dolu = {
            datetime.fromisoformat(r[0])
            for r in c.execute("SELECT plan FROM gonderi WHERE platform = ? AND plan IS NOT NULL AND durum != 'hata'", (p,))
        }
        bos = _sira(
            c.execute(
                """SELECT g.id, t.sablon FROM gonderi g JOIN tiktok_video v ON v.id = g.video_id JOIN tasarim t ON t.id = v.tasarim_id
                   WHERE g.platform = ? AND g.durum = 'bekliyor' AND g.plan IS NULL ORDER BY v.olusturma, v.id""",
                (p,),
            ).fetchall()
        )
        for r, z in zip(bos, slotlar(ayarlar[p]["saatler"], dolu, len(bos), simdi), strict=True):
            c.execute("UPDATE gonderi SET plan = ? WHERE id = ?", (z.isoformat(timespec="minutes"), r["id"]))
            n += 1
    c.commit()
    return n


# --- gönderme ---


def _is(c, r) -> Is:
    from matbaa.pinterest import pano_adi

    klasor = KOK / r["klasor"]
    link = ilan_linki(c, r["tasarim_id"])
    nis = c.execute(
        "SELECT i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.id = ?", (r["tasarim_id"],)
    ).fetchone()[0]
    etiketler = json.loads(r["etiketler"] or "[]")
    kapak = klasor / "kapak.jpg"
    return Is(
        gonderi_id=r["id"],
        platform=r["platform"],
        video=klasor / "video.mp4",
        kapak=kapak if kapak.exists() else None,
        baslik=_kisalt(r["hook"], YT_BASLIK_MAKS),
        metin=metinler(r["aciklama"], etiketler, link)[r["platform"]],
        link=link,
        ai=bool(r["ai"]),
        plan=datetime.fromisoformat(r["plan"]),
        pano=pano_adi(nis, "tisort"),
    )


def gonder(c, istemciler: dict[str, Platform], simdi: datetime, ayarlar: dict, yazdir=print) -> dict:
    """Saati gelen (ya da zamanlama ufkuna giren) bekleyen gönderiler. Hata: `MAKS_DENEME` kez yeniden denenir, sonra `hata`
    kalır ve alarm olur. TikTok'a giden video panodaki "elle yükle" kartından düşer (`tiktok_video.durum`)."""
    sayac = {"zamanlandi": 0, "yayinda": 0, "hata": 0}
    alarm: list[str] = []
    satirlar = c.execute(
        f"""SELECT g.id, g.platform, g.plan, g.deneme, v.id AS video_id, v.tasarim_id, v.klasor, v.hook, v.aciklama, v.etiketler,
                   v.ai FROM gonderi g JOIN tiktok_video v ON v.id = g.video_id
            WHERE g.durum = 'bekliyor' AND g.plan IS NOT NULL AND g.platform IN ({",".join("?" * len(istemciler))})
            ORDER BY g.plan""",
        tuple(istemciler),
    ).fetchall()
    for r in satirlar:
        plan = datetime.fromisoformat(r["plan"])
        ileri = timedelta(days=ayarlar[r["platform"]].get("ileri_gun", 0))
        if plan <= simdi:
            zamanli = False
        elif ileri and plan <= simdi + ileri:
            zamanli = True
        else:
            continue
        try:
            s = istemciler[r["platform"]].gonder(_is(c, r), zamanli)
        except Exception as e:  # tek gönderi düşerse diğerleri sürer
            deneme = r["deneme"] + 1
            durum = "hata" if deneme >= MAKS_DENEME else "bekliyor"
            hata = f"{type(e).__name__}: {str(e)[:400]}"
            c.execute(
                "UPDATE gonderi SET durum = ?, deneme = ?, hata = ?, guncelleme = ? WHERE id = ?",
                (durum, deneme, hata, db.simdi(), r["id"]),
            )
            sayac["hata"] += 1
            yazdir(f"  paylaşım hata {r['platform']} video {r['video_id']} ({deneme}/{MAKS_DENEME}): {hata[:150]}")
            if durum == "hata":
                alarm.append(f"{r['platform']}: video {r['video_id']} {MAKS_DENEME} denemede gönderilemedi ({hata[:120]})")
        else:
            c.execute(
                "UPDATE gonderi SET durum = ?, dis_id = ?, url = ?, hata = NULL, guncelleme = ? WHERE id = ?",
                (s.durum, s.dis_id, s.url, db.simdi(), r["id"]),
            )
            if r["platform"] == "tiktok":
                c.execute("UPDATE tiktok_video SET durum = 'paylasildi', plan = ? WHERE id = ?", (r["plan"], r["video_id"]))
            db.olay(c, "gonderi", r["id"], "bekliyor", s.durum, f"{r['platform']} video {r['video_id']} {r['plan']}")
            sayac[s.durum] += 1
            yazdir(f"  {r['platform']}: video {r['video_id']} {s.durum} ({r['plan']})")
        c.commit()
    return sayac | {"alarm": alarm}


def paylas(c, istemciler: dict[str, Platform], simdi: datetime | None = None, yazdir=print, ayarlar: dict | None = None) -> dict:
    """Günlük koşu ve saatlik görev bunu çağırır: kuyruk → takvim → gönderme. Yalnız istemcisi olan platformlar."""
    simdi = simdi or datetime.now(UTC)
    ayarlar = ayarlar or ayar()
    acik = {p: i for p, i in istemciler.items() if p in ayarlar}
    eklenen = kuyruga_ekle(c, list(acik))
    planlanan = planla(c, list(acik), simdi, ayarlar)
    return {"platform": sorted(acik), "eklenen": eklenen, "planlanan": planlanan} | gonder(c, acik, simdi, ayarlar, yazdir)


# --- Zernio ---


class ZernioPlatform:
    """Bir platformun Zernio üzerinden gönderimi. Platforma özel alanlar docs.zernio.com/platforms (2026-10-20)."""

    def __init__(self, z, platform: str):
        self.z, self.platform = z, platform

    def gonder(self, is_: Is, zamanli: bool) -> Sonuc:
        kok: dict = {}
        if self.platform == "tiktok":
            # Kendi ürünümüzü tanıtıyoruz: "brand_organic" (TikTok'un ticari içerik açıklaması). Önizleme ve açık onay alanları
            # zorunlu; Scryne otomatik paylaşımı onayladı (K-38). Zernio'nun denetimli uygulamasında video yalnız herkese açık.
            kok["tiktokSettings"] = {
                "privacy_level": "PUBLIC_TO_EVERYONE",
                "allow_comment": True,
                "allow_duet": True,
                "allow_stitch": True,
                "content_preview_confirmed": True,
                "express_consent_given": True,
                "commercialContentType": "brand_organic",
                "video_made_with_ai": is_.ai,
            }
            ozel: dict = {}
        elif self.platform == "instagram":
            ozel = {"shareToFeed": True, "isAiGenerated": is_.ai}
        elif self.platform == "facebook":
            ozel = {"contentType": "reel", "title": is_.baslik}
        elif self.platform == "youtube":
            ozel = {"title": is_.baslik, "visibility": "public", "madeForKids": False, "containsSyntheticMedia": is_.ai}
        elif self.platform == "pinterest":
            ozel = {
                "boardId": self.z.pano(is_.pano),
                "title": _kisalt(is_.baslik, 100),
                "link": is_.link,
                "isAiGenerated": is_.ai,
            }
        else:
            raise ValueError(self.platform)
        post = self.z.gonder(
            self.platform,
            is_.metin,
            [{"type": "video", "url": self.z.medya(is_.video)}],
            is_.plan if zamanli else None,
            ozel,
            f"matbaa-gonderi-{is_.gonderi_id}",
            kok,
        )
        from matbaa.entegrasyon.zernio import platform_url

        return Sonuc("zamanlandi" if zamanli else "yayinda", str(post.get("_id") or post.get("id") or ""), platform_url(post))


def istemciler(z=None) -> dict[str, Platform]:
    """Zernio'da bağlı her platform için istemci. Anahtar yoksa boş: paylaşım adımı hiçbir şey yapmaz."""
    import os

    if z is None:
        if not os.environ.get("ZERNIO_API_KEY"):
            return {}
        from matbaa.entegrasyon.zernio import Zernio

        z = Zernio()
    return {p: ZernioPlatform(z, p) for p in z.hesaplar() if p in PLATFORMLAR}


def durum_yokla(c, z, simdi: datetime, yazdir=print) -> dict:
    """Saati geçmiş zamanlı gönderiler yayınlandı mı: adres yazılır; platform reddettiyse `hata` ve alarm (sessiz kaybolmasın)."""
    from matbaa.entegrasyon.zernio import platform_url

    sayac = {"yayinda": 0, "hata": 0, "alarm": []}
    for r in c.execute(
        "SELECT id, platform, video_id, dis_id FROM gonderi WHERE durum = 'zamanlandi' AND dis_id != '' AND plan < ?",
        ((simdi - timedelta(hours=1)).isoformat(timespec="minutes"),),
    ).fetchall():
        try:
            post = z.gonderi(r["dis_id"])
        except Exception as e:
            yazdir(f"  paylaşım durumu okunamadı {r['platform']} {r['dis_id']}: {type(e).__name__}")
            continue
        durumlar = {str(p.get("status", "")).lower() for p in post.get("platforms") or []} | {str(post.get("status", "")).lower()}
        if durumlar & {"failed", "error"}:
            hata = str(
                post.get("error") or post.get("errorMessage") or [p.get("errorMessage") for p in post.get("platforms") or []]
            )
            c.execute(
                "UPDATE gonderi SET durum = 'hata', hata = ?, guncelleme = ? WHERE id = ?", (hata[:500], db.simdi(), r["id"])
            )
            sayac["hata"] += 1
            sayac["alarm"].append(f"{r['platform']}: video {r['video_id']} platformda yayınlanamadı ({hata[:120]})")
        elif "published" in durumlar:
            c.execute(
                "UPDATE gonderi SET durum = 'yayinda', url = ?, guncelleme = ? WHERE id = ?",
                (platform_url(post), db.simdi(), r["id"]),
            )
            sayac["yayinda"] += 1
    c.commit()
    return sayac


def gunluk_adim(c, simdi: datetime | None = None, yazdir=print, z=None) -> dict:
    """Günlük koşunun paylaşım adımı: videolar (bütün bağlı platformlar), ilan pinleri (Pinterest bağlıysa CSV yerine) ve geçmiş
    zamanlı gönderilerin sonucu. Zernio anahtarı yoksa hiçbir şey yapmaz (Scryne bağlayana kadar)."""
    from matbaa import pinterest

    simdi = simdi or datetime.now(UTC)
    ist = istemciler(z)
    if not ist:
        return {"atlandi": "Zernio bağlı değil (ZERNIO_API_KEY yok ya da hesap bağlanmamış)", "alarm": []}
    z = next(iter(ist.values())).z
    s = paylas(c, ist, simdi, yazdir)
    alarm = list(s.pop("alarm"))
    y = durum_yokla(c, z, simdi, yazdir)
    alarm += y.pop("alarm")
    s["yoklama"] = y
    if "pinterest" in ist:
        s["ilan_pini"] = pinterest.zernio_gonder(c, z, simdi, yazdir)
    return s | {"alarm": alarm}


def ozet(c) -> dict:
    """Pano ve rapor için: platform başına durum sayıları ve sıradaki saat."""
    sonuc: dict[str, dict] = {}
    for p, durum, n in c.execute("SELECT platform, durum, count(*) FROM gonderi GROUP BY platform, durum"):
        sonuc.setdefault(p, {})[durum] = n
    for p, plan in c.execute("SELECT platform, min(plan) FROM gonderi WHERE durum = 'bekliyor' GROUP BY platform"):
        sonuc.setdefault(p, {})["siradaki"] = plan
    return sonuc
