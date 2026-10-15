"""TikTok kısa videoları (K-34, 2026-10-15): mağazaya bilinirlik. Her yayındaki tasarım için 9:16 video + açıklama/hashtag +
önerilen paylaşım saati. Yükleme Scryne'da (TikTok Studio, 10 gün ileri zamanlama): onaysız API yalnız "sadece ben" paylaşıyor
ve kendi hesabını yöneten araç API denetiminden geçmiyor (araştırma 2026-10-15). Video, fotoğraf karuselinden gönderi başına
~5,6 kat izlenme alıyor (Metricool, 2,3 milyon gönderi, 2026): karusel üretilmez.

Neden kodla: görselden video üreten modeller tişörtteki sloganı bozabilir (K-32). Burada her kare gerçek ürünün kendisi:
Etsy ilanındaki Printify mockup'ları (alıcının sipariş edeceği ürün), kendi baskı dosyamızın kumaş üstü yakın planı ve marka
kapanış kartı. Yazılar fonttan yola çevrilir (her makinede aynı, sistem fontu yok). Ses yok: TikTok'ta trend ses uygulama
içinde eklenir.

Kare düzeni TikTok arayüzüne göre: alt ~%25 (açıklama, ses adı) ve sağ şerit (beğeni/yorum düğmeleri) kapalı alan; yazı
`GUVENLI` kutusunda kalır. Akış: kanca (vitrin mockup'ı + soru/kanca cümlesi) → baskı yakın planı → diğer renk/ürünler →
süs (varsa) → kapanış (mağaza adı, ücretsiz kargo). Kesmeler sert, her karede hafif yakınlaşma (TikTok'un doğal dili).
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import resvg_py
from PIL import Image

from matbaa import db, llm
from matbaa.ayar import KOK
from matbaa.fiyat import urunler
from matbaa.tasarim.yazi import font

G, Y = 1080, 1920
FPS = 30
# x0, y0, x1, y1: yazı bu kutuda. Telefon ekranı 9:16'dan uzun (~9:19,5): TikTok videoyu yükseklikten doldurup iki yandan ~100 px
# kırpıyor, sağda düğme şeridi var (2026-10-15 Studio önizlemesinde kapanış kartı iki yandan kesildi). Alt: açıklama alanı.
GUVENLI = (110, 150, 870, 1380)
ORTA = (GUVENLI[0] + GUVENLI[2]) / 2
CIKTI = KOK / "calisma" / "tiktok"
MAGAZA = "HobbyHeartPrints"
KREM, LACIVERT, MERCAN = "#F4EDE1", "#2B3A55", "#E07A5F"
KALIN_F, BASLIK_F, ALT_F = "ArchivoBlack-Regular.ttf", "DMSerifDisplay-Regular.ttf", "BebasNeue-Regular.ttf"
GUNLUK = 2  # günlük koşuda en çok bu kadar yeni video (her biri ~30 sn: Etsy görselleri, Claude, render)
ABD, TR = ZoneInfo("America/New_York"), ZoneInfo("Europe/Istanbul")
PAYLASIM_SAATI = time(19, 0)  # ABD doğu yakası akşamı: alıcıların çoğu doğu/orta saat diliminde, iş sonrası kaydırma


# --- kare çizimi ---


def _svg(parcalar: list[str], arka: str | None = None) -> Image.Image:
    zemin = f'<rect width="{G}" height="{Y}" fill="{arka}"/>' if arka else ""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{G}" height="{Y}" viewBox="0 0 {G} {Y}">{zemin}{"".join(parcalar)}</svg>'
    )
    return Image.open(
        io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg, width=G, height=Y, skip_system_fonts=True)))
    ).convert("RGBA")


def _satirlara_bol(metin: str, dosya: str, boy: float, genislik: float) -> list[str]:
    """Kelime sınırından satırlara böler: her satır `boy` büyük harf yüksekliğinde `genislik`e sığar."""
    f = font(dosya)
    k = boy / f.buyuk_harf
    satirlar: list[str] = []
    for kelime in metin.split():
        aday = f"{satirlar[-1]} {kelime}" if satirlar else kelime
        if satirlar and f.satir(aday).ilerleme * k <= genislik:
            satirlar[-1] = aday
        else:
            satirlar.append(kelime)
    return satirlar


def _yazi(metin: str, dosya: str, cx: float, taban: float, boy: float, renk: str) -> tuple[str, float]:
    """Taban çizgisi `taban`da, `cx` ortalı tek satır; büyük harf yüksekliği `boy`. (svg, genişlik)"""
    f = font(dosya)
    s = f.satir(metin)
    k = boy / f.buyuk_harf
    tx = cx - (s.x0 + s.genislik / 2) * k
    return f'<path fill="{renk}" d="{s.yol}" transform="translate({tx:.1f} {taban:.1f}) scale({k:.5f})"/>', s.genislik * k


def etiket_katmani(
    metin: str, ust: float, boy: float = 58, dosya: str = KALIN_F, maks_satir: int = 4, koyu_zemin: bool = False
) -> tuple[Image.Image, float]:
    """TikTok'un yerel yazı dili: her satır yuvarlak kutuda kalın yazı. Açık zeminde (beyaz stüdyo mockup'ı) lacivert kutu
    krem yazı, koyu zeminde krem kutu lacivert yazı: kutu zeminde kaybolmaz. Sığmazsa küçülür. (katman, alt kenar)"""
    kutu_renk, yazi_renk = (KREM, LACIVERT) if koyu_zemin else (LACIVERT, "#FFFFFF")
    x0, _, x1, _ = GUVENLI
    while True:
        satirlar = _satirlara_bol(metin, dosya, boy, (x1 - x0) - boy * 0.9)
        if len(satirlar) <= maks_satir or boy <= 30:
            break
        boy *= 0.9
    p, y, cx = [], ust, (x0 + x1) / 2
    adim, pay_y, pay_x = boy * 1.95, boy * 0.42, boy * 0.45
    for s in satirlar:
        svg, g = _yazi(s, dosya, cx, y + pay_y + boy, boy, yazi_renk)
        p.append(
            f'<rect x="{cx - g / 2 - pay_x:.1f}" y="{y:.1f}" width="{g + 2 * pay_x:.1f}" height="{boy + 2 * pay_y:.1f}" '
            f'rx="{boy * 0.28:.1f}" fill="{kutu_renk}"/>'
        )
        p.append(svg)
        y += adim
    return _svg(p), y


FOTO_ALT = 1580  # ürün fotoğrafının alt sınırı: altı TikTok'un açıklama alanı


def _kenar_rengi(foto: Image.Image) -> tuple[int, int, int]:
    """Fotoğrafın kenar şeridinin medyan rengi: mockup'ın stüdyo zemini (beyaz) ya da yakın planın kumaşı."""
    a = np.asarray(foto.convert("RGB"))
    kenar = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    return tuple(int(v) for v in np.median(kenar, axis=0))


