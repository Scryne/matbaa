"""Harcama tavanları (K-7): para harcayan adım, harcamadan önce burada sorar; tavan aşılacaksa `TavanAsildi` fırlar.

Sayım veritabanındaki olay günlüğünden yapılır: tavanın kendi sayacı yok, "ne harcandı" sorusunun tek kaynağı olaylar.
"""

from __future__ import annotations

import tomllib
from datetime import UTC, datetime
from functools import cache

from matbaa.ayar import CONFIG
from matbaa.fiyat import ucretler


class TavanAsildi(RuntimeError):
    pass


@cache
def tavanlar() -> dict:
    return tomllib.loads((CONFIG / "tavanlar.toml").read_text(encoding="utf-8"))


def _ay_basi(simdi: datetime) -> str:
    return simdi.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def ilan_ucreti(c, bas: str, son: str | None = None) -> float:
    """[bas, son) aralığında Printify'a açılan ürün (= Etsy ilanı) sayısı × listeleme ücreti, USD."""
    n = c.execute(
        "SELECT count(*) FROM olay WHERE varlik = 'urun' AND yeni LIKE '%:printify' AND zaman >= ? AND zaman < ?",
        (bas, son or "9999"),
    ).fetchone()[0]
    return round(n * ucretler()["listeleme_usd"], 2)


def ilan_kontrol(c, simdi: datetime | None = None) -> None:
    """Bir ilan daha açmadan önce: bu ayın listeleme harcaması + bir ilan tavanı aşıyor mu?"""
    simdi = simdi or datetime.now(UTC)
    harcanan = ilan_ucreti(c, _ay_basi(simdi))
    tavan = tavanlar()["aylik_ilan_ucreti_usd"]
    if harcanan + ucretler()["listeleme_usd"] > tavan + 1e-9:
        raise TavanAsildi(f"aylık ilan ücreti tavanı: bu ay ${harcanan:.2f} harcandı, tavan ${tavan:.2f} (config/tavanlar.toml)")


def ip_kontrol(c, simdi: datetime | None = None) -> None:
    """Bir ifade daha IP kapısına (TypeSafe çağrısı) girmeden önce: bugünkü denetim sayısı tavanda mı?"""
    simdi = simdi or datetime.now(UTC)
    bugun = simdi.date().isoformat()
    n = c.execute("SELECT count(*) FROM olay WHERE varlik = 'ifade' AND yeni LIKE 'kapi:%' AND zaman >= ?", (bugun,)).fetchone()[
        0
    ]
    tavan = tavanlar()["gunluk_ip_denetim"]
    if n >= tavan:
        raise TavanAsildi(f"günlük IP denetimi tavanı: bugün {n} ifade denetlendi, tavan {tavan} (config/tavanlar.toml)")
