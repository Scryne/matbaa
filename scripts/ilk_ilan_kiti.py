"""Etsy mağaza açılışı için ilk ilan kiti: Etsy açılışta en az bir ilan ister; Printify bağlanınca bu ilan silinir.

    uv run python scripts/ilk_ilan_kiti.py [tasarim_id]

Çıktı `calisma/ilk_ilan_kiti/`: iki tişört provası (2000x2000 JPG), baskı dosyası, `ilan.txt` (başlık, 13 etiket, açıklama, fiyat).
"""

from __future__ import annotations

import json
import sys

from PIL import Image, ImageDraw, ImageFilter

from matbaa import db
from matbaa.ayar import KOK

CIKTI = KOK / "calisma" / "ilk_ilan_kiti"
# Paneldeki tişört silüetiyle aynı (400x440 düzlem), çokgen olarak.
TISORT = [
    (120, 22),
    (160, 40),
    (200, 46),
    (240, 40),
    (280, 22),
    (382, 74),
    (346, 158),
    (308, 138),
    (308, 424),
    (92, 424),
    (92, 138),
    (54, 158),
    (18, 74),
]


def prova(baski: Image.Image, kumas: str, zemin: str = "#e9e6df", g: int = 2000) -> Image.Image:
    olcek = g * 0.88 / 440  # silüet tuvalin %88'i: kenarlarda nefes payı
    ox, oy = (g - 400 * olcek) / 2, (g - 440 * olcek) / 2
    tuval = Image.new("RGB", (g, g), zemin)
    golge = Image.new("L", (g, g), 0)
    ImageDraw.Draw(golge).polygon([(ox + x * olcek + 14, oy + yy * olcek + 22) for x, yy in TISORT], fill=90)
    tuval.paste(Image.new("RGB", (g, g), "#000000"), mask=golge.filter(ImageFilter.GaussianBlur(26)))
    ImageDraw.Draw(tuval).polygon([(ox + x * olcek, oy + yy * olcek) for x, yy in TISORT], fill=kumas)
    kutu = baski.getchannel("A").getbbox()
    b = baski.crop((0, 0, baski.width, kutu[3] + 40))
    genislik = int(150 * olcek)  # göğüs baskısı: silüet genişliğinin %37,5'i (panelle aynı)
    b = b.resize((genislik, int(b.height * genislik / b.width)), Image.LANCZOS)
    tuval.paste(b, (int(ox + 125 * olcek), int(oy + 92 * olcek)), b)
    return tuval


def main() -> None:
    c = db.baglan()
    secili = int(sys.argv[1]) if len(sys.argv) > 1 else None
    t = c.execute(
        "SELECT id, dosyalar FROM tasarim WHERE durum = 'onay_bekliyor'" + (" AND id = ?" if secili else " ORDER BY id LIMIT 1"),
        (secili,) if secili else (),
    ).fetchone()
    il = c.execute("SELECT * FROM ilan WHERE tasarim_id = ? AND urun = 'tisort'", (t["id"],)).fetchone()
    d = json.loads(t["dosyalar"])
    CIKTI.mkdir(parents=True, exist_ok=True)
    koyu, acik = Image.open(KOK / d["koyu_png"]).convert("RGBA"), Image.open(KOK / d["acik_png"]).convert("RGBA")
    prova(koyu, "#f0e8d6").save(CIKTI / "1-prova-ivory.jpg", quality=92)
    prova(acik, "#1f2a44").save(CIKTI / "2-prova-navy.jpg", quality=92)
    koyu.save(CIKTI / "baski-dosyasi-acik-kumas.png")
    (CIKTI / "ilan.txt").write_text(
        "\n".join(
            [
                f"BAŞLIK:\n{il['baslik']}\n",
                "ETİKETLER (13, tek tek gir):\n" + "\n".join(json.loads(il["etiketler"])) + "\n",
                f"FİYAT: {il['fiyat']} USD  ·  KARGO: {il['kargo']} USD\n",
                f"AÇIKLAMA:\n{il['aciklama']}",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Kit hazır → {CIKTI} (tasarım #{t['id']})")


if __name__ == "__main__":
    main()