def _urun_kutusu(foto: Image.Image, renk: tuple[int, int, int], pay: float = 0.06) -> tuple[int, int, int, int]:
    """Mockup'ta ürünün kapladığı kutu (stüdyo zemininden farklı pikseller), kenar payıyla: mockup'ın boşluğu ekranı yemesin."""
    a = np.asarray(foto, dtype=np.int16)
    fark = np.abs(a - np.array(renk, dtype=np.int16)).max(axis=2) > 24
    ys, xs = np.nonzero(fark)
    if len(xs) < 100:
        return (0, 0, foto.width, foto.height)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    p = round(max(x1 - x0, y1 - y0) * pay)
    return (max(0, x0 - p), max(0, y0 - p), min(foto.width, x1 + p), min(foto.height, y1 + p))


def koyu_mu(renk: tuple[int, int, int]) -> bool:
    return 0.299 * renk[0] + 0.587 * renk[1] + 0.114 * renk[2] < 140


def _sigdir(foto: Image.Image, ust: float | None = None) -> Image.Image:
    """Mockup'ı 9:16'ya: zemin fotoğrafın kendi kenar rengi (dikişsiz), ürün boş kenarlarından kırpılıp alana sığacak kadar büyür.
    `ust`: üstte yazı varsa ürün onun altından `FOTO_ALT`a kadarki alana oturur (yazı ürünün üstüne binmez)."""
    foto = foto.convert("RGB")
    renk = _kenar_rengi(foto)
    zemin = Image.new("RGB", (G, Y), renk)
    urun = foto.crop(_urun_kutusu(foto, renk))
    bas = GUVENLI[1] if ust is None else ust
    k = min(G * 0.8 / urun.width, (FOTO_ALT - bas) / urun.height)  # telefonda yanlardan kırpılan ~100 px'e kol taşmasın
    on = urun.resize((round(urun.width * k), round(urun.height * k)), Image.LANCZOS)
    zemin.paste(on, ((G - on.width) // 2, round(bas + (FOTO_ALT - bas - on.height) / 2)))
    return zemin


@dataclass
class Sahne:
    zemin: Image.Image  # 1080x1920 RGB; videoda üstünde hafif yakınlaşma
    katman: Image.Image | None  # sabit yazı katmanı (RGBA)
    sure: float

    def kare(self, t: float = 1.0) -> Image.Image:
        """`t` 0..1: sahnenin ilerleyişi. Zemin %0 → %5 yakınlaşır, yazı sabit."""
        z = 1.0 + 0.05 * t
        g, y = G / z, Y / z
        kutu = ((G - g) / 2, (Y - y) / 2, (G + g) / 2, (Y + y) / 2)
        img = self.zemin.resize((G, Y), Image.BILINEAR, box=kutu).convert("RGBA")
        if self.katman is not None:
            img.alpha_composite(self.katman)
        return img.convert("RGB")


def _sigan_boy(metin: str, dosya: str, boy: float) -> float:
    """İstenen büyük harf yüksekliği; satır güvenli genişliği aşacaksa küçültülür."""
    f = font(dosya)
    return min(boy, (GUVENLI[2] - GUVENLI[0]) * f.buyuk_harf / f.satir(metin).ilerleme)


def kapanis(tasarim_png: Path | None, alt_satir: str) -> Image.Image:
    satirlar = [
        ("FIND IT ON ETSY", ALT_F, 420, 64, MERCAN),
        (MAGAZA, BASLIK_F, 560, 104, LACIVERT),
        (alt_satir.upper(), ALT_F, 1330, 58, LACIVERT),
        ("SEARCH  HOBBYHEARTPRINTS", KALIN_F, 1430, 40, MERCAN),
    ]
    p = [_yazi(m, d, ORTA, y, _sigan_boy(m, d, b), r)[0] for m, d, y, b, r in satirlar]
    zemin = _svg(p, KREM)
    if tasarim_png and tasarim_png.exists():
        t = Image.open(tasarim_png).convert("RGBA")
        t = t.crop(t.getchannel("A").getbbox())
        t.thumbnail((GUVENLI[2] - GUVENLI[0], 560), Image.LANCZOS)
        zemin.alpha_composite(t, (round(ORTA - t.width / 2), 650 + (560 - t.height) // 2))
    return zemin.convert("RGB")


# --- metin ---

METIN_SEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "string", "description": "on-screen hook, max 70 characters, sentence case, no hashtags, no emoji"},
        "caption": {"type": "string", "description": "TikTok caption, max 150 characters, no hashtags, no emoji"},
        "hashtags": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 6},
    },
    "required": ["hook", "caption", "hashtags"],
}
METIN_SISTEM = (
    "You write short TikTok copy for a small Etsy gift shop that sells funny hobby T-shirts, sweatshirts and Christmas ornaments "
    "to American buyers. The hook is the text on the first frame: it must make the right person stop scrolling (a relatable "
    "situation, a 'gift idea for' angle, or a POV), and must not just repeat the slogan. Plain, natural American English. "
    "Never use brand names, trademarks, celebrity, team, movie or song references, prices, discounts or claims you cannot "
    "verify. Hashtags: lowercase, no '#', niche and gift words buyers search (for example fishinggifts, giftsfordad)."
)


