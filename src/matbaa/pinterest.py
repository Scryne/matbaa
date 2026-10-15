"""Pinterest toplu pin dosyası (2026-10-15): Etsy ilanlarına API'siz trafik.

Neden CSV: Pinterest API'sinin deneme erişiminde açılan pinler yalnız sahibine görünür, standart erişim video ve haftalarca
inceleme ister; Pinterest'in kendi "bulk create Pins" aracı ise işletme hesabında CSV ile 200 pine kadar yükler (help.pinterest.com
"Bulk upload Pins", 2026-10-15 okundu). Görsel, Etsy'nin herkese açık ilan görselidir (`url_fullxfull`): ayrı barındırma yok.

Akış: günlük koşu yeni aktif ilanları `pin` kuyruğuna ekler (`kuyruga_ekle`, ilan başına bir pin). Panodaki "CSV indir" o an
bekleyen pinlere yarından başlayarak yayın saati verir (`csv_uret`) ve onları `verildi` sayar; Scryne dosyayı Pinterest'e yükler.
Tempo günde `GUNLUK` pin, en çok `GUN` gün ileri: yeni hesaba önerilen 1-5 pin/gün aralığı (resmî sınır yok; aynı siteden hızlı
çok pin geçici engel sebebi) ve Pinterest'in "iki hafta önceden zamanla" sınırı.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import UTC, date, datetime, time, timedelta

from matbaa import db

GUNLUK = 3
GUN = 14
SAATLER = (time(13, 0), time(18, 0), time(23, 30))  # UTC: ABD doğu yakası sabah 9, öğleden sonra 2, akşam 7:30
BASLIK_MAKS, ACIKLAMA_MAKS = 100, 500
SUTUNLAR = ["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"]
ILAN_URL = "https://www.etsy.com/listing/{}"


def _kisalt(metin: str, maks: int) -> str:
    metin = " ".join(metin.split())
    if len(metin) <= maks:
        return metin
    kes = metin[: maks - 1].rsplit(" ", 1)[0].rstrip(",;:-")
    return kes + "…"


def pano_adi(nis: str, urun: str) -> str:
    """Pano niş adından; süsler mevsim panosunda. `/` Pinterest'te bölüm ayracıdır, pano adına girmez."""
    from matbaa.ifade.uret import nisler

    bolum = (nisler().get(nis, {}).get("vitrin_bolumu") or nis.replace("_", " ").title()).replace("/", " ")
    if urun == "isimli_susleme":
        return "Personalized Christmas Ornaments"
    if urun == "susleme":
        return "Christmas Ornaments"
    return f"{bolum} Gifts"


def aciklama(ilan_aciklama: str) -> str:
    """İlanın ilk paragrafı (satış cümlesi), sonuna çağrı; teknik bölümler (bakım, AI beyanı) pine girmez."""
    ilk = re.split(r"\n\s*\n", ilan_aciklama.strip(), maxsplit=1)[0]
    cagri = " Printed to order in the USA, free US shipping. Tap to see it on Etsy."
    return _kisalt(ilk, ACIKLAMA_MAKS - len(cagri)) + cagri


