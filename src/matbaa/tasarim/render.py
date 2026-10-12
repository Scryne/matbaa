"""SVG → şeffaf PNG baskı dosyası (4500x5400, 300 DPI)."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import resvg_py
from PIL import Image

from .sablonlar import TUVAL_G, TUVAL_Y

DPI = 300


def png_bayt(svg: str) -> bytes:
    # Yazılar yol olduğu için sistem fontu yüklenmez: render her makinede aynı.
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=TUVAL_G, height=TUVAL_Y, skip_system_fonts=True))


def goruntu(svg: str) -> Image.Image:
    return Image.open(io.BytesIO(png_bayt(svg))).convert("RGBA")


def kaydet(img: Image.Image, yol: str | Path) -> Path:
    yol = Path(yol)
    yol.parent.mkdir(parents=True, exist_ok=True)
    img.save(yol, dpi=(DPI, DPI), optimize=True)
    return yol


def onizleme(img: Image.Image, kumas: str, genislik: int = 600) -> Image.Image:
    """Göz kontrolü için: tasarımı kumaş renginde küçük bir zemine bas."""
    zemin = Image.new("RGBA", img.size, kumas)
    zemin.alpha_composite(img)
    oran = genislik / img.width
    return zemin.convert("RGB").resize((genislik, int(img.height * oran)), Image.LANCZOS)


def alfa(img: Image.Image) -> np.ndarray:
    return np.asarray(img.getchannel("A"))