@dataclass
class Metin:
    hook: str
    aciklama: str
    etiketler: list[str]

    def gonderi(self) -> str:
        """TikTok'a yapıştırılacak açıklama: cümle + hashtag'ler."""
        return f"{self.aciklama} " + " ".join(f"#{e}" for e in self.etiketler)


def _temiz_etiket(e: str) -> str:
    return re.sub(r"[^a-z0-9]", "", e.lower())


def metin_yaz(satirlar: list[str], nis: str, urun_adlari: list[str], yazar=None, onceki: list[str] | None = None) -> Metin:
    """Claude ile kanca + açıklama + hashtag; düşerse niş kartından kalıp metin (video yine çıkar). Hashtag'ler marka süzgecinden.
    `onceki`: son kancalar; aynı kalıp ("Gift idea for…") her videoda tekrarlanmasın."""
    from matbaa.ifade.uret import aktif_mevsimler, nisler
    from matbaa.ip import marka

    k = nisler()[nis]
    mevsim = [m["ad"] for m in aktif_mevsimler(nis)]  # Ekim'de "fathersdaygift" önerilmesin
    istem = "\n".join(
        [
            f"Printed slogan: {' / '.join(satirlar)}",
            f"Niche and buyer: {k['ad']}. {k['alici']}",
            f"Products in the video: {', '.join(urun_adlari)}; free US shipping; shop name {MAGAZA} on Etsy.",
            f"Upcoming gift occasion now: {', '.join(mevsim) or 'none in particular'}; no hashtags for other holidays.",
            "Write the hook, the caption (end it by pointing to the shop name on Etsy) and 4 to 6 hashtags.",
            *([f"Recent hooks from this account; use a different opening and angle: {' | '.join(onceki)}"] if onceki else []),
        ]
    )
    try:
        ham = (yazar or llm.yapilandirilmis)(istem, METIN_SISTEM, METIN_SEMA)
        hook, aciklama = " ".join(ham["hook"].split())[:90], " ".join(ham["caption"].split())[:200]
        etiketler = [e for e in (_temiz_etiket(x) for x in ham["hashtags"]) if e]
    except Exception:  # Claude yoksa da video çıkar
        hook = f"Gift idea for the {k['roller'][0].lower()} who lives for {k['ad'].split('(')[0].strip().lower()}"
        aciklama = f"Made to order, free US shipping. Find it at {MAGAZA} on Etsy."
        etiketler = []
    d = marka.dizin()
    etiketler = [e for e in dict.fromkeys(etiketler) if d.kontrol(e).temiz][:6]
    if len(etiketler) < 3:
        etiketler += [e for e in ("giftideas", "etsyfinds", "christmasgifts") if e not in etiketler][: 3 - len(etiketler)]
    return Metin(hook, aciklama, etiketler)


