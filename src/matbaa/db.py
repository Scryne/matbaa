"""Hat durumu: tek SQLite dosyası, tasarım durum makinesi, olay günlüğü.

Her durum geçişi `olay` tablosuna yazılır; hat yarıda kesilirse kaldığı yerden sürer ve "bu ilan neden
yayında" sorusunun cevabı kayıttadır.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from matbaa.ayar import KOK

DB = KOK / "matbaa.db"

# Tasarımın yaşam döngüsü. IP kapısı ifade düzeyindedir; tasarım ancak temiz ifadeden doğar.
GECISLER: dict[str, set[str]] = {
    "aday": {"kalite_ok", "ret"},
    "kalite_ok": {"metin_ok", "ret"},
    "metin_ok": {"onay_bekliyor", "ret"},
    "onay_bekliyor": {"onaylandi", "ret", "aday"},  # "aday": Scryne düzeltme istedi, yeniden üretilir
    "onaylandi": {"yayinda", "ret", "onay_bekliyor"},  # "onay_bekliyor": yayından önce onay geri alındı
    "yayinda": {"kaldirildi"},  # en az bir ürünü Etsy'de aktif
    "kaldirildi": set(),
    "ret": set(),
}
# Bir tasarım birden çok ürüne (tişört, sweatshirt, hoodie) dönüşür; yayın durumu ürün başına.
# bekliyor → olusturuldu (Printify ürünü var, kimliği kayıtlı) → printify (Etsy'ye yayın istendi) → etsy_taslak → aktif.
# Hata, düştüğü adımdan yeniden denenir (`hata_oncesi`): Printify ürünü açılmışsa ikinci ürün açılmaz.
URUN_GECISLERI: dict[str, set[str]] = {
    "bekliyor": {"olusturuldu", "hata"},
    "olusturuldu": {"printify", "hata"},
    "printify": {"etsy_taslak", "hata", "olusturuldu"},  # "olusturuldu": yayın zaman aşımı, yeniden yayın
    "etsy_taslak": {"aktif", "hata"},
    "aktif": {"kaldirildi"},
    "hata": {"bekliyor", "olusturuldu", "printify", "etsy_taslak"},
    "kaldirildi": set(),
}

SEMA = """
CREATE TABLE IF NOT EXISTS ifade (
    id INTEGER PRIMARY KEY,
    nis TEXT NOT NULL,
    satirlar TEXT NOT NULL,           -- JSON liste
    kaynak TEXT NOT NULL,             -- claude | elle
    kapi_karar TEXT,                  -- temiz | ret | insan
    kapi_nedenler TEXT,               -- JSON
    kapi_kayit TEXT,                  -- JSON ham sinyaller (kalibrasyon)
    olusturma TEXT NOT NULL,
    UNIQUE (nis, satirlar)
);
CREATE TABLE IF NOT EXISTS tasarim (
    id INTEGER PRIMARY KEY,
    ifade_id INTEGER NOT NULL REFERENCES ifade(id),
    sablon TEXT NOT NULL,
    fontlar TEXT NOT NULL,            -- JSON
    dosyalar TEXT,                    -- JSON {koyu_png, acik_png, koyu_svg, acik_svg}
    kalite TEXT,                      -- JSON kapı sonuçları
    durum TEXT NOT NULL DEFAULT 'aday',
    durum_zamani TEXT NOT NULL,
    ret_nedeni TEXT
);
CREATE TABLE IF NOT EXISTS ilan (
    tasarim_id INTEGER NOT NULL REFERENCES tasarim(id),
    urun TEXT NOT NULL,               -- config/urunler.toml anahtarı
    baslik TEXT NOT NULL,
    etiketler TEXT NOT NULL,          -- JSON, 13 adet
    aciklama TEXT NOT NULL,
    alt_metin TEXT,
    fiyat REAL, kargo REAL,
    PRIMARY KEY (tasarim_id, urun)
);
CREATE TABLE IF NOT EXISTS urun (
    tasarim_id INTEGER NOT NULL REFERENCES tasarim(id),
    urun TEXT NOT NULL,
    durum TEXT NOT NULL DEFAULT 'bekliyor',
    printify_id TEXT,
    etsy_listing_id TEXT,
    hata TEXT,
    guncelleme TEXT,
    PRIMARY KEY (tasarim_id, urun)
);
CREATE TABLE IF NOT EXISTS siparis (
    etsy_receipt_id TEXT PRIMARY KEY,
    printify_order_id TEXT,
    tasarim_id INTEGER REFERENCES tasarim(id),
    brut REAL, net REAL, para_birimi TEXT,
    durum TEXT, takip TEXT,
    olusturma TEXT, guncelleme TEXT
);
CREATE TABLE IF NOT EXISTS isimli_siparis (   -- Faz 11: isimli süs makbuzu → Printify API siparişi (isimli.py)
    etsy_receipt_id TEXT PRIMARY KEY,
    durum TEXT NOT NULL,              -- yeni | acildi | uretimde | takip_yazildi | iptal | hata
    kalemler TEXT,                    -- JSON: transaction_id, tasarim_id, isim, varyant_id, adet
    printify_order_id TEXT,
    takip TEXT, hata TEXT,
    olusturma TEXT, guncelleme TEXT
);
CREATE TABLE IF NOT EXISTS pin (               -- Pinterest toplu pin kuyruğu (pinterest.py): ilan başına bir pin
    id INTEGER PRIMARY KEY,
    etsy_listing_id TEXT NOT NULL UNIQUE,
    tasarim_id INTEGER, urun TEXT,
    gorsel_url TEXT NOT NULL, baslik TEXT NOT NULL, aciklama TEXT, pano TEXT NOT NULL, anahtar TEXT,
    durum TEXT NOT NULL,              -- bekliyor | verildi (CSV'ye girdi, yayın saati atandı)
    yayin TEXT, dosya TEXT, olusturma TEXT
);
CREATE TABLE IF NOT EXISTS olay (
    id INTEGER PRIMARY KEY,
    zaman TEXT NOT NULL,
    varlik TEXT NOT NULL,
    varlik_id INTEGER,
    eski TEXT, yeni TEXT,
    aciklama TEXT
);
CREATE TABLE IF NOT EXISTS goruntulenme (    -- Etsy aktif ilan anlık görüntüsü; haftalık fark = görüntülenme
    tarih TEXT NOT NULL,              -- YYYY-MM-DD
    etsy_listing_id TEXT NOT NULL,
    views INTEGER, favori INTEGER,
    PRIMARY KEY (tarih, etsy_listing_id)
);
CREATE INDEX IF NOT EXISTS tasarim_durum ON tasarim(durum);
"""


class GecersizGecis(ValueError):
    pass


def simdi() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def baglan(yol: Path | str | None = None, thread_serbest: bool = False) -> sqlite3.Connection:
    """`thread_serbest`: bağlantı tek bir isteğe ait ama açılıp kapanması farklı iş parçacığında olabilir (panelin FastAPI bağımlılığı)."""
    # DB çalışma anında okunur: testler geçici veritabanına yönlendirebilir. Panel ve günlük koşu aynı anda yazabilir:
    # WAL okuyucuyu yazana takmaz, 30 sn bekleme ağ çağrısı süren bir yazma işleminin bitmesini bekler ("database is locked" yerine).
    c = sqlite3.connect(yol or DB, timeout=30, check_same_thread=not thread_serbest)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(SEMA)
    # Sonradan eklenen sütunlar (eski veritabanlarına uygulanır).
    for tablo, sutun in (("ifade", "yapi TEXT"),):
        try:
            c.execute(f"ALTER TABLE {tablo} ADD COLUMN {sutun}")
        except sqlite3.OperationalError:
            pass
    return c


def olay(
    c: sqlite3.Connection, varlik: str, varlik_id: int | None, eski: str | None, yeni: str | None, aciklama: str = ""
) -> None:
    c.execute(
        "INSERT INTO olay (zaman, varlik, varlik_id, eski, yeni, aciklama) VALUES (?, ?, ?, ?, ?, ?)",
        (simdi(), varlik, varlik_id, eski, yeni, aciklama),
    )


def ifade_ekle(
    c: sqlite3.Connection, nis: str, satirlar: list[str], kaynak: str = "claude", yapi: dict | None = None
) -> int | None:
    """Aynı niş + satırlar ikinci kez eklenmez (None döner): aynı ifadeyi tekrar tekrar üretmeyi engeller."""
    try:
        cur = c.execute(
            "INSERT INTO ifade (nis, satirlar, kaynak, olusturma, yapi) VALUES (?, ?, ?, ?, ?)",
            (nis, json.dumps(satirlar, ensure_ascii=False), kaynak, simdi(), json.dumps(yapi or {}, ensure_ascii=False)),
        )
    except sqlite3.IntegrityError:
        return None
    olay(c, "ifade", cur.lastrowid, None, "eklendi", " / ".join(satirlar))
    return cur.lastrowid


def kapi_yaz(c: sqlite3.Connection, ifade_id: int, karar: str, nedenler: list[str], kayit: list[dict]) -> None:
    c.execute(
        "UPDATE ifade SET kapi_karar = ?, kapi_nedenler = ?, kapi_kayit = ? WHERE id = ?",
        (karar, json.dumps(nedenler, ensure_ascii=False), json.dumps(kayit, ensure_ascii=False, default=str), ifade_id),
    )
    olay(c, "ifade", ifade_id, None, f"kapi:{karar}", "; ".join(nedenler)[:500])


def tasarim_ekle(c: sqlite3.Connection, ifade_id: int, sablon: str, fontlar: list[str]) -> int:
    karar = c.execute("SELECT kapi_karar FROM ifade WHERE id = ?", (ifade_id,)).fetchone()
    if karar is None or karar[0] not in ("temiz", "insan"):  # "insan": onay panelinde işaretli gider (K-13)
        raise GecersizGecis(f"ifade {ifade_id} IP kapısından geçmedi ({karar and karar[0]}); tasarım üretilemez (K-13)")
    cur = c.execute(
        "INSERT INTO tasarim (ifade_id, sablon, fontlar, durum, durum_zamani) VALUES (?, ?, ?, 'aday', ?)",
        (ifade_id, sablon, json.dumps(fontlar), simdi()),
    )
    olay(c, "tasarim", cur.lastrowid, None, "aday", sablon)
    return cur.lastrowid


def gecis(c: sqlite3.Connection, tasarim_id: int, yeni: str, aciklama: str = "") -> None:
    satir = c.execute("SELECT durum FROM tasarim WHERE id = ?", (tasarim_id,)).fetchone()
    if satir is None:
        raise KeyError(tasarim_id)
    eski = satir[0]
    if yeni not in GECISLER.get(eski, set()):
        raise GecersizGecis(f"tasarım {tasarim_id}: {eski} → {yeni} izinli değil")
    c.execute(
        "UPDATE tasarim SET durum = ?, durum_zamani = ?, ret_nedeni = ? WHERE id = ?",
        (yeni, simdi(), aciklama if yeni == "ret" else None, tasarim_id),
    )
    olay(c, "tasarim", tasarim_id, eski, yeni, aciklama)


def urun_gecis(c: sqlite3.Connection, tasarim_id: int, urun: str, yeni: str, aciklama: str = "", **alanlar: str) -> None:
    satir = c.execute("SELECT durum FROM urun WHERE tasarim_id = ? AND urun = ?", (tasarim_id, urun)).fetchone()
    if satir is None:
        raise KeyError((tasarim_id, urun))
    if yeni not in URUN_GECISLERI.get(satir[0], set()):
        raise GecersizGecis(f"ürün {tasarim_id}/{urun}: {satir[0]} → {yeni} izinli değil")
    ek = "".join(f", {k} = ?" for k in alanlar)
    c.execute(
        f"UPDATE urun SET durum = ?, guncelleme = ?, hata = ?{ek} WHERE tasarim_id = ? AND urun = ?",
        (yeni, simdi(), aciklama if yeni == "hata" else None, *alanlar.values(), tasarim_id, urun),
    )
    olay(c, "urun", tasarim_id, satir[0], f"{urun}:{yeni}", aciklama)


def hata_oncesi(c: sqlite3.Connection, tasarim_id: int, urun: str) -> str | None:
    """Ürün `hata`daysa hangi adımda düştüğü (son `hata` geçişinin eski durumu); yeniden deneme oradan başlar."""
    r = c.execute(
        "SELECT eski FROM olay WHERE varlik = 'urun' AND varlik_id = ? AND yeni = ? ORDER BY id DESC LIMIT 1",
        (tasarim_id, f"{urun}:hata"),
    ).fetchone()
    return r[0] if r else None


YEDEK_SAKLA = 14  # gün


def yedekle(c: sqlite3.Connection, dizin: Path, gun: str | None = None, sakla: int = YEDEK_SAKLA) -> Path:
    """Tutarlı anlık kopya (`sqlite3.backup`, yazma sürerken de güvenli) → `<dizin>/matbaa-<gün>.db`; en yeni `sakla` kopya kalır.

    Veritabanı canlı ilanların Printify/Etsy kimliklerini ve sipariş defterini taşır, git dışındadır: kaybı elle eşleme demektir.
    """
    dizin.mkdir(parents=True, exist_ok=True)
    hedef = dizin / f"matbaa-{gun or datetime.now(UTC).date().isoformat()}.db"
    gecici = hedef.with_suffix(".db.tmp")
    with sqlite3.connect(gecici) as kopya:
        c.backup(kopya)
    kopya.close()
    gecici.replace(hedef)
    for eski in sorted(dizin.glob("matbaa-????-??-??.db"))[:-sakla]:
        eski.unlink()
    return hedef


def durumdakiler(c: sqlite3.Connection, durum: str) -> list[sqlite3.Row]:
    return c.execute("SELECT * FROM tasarim WHERE durum = ? ORDER BY id", (durum,)).fetchall()
