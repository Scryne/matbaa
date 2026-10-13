"""Proje yolları ve yapılandırma."""

from __future__ import annotations

import tomllib
from functools import cache
from pathlib import Path

KOK = Path(__file__).resolve().parents[2]
CONFIG = KOK / "config"
VERI = KOK / "veri"


@cache
def modeller() -> dict:
    return tomllib.loads((CONFIG / "modeller.toml").read_text(encoding="utf-8"))


def env_yukle(dosya=None) -> None:
    """`.env` satırlarını ortam değişkenine yükler (var olanı ezmez). Gizli bilgiler git dışında kalır."""
    import os

    dosya = dosya or KOK / ".env"
    if not dosya.exists():
        return
    for satir in dosya.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if satir and not satir.startswith("#") and "=" in satir:
            k, v = satir.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def env_yaz(anahtar: str, deger: str, dosya=None) -> None:
    """`.env`'de `anahtar=` satırını yazar (yoksa ekler) ve ortama da koyar: kurulum betikleri kimlikleri elle kopyalatmaz."""
    import os

    dosya = dosya or KOK / ".env"
    satirlar = dosya.read_text(encoding="utf-8").splitlines() if dosya.exists() else []
    yeni = f"{anahtar}={deger}"
    for i, s in enumerate(satirlar):
        if s.split("=", 1)[0].strip() == anahtar:
            satirlar[i] = yeni
            break
    else:
        satirlar.append(yeni)
    dosya.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    os.environ[anahtar] = deger
