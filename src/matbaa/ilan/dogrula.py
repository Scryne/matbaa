"""Etsy ilan kuralları: düzeltilebilen düzeltilir, düzeltilemeyen `sorunlar`a yazılır (boş değilse ilan onaya gitmez).

Sınırlar: başlık ≤ 140 karakter, % : & + birer kez; 13 etiket, her biri ≤ 20 karakter, yalnız harf/rakam/boşluk ve - ' ™ © ®
dışı karakter yok; aynı etiket iki kez yok. Açıklamada AI beyanı ve üretim ortağı cümlesi zorunlu (Creativity Standards).
"""

from __future__ import annotations

import re

from matbaa.ilan.metin import AI_BEYANI, URETIM_ORTAGI, Ilan

BASLIK_MAKS = 140
BASLIK_KELIME = 15
ETIKET_SAYI = 13
ETIKET_MAKS = 20
YASAK_BASLIK = re.compile(r"[!$^*{}<>\[\]~`]|(\b[A-Z]{4,}\b.*){3,}")  # sembol yığını ya da baştan sona büyük harf


# Etiket bu kelimelerle bitemez: 20 karaktere kısaltılınca "christmas gift for" gibi yarım ifade kalıyordu (ilk 44 ilan).
ASILI_KELIME = {
    "for",
    "to",
    "of",
    "and",
    "or",
    "the",
    "a",
    "an",
    "with",
    "in",
    "on",
    "at",
    "my",
    "your",
    "from",
    "by",
    "who",
    "is",
}


def _etiket_temizle(t: str) -> str:
    t = re.sub(r"[^A-Za-z0-9 '\-]", "", t).strip().lower()
    return re.sub(r"\s+", " ", t)


def _asiliyi_at(t: str) -> str:
    k = t.split()
    while k and k[-1] in ASILI_KELIME:
        k.pop()
    return " ".join(k)


# Etsy API (createDraftListing/updateListing `title`): "%, :, & ve + karakterleri birer kez kullanılabilir"; ikincisi ilanı reddettirir.
TEK_KULLANIM = {"&": " and ", "+": " and ", ":": ",", "%": " percent"}


def _tek_kullanim(baslik: str) -> str:
    """Dört özel karakterin ilkini bırakır, sonrakileri sözcükle değiştirir ("Fishing & Hunting & Camping" → "... and Camping")."""
    for ch, yerine in TEK_KULLANIM.items():
        if baslik.count(ch) > 1:
            ilk = baslik.index(ch) + 1
            baslik = baslik[:ilk] + baslik[ilk:].replace(ch, yerine)
    return re.sub(r"\s+", " ", re.sub(r"\s+,", ",", baslik)).strip()


def dogrula(ilan: Ilan) -> Ilan:
    sorunlar: list[str] = []
    baslik = _tek_kullanim(re.sub(r"\s+", " ", ilan.baslik).strip())
    if len(baslik) > BASLIK_MAKS:
        kes = baslik[:BASLIK_MAKS].rsplit(" ", 1)[0].rstrip(",-|")
        baslik = kes
    if len(baslik.split()) > BASLIK_KELIME:
        # Virgül sınırından kısalt: Etsy kısa, ürün adıyla başlayan başlık öneriyor (S7).
        parcalar, kalan = [], baslik.split(",")
        for p in kalan:
            if len(" ".join(parcalar + [p]).split()) > BASLIK_KELIME:
                break
            parcalar.append(p)
        baslik = ",".join(parcalar).strip(" ,") if parcalar else " ".join(baslik.split()[:BASLIK_KELIME])
    if YASAK_BASLIK.search(baslik):
        sorunlar.append("başlıkta yasak sembol ya da aşırı büyük harf")

    etiketler: list[str] = []
    for t in ilan.etiketler:
        t = _etiket_temizle(t)
        if not t or len(t) > ETIKET_MAKS:
            # uzun etiketi kelime sınırında kısalt; anlamsız kalırsa at
            kisa = t[:ETIKET_MAKS].rsplit(" ", 1)[0] if len(t) > ETIKET_MAKS else t
            if len(kisa.split()) < 2:
                continue
            t = kisa
        t = _asiliyi_at(t)
        if len(t.split()) < 2 and len(t) < 6:
            continue  # tek kısa kelime alıcı araması değil
        if t not in etiketler:
            etiketler.append(t)
    etiketler = etiketler[:ETIKET_SAYI]
    if len(etiketler) < ETIKET_SAYI:
        sorunlar.append(f"{len(etiketler)} geçerli etiket (13 gerekli)")

    if AI_BEYANI not in ilan.aciklama:
        sorunlar.append("AI beyanı yok")
    if URETIM_ORTAGI not in ilan.aciklama:
        sorunlar.append("üretim ortağı cümlesi yok")
    return Ilan(baslik, etiketler, ilan.aciklama, ilan.alt_metin, sorunlar)