def kuyruga_ekle(c, etsy, sinir: int = 40, yazdir=print) -> dict:
    """Pini olmayan aktif ilanlar → `pin` kuyruğu (ilk görsel: vitrin mockup'ı). Görsel adresi Etsy'den (ilan başına 1 istek)."""
    sayac = {"eklenen": 0, "hata": 0}
    for r in c.execute(
        """SELECT u.tasarim_id, u.urun, u.etsy_listing_id, i.nis, il.baslik, il.aciklama, il.etiketler FROM urun u
           JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           JOIN ilan il ON il.tasarim_id = u.tasarim_id AND il.urun = u.urun
           WHERE u.durum = 'aktif' AND u.etsy_listing_id IS NOT NULL
             AND NOT EXISTS (SELECT 1 FROM pin p WHERE p.etsy_listing_id = u.etsy_listing_id)
           ORDER BY u.guncelleme LIMIT ?""",
        (sinir,),
    ).fetchall():
        try:
            gorseller = etsy.ilan_gorselleri(int(r["etsy_listing_id"]))
            if not gorseller:
                continue
            g = gorseller[0]
            c.execute(
                """INSERT INTO pin (etsy_listing_id, tasarim_id, urun, gorsel_url, baslik, aciklama, pano, anahtar, durum, olusturma)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'bekliyor', ?)""",
                (
                    str(r["etsy_listing_id"]),
                    r["tasarim_id"],
                    r["urun"],
                    g.get("url_fullxfull") or g["url_570xN"],
                    _kisalt(r["baslik"], BASLIK_MAKS),
                    aciklama(r["aciklama"]),
                    pano_adi(r["nis"], r["urun"]),
                    ",".join(json.loads(r["etiketler"] or "[]")[:8]),
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )
            c.commit()
            sayac["eklenen"] += 1
        except Exception as e:  # görsel okunamadıysa ertesi gün yeniden denenir
            sayac["hata"] += 1
            yazdir(f"  pin hata {r['tasarim_id']}/{r['urun']}: {type(e).__name__}: {str(e)[:120]}")
    return sayac


def _sirala(pinler: list) -> list:
    """Ardışık iki pin aynı tasarımdan olmasın (aynı ürünün varyantlarını art arda atmak spam sayılabilir)."""
    gruplar: dict[int, list] = {}
    for p in pinler:
        gruplar.setdefault(p["tasarim_id"], []).append(p)
    sonuc = []
    while gruplar:
        for t in list(gruplar):
            sonuc.append(gruplar[t].pop(0))
            if not gruplar[t]:
                del gruplar[t]
    return sonuc


def slotlar(bas: date, n: int) -> list[datetime]:
    return [datetime.combine(bas + timedelta(days=i // GUNLUK), SAATLER[i % GUNLUK], UTC) for i in range(n)]


def _yaz(satirlar: list) -> bytes:
    b = io.StringIO()
    w = csv.writer(b, quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(SUTUNLAR)
    for p in satirlar:
        w.writerow(
            [
                p["baslik"],
                p["gorsel_url"],
                p["pano"],
                "",
                p["aciklama"],
                ILAN_URL.format(p["etsy_listing_id"]),
                p["yayin"],
                p["anahtar"] or "",
            ]
        )
    return b.getvalue().encode("utf-8")


def bekleyen(c) -> int:
    return c.execute("SELECT count(*) FROM pin WHERE durum = 'bekliyor'").fetchone()[0]


def csv_uret(c, simdi: datetime | None = None) -> tuple[str, bytes, int]:
    """Bekleyen pinlerden en çok `GUNLUK × GUN` tanesine yarından başlayan yayın saatleri verir ve onları `verildi` sayar.
    Önceki dosyanın son saatinden sonrasına eklenir: iki indirme aynı saate iki pin koymaz."""
    simdi = simdi or datetime.now(UTC)
    yarin = simdi.date() + timedelta(days=1)
    son = c.execute("SELECT max(yayin) FROM pin WHERE durum = 'verildi'").fetchone()[0]
    dolu = datetime.fromisoformat(son).date() + timedelta(days=1) if son else yarin
    bas = max(yarin, dolu)
    yer = GUNLUK * max((simdi.date() + timedelta(days=GUN) - bas).days + 1, 0)
    pinler = _sirala([dict(r) for r in c.execute("SELECT * FROM pin WHERE durum = 'bekliyor' ORDER BY id")])[:yer]
    dosya = f"pinterest-{simdi:%Y%m%d-%H%M}.csv"
    for p, s in zip(pinler, slotlar(bas, len(pinler)), strict=False):
        p["yayin"] = s.strftime("%Y-%m-%dT%H:%M:%S")
        c.execute("UPDATE pin SET durum = 'verildi', yayin = ?, dosya = ? WHERE id = ?", (p["yayin"], dosya, p["id"]))
    if pinler:
        db.olay(
            c, "pin", None, None, "csv", f"{dosya}: {len(pinler)} pin, {pinler[0]['yayin'][:10]} → {pinler[-1]['yayin'][:10]}"
        )
    c.commit()
    return dosya, _yaz(pinler), len(pinler)


def son_csv(c) -> tuple[str, bytes, int] | None:
    """Son indirilen dosyanın aynısı (yükleme yarıda kaldıysa yeniden indirmek için; tarihler değişmez)."""
    r = c.execute("SELECT dosya FROM pin WHERE durum = 'verildi' ORDER BY yayin DESC LIMIT 1").fetchone()
    if not r:
        return None
    pinler = [dict(x) for x in c.execute("SELECT * FROM pin WHERE dosya = ? ORDER BY yayin", (r[0],))]
    return r[0], _yaz(pinler), len(pinler)


def ozet(c) -> dict:
    son = c.execute(
        "SELECT dosya, count(*), min(yayin), max(yayin) FROM pin WHERE durum = 'verildi' GROUP BY dosya ORDER BY max(yayin) DESC LIMIT 1"
    ).fetchone()
    return {
        "bekleyen": bekleyen(c),
        "verilen": c.execute("SELECT count(*) FROM pin WHERE durum = 'verildi'").fetchone()[0],
        "son_dosya": dict(zip(("dosya", "adet", "ilk", "son"), son, strict=True)) if son else None,
        "kapasite": GUNLUK * GUN,
    }
