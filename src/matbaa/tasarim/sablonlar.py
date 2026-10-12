"""Tipografik yerleşim şablonları.

Her şablon 4500x5400 tuvalde (tişört göğüs baskısı, 15x18 inç @300 DPI) tek renkli bir SVG
üretir. Tek renk bilinçli: DTG'de temiz basılır, koyu/açık kumaş için yalnız mürekkep rengi değişir.
Tasarım tuvalin üstüne hizalanır; Printify baskı alanında yukarıdan konumlandırır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .yazi import Satir, font

TUVAL_G, TUVAL_Y = 4500, 5400
UST_PAY = 150
ICERIK_G = 4050  # tuvalin %90'ı
ICERIK_Y_MAKS = 4600
KUCUK_YAZI = 170  # px; ikincil satırların hedef alt sınırı (~1,4 cm baskıda)


@dataclass(frozen=True)
class Yazi:
    metin: str
    font: str
    harf_araligi: float = 0.0
    oran: float = 1.0  # içerik genişliğinin kesri
    kucuk: bool = False  # ikincil satır (üst/alt); yükseklik sınırı yalnız ana satırlara uygulanır


@dataclass
class Cizim:
    """Mutlak koordinatlı SVG parçaları; ölçek ve konum hesabı burada biter."""

    parcalar: list[str] = field(default_factory=list)
    tanimlar: list[str] = field(default_factory=list)
    alt: float = 0.0  # kullanılan en alt y
    en_kucuk_yazi: float = float("inf")  # en kısa yazı öğesinin yüksekliği, px
    okunacak: list[str] = field(default_factory=list)  # OCR kapısının araması gereken düz satırlar

    def yazi(self, parca: str, yukseklik: float, metin: str | None = None) -> None:
        """`metin` verilmezse öğe OCR kapısına girmez (kavisli yazı: geometrisi çakışmayı zaten önler)."""
        self.parcalar.append(parca)
        self.en_kucuk_yazi = min(self.en_kucuk_yazi, yukseklik)
        if metin:
            self.okunacak.append(metin)

    def svg(self, murekkep: str) -> str:
        defs = f"<defs>{''.join(self.tanimlar)}</defs>" if self.tanimlar else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{TUVAL_G}" height="{TUVAL_Y}" '
            f'viewBox="0 0 {TUVAL_G} {TUVAL_Y}">{defs}<g fill="{murekkep}">{"".join(self.parcalar)}</g></svg>'
        )


def _yol(satir: Satir, olcek: float, x_merkez: float, y_ust: float, ek: str = "") -> tuple[str, float]:
    tx = x_merkez - (satir.x0 + satir.genislik / 2) * olcek
    ty = y_ust - satir.y0 * olcek
    return (
        f'<path d="{satir.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({olcek:.5f})"{ek}/>',
        satir.yukseklik * olcek,
    )


ANA_YUKSEKLIK_SINIRI = 1.5  # bir ana satır, ana satırların en kısasının bu katından yüksek olamaz


def yigin(satirlar: list[Yazi], bosluk: float = 0.14) -> Cizim:
    """Satırlar alt alta, her biri kendi genişlik oranına ölçeklenir (klasik blok tişört).

    Tam genişliğe yayılan kısa satır devleşir ("MY", "WIP"); ana satırların yüksekliği en kısa ana satırın
    `ANA_YUKSEKLIK_SINIRI` katıyla sınırlanır, aşan satır daralıp ortalanır (S5 sonrası pano: hiyerarşi kayboluyordu).
    """
    olculer = [font(y.font).satir(y.metin, y.harf_araligi) for y in satirlar]
    olcekler = [ICERIK_G * y.oran / s.genislik for y, s in zip(satirlar, olculer, strict=True)]
    ana = [s.yukseklik * k for y, s, k in zip(satirlar, olculer, olcekler, strict=True) if not y.kucuk]
    if ana:
        tavan = min(ana) * ANA_YUKSEKLIK_SINIRI
        olcekler = [k if y.kucuk else min(k, tavan / s.yukseklik) for y, s, k in zip(satirlar, olculer, olcekler, strict=True)]
    yukseklikler = [s.yukseklik * k for s, k in zip(olculer, olcekler, strict=True)]
    ara = bosluk * sum(yukseklikler) / len(yukseklikler)
    toplam = sum(yukseklikler) + ara * (len(satirlar) - 1)
    kucult = min(1.0, ICERIK_Y_MAKS / toplam)
    c = Cizim()
    y = UST_PAY
    for s, k in zip(olculer, olcekler, strict=True):
        parca, h = _yol(s, k * kucult, TUVAL_G / 2, y)
        c.yazi(parca, h, s.metin)
        y += h + ara * kucult
    c.alt = y - ara * kucult
    return c


def dengeli_bol(satirlar: list[str], dosya: str, harf_araligi: float = 0.0, maks_satir: int = 3) -> list[str]:
    """Ana mesajı 1–3 satıra, genişlikler birbirine yakın ve anlam bütün kalacak şekilde böler.

    Modelin satır sonları anlam taşır ("1. CAST / 2. WAIT / 3. REPEAT") ama orantıyı bozabilir
    ("Catch and Release / MY / PATIENCE"). Modelin sonları tercih edilen kırılımdır; başka yerden kırmak cezalı.
    Ceza: en geniş/en dar satır oranı; tek başına kalan kısa kelime; tek satırda aşırı yatay şerit.
    """
    kelimeler = " ".join(satirlar).split()
    tercih, i = set(), 0
    for satir in satirlar[:-1]:
        i += len(satir.split())
        tercih.add(i)
    f = font(dosya)
    en_iyi, en_iyi_puan = list(satirlar), float("inf")

    def bolumler(bas: int, kalan: int):
        if kalan == 1:
            yield [len(kelimeler)]
            return
        for j in range(bas + 1, len(kelimeler) - kalan + 2):
            for devam in bolumler(j, kalan - 1):
                yield [j, *devam]

    for n in range(1, min(maks_satir, len(kelimeler)) + 1):
        for sinirlar in bolumler(0, n):
            aday, bas = [], 0
            for son in sinirlar:
                aday.append(" ".join(kelimeler[bas:son]))
                bas = son
            olcu = [f.satir(x, harf_araligi) for x in aday]
            g = [o.genislik for o in olcu]
            puan = max(g) / min(g)
            puan += sum(1.5 for x in aday if len(x.replace(" ", "")) <= 3 and n > 1)
            puan += 0.8 * sum(1 for k in sinirlar[:-1] if k not in tercih)
            puan += 0.4 * len(tercih - set(sinirlar))  # modelin satır sonunu kaldırmak da bedelli ("1. CAST 2. WAIT")
            # Blok en-boy oranı: her satır tam genişliğe ölçeklenince toplam yükseklik; 2,6:1'den yatay blok pankart gibi durur.
            blok_yukseklik = sum(o.yukseklik / o.genislik for o in olcu) * 1.12
            puan += max(0.0, 1 / blok_yukseklik - 2.6) * 0.5
            puan += 0.15 * n
            if puan < en_iyi_puan:
                en_iyi, en_iyi_puan = aday, puan
    return en_iyi


def _kavisli(satir: Satir, olcek: float, cx: float, cy: float, r: float) -> list[str]:
    """Glifleri (cx, cy) merkezli r yarıçaplı yayın üstüne, taban çizgisi yayda olacak şekilde dizer."""
    yay = satir.ilerleme * olcek / r
    parcalar = []
    for g in satir.glifler:
        orta = (g.x + g.ilerleme / 2) * olcek
        teta = -yay / 2 + orta / r
        px, py = cx + r * math.sin(teta), cy - r * math.cos(teta)
        parcalar.append(
            f'<path d="{g.yol}" transform="translate({px:.2f} {py:.2f}) rotate({math.degrees(teta):.3f}) '
            f'translate({-g.ilerleme / 2 * olcek:.2f} 0) scale({olcek:.5f})"/>'
        )
    return parcalar


def _kucuk(satir: Satir, hedef: float, genislik_siniri: float) -> float:
    """İkincil satır ölçeği: hedef yüksekliğe çık ama genişlik sınırını aşma."""
    return min(max(hedef, KUCUK_YAZI) / satir.yukseklik, genislik_siniri / satir.genislik)


def kavis(ust: Yazi, orta: Yazi, alt: Yazi | None = None, yay_derece: float = 70.0) -> Cizim:
    """Kolej tarzı: üstte kavisli yazı, yayın uçlarının altında büyük düz satır, en altta küçük satır.

    Kavisli satır, kirişi içerik genişliğinin %90'ını tutacak şekilde ölçeklenir; orta satır yay
    uçlarının altından başlar, yani çakışma inşa gereği olmaz.
    """
    fu = font(ust.font)
    su, so = (
        fu.satir(ust.metin, ust.harf_araligi),
        font(orta.font).satir(orta.metin, orta.harf_araligi),
    )
    yay = math.radians(yay_derece)
    olcek_u = ICERIK_G * 0.9 * yay / (2 * math.sin(yay / 2) * su.ilerleme)
    olcek_u = min(olcek_u, ICERIK_G * 0.13 / fu.buyuk_harf)
    r = su.ilerleme * olcek_u / yay
    buyuk = fu.buyuk_harf * olcek_u
    cy = UST_PAY + r + buyuk
    c = Cizim()
    for parca in _kavisli(su, olcek_u, TUVAL_G / 2, cy, r):
        c.yazi(parca, buyuk)
    # Uç glifin dış üst köşesi yay ucundan biraz aşağı sarkar; taban noktası ile güvenli pay.
    y_uc = cy - r * math.cos(yay / 2) + buyuk * math.sin(yay / 2) * 0.35
    orta_ust = y_uc + buyuk * 0.35
    olcek_o = ICERIK_G * 0.82 * orta.oran / so.genislik
    olcek_o = min(olcek_o, buyuk * 2.2 / so.yukseklik)
    parca, h = _yol(so, olcek_o, TUVAL_G / 2, orta_ust)
    c.yazi(parca, h, so.metin)
    c.alt = orta_ust + h
    if alt:
        sa = font(alt.font).satir(alt.metin, alt.harf_araligi)
        olcek_a = _kucuk(sa, h * 0.32, ICERIK_G * 0.7 * alt.oran)
        parca, h2 = _yol(sa, olcek_a, TUVAL_G / 2, c.alt + 0.18 * h)
        c.yazi(parca, h2, sa.metin)
        c.alt += 0.18 * h + h2
    return c


def rozet(ust: Yazi, orta: Yazi, alt: Yazi | None = None) -> Cizim:
    """ "EST. 2026" tipi: küçük üst satır iki yanında çizgiyle, büyük kelime, küçük alt satır."""
    su = font(ust.font).satir(ust.metin, ust.harf_araligi)
    so = font(orta.font).satir(orta.metin, orta.harf_araligi)
    olcek_o = ICERIK_G * 0.92 * orta.oran / so.genislik
    h_o = so.yukseklik * olcek_o
    olcek_u = _kucuk(su, h_o * 0.2, ICERIK_G * 0.5)
    c = Cizim()
    parca, h_u = _yol(su, olcek_u, TUVAL_G / 2, UST_PAY)
    c.yazi(parca, h_u, su.metin)
    # Yan çizgiler: kalınlık baskı alt sınırının (~1 mm = 12 px) epey üstünde.
    kalinlik = max(28.0, h_u * 0.09)
    yazi_g = su.genislik * olcek_u
    bosluk = h_u * 0.6
    sol, sag = (TUVAL_G - ICERIK_G * 0.92) / 2, (TUVAL_G + ICERIK_G * 0.92) / 2
    y_cizgi = UST_PAY + h_u / 2 - kalinlik / 2
    for x0, x1 in (
        (sol, TUVAL_G / 2 - yazi_g / 2 - bosluk),
        (TUVAL_G / 2 + yazi_g / 2 + bosluk, sag),
    ):
        if x1 - x0 > kalinlik * 4:
            c.parcalar.append(
                f'<rect x="{x0:.1f}" y="{y_cizgi:.1f}" width="{x1 - x0:.1f}" height="{kalinlik:.1f}" rx="{kalinlik / 2:.1f}"/>'
            )
    y = UST_PAY + h_u + h_u * 0.55
    parca, _ = _yol(so, olcek_o, TUVAL_G / 2, y)
    c.yazi(parca, h_o, so.metin)
    c.alt = y + h_o
    if alt:
        sa = font(alt.font).satir(alt.metin, alt.harf_araligi)
        olcek_a = _kucuk(sa, h_o * 0.2, ICERIK_G * 0.92 * alt.oran)
        parca, h_a = _yol(sa, olcek_a, TUVAL_G / 2, c.alt + h_u * 0.55)
        c.yazi(parca, h_a, sa.metin)
        c.alt += h_u * 0.55 + h_a
    return c


def el_yazisi_blok(blok: Yazi, el: Yazi, aci: float = -6.0, oyma: float = 60.0) -> Cizim:
    """Büyük blok kelimenin alt kenarına binen eğik el yazısı; el yazısının çevresi bloktan oyulur.

    El yazısı bloğun ortasına konursa blok okunmaz (S5 ilk tur: "TEACH" → "TEASH"); alt kenara biner,
    bloğun üst yarısı harfleri tanıtmaya yeter.
    """
    sb = font(blok.font).satir(blok.metin, blok.harf_araligi)
    se = font(el.font).satir(el.metin, el.harf_araligi)
    olcek_b = ICERIK_G * 0.92 * blok.oran / sb.genislik
    h_b = sb.yukseklik * olcek_b
    olcek_e = min(ICERIK_G * 0.62 * el.oran / se.genislik, h_b * 0.9 / se.yukseklik)
    h_e = se.yukseklik * olcek_e
    ust = UST_PAY
    blok_parca, _ = _yol(sb, olcek_b, TUVAL_G / 2, ust)
    merkez_y = ust + h_b * 0.98
    tx = TUVAL_G / 2 - (se.x0 + se.genislik / 2) * olcek_e
    ty = merkez_y - (se.y0 + se.yukseklik / 2) * olcek_e
    don = f"rotate({aci} {TUVAL_G / 2} {merkez_y:.1f})"
    el_yol = f'd="{se.yol}" transform="{don} translate({tx:.2f} {ty:.2f}) scale({olcek_e:.5f})"'
    c = Cizim()
    c.tanimlar.append(
        f'<mask id="oyma" maskUnits="userSpaceOnUse" x="0" y="0" width="{TUVAL_G}" height="{TUVAL_Y}">'
        f'<rect width="{TUVAL_G}" height="{TUVAL_Y}" fill="#fff"/>'
        f'<path {el_yol} fill="#000" stroke="#000" stroke-width="{oyma / olcek_e:.2f}" stroke-linejoin="round"/></mask>'
    )
    c.yazi(f'<g mask="url(#oyma)">{blok_parca}</g>', h_b, sb.metin)
    c.yazi(f"<path {el_yol}/>", h_e, se.metin)
    c.alt = max(ust + h_b, merkez_y + h_e / 2)
    return c
