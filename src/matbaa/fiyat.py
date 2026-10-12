"""Sipariş başına net kâr: Etsy TR ücret yığını + Printify maliyeti. Fiyat kararları buna göre verilir (K-11)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache

from matbaa.ayar import CONFIG


@cache
def ucretler() -> dict:
    return tomllib.loads((CONFIG / "ucretler.toml").read_text(encoding="utf-8"))


@cache
def urunler() -> dict:
    return tomllib.loads((CONFIG / "urunler.toml").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Kirilim:
    gelir: float
    etsy_ucret: float
    kdv: float
    uretim: float
    offsite: float
    net: float

    @property
    def marj(self) -> float:
        return self.net / self.gelir if self.gelir else 0.0


def hesap(fiyat: float, kargo: float, uretim: float, offsite: bool = False, ilan_try: bool = False) -> Kirilim:
    u = ucretler()
    gelir = fiyat + kargo
    vergi_dahil = gelir * (1 + u["abd_satis_vergisi_ort"])
    etsy = (
        u["listeleme_usd"]
        + u["islem_orani"] * gelir
        + u["odeme_orani"] * vergi_dahil
        + u["odeme_sabit_try"] / u["try_usd"]
        + u["rof_orani"] * gelir
        + (0.0 if ilan_try else u["kur_donusum_orani"] * gelir)
    )
    off = u["offsite_orani"] * gelir if offsite else 0.0
    kdv = u["ucretlere_kdv"] * (etsy + off)
    net = gelir - etsy - off - kdv - uretim
    return Kirilim(round(gelir, 2), round(etsy, 2), round(kdv, 2), round(uretim, 2), round(off, 2), round(net, 2))


def urun_hesap(urun: str, offsite: bool = False) -> Kirilim:
    p = urunler()[urun]
    return hesap(p["fiyat"], p["kargo"], p["tahmini_maliyet"] + p["tahmini_abd_kargo"], offsite)


def beklenen_net(urun: str) -> float:
    """Offsite reklam payı tahminiyle ağırlıklı sipariş başı net."""
    pay = ucretler()["offsite_payi_tahmini"]
    return round((1 - pay) * urun_hesap(urun).net + pay * urun_hesap(urun, offsite=True).net, 2)
