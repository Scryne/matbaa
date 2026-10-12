"""Metni fonttan vektör yola çevirir.

Yazı SVG'ye <text> olarak değil yol olarak girer: genişlik ölçülebilir, çıktı fonta bağlı kalmaz,
render eden makinede font eksikliği sessizce başka fonta düşmez. Şekillendirme HarfBuzz'la
(kerning, ligatür), çizim fontTools ile yapılır. Birimler font birimidir, y aşağı doğru (SVG).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_DIZINI = Path(__file__).resolve().parents[3] / "varliklar" / "fontlar"


class EksikGlif(ValueError):
    """Fontta karşılığı olmayan karakter: sessizce kutu basmak yerine durur."""


@dataclass(frozen=True)
class Glif:
    yol: str  # kendi orijininde (taban çizgisi sol), y aşağı
    x: float  # satır içindeki ilerleme konumu
    ilerleme: float


@dataclass(frozen=True)
class Satir:
    metin: str
    yol: str  # tüm satır tek yol, taban çizgisi y=0
    x0: float
    y0: float
    x1: float
    y1: float
    ilerleme: float  # toplam ilerleme (son harfin sağı)
    glifler: tuple[Glif, ...]

    @property
    def genislik(self) -> float:
        return self.x1 - self.x0

    @property
    def yukseklik(self) -> float:
        return self.y1 - self.y0


class Font:
    def __init__(self, dosya: str | Path):
        dosya = Path(dosya)
        if not dosya.is_absolute():
            dosya = FONT_DIZINI / dosya
        self.dosya = dosya
        self.tt = TTFont(dosya)
        self.glifler = self.tt.getGlyphSet()
        self.sira = self.tt.getGlyphOrder()
        self.upm = self.tt["head"].unitsPerEm
        self._hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(dosya))))
        os2 = self.tt["OS/2"]
        self.buyuk_harf = getattr(os2, "sCapHeight", 0) or int(self.tt["hhea"].ascent * 0.7)

    def _cizim(self, ad: str, x: float) -> str:
        pen = SVGPathPen(self.glifler)
        self.glifler[ad].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        return pen.getCommands()

    def satir(self, metin: str, harf_araligi: float = 0.0) -> Satir:
        """`harf_araligi` em'in kesri (0.05 = %5 em ek boşluk)."""
        tampon = hb.Buffer()
        tampon.add_str(metin)
        tampon.guess_segment_properties()
        hb.shape(self._hb, tampon, {"kern": True, "liga": True})
        ek = harf_araligi * self.upm
        x = 0.0
        parcalar: list[str] = []
        glifler: list[Glif] = []
        sinir = BoundsPen(self.glifler)
        for bilgi, konum in zip(tampon.glyph_infos, tampon.glyph_positions):
            if bilgi.codepoint == 0:
                karakter = metin[bilgi.cluster] if bilgi.cluster < len(metin) else "?"
                raise EksikGlif(f"{self.dosya.name}: {karakter!r} için glif yok")
            ad = self.sira[bilgi.codepoint]
            gx = x + konum.x_offset
            parcalar.append(self._cizim(ad, gx))
            glifler.append(Glif(self._cizim(ad, 0), gx, konum.x_advance + ek))
            self.glifler[ad].draw(TransformPen(sinir, (1, 0, 0, -1, gx, 0)))
            x += konum.x_advance + ek
        if sinir.bounds is None:
            raise ValueError(f"boş satır: {metin!r}")
        x0, y0, x1, y1 = sinir.bounds
        return Satir(
            metin,
            " ".join(p for p in parcalar if p),
            x0,
            y0,
            x1,
            y1,
            x - ek,
            tuple(glifler),
        )


@cache
def font(dosya: str) -> Font:
    return Font(dosya)
