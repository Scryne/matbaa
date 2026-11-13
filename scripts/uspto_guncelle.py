"""ABD giyim sınıfı (25) canlı marka tablosunu yeniler → veri/uspto_25_canli.parquet

Kaynak: Hugging Face `illeatmyhat/uspto-trademarks` (USPTO TRTYRAP + TRTDXFAP'tan derlenmiş, kamu malı).
Resmî ODP API'si anahtar istiyor (401, 2026-10-13); anahtar alınınca kaynak resmî bulk'a çevrilir.
Ayda bir çalıştırılır; ~2-3 dk, ~7 MB.
"""

import time

import duckdb

from matbaa.ayar import VERI

B = "hf://datasets/illeatmyhat/uspto-trademarks"


def main() -> None:
    t = time.time()
    VERI.mkdir(exist_ok=True)
    hedef = VERI / "uspto_25_canli.parquet"
    gecici = hedef.with_suffix(".parquet.tmp")  # yarıda kalan indirme çalışan marka dosyasını bozmasın
    c = duckdb.connect()
    c.sql("INSTALL httpfs; LOAD httpfs;")
    c.sql(f"CREATE TABLE durum AS SELECT * FROM read_csv('{B}/lookups/status_codes.csv', all_varchar=true)")
    c.sql(
        f"CREATE TABLE s25 AS SELECT DISTINCT serial_no FROM '{B}/data/intl_class/*.parquet' WHERE ltrim(intl_class_cd, '0') = '25'"
    )
    # DISTINCT: 2026-11'de kaynak case_file aynı başvuruyu birden çok dosyada taşıyor (788 bin satır, 408 bin başvuru).
    # Bir başvurunun farklı sürümleri (durum/tarih değişmiş) ayrı satır kalır: eski sürümü hâlâ canlıysa marka denetimi
    # onu da görür, temkinli yön.
    c.sql(f"""COPY (
      SELECT DISTINCT cf.serial_no, cf.registration_no, cf.mark_id_char AS marka, cf.status_cd, d.live_dead_indicator AS durum, cf.filing_dt
      FROM '{B}/data/case_file/*.parquet' cf JOIN s25 USING (serial_no) JOIN durum d ON d.code = cf.status_cd
      WHERE d.live_dead_indicator LIKE 'Live%' AND cf.mark_id_char IS NOT NULL
    ) TO '{gecici.as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
    # DuckDB 2: relation fetchone() yok
    n = c.sql(f"SELECT count(DISTINCT serial_no) FROM read_parquet('{gecici.as_posix()}')").fetchall()[0][0]
    c.close()
    if n < 100_000:  # sınıf 25'te ~400 bin canlı marka var (2026-10); çok azı kaynağın bozulduğunu gösterir
        gecici.unlink()
        raise RuntimeError(f"USPTO verisi şüpheli ({n} başvuru): eski dosya korundu")  # hat._uspto yakalar
    gecici.replace(hedef)
    print(f"{n} canlı sınıf-25 başvurusu → {hedef} ({time.time() - t:.0f} sn)")


if __name__ == "__main__":
    main()
