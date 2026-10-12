"""IP kapısı: bir tasarımın tüm ifadeleri yayından önce buradan geçer.

Sıra: önce kod (USPTO, ücretsiz, kesin), sonra anlamsal katman (Jev). Bir satır bile reddedilirse tasarım
reddedilir; "insan" sonucu onay kuyruğuna gider. Yanlış ret ucuzdur (yeni ifade üretilir), kaçan ifade
mağazaya şikâyet getirir: kurallar kaçırmayı en aza indirecek yönde seçildi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import anlam, marka


@dataclass
class Karar:
    karar: str  # "temiz" | "ret" | "insan"
    nedenler: list[str] = field(default_factory=list)
    kayit: list[dict] = field(default_factory=list)  # satır bazında ham sinyaller (sonradan kalibrasyon için)


def denetle(satirlar: list[str], nis: str, anlamsal: bool = True) -> Karar:
    d = marka.dizin()
    k = Karar("temiz")
    tum = " ".join(satirlar)
    for ifade in dict.fromkeys([*satirlar, tum]):
        m = d.kontrol(ifade)
        satir = {"ifade": ifade, "uspto_red": m.reddet, "adaylar": m.adaylar, "benzerler": m.benzerler}
        k.kayit.append(satir)
        if not m.temiz:
            k.karar = "ret"
            k.nedenler += [f"USPTO: {r[0]} ({r[1]}, seri {r[2]})" for r in m.reddet]
    if k.karar == "ret" or not anlamsal:
        return k
    y = anlam.yargila(tum, f"T-shirt slogan for a {nis} niche shop", k.kayit[-1]["benzerler"])
    k.kayit.append({"anlam": y.karar, "olasiliklar": y.olasiliklar, "model": y.model})
    if y.karar != "temiz":
        k.karar = y.karar
        k.nedenler += [f"Jev: {n}" for n in y.nedenler]
    return k
