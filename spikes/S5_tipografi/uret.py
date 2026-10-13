"""S5 spike: 10 tipografik tasarım, iki mürekkep, kalite kapıları, önizleme panosu.

Çalıştır: uv run python spikes/S5_tipografi/uret.py
Çıktı: calisma/S5/ (git dışı)

Kayıt olarak duruyor: `el_yazisi_blok` ve GreatVibes Faz 2'de kaldırıldı; yeniden koşturmak için `git checkout 311682e`.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from matbaa.tasarim import kapilar, render
from matbaa.tasarim.sablonlar import Yazi, el_yazisi_blok, kavis, rozet, yigin

CIKTI = Path(__file__).resolve().parents[2] / "calisma" / "S5"

KOYU_MUREKKEP, ACIK_MUREKKEP = "#1d1d1f", "#f3ead8"
ACIK_KUMAS = ["#ffffff", "#efe6d2", "#c9d6c3"]  # beyaz, ivory, sage
KOYU_KUMAS = ["#141414", "#1f2a44", "#2f4a3a"]  # siyah, lacivert, orman yeşili

TASARIMLAR = {
    "01-kitap-kulubu": lambda: kavis(
        Yazi("BOOK CLUB", "AlfaSlabOne-Regular.ttf", 0.06),
        Yazi("Chapter Lover", "Lobster-Regular.ttf"),
        Yazi("EST. 2026", "BebasNeue-Regular.ttf", 0.12),
    ),
    "02-bitki": lambda: yigin(
        [
            Yazi("JUST ONE", "Anton-Regular.ttf", 0.04, 0.62),
            Yazi("MORE", "Anton-Regular.ttf", 0.02),
            Yazi("PLANT", "Anton-Regular.ttf", 0.02),
        ]
    ),
    "03-mama": lambda: rozet(
        Yazi("EST. 2026", "BebasNeue-Regular.ttf", 0.15),
        Yazi("Mama", "Shrikhand-Regular.ttf"),
        Yazi("WORTH EVERY SLEEPLESS NIGHT", "BebasNeue-Regular.ttf", 0.08),
    ),
    "04-ogretmen": lambda: el_yazisi_blok(
        Yazi("TEACH", "ArchivoBlack-Regular.ttf"),
        Yazi("love inspire", "Pacifico-Regular.ttf"),
    ),
    "05-balik": lambda: kavis(
        Yazi("REEL COOL", "Righteous-Regular.ttf", 0.05),
        Yazi("GRANDPA", "AlfaSlabOne-Regular.ttf"),
        Yazi("SINCE 1961", "BebasNeue-Regular.ttf", 0.15),
    ),
    "06-kahve": lambda: yigin(
        [
            Yazi("Powered by", "Pacifico-Regular.ttf", 0, 0.6),
            Yazi("COFFEE", "AbrilFatface-Regular.ttf", 0.02),
            Yazi("& CHAOS", "BebasNeue-Regular.ttf", 0.1, 0.55),
        ]
    ),
    "07-kosu": lambda: rozet(
        Yazi("RUN CLUB", "BebasNeue-Regular.ttf", 0.2),
        Yazi("Slow & Steady", "DMSerifDisplay-Regular.ttf"),
        Yazi("STILL LAPPING THE COUCH", "BebasNeue-Regular.ttf", 0.08),
    ),
    "08-hemsire": lambda: el_yazisi_blok(
        Yazi("NIGHT SHIFT", "Anton-Regular.ttf", 0.02),
        Yazi("survivor", "GreatVibes-Regular.ttf"),
    ),
    "09-ogretmen-yigin": lambda: yigin(
        [
            Yazi("IN MY", "BebasNeue-Regular.ttf", 0.12, 0.45),
            Yazi("TEACHER", "Shrikhand-Regular.ttf", 0.0),
            Yazi("ERA", "BebasNeue-Regular.ttf", 0.3, 0.45),
        ]
    ),
    "10-kedi": lambda: kavis(
        Yazi("PROFESSIONAL", "BebasNeue-Regular.ttf", 0.1),
        Yazi("Cat Napper", "DMSerifDisplay-Regular.ttf"),
        Yazi("CERTIFIED SINCE 2026", "BebasNeue-Regular.ttf", 0.1),
    ),
}


def main() -> None:
    CIKTI.mkdir(parents=True, exist_ok=True)
    pano: list[Image.Image] = []
    ozet = []
    for ad, kur in TASARIMLAR.items():
        t0 = time.perf_counter()
        cizim = kur()
        satir = []
        for etiket, murekkep, kumaslar in (
            ("koyu", KOYU_MUREKKEP, ACIK_KUMAS),
            ("acik", ACIK_MUREKKEP, KOYU_KUMAS),
        ):
            svg = cizim.svg(murekkep)
            (CIKTI / f"{ad}-{etiket}.svg").write_text(svg, encoding="utf-8")
            img = render.goruntu(svg)
            render.kaydet(img, CIKTI / f"{ad}-{etiket}.png")
            sonuclar = kapilar.denetle(img, murekkep, kumaslar, cizim.okunacak, cizim.en_kucuk_yazi)
            hatalar = [str(s) for s in sonuclar if not s.gecti]
            ozet.append(
                (
                    ad,
                    etiket,
                    kapilar.gecti(sonuclar),
                    hatalar,
                    [str(s) for s in sonuclar if s.kapi.split()[0] in ("en_kucuk_yazi", "okunurluk")],
                )
            )
            satir.append(render.onizleme(img, kumaslar[0], 360))
        pano.append(satir)
        print(f"{ad}: {time.perf_counter() - t0:.1f} sn")
    g, y = 360, pano[0][0].height
    tuval = Image.new("RGB", (g * 4, y * 5), "#808080")
    for i, (a, b) in enumerate(pano):
        sx, sy = (i % 2) * 2 * g, (i // 2) * y
        tuval.paste(a, (sx, sy))
        tuval.paste(b, (sx + g, sy))
    tuval.save(CIKTI / "pano.png")
    for ad, etiket, ok, hatalar, temel in ozet:
        print(
            f"{'GEÇTİ' if ok else 'KALDI'} {ad}-{etiket} | {' | '.join(temel)}" + (f" || {'; '.join(hatalar)}" if hatalar else "")
        )


if __name__ == "__main__":
    main()
