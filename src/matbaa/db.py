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
URUN_GECISLERI: dict[str, set[str]] = {
    "bekliyor": {"printify", "hata"},
    "printify": {"etsy_taslak", "hata"},
    "etsy_taslak": {"aktif", "hata"},
    "aktif": {"kaldirildi"},
    "hata": {"bekliyor"},
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
CREATE TABLE IF NOT EXISTS olay (
    id INTEGER PRIMARY KEY,
    zaman TEXT NOT NULL,
    varlik TEXT NOT NULL,
    varlik_id INTEGER,
    eski TEXT, yeni TEXT,
    aciklama TEXT
);
CREATE INDEX IF NOT EXISTS tasarim_durum ON tasarim(durum);
"""


class GecersizGecis(ValueError):
    pass


def simdi() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def baglan(yol: Path | str | None = None) -> sqlite3.Connection:
    c = sqlite3.connect(yol or DB)  # DB çalışma anında okunur: testler geçici veritabanına yönlendirebilir
    c.row_factory = sqlite3.Row
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
    if karar is None or karar[0] != "temiz":
        raise GecersizGecis(f"ifade {ifade_id} IP kapısından temiz geçmedi ({karar and karar[0]}); tasarım üretilemez (K-13)")
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


def durumdakiler(c: sqlite3.Connection, durum: str) -> list[sqlite3.Row]:
    return c.execute("SELECT * FROM tasarim WHERE durum = ? ORDER BY id", (durum,)).fetchall()
