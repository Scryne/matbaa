"""Niş radarı (Faz 15): yükselen hobi/meslek nişlerini Etsy API verisiyle sıralar.

Ölçü (aday başına tek istek): `findAllListingsActive` "<kelime> shirt", score sıralı üst ilanlar.
- rekabet = toplam aktif ilan (`count`)
- talep = üst ilanların günlük görüntülenme hızı medyanı (views / yaş günü; `min_yas_gun`'den genç ilan dışarıda)
- favori oranı = favori / görüntülenme (ilginin satın almaya yakınlığı için zayıf sinyal)
- fırsat = talep / log10(rekabet): çok talep, az ilan. Mevcut nişler aynı ölçekle kıyas için yazılır.
Marka kapısı (USPTO) aday kelimesini ve en sık etiketleri süzer. Seçim ve niş kartı Aria'nın; radar karar vermez, sıralar.
"""

from __future__ import annotations

import json
import math
import statistics
import time
import tomllib
from collections import Counter
from datetime import UTC, datetime

from matbaa.ayar import CONFIG, KOK

CIKTI = KOK / "calisma" / "radar"


def ayar() -> dict:
    return tomllib.loads((CONFIG / "radar.toml").read_text(encoding="utf-8"))


def olc(etsy, kelime: str, simdi: float | None = None) -> dict:
    a = ayar()
    simdi = simdi or time.time()
    r = etsy._i("GET", "/listings/active", params={"keywords": f"{kelime} {a['ek']}", "limit": a["ust_ilan"], "sort_on": "score"})
    hizlar, favori, gor, fiyat, etiket = [], 0, 0, [], Counter()
    for x in r.get("results", []):
        yas = (simdi - (x.get("original_creation_timestamp") or x.get("creation_timestamp") or simdi)) / 86400
        v = x.get("views") or 0
        favori += x.get("num_favorers") or 0
        gor += v
        if yas >= a["min_yas_gun"]:
            hizlar.append(v / yas)
        p = x.get("price") or {}
        if p.get("amount"):
            fiyat.append(p["amount"] / (p.get("divisor") or 100))
        etiket.update(t.lower() for t in x.get("tags") or [])
    rekabet = int(r.get("count") or 0)
    talep = statistics.median(hizlar) if hizlar else 0.0
    return {
        "kelime": kelime,
        "rekabet": rekabet,
        "talep": round(talep, 3),
        "favori_orani": round(favori / gor, 4) if gor else 0.0,
        "medyan_fiyat": round(statistics.median(fiyat), 2) if fiyat else None,
        "firsat": round(talep / math.log10(max(rekabet, 10)), 4),
        "ornek": len(hizlar),
        "etiketler": [t for t, _ in etiket.most_common(15)],
    }


def tara(etsy, marka_dizini=None, bekle=time.sleep, yazdir=print) -> dict:
    """Bütün adayları ve mevcut nişleri ölçer, fırsata göre sıralar; marka kapısından geçmeyen aday işaretlenir."""
    a = ayar()
    sonuc: dict = {"zaman": datetime.now(UTC).isoformat(timespec="seconds"), "adaylar": [], "mevcut": []}
    for grup, liste in (("mevcut", a["mevcut"]), ("adaylar", a["adaylar"])):
        for k in liste:
            try:
                o = olc(etsy, k)
            except Exception as e:  # tek aday düşerse tarama sürer
                yazdir(f"  radar hata {k}: {type(e).__name__}: {str(e)[:120]}")
                continue
            if marka_dizini is not None:
                o["marka_temiz"] = bool(marka_dizini.kontrol(f"{k} {a['ek']}").temiz)
            sonuc[grup].append(o)
            bekle(0.25)  # Etsy 5 istek/sn
    for grup in ("mevcut", "adaylar"):
        sonuc[grup].sort(key=lambda o: o["firsat"], reverse=True)
    esik = statistics.median([o["firsat"] for o in sonuc["mevcut"]]) if sonuc["mevcut"] else 0.0
    sonuc["mevcut_medyan_firsat"] = esik
    for o in sonuc["adaylar"] + sonuc["mevcut"]:
        o["giysi"] = o["medyan_fiyat"] is None or o["medyan_fiyat"] >= a["min_medyan_fiyat"]
    sonuc["one_cikan"] = [
        o["kelime"] for o in sonuc["adaylar"] if o["firsat"] > esik and o.get("marka_temiz", True) and o["giysi"]
    ][:8]
    return sonuc


def kaydet(sonuc: dict) -> tuple:
    CIKTI.mkdir(parents=True, exist_ok=True)
    gun = sonuc["zaman"][:10]
    js = CIKTI / f"{gun}.json"
    js.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    satirlar = [
        f"# Niş radarı {gun}",
        "",
        f"Fırsat = günlük görüntülenme hızı medyanı / log10(ilan sayısı). Mevcut nişlerin medyanı: {sonuc['mevcut_medyan_firsat']:.4f}.",
        f"Öne çıkan (mevcut medyanın üstünde, marka temiz): {', '.join(sonuc['one_cikan']) or '-'}",
        "",
        "| Grup | Kelime | Fırsat | Talep (görüntülenme/gün) | İlan | Favori oranı | Medyan fiyat | Marka |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for grup in ("mevcut", "adaylar"):
        for o in sonuc[grup]:
            satirlar.append(
                f"| {grup} | {o['kelime']} | {o['firsat']:.4f} | {o['talep']:.2f} | {o['rekabet']} | {o['favori_orani']:.3f} | "
                f"{o['medyan_fiyat'] or '-'} | {'temiz' if o.get('marka_temiz', True) else 'RİSK'}{'' if o.get('giysi', True) else ' · desen?'} |"
            )
    md = CIKTI / f"{gun}.md"
    md.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return js, md