# --- video ---


def sahneler(
    fotolar: dict[str, list[Image.Image]], yakin: Image.Image | None, tasarim_png: Path | None, metin: Metin
) -> list[Sahne]:
    """`fotolar`: ürün → o ilanın mockup'ları (ilki vitrin). Sıra: kanca, yakın plan, diğer renk/ürün, süs, kapanış."""
    ad = {u: p["etsy_turu"].lower() for u, p in urunler().items()}
    sira = [u for u in ("tisort", "sweatshirt", "hoodie", "kupa", "susleme", "isimli_susleme") if fotolar.get(u)]
    if not sira:
        raise ValueError("videoya girecek mockup yok")
    ilk = sira[0]

    def yazili(foto: Image.Image, metin_: str, boy: float, sure: float) -> Sahne:
        katman, alt = etiket_katmani(metin_, GUVENLI[1] + 30, boy, maks_satir=3, koyu_zemin=koyu_mu(_kenar_rengi(foto)))
        return Sahne(_sigdir(foto, alt + 10), katman, sure)

    s = [yazili(fotolar[ilk][0], metin.hook, 60, 2.6)]
    if yakin is not None:
        s.append(yazili(yakin, "Printed to order in the USA", 44, 1.7))
    renkler = fotolar[ilk][1:3]
    for f in renkler:
        s.append(Sahne(_sigdir(f), None, 1.1))
    for u in sira[1:]:
        if u in ("susleme", "isimli_susleme"):
            yazi = "Add your name: matching ornament" if u == "isimli_susleme" else "Also a Christmas ornament"
        else:
            yazi = f"Also a {ad[u]}"
        s.append(yazili(fotolar[u][0], yazi, 44, 1.5))
    s.append(Sahne(kapanis(tasarim_png, "Free US shipping  ·  Made to order"), None, 2.4))
    return s


def video_yaz(sahne_listesi: list[Sahne], hedef: Path) -> Path:
    """H.264, yuv420p, 30 fps, sessiz (ses TikTok'ta eklenir). ffmpeg imageio-ffmpeg paketinden: sistem kurulumu gerekmez."""
    import imageio_ffmpeg

    hedef.parent.mkdir(parents=True, exist_ok=True)
    gecici = hedef.with_suffix(".tmp.mp4")
    yazici = imageio_ffmpeg.write_frames(
        str(gecici), (G, Y), fps=FPS, codec="libx264", pix_fmt_out="yuv420p", quality=8, macro_block_size=8,
        output_params=["-movflags", "+faststart"],
    )  # fmt: skip
    yazici.send(None)
    for sh in sahne_listesi:
        n = max(1, round(sh.sure * FPS))
        for i in range(n):
            yazici.send(np.ascontiguousarray(np.asarray(sh.kare(i / n))))
    yazici.close()
    gecici.replace(hedef)
    return hedef


