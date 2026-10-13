"""Slogan yapısından (üst / ana / alt) şablon ve font seçimi, kalite kapılarıyla birlikte.

Aynı mağazada aynı şablon + ana font çifti art arda tekrar etmesin (toplu üretim görünümüne karşı, K-4):
son `CESITLILIK_PENCERE` tasarımda kullanılan çiftler sona atılır; şablonlar son `SABLON_PENCERE` tasarımdaki
kullanımı en az olandan başlayarak denenir (ilk 44 tasarımın 43'ü `yigin` çıkmıştı).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from PIL import Image

from . import kapilar, render
from .sablonlar import Cizim, Yazi, ayirici, cerceve, dengeli_bol, egik, el_yazisi, kavis, madalyon, rozet, yigin

KOYU_MUREKKEP, ACIK_MUREKKEP = "#1d1d1f", "#f3ead8"


def _kumaslar(murekkep: str) -> list[str]:
    """Katalogdaki, bu mürekkeple basılacak tüm kumaş renkleri: kontrast kapısı satılacak her renge karşı ölçülür."""
    from matbaa.fiyat import urunler

    return sorted({r["hex"] for u in urunler().values() for r in u["renkler"] if r["murekkep"] == murekkep})


ACIK_KUMAS = _kumaslar("koyu")  # koyu mürekkep → açık kumaşlar
KOYU_KUMAS = _kumaslar("acik")

# Vurgu paletleri: (açık kumaşta vurgu, koyu kumaşta vurgu). Küçük satırlar, yay yazısı ve çizgiler bu renge geçer.
# Kontrast kapısından geçmeyen palet (ör. hardal adaçayı yeşilinde) aday olmaz; None = tek renk.
PALETLER: dict[str, tuple[str, str] | None] = {
    "tek": None,
    "kiremit": ("#9a3a2b", "#e8826a"),
    "orman": ("#2f5d46", "#9cc4a2"),
    "lacivert": ("#23395b", "#8fb8d8"),
    "hardal": ("#76510c", "#e3b448"),
}


def gecerli_paletler() -> list[str]:
    ok = []
    for ad, p in PALETLER.items():
        if p is None or (
            min(kapilar.kontrast(p[0], k) for k in ACIK_KUMAS) >= kapilar.KONTRAST_MIN
            and min(kapilar.kontrast(p[1], k) for k in KOYU_KUMAS) >= kapilar.KONTRAST_MIN
        ):
            ok.append(ad)
    return ok


CESITLILIK_PENCERE = 5  # (şablon, ana font) çifti bu kadar tasarımda bir kez
SABLON_PENCERE = 12  # şablon dengesi: son bu kadar tasarımda en az kullanılan şablon önce denenir

# Şablon–font uyum tablosu (Faz 2). Roller: ana = büyük blok satır; kucuk = büyük harfli ikincil satır;
# kavis = yay üstü yazı (dar ve düzgün kenarlı); el = el yazısı, yalnız ikincil satırda ve kendi büyük/küçük harfiyle.
# Örnek sayfası: calisma/faz2/fontlar.png. İnce çizgili el yazısı (GreatVibes) baskı kapısında kopar, havuzda yok.
FONTLAR: dict[str, set[str]] = {
    "Anton-Regular.ttf": {"ana", "kucuk"},
    "AlfaSlabOne-Regular.ttf": {"ana", "kavis"},
    "ArchivoBlack-Regular.ttf": {"ana", "kucuk", "kavis"},
    "Shrikhand-Regular.ttf": {"ana"},
    "AbrilFatface-Regular.ttf": {"ana"},
    "DMSerifDisplay-Regular.ttf": {"ana"},
    "Righteous-Regular.ttf": {"ana", "kucuk", "kavis"},
    "BebasNeue-Regular.ttf": {"ana", "kucuk", "kavis"},
    "Bevan-Regular.ttf": {"ana", "kavis"},
    "BlackOpsOne-Regular.ttf": {"ana"},
    "BowlbyOne-Regular.ttf": {"ana"},
    "Bungee-Regular.ttf": {"ana", "kucuk", "kavis"},
    "ChangaOne-Regular.ttf": {"ana", "kavis"},
    "FjallaOne-Regular.ttf": {"ana", "kucuk"},
    "Graduate-Regular.ttf": {"kucuk", "kavis"},
    "HoltwoodOneSC-Regular.ttf": {"ana"},
    "Knewave-Regular.ttf": {"ana"},
    "LilitaOne-Regular.ttf": {"ana"},
    "PassionOne-Regular.ttf": {"ana", "kucuk"},
    "PatuaOne-Regular.ttf": {"ana"},
    "Rye-Regular.ttf": {"ana"},
    "SigmarOne-Regular.ttf": {"ana"},
    "Staatliches-Regular.ttf": {"ana", "kucuk", "kavis"},
    "TitanOne-Regular.ttf": {"ana"},
    "YesevaOne-Regular.ttf": {"ana"},
    "Pacifico-Regular.ttf": {"el"},
    "Lobster-Regular.ttf": {"el"},
    "KaushanScript-Regular.ttf": {"el"},
}


def rol(ad: str) -> list[str]:
    return [f for f, r in FONTLAR.items() if ad in r]


ANA_FONTLAR, KUCUK_FONTLAR, KAVIS_FONTLAR, EL_FONTLAR = rol("ana"), rol("kucuk"), rol("kavis"), rol("el")
# Eski kayıtlarda kavis/rozet ana fontu ikinci sırada; yeni şablonlarda hep ilk sırada.
_ANA_SIRA = {"kavis": 1, "rozet": 1}
EL_YAZISI_MAKS = 24  # karakter; daha uzun ikincil satır el yazısında okunmaz


def ana_font(sablon: str, fontlar: list[str]) -> str:
    return fontlar[_ANA_SIRA.get(sablon, 0)]


@dataclass
class Secim:
    sablon: str
    fontlar: list[str]
    palet: str
    cizim: Cizim
    koyu: Image.Image
    acik: Image.Image
    kalite: dict[str, list[str]]


Kurucu = Callable[[str, random.Random], tuple[list[str], Callable[[], Cizim]] | None]


def _kurucular(ust: str, ana: list[str], alt: str) -> dict[str, Kurucu]:
    """Şablon adı → (ana font, rnd) → (fontlar, çizim kurucu) ya da None (şablon bu yapıya uymuyor)."""
    tek = len(ana) == 1

    def blok(f: str, vurgulu: bool = True) -> list[Yazi]:
        bolum = dengeli_bol(ana, f, 0.02)
        # Küçük satır yoksa vurgu rengi bir ana satıra geçer: 2 satırda ikincisi, 3 satırda ortadaki.
        vurgu_i = (len(bolum) // 2 if len(bolum) == 3 else 1) if (vurgulu and not ust and not alt and len(bolum) >= 2) else -1
        return [Yazi(s, f, 0.02, vurgu=(j == vurgu_i)) for j, s in enumerate(bolum)]

    def kucukler(k: str) -> tuple[Yazi | None, Yazi | None]:
        return (
            Yazi(ust.upper(), k, 0.12, 0.45, kucuk=True) if ust else None,
            Yazi(alt.upper(), k, 0.08, 0.6, kucuk=True) if alt else None,
        )

    def yigin_k(f, rnd):
        k = rnd.choice(KUCUK_FONTLAR)
        u, a = kucukler(k)
        return [f, k], lambda: yigin([x for x in (u, *blok(f), a) if x])

    def egik_k(f, rnd):
        k = rnd.choice(KUCUK_FONTLAR)
        u, a = kucukler(k)
        return [f, k], lambda: egik([x for x in (u, *blok(f), a) if x])

    def ayirici_k(f, rnd):
        if not ust and len(dengeli_bol(ana, f, 0.02)) < 2:
            return None
        k = rnd.choice(KUCUK_FONTLAR)
        u, a = kucukler(k)
        return [f, k], lambda: ayirici(u, blok(f, vurgulu=False), a)

    def cerceve_k(f, rnd):
        k = rnd.choice(KUCUK_FONTLAR)
        return [f, k], lambda: cerceve(
            blok(f), Yazi(ust.upper(), k, 0.15) if ust else None, Yazi(alt.upper(), k, 0.1) if alt else None
        )

    def kavis_k(f, rnd):
        if not (tek and ust):
            return None
        kf, k = rnd.choice(KAVIS_FONTLAR), rnd.choice(KUCUK_FONTLAR)
        return [kf, f, k], lambda: kavis(
            Yazi(ust.upper(), kf, 0.06), Yazi(ana[0], f), Yazi(alt.upper(), k, 0.12) if alt else None
        )

    def rozet_k(f, rnd):
        if not (tek and ust):
            return None
        k = rnd.choice(KUCUK_FONTLAR)
        return [k, f, k], lambda: rozet(Yazi(ust.upper(), k, 0.15), Yazi(ana[0], f), Yazi(alt.upper(), k, 0.08) if alt else None)

    def madalyon_k(f, rnd):
        if not (tek and ust and alt):
            return None
        kf = rnd.choice(KAVIS_FONTLAR)
        return [f, kf], lambda: madalyon(Yazi(ust.upper(), kf, 0.08), Yazi(ana[0], f), Yazi(alt.upper(), kf, 0.12))

    def el_k(f, rnd):
        # El yazısı ikincil satırı taşır: altı varsa alt (bloğun altında), yoksa üst (bloğun üstünde); diğeri yoksa.
        if bool(ust) == bool(alt):
            return None
        el = alt or ust
        if len(el) > EL_YAZISI_MAKS or el == el.upper():
            return None  # büyük harfli el yazısı okunmaz ve kaba durur (pano: "MERRY MILEAGE", "AUNTIE")
        e = rnd.choice(EL_FONTLAR)
        return [f, e], lambda: el_yazisi(blok(f, vurgulu=False), Yazi(el, e), ustte=not alt)

    return {
        "yigin": yigin_k,
        "egik": egik_k,
        "ayirici": ayirici_k,
        "cerceve": cerceve_k,
        "kavis": kavis_k,
        "rozet": rozet_k,
        "madalyon": madalyon_k,
        "el_yazisi": el_k,
    }


def _adaylar(
    ust: str, ana: list[str], alt: str, rnd: random.Random, son: list[tuple[str, str]], tur: int = 2
) -> list[tuple[str, list[str], Callable[[], Cizim]]]:
    """Şablonlar son kullanımı en az olandan başlar; her şablona yakın zamanda onunla kullanılmamış bir ana font düşer.

    Sıra tur tur: önce her uygun şablon bir kez, sonra ikinci fontlarıyla. Kapıdan geçemeyen şablon diğerlerini bekletmez.
    """
    yakin = set(son[-CESITLILIK_PENCERE:])
    sayim: dict[str, int] = {}
    for s, _ in son[-SABLON_PENCERE:]:
        sayim[s] = sayim.get(s, 0) + 1
    kurucular = _kurucular(ust, ana, alt)
    sira = sorted(kurucular, key=lambda s: (sayim.get(s, 0), rnd.random()))
    turlar: list[list] = [[] for _ in range(tur)]
    for s in sira:
        fontlar = sorted(rnd.sample(ANA_FONTLAR, len(ANA_FONTLAR)), key=lambda f, s=s: (s, f) in yakin)
        n = 0
        for f in fontlar:
            if n == tur:
                break
            sonuc = kurucular[s](f, rnd)
            if sonuc is None:
                break  # şablon bu yapıya uymuyor; font değiştirmek fark etmez
            turlar[n].append((s, *sonuc))
            n += 1
    return [a for t in turlar for a in t]


def sec(
    ust: str, ana: list[str], alt: str, son_kullanilan: list[tuple[str, str]], tohum: int, deneme: int = 8
) -> tuple[Secim | None, list[str]]:
    """İlk kapılardan geçen tasarımı döner; geçemezse (None, ret nedenleri). `son_kullanilan`: eskiden yeniye (şablon, ana font)."""
    rnd = random.Random(tohum)
    adaylar = _adaylar(ust, ana, alt, rnd, son_kullanilan)
    paletler = gecerli_paletler()
    palet = paletler[tohum % len(paletler)]  # deterministik: aynı ifade aynı paleti alır
    vurgu = PALETLER[palet]
    nedenler: list[str] = []
    for sablon, fontlar, kur in adaylar[:deneme]:
        try:
            cizim = kur()
        except ValueError as e:  # EksikGlif, boş satır
            nedenler.append(f"{sablon}/{fontlar}: {e}")
            continue
        kalite, gecti = {}, True
        goruntuler = {}
        for etiket, murekkep, kumaslar, v in (
            ("koyu", KOYU_MUREKKEP, ACIK_KUMAS, vurgu[0] if vurgu else None),
            ("acik", ACIK_MUREKKEP, KOYU_KUMAS, vurgu[1] if vurgu else None),
        ):
            img = render.goruntu(cizim.svg(murekkep, v))
            s = kapilar.denetle(img, murekkep, kumaslar, cizim.okunacak, cizim.en_kucuk_yazi, vurgu=v)
            kalite[etiket] = [str(x) for x in s]
            goruntuler[etiket] = img
            if not kapilar.gecti(s):
                gecti = False
                nedenler.append(f"{sablon}/{fontlar[0]}: " + "; ".join(str(x) for x in s if not x.gecti))
                break
        if gecti:
            return Secim(sablon, fontlar, palet, cizim, goruntuler["koyu"], goruntuler["acik"], kalite), nedenler
    return None, nedenler
