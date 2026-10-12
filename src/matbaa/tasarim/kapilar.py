"""Baskı dosyası kalite kapıları.

Her kapı ölçtüğü değeri ve eşiği döner; hiçbiri sessizce geçmez. Eşiklerin kaynağı:
Printful/Printify baskı dosyası rehberleri (yarı saydam piksel = beyaz alt baskı/hale,
kenarda artık piksel, ince çizgi) — docs/arastirma/02 ve 04.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image
from scipy import ndimage

from .sablonlar import TUVAL_G, TUVAL_Y

KENAR_PAYI = 60  # px, ~5 mm
YARI_SAYDAM_MAKS = 0.06  # kenar yumuşatması dışındaki yarı saydamlık hata sayılır
INCE_YARICAP = 3  # px; ~0,6 mm'den ince çizgi DTG'de kopar
INCE_KAYIP_MAKS = 0.03
KONTRAST_MIN = 3.0  # WCAG büyük yazı eşiği; kumaş üstünde okunurluk
EN_KUCUK_YAZI = 150  # px (~1,3 cm); altı göğüs baskısında uzaktan okunmaz
OKUNURLUK_MIN = 0.8  # beklenen kelimelerin OCR'da bulunma oranı


@dataclass(frozen=True)
class Sonuc:
    kapi: str
    gecti: bool
    deger: float
    esik: str

    def __str__(self) -> str:
        return f"{'✓' if self.gecti else '✗'} {self.kapi}: {self.deger:.4g} ({self.esik})"


def _bagil_parlaklik(hex_renk: str) -> float:
    r, g, b = (int(hex_renk.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def kanal(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)


def kontrast(a: str, b: str) -> float:
    la, lb = sorted((_bagil_parlaklik(a), _bagil_parlaklik(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@lru_cache(maxsize=1)
def _ocr():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _kelimeler(metin: str) -> list[str]:
    return [k for k in re.findall(r"[A-Z0-9]+", metin.upper()) if k]


def okunurluk(img: Image.Image, murekkep: str, beklenen: list[str]) -> tuple[float, list[str]]:
    """Tasarımı kendi zemininde OCR'la okur; beklenen kelimelerin kaçı bulunuyor.

    Yazım hatası kodla üretilen yazıda olmaz; bu kapı yerleşimin yazıyı bozup bozmadığını
    (üst üste binme, aşırı kavis, okunmaz el yazısı) yakalar.
    """
    zemin = "#ffffff" if kontrast(murekkep, "#ffffff") >= kontrast(murekkep, "#000000") else "#000000"
    tuval = Image.new("RGBA", img.size, zemin)
    tuval.alpha_composite(img)
    a = np.asarray(img.getchannel("A"))
    ys, xs = np.nonzero(a)
    kirp = tuval.crop((max(xs.min() - 80, 0), max(ys.min() - 80, 0), xs.max() + 80, ys.max() + 80))
    # Tek ölçek yetmiyor: 1600 px'de dev harfler algılanmıyor (S5: "MORE PLANT" kaçtı); iki ölçeğin birleşimi.
    # Yön sınıflandırıcısı kapalı: el yazısını ters çevirip okuyordu ("Powered by" → "hg pauromod").
    okunan: list[str] = []
    for g in (1000, 700):
        kucuk = kirp.convert("RGB").resize((g, max(int(kirp.height * g / kirp.width), 1)), Image.LANCZOS)
        sonuc, _ = _ocr()(np.asarray(kucuk), use_cls=False)
        okunan += _kelimeler(" ".join(r[1] for r in (sonuc or [])))
    birlesik = "".join(okunan)
    bulunan, eksik = 0, []
    for k in (k for satir in beklenen for k in _kelimeler(satir)):
        if k in okunan or k in birlesik or any(difflib.SequenceMatcher(None, k, o).ratio() >= 0.8 for o in okunan):
            bulunan += 1
        else:
            eksik.append(k)
    toplam = bulunan + len(eksik)
    return (bulunan / toplam if toplam else 1.0), eksik


def denetle(
    img: Image.Image,
    murekkep: str,
    kumaslar: list[str],
    beklenen: list[str] | None = None,
    en_kucuk_yazi: float | None = None,
) -> list[Sonuc]:
    a = np.asarray(img.getchannel("A"))
    sonuc = [
        Sonuc(
            "boyut",
            img.size == (TUVAL_G, TUVAL_Y),
            img.size[0] * 10000 + img.size[1],
            f"= {TUVAL_G}x{TUVAL_Y}",
        )
    ]
    dolu = a > 0
    if not dolu.any():
        return sonuc + [Sonuc("bos_degil", False, 0, "> 0 piksel")]
    ys, xs = np.nonzero(dolu)
    pay = min(xs.min(), ys.min(), TUVAL_G - 1 - xs.max(), TUVAL_Y - 1 - ys.max())
    sonuc.append(Sonuc("kenar_payi", pay >= KENAR_PAYI, pay, f">= {KENAR_PAYI} px"))

    opak = a == 255
    yari = dolu & ~opak
    # Kenar yumuşatması (anti-alias) yalnız opak bölgenin 1-2 px çevresinde olur; onun dışındaki
    # yarı saydamlık gölge/degrade demektir ve DTG'de hale basar.
    kenar = ndimage.binary_dilation(opak, iterations=2) & ~opak
    serbest_yari = yari & ~kenar
    oran = serbest_yari.sum() / max(dolu.sum(), 1)
    sonuc.append(Sonuc("yari_saydam", oran <= YARI_SAYDAM_MAKS, oran, f"<= {YARI_SAYDAM_MAKS}"))

    govde = a >= 128
    disk = np.hypot(*np.mgrid[-INCE_YARICAP : INCE_YARICAP + 1, -INCE_YARICAP : INCE_YARICAP + 1]) <= INCE_YARICAP
    acilmis = ndimage.binary_opening(govde, structure=disk)
    kayip = (govde & ~acilmis).sum() / max(govde.sum(), 1)
    sonuc.append(
        Sonuc(
            "ince_cizgi",
            kayip <= INCE_KAYIP_MAKS,
            kayip,
            f"<= {INCE_KAYIP_MAKS} kayıp, r={INCE_YARICAP}px",
        )
    )

    # Bilgi amaçlı: mürekkep alanı (kumaşın sertleşmesi ve maliyet). Kapı değil.
    kutu = (xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)
    sonuc.append(Sonuc("murekkep_orani", True, govde.sum() / kutu, "bilgi"))

    for k in kumaslar:
        oran_k = kontrast(murekkep, k)
        sonuc.append(Sonuc(f"kontrast {k}", oran_k >= KONTRAST_MIN, oran_k, f">= {KONTRAST_MIN}"))
    if en_kucuk_yazi is not None:
        sonuc.append(
            Sonuc(
                "en_kucuk_yazi",
                en_kucuk_yazi >= EN_KUCUK_YAZI,
                en_kucuk_yazi,
                f">= {EN_KUCUK_YAZI} px",
            )
        )
    if beklenen:
        puan, eksik = okunurluk(img, murekkep, beklenen)
        sonuc.append(
            Sonuc(
                "okunurluk" + (f" eksik={','.join(eksik)}" if eksik else ""),
                puan >= OKUNURLUK_MIN,
                puan,
                f">= {OKUNURLUK_MIN}",
            )
        )
    return sonuc


def gecti(sonuclar: list[Sonuc]) -> bool:
    return all(s.gecti for s in sonuclar)