# --- hat ---


def _indir(url: str) -> Image.Image:
    import httpx

    return Image.open(io.BytesIO(httpx.get(url, timeout=60, follow_redirects=True).content))


def _mockuplar(etsy, listing_id: int, indir) -> list[Image.Image]:
    """İlanın Printify mockup'ları (alt metni olmayanlar; kendi kartlarımızın alt metni var), galeri sırasıyla, en çok 3."""
    gorseller = [g for g in etsy.ilan_gorselleri(listing_id) if not (g.get("alt_text") or "").strip()]
    return [indir(g.get("url_fullxfull") or g["url_570xN"]) for g in gorseller[:3]]


def uret(c, etsy, tasarim_id: int, indir=None, yazar=None) -> dict:
    """Bir tasarımın videosunu, kapağını ve metnini üretir → `calisma/tiktok/<id>/`, `video` tablosuna `hazir`."""
    from matbaa.ilan import gorsel

    indir = indir or _indir
    t = c.execute(
        "SELECT t.id, t.dosyalar, i.satirlar, i.nis FROM tasarim t JOIN ifade i ON i.id = t.ifade_id WHERE t.id = ?",
        (tasarim_id,),
    ).fetchone()
    urun_ilan = dict(
        c.execute(
            "SELECT urun, etsy_listing_id FROM urun WHERE tasarim_id = ? AND durum = 'aktif' AND etsy_listing_id IS NOT NULL",
            (tasarim_id,),
        ).fetchall()
    )
    fotolar = {u: _mockuplar(etsy, int(lid), indir) for u, lid in urun_ilan.items()}
    dos = {k: KOK / v for k, v in json.loads(t["dosyalar"]).items()}
    yakin = None
    ilk = next((u for u in ("tisort", "sweatshirt", "hoodie") if u in urun_ilan), None)
    if ilk:
        u = urunler()[ilk]
        renk = next((r for r in u["renkler"] if r["ad"] == u.get("vitrin_rengi")), u["renkler"][0])
        yakin = gorsel.yakin_plan(dos[f"{renk['murekkep']}_png"], renk["hex"], tohum=tasarim_id)
    satirlar = json.loads(t["satirlar"])
    eski = c.execute("SELECT hook, aciklama, etiketler FROM video WHERE tasarim_id = ?", (tasarim_id,)).fetchone()
    if eski and eski["hook"]:  # yeniden üretim (görsel düzeltmesi): metin aynı kalır, Studio'ya yapıştırılan açıklama tutar
        m = Metin(eski["hook"], eski["aciklama"], json.loads(eski["etiketler"] or "[]"))
    else:
        onceki = [r[0] for r in c.execute("SELECT hook FROM video ORDER BY olusturma DESC LIMIT 8")]
        m = metin_yaz(satirlar, t["nis"], [urunler()[u]["etsy_turu"] for u in fotolar], yazar, onceki)
    sh = sahneler(fotolar, yakin, dos.get("koyu_png"), m)
    klasor = CIKTI / f"{tasarim_id:05d}"
    video_yaz(sh, klasor / "video.mp4")
    kapak = sh[0].kare(0.0)
    kapak.thumbnail((360, 640))
    kapak.save(klasor / "kapak.jpg", "JPEG", quality=85)
    (klasor / "aciklama.txt").write_text(m.gonderi() + "\n", encoding="utf-8")
    c.execute(
        """INSERT OR REPLACE INTO video (tasarim_id, durum, klasor, hook, aciklama, etiketler, sure, olusturma)
           VALUES (?, 'hazir', ?, ?, ?, ?, ?, ?)""",
        (
            tasarim_id, str(klasor.relative_to(KOK)) if klasor.is_relative_to(KOK) else str(klasor), m.hook, m.aciklama,
            json.dumps(m.etiketler), round(sum(s.sure for s in sh), 1), datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )  # fmt: skip
    db.olay(c, "video", tasarim_id, None, "hazir", m.hook[:200])
    c.commit()
    return {"tasarim": tasarim_id, "hook": m.hook, "sahne": len(sh)}


def hazirla(c, etsy, sinir: int = GUNLUK, yazdir=print, indir=None, yazar=None) -> dict:
    """Günlük adım: videosu olmayan yayındaki tasarımlar (en eski yayın önce), en çok `sinir` tanesi."""
    sayac = {"hazir": 0, "hata": 0}
    adaylar = c.execute(
        """SELECT u.tasarim_id, min(u.guncelleme) AS ilk FROM urun u WHERE u.durum = 'aktif' AND u.etsy_listing_id IS NOT NULL
             AND u.urun IN ('tisort', 'sweatshirt', 'hoodie')
             AND NOT EXISTS (SELECT 1 FROM video v WHERE v.tasarim_id = u.tasarim_id)
           GROUP BY u.tasarim_id ORDER BY ilk LIMIT ?""",
        (sinir,),
    ).fetchall()
    for r in adaylar:
        try:
            s = uret(c, etsy, r["tasarim_id"], indir, yazar)
        except Exception as e:  # tek tasarımın videosu düşerse diğerleri sürer; ertesi gün yeniden denenir
            sayac["hata"] += 1
            yazdir(f"  tiktok hata {r['tasarim_id']}: {type(e).__name__}: {str(e)[:150]}")
            continue
        sayac["hazir"] += 1
        yazdir(f"  tiktok videosu: tasarım {s['tasarim']}: {s['hook']}")
    return sayac


def plan(c, n: int, simdi: datetime | None = None) -> list[datetime]:
    """Sıradaki `n` paylaşım saati (UTC): günde bir, ABD doğu 19:00; en son zamanlanan videonun ertesi gününden ya da bugünden."""
    simdi = simdi or datetime.now(UTC)
    son = c.execute("SELECT max(plan) FROM video WHERE durum = 'paylasildi'").fetchone()[0]
    gun = simdi.astimezone(ABD).date()
    if datetime.combine(gun, PAYLASIM_SAATI, ABD) <= simdi + timedelta(minutes=20):  # Studio en az ~15 dk ileri zamanlar
        gun += timedelta(days=1)
    if son:
        gun = max(gun, datetime.fromisoformat(son).astimezone(ABD).date() + timedelta(days=1))
    return [datetime.combine(gun + timedelta(days=i), PAYLASIM_SAATI, ABD).astimezone(UTC) for i in range(n)]


def ozet(c, simdi: datetime | None = None) -> dict:
    hazir = [
        dict(r)
        for r in c.execute(
            """SELECT v.tasarim_id, v.hook, v.aciklama, v.etiketler, v.sure, v.olusturma,
                      (SELECT group_concat(x, ' ') FROM (SELECT value AS x FROM json_each(i.satirlar))) AS slogan
               FROM video v JOIN tasarim t ON t.id = v.tasarim_id JOIN ifade i ON i.id = t.ifade_id
               WHERE v.durum = 'hazir' ORDER BY v.olusturma"""
        )
    ]
    for h, z in zip(hazir, plan(c, len(hazir), simdi), strict=True):
        h["gonderi"] = Metin(h["hook"], h["aciklama"], json.loads(h.pop("etiketler") or "[]")).gonderi()
        h["plan"] = z.isoformat(timespec="minutes")
        h["plan_tr"] = z.astimezone(TR).strftime("%Y-%m-%dT%H:%M")  # Studio tarayıcının saat dilimiyle (Türkiye) zamanlar
    return {
        "hazir": hazir,
        "paylasilan": c.execute("SELECT count(*) FROM video WHERE durum = 'paylasildi'").fetchone()[0],
    }


def paylasildi(c, tasarim_id: int, simdi: datetime | None = None) -> None:
    """Paylaşıldı/zamanlandı: video sıradaki boş saati alır (`plan`), sonraki videolar onun ertesi gününe kayar."""
    simdi = simdi or datetime.now(UTC)
    saat = plan(c, 1, simdi)[0].isoformat(timespec="minutes")
    if (
        c.execute(
            "UPDATE video SET durum = 'paylasildi', paylasim = ?, plan = ? WHERE tasarim_id = ? AND durum = 'hazir'",
            (simdi.isoformat(timespec="seconds"), saat, tasarim_id),
        ).rowcount
        != 1
    ):
        raise KeyError(tasarim_id)
    db.olay(c, "video", tasarim_id, "hazir", "paylasildi", "TikTok")
    c.commit()
