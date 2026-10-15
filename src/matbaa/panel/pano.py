"""Takip panosu (2026-10-15): mağazanın, hattın ve paranın tek sayfalık özeti. Yalnız yerel veriden okur (veritabanı, son günlük
koşu raporu, roadmap); sayfa açılırken Etsy'ye ya da Printify'a istek atmaz, sayfa yenilemesi API kotası yemez.
Görüntülenme verisi günlük koşunun aldığı anlık görüntülerdir (`goruntulenme`), yani en çok bir gün gecikir."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, date, datetime, timedelta

from matbaa import fiyat, pinterest, siparis, tavan
from matbaa.ayar import KOK

MAGAZA_URL = "https://www.etsy.com/shop/HobbyHeartPrints"
ILAN_URL = "https://www.etsy.com/listing/{}"
DURUM_ISARET = {"✅": "bitti", "🔄": "suruyor", "⏳": "bekliyor"}


def _son_kosu() -> dict | None:
    from matbaa import hat

    try:
        k = json.loads(hat.SON_KOSU.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    adimlar = {}
    for ad in ("yayin", "etsy", "gorsel", "mevsimlik", "isimli", "siparis"):
        v = k.get(ad)
        if isinstance(v, dict):
            adimlar[ad] = {x: y for x, y in v.items() if isinstance(y, int | float) and not isinstance(y, bool)}
        elif isinstance(v, str):
            adimlar[ad] = v
    return {
        "basladi": k.get("basladi"),
        "sure_sn": k.get("sure_sn"),
        "hatalar": k.get("hatalar", []),
        "alarmlar": k.get("alarmlar", []),
        "adimlar": adimlar,
        "suruyor": _kosu_suruyor(hat.SON_KOSU.parent / "kosu.kilit"),
    }


def _kosu_suruyor(kilit) -> bool:
    """Kilit dosyası kalıcıdır (işletim sistemi kilidi, `kilit.py`): içindeki süreç numarası yaşayan bir Python süreci mi.
    Kilidi denemek yerine bakılır: pano, o anda başlayan bir günlük koşunun kilidini kapmasın."""
    try:
        pid = int(kilit.read_text(encoding="utf-8").strip())
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5, errors="replace"
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    return "python" in r.stdout.lower() or "uv.exe" in r.stdout.lower()


def _sonraki_kosu() -> str | None:
    """Windows görevinin bir sonraki çalışma zamanı (schtasks; görev yoksa ya da Windows değilse None)."""
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/tn", "Matbaa-Gunluk", "/fo", "LIST"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(?:Next Run Time|Sonraki Çalışma Zamanı):\s*(.+)", r.stdout)
    return m.group(1).strip() if m else None


def _roadmap() -> list[dict]:
    try:
        metin = (KOK / "docs" / "Roadmap.md").read_text(encoding="utf-8")
    except OSError:
        return []
    sonuc = []
    for m in re.finditer(r"^\| (\d+) \| ([^|]+) \| (✅|🔄|⏳)[^|]*\| ([^|]+) \|", metin, re.M):
        sonuc.append({"no": int(m[1]), "ad": m[2].strip(), "durum": DURUM_ISARET[m[3]], "kriter": m[4].strip()})
    return sonuc


def _goruntulenme(c, gun: int = 21) -> dict:
    """Günlük toplam görüntülenme/favori (anlık görüntü toplamı) ve günlük artış; ilan başına son değer."""
    bas = (date.today() - timedelta(days=gun)).isoformat()
    seri = [
        {"tarih": r[0], "views": r[1], "favori": r[2]}
        for r in c.execute(
            "SELECT tarih, sum(views), sum(favori) FROM goruntulenme WHERE tarih >= ? GROUP BY tarih ORDER BY tarih", (bas,)
        )
    ]
    for onceki, x in zip([None, *seri], seri, strict=False):
        x["artis"] = None if onceki is None else max(x["views"] - onceki["views"], 0)
    son = c.execute("SELECT max(tarih) FROM goruntulenme").fetchone()[0]
    ilan = {
        r[0]: (r[1], r[2]) for r in c.execute("SELECT etsy_listing_id, views, favori FROM goruntulenme WHERE tarih = ?", (son,))
    }
    return {"seri": seri, "son_tarih": son, "ilan": ilan}


def _ilanlar(c, gor: dict) -> list[dict]:
    adlar = {u: p["etsy_turu"] for u, p in fiyat.urunler().items()}
    gorsel = {r[0]: r[1] for r in c.execute("SELECT etsy_listing_id, gorsel_url FROM pin")}
    sonuc = []
    for r in c.execute(
        """SELECT u.tasarim_id, u.urun, u.durum, u.etsy_listing_id, u.guncelleme, i.satirlar, i.nis, il.fiyat
           FROM urun u JOIN tasarim t ON t.id = u.tasarim_id JOIN ifade i ON i.id = t.ifade_id
           LEFT JOIN ilan il ON il.tasarim_id = u.tasarim_id AND il.urun = u.urun
           WHERE u.durum NOT IN ('kaldirildi', 'bekliyor') ORDER BY u.tasarim_id, u.rowid"""
    ):
        v, f = gor["ilan"].get(str(r["etsy_listing_id"]), (None, None))
        g = gorsel.get(str(r["etsy_listing_id"]))
        sonuc.append(
            {
                "tasarim": r["tasarim_id"],
                "slogan": " ".join(json.loads(r["satirlar"])),
                "nis": r["nis"],
                "urun": r["urun"],
                "urun_adi": adlar.get(r["urun"], r["urun"]),
                "durum": r["durum"],
                "fiyat": r["fiyat"],
                "views": v,
                "favori": f,
                "url": ILAN_URL.format(r["etsy_listing_id"]) if r["etsy_listing_id"] else None,
                # Etsy'nin vitrin görseli (pin kuyruğu günlük koşuda alır); 570 px sürümü aynı adreste boyut adıyla durur
                "gorsel": g.replace("/il_fullxfull.", "/il_570xN.") if g else None,
            }
        )
    return sonuc


def _siparisler(c) -> dict:
    son = [
        dict(r)
        for r in c.execute(
            """SELECT s.etsy_receipt_id, s.tasarim_id, s.brut, s.net, s.durum, s.takip, s.olusturma,
                      (SELECT group_concat(x, ' ') FROM (SELECT value AS x FROM json_each(i.satirlar))) AS slogan
               FROM siparis s LEFT JOIN tasarim t ON t.id = s.tasarim_id LEFT JOIN ifade i ON i.id = t.ifade_id
               ORDER BY s.olusturma DESC LIMIT 15"""
        )
    ]
    isimli = [
        {
            **dict(r),
            "isimler": [k.get("isim") for k in json.loads(r["kalemler"] or "[]")],
            # Panelden isim düzeltmesi için: kalem kimliği + alıcının yazdığı (ya da en son elle verilen) isim
            "kalemler": [
                {
                    "transaction_id": k.get("transaction_id"),
                    "isim": json.loads(r["duzeltme"] or "{}").get(k.get("transaction_id"), k.get("isim")),
                }
                for k in json.loads(r["kalemler"] or "[]")
            ],
        }
        for r in c.execute(
            "SELECT etsy_receipt_id, durum, kalemler, duzeltme, printify_order_id, takip, hata, guncelleme FROM isimli_siparis "
            "ORDER BY guncelleme DESC LIMIT 10"
        )
    ]
    return {"son": son, "isimli": isimli, "geciken": siparis.geciken(c)}


def _hat(c) -> dict:
    from matbaa import yayin

    tasarim = dict(c.execute("SELECT durum, count(*) FROM tasarim GROUP BY durum").fetchall())
    urun = dict(c.execute("SELECT durum, count(*) FROM urun GROUP BY durum").fetchall())
    gunluk = yayin.gunluk_sinir(c)
    onayli = tasarim.get("onaylandi", 0)
    simdi = datetime.now(UTC)
    ay_basi = simdi.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    return {
        "tasarim": tasarim,
        "urun": urun,
        "gunluk_sinir": gunluk,
        "magaza_yasi": yayin.magaza_yasi(c),
        "kuyruk_gun": round(onayli / gunluk, 1) if gunluk else None,
        "ilan_ucreti": tavan.ilan_ucreti(c, ay_basi),
        "ilan_tavani": tavan.aylik_ilan_tavani(c, simdi),
    }


URUN_AD = {
    "tisort": "Tişört",
    "sweatshirt": "Sweatshirt",
    "hoodie": "Hoodie",
    "susleme": "Süs",
    "isimli_susleme": "İsimli süs",
    "kupa": "Kupa",
}
URUN_ADIM = {"aktif": ("yayına girdi", "iyi"), "bekliyor": ("ilan metni yazıldı", ""), "kaldirildi": ("yayından kalktı", "")}
TASARIM_ADIM = {"onay_bekliyor": ("onaya geldi", ""), "onaylandi": ("onaylandı", "iyi"), "ret": ("reddedildi", "kotu")}


def _olay_metni(o) -> tuple[str, str, str | None] | None:
    """Olay → (metin, tür, ürün) ya da None (ara adım/eşitleme kaydı: akışta gürültü)."""
    yeni = o["yeni"] or ""
    if o["varlik"] == "urun" and ":" in yeni:
        urun, adim = yeni.split(":", 1)
        if adim == "hata":
            return f"hata: {(o['aciklama'] or '')[:90]}", "kotu", URUN_AD.get(urun, urun)
        if adim in URUN_ADIM:
            return (*URUN_ADIM[adim], URUN_AD.get(urun, urun))
        return None
    if o["varlik"] == "tasarim" and yeni in TASARIM_ADIM:
        return (*TASARIM_ADIM[yeni], None)
    if o["varlik"] == "pin" and yeni == "csv":
        return f"Pinterest dosyası indirildi ({(o['aciklama'] or '').split(': ', 1)[-1]})", "", None
    if o["varlik"] == "siparis" and yeni != "izlendi":
        return f"sipariş: {yeni}", "iyi", None
    return None


def _olaylar(c, n: int = 12) -> list[dict]:
    """İnsan dilinde, gruplanmış etkinlik. Aynı tasarımın aynı adımı ürünleri toplar ("Tişört, Hoodie yayına girdi"); ardışık
    tasarımlarda aynı adım ve aynı ürünler tek satır olur ("12 tasarıma Süs ilan metni"). Gruplar 2 saatlik pencerede."""
    slogan = {
        r[0]: " ".join(json.loads(r[1]))
        for r in c.execute("SELECT t.id, i.satirlar FROM tasarim t JOIN ifade i ON i.id = t.ifade_id")
    }
    yakin = lambda a, b: abs(datetime.fromisoformat(a) - datetime.fromisoformat(b)) < timedelta(hours=2)  # noqa: E731
    adimlar: list[dict] = []  # 1. geçiş: tasarım + adım başına ürünler
    for o in c.execute("SELECT zaman, varlik, varlik_id, yeni, aciklama FROM olay ORDER BY id DESC LIMIT 800"):
        m = _olay_metni(o)
        if m is None:
            continue
        metin, tur, urun = m
        tasarim = o["varlik_id"] if o["varlik"] in ("urun", "tasarim") else None
        x = adimlar[-1] if adimlar else None
        if x and x["tasarim"] == tasarim and x["metin"] == metin and yakin(x["zaman"], o["zaman"]):
            if urun and urun not in x["urunler"]:
                x["urunler"].insert(0, urun)
            continue
        adimlar.append({"zaman": o["zaman"], "tasarim": tasarim, "metin": metin, "tur": tur, "urunler": [urun] if urun else []})
    sonuc: list[dict] = []  # 2. geçiş: aynı adım + aynı ürünler, ardışık tasarımlar
    for a in adimlar:
        x = sonuc[-1] if sonuc else None
        if (
            x
            and a["tasarim"] is not None
            and x["tasarimlar"]
            and x["metin"] == a["metin"]
            and x["urunler"] == a["urunler"]
            and yakin(x["zaman"], a["zaman"])
        ):
            x["tasarimlar"].append({"id": a["tasarim"], "slogan": slogan.get(a["tasarim"])})
            continue
        if len(sonuc) >= n:
            break
        t = [{"id": a["tasarim"], "slogan": slogan.get(a["tasarim"])}] if a["tasarim"] is not None else []
        sonuc.append({k: a[k] for k in ("zaman", "metin", "tur", "urunler")} | {"tasarimlar": t})
    return sonuc


def _acilis(c) -> str | None:
    """Mağazanın ilk ilanının yayına girdiği gün (Etsy Ads açılıştan 15 gün sonra açılabiliyor)."""
    r = c.execute("SELECT min(zaman) FROM olay WHERE varlik = 'urun' AND yeni LIKE '%:aktif'").fetchone()[0]
    return r[:10] if r else None


def pano(c) -> dict:
    gor = _goruntulenme(c)
    ilanlar = _ilanlar(c, gor)
    aktif = [x for x in ilanlar if x["durum"] == "aktif"]
    return {
        "simdi": datetime.now(UTC).isoformat(timespec="seconds"),
        "magaza_url": MAGAZA_URL,
        "ozet": {
            "aktif_ilan": len(aktif),
            "views": sum(x["views"] or 0 for x in aktif),
            "favori": sum(x["favori"] or 0 for x in aktif),
            "son_gun_artis": gor["seri"][-1]["artis"] if gor["seri"] else None,
            "kar_30g": siparis.ozet(c),
            "ay": siparis.aylik(c),
        },
        "goruntulenme": {"seri": gor["seri"], "son_tarih": gor["son_tarih"]},
        "ilanlar": ilanlar,
        "siparisler": _siparisler(c),
        "hat": _hat(c),
        "son_kosu": _son_kosu(),
        "sonraki_kosu": _sonraki_kosu(),
        "roadmap": _roadmap(),
        "olaylar": _olaylar(c),
        "pinterest": pinterest.ozet(c),
        "acilis": _acilis(c),
    }
