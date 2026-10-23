"""Sipariş başına net kâr: Etsy TR ücret yığını + Printify maliyeti. Fiyat kararları buna göre verilir (K-11)."""

from __future__ import annotations

import json
import re
import time
import tomllib
from dataclasses import dataclass
from functools import cache

from matbaa.ayar import CONFIG, VERI

KUR_DOSYASI = VERI / "kur.json"
KUR_TAZELIK_GUN = 7
TCMB = "https://www.tcmb.gov.tr/kurlar/today.xml"


@cache
def ucretler() -> dict:
    return tomllib.loads((CONFIG / "ucretler.toml").read_text(encoding="utf-8"))


@cache
def urunler() -> dict:
    return tomllib.loads((CONFIG / "urunler.toml").read_text(encoding="utf-8"))


def _ay_gun(gun) -> str:
    from datetime import date

    return (gun or date.today()).strftime("%m-%d")


def mevsimde(urun: str, gun=None) -> bool:
    """Mevsimlik ürün (`kosul.bas`–`kosul.son`, ay-gün) bugün açılabilir/yayınlanabilir mi; koşulsuz ürün hep açık."""
    k = urunler()[urun].get("kosul")
    return not k or k["bas"] <= _ay_gun(gun) <= k["son"]


def mevsim_bitti(urun: str, gun=None) -> bool:
    """Mevsimlik ürünün aktif ilanı pasife alınmalı mı (`kosul.kapanis`tan sonra, yeni pencere açılana kadar)."""
    k = urunler()[urun].get("kosul")
    if not k or not k.get("kapanis"):
        return False
    g = _ay_gun(gun)
    return g >= k["kapanis"] or g < k["bas"]


def urun_uygun(urun: str, nis: str, satirlar: list[str], gun=None) -> bool:
    """Bu tasarıma bu ürün açılır mı. `yalniz_satan` (kupa) satışa bağlıdır, burada hep hayır (yayin.kosullu_ac açar).
    `kosul` (süs, K-30): pencere içinde ve niş listede ya da basılı metinde Noel kelimesi varsa.
    K-37: `cizimli` nişin tasarımına yalnız `tur = "cizim"` ürünler açılır, o ürünler de yalnız ona (baskı dosyası raster çizim).
    `cizimli_de` (süs, 2026-10-23): iki hatta da açılır; süs baskısı tasarımın kendi PNG'sini daireye sığdırır."""
    from matbaa.ifade.uret import nisler

    p = urunler()[urun]
    if not p.get("cizimli_de") and (p.get("tur") == "cizim") != bool(nisler().get(nis, {}).get("cizimli")):
        return False
    if p.get("yalniz_satan"):
        return False
    k = p.get("kosul")
    if not k:
        return True
    if not mevsimde(urun, gun):
        return False
    if nis in k.get("nisler", []):
        return True
    if k.get("mevsim_kelimesi"):
        from matbaa.tasarim.ikon import MEVSIM_KELIMELERI

        kelimeler = {w.strip(".,!?'’\"()") for w in " ".join(satirlar).upper().split()}
        return bool(kelimeler & MEVSIM_KELIMELERI)
    return False


def tasarim_urunleri(nis: str, satirlar: list[str], gun=None) -> list[str]:
    """Yeni tasarımın ilan metni yazılacak ürünleri (katalog sırasıyla)."""
    return [u for u in urunler() if urun_uygun(u, nis, satirlar, gun)]


def kur_guncelle(http=None) -> float:
    """TCMB günlük USD döviz satış kuru → veri/kur.json. Etsy'nin TRY sabit ödeme ücreti (14 TRY) bu kurla USD'ye çevrilir."""
    import httpx

    if http is None:
        with httpx.Client(timeout=30) as h:
            r = h.get(TCMB)
    else:
        r = http.get(TCMB)
    r.raise_for_status()
    m = re.search(r'Kod="USD".*?<ForexSelling>([\d.]+)</ForexSelling>', r.text, re.S)
    if not m:
        raise ValueError("TCMB yanıtında USD satış kuru yok")
    kur = float(m.group(1))
    VERI.mkdir(exist_ok=True)
    KUR_DOSYASI.write_text(json.dumps({"try_usd": kur, "zaman": int(time.time()), "kaynak": TCMB}))
    return kur


def try_usd() -> float:
    """Taze (≤ 7 gün) TCMB kuru varsa o, yoksa config'teki elle girilmiş değer."""
    try:
        k = json.loads(KUR_DOSYASI.read_text())
        if time.time() - k["zaman"] <= KUR_TAZELIK_GUN * 86400:
            return float(k["try_usd"])
    except (OSError, ValueError, KeyError):
        pass
    return ucretler()["try_usd"]


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


def hesap(fiyat: float, kargo: float, uretim: float, offsite: bool = False, ilan_try: bool = False, adet: int = 1) -> Kirilim:
    """`adet`: siparişteki ürün adedi; Etsy satılan her adet için ilanı yeniler (listeleme ücreti adet başına)."""
    u = ucretler()
    gelir = fiyat + kargo
    vergi_dahil = gelir * (1 + u["abd_satis_vergisi_ort"])
    etsy = (
        u["listeleme_usd"] * max(adet, 1)
        + u["islem_orani"] * gelir
        + u["odeme_orani"] * vergi_dahil
        + u["odeme_sabit_try"] / try_usd()
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
