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
    vurgu: bool = False  # ana satır ikinci renkte (küçük satırlar zaten vurgu rengindedir)


@dataclass
class Cizim:
    """Mutlak koordinatlı SVG parçaları; ölçek ve konum hesabı burada biter."""

    parcalar: list[str] = field(default_factory=list)
    tanimlar: list[str] = field(default_factory=list)
    alt: float = 0.0  # kullanılan en alt y
    en_kucuk_yazi: float = float("inf")  # en kısa yazı öğesinin yüksekliği, px
    okunacak: list[str] = field(default_factory=list)  # OCR kapısının araması gereken düz satırlar
    vurgu_parcalar: list[str] = field(default_factory=list)  # ikinci renkte basılacak öğeler (küçük satır, yay, çizgi)

    def yazi(self, parca: str, yukseklik: float, metin: str | None = None, vurgu: bool = False) -> None:
        """`metin` verilmezse öğe OCR kapısına girmez (kavisli yazı: geometrisi çakışmayı zaten önler)."""
        (self.vurgu_parcalar if vurgu else self.parcalar).append(parca)
        self.en_kucuk_yazi = min(self.en_kucuk_yazi, yukseklik)
        if metin:
            self.okunacak.append(metin)

    def svg(self, murekkep: str, vurgu: str | None = None) -> str:
        """`vurgu` verilmezse tasarım tek renk basılır (vurgu öğeleri de ana mürekkeple)."""
        defs = f"<defs>{''.join(self.tanimlar)}</defs>" if self.tanimlar else ""
        ikinci = f'<g fill="{vurgu or murekkep}">{"".join(self.vurgu_parcalar)}</g>' if self.vurgu_parcalar else ""
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{TUVAL_G}" height="{TUVAL_Y}" '
            f'viewBox="0 0 {TUVAL_G} {TUVAL_Y}">{defs}<g fill="{murekkep}">{"".join(self.parcalar)}</g>{ikinci}</svg>'
        )


def _yol(satir: Satir, olcek: float, x_merkez: float, y_ust: float, ek: str = "") -> tuple[str, float]:
    tx = x_merkez - (satir.x0 + satir.genislik / 2) * olcek
    ty = y_ust - satir.y0 * olcek
    return (
        f'<path d="{satir.yol}" transform="translate({tx:.2f} {ty:.2f}) scale({olcek:.5f})"{ek}/>',
        satir.yukseklik * olcek,
    )


ANA_YUKSEKLIK_SINIRI = 1.5  # bir ana satır, ana satırların en kısasının bu katından yüksek olamaz
KUCUK_YUKSEKLIK_SINIRI = 0.45  # küçük (üst/alt) satır, en kısa ana satırın bu katından yüksek olamaz


CIZGI_MIN = 28.0  # px; baskıda çizgi/çerçeve kalınlığının alt sınırı (~2,4 mm, DTG'de güvenli)


def yigin(
    satirlar: list[Yazi],
    bosluk: float = 0.14,
    genislik: float = ICERIK_G,
    ust: float = UST_PAY,
    yukseklik_maks: float = ICERIK_Y_MAKS,
    ayrac_sonra: int | None = None,
) -> Cizim:
    """Satırlar alt alta, her biri kendi genişlik oranına ölçeklenir (klasik blok tişört).

    Tam genişliğe yayılan kısa satır devleşir ("MY", "WIP"); ana satırların yüksekliği en kısa ana satırın
    `ANA_YUKSEKLIK_SINIRI` katıyla sınırlanır, aşan satır daralıp ortalanır (S5 sonrası pano: hiyerarşi kayboluyordu).
    `ayrac_sonra` verilirse o satırın altına vurgu renginde yatay bir çizgi girer (`ayirici` şablonu).
    """
    olculer = [font(y.font).satir(y.metin, y.harf_araligi) for y in satirlar]
    olcekler = [genislik * y.oran / s.genislik for y, s in zip(satirlar, olculer, strict=True)]
    ana = [s.yukseklik * k for y, s, k in zip(satirlar, olculer, olcekler, strict=True) if not y.kucuk]
    if ana:
        tavan = min(ana) * ANA_YUKSEKLIK_SINIRI
        # Kısa küçük satır ("EST. 2027") genişliğe ölçeklenince ana satır boyuna çıkıyordu (pano #41): küçük satır en kısa ana satırın
        # `KUCUK_YUKSEKLIK_SINIRI` katını aşamaz.
        kucuk_tavan = min(ana) * KUCUK_YUKSEKLIK_SINIRI
        olcekler = [
            min(k, max(kucuk_tavan, KUCUK_YAZI) / s.yukseklik) if y.kucuk else min(k, tavan / s.yukseklik)
            for y, s, k in zip(satirlar, olculer, olcekler, strict=True)
        ]
    yukseklikler = [s.yukseklik * k for s, k in zip(olculer, olcekler, strict=True)]
    ara = bosluk * sum(yukseklikler) / len(yukseklikler)
    kalinlik = max(CIZGI_MIN, 0.05 * sum(yukseklikler) / len(yukseklikler))
    # Çizginin üstü ve altı: satır arasıyla aynı olursa çizgi alt çizgi gibi yazıya yapışık durur (pano: "MOM SERVES").
    ayrac_ara = 0.45 * sum(yukseklikler) / len(yukseklikler)
    toplam = sum(yukseklikler) + ara * (len(satirlar) - 1) + (2 * ayrac_ara - ara + kalinlik if ayrac_sonra is not None else 0)
    kucult = min(1.0, yukseklik_maks / toplam)
    c = Cizim()
    y = ust
    for i, (yz, s, k) in enumerate(zip(satirlar, olculer, olcekler, strict=True)):
        parca, h = _yol(s, k * kucult, TUVAL_G / 2, y)
        c.yazi(parca, h, s.metin, vurgu=yz.kucuk or yz.vurgu)
        y += h + ara * kucult
        if i == ayrac_sonra:
            y += (ayrac_ara - ara) * kucult
            kal = max(CIZGI_MIN, kalinlik * kucult)
            g = genislik * 0.42
            c.vurgu_parcalar.append(
                f'<rect x="{(TUVAL_G - g) / 2:.1f}" y="{y:.1f}" width="{g:.1f}" height="{kal:.1f}" rx="{kal / 2:.1f}"/>'
            )
            y += kal + ayrac_ara * kucult
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
        c.yazi(parca, buyuk, vurgu=True)
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
        c.yazi(parca, h2, sa.metin, vurgu=True)
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
    c.yazi(parca, h_u, su.metin, vurgu=True)
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
            c.vurgu_parcalar.append(
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
        c.yazi(parca, h_a, sa.metin, vurgu=True)
        c.alt += h_u * 0.55 + h_a
    return c


def _yuvarlak_dortgen(x: float, y: float, g: float, y_: float, r: float) -> str:
    return (
        f"M{x + r:.1f},{y:.1f} H{x + g - r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x + g:.1f},{y + r:.1f} V{y + y_ - r:.1f} "
        f"A{r:.1f},{r:.1f} 0 0 1 {x + g - r:.1f},{y + y_:.1f} H{x + r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x:.1f},{y + y_ - r:.1f} "
        f"V{y + r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x + r:.1f},{y:.1f} Z"
    )


def _daire(cx: float, cy: float, r: float) -> str:
    return f"M{cx - r:.1f},{cy:.1f} A{r:.1f},{r:.1f} 0 1 0 {cx + r:.1f},{cy:.1f} A{r:.1f},{r:.1f} 0 1 0 {cx - r:.1f},{cy:.1f} Z"


def cerceve(ana: list[Yazi], ust: Yazi | None = None, alt: Yazi | None = None) -> Cizim:
    """Yuvarlak köşeli çerçeve içinde ana satırlar; küçük satırlar çerçevenin üst/alt kenarını keserek üstüne oturur.

    Çerçeve dolgu yoludur (iç ve dış dörtgen, evenodd): kalınlığı baskı sınırının epey üstünde, renk vurgu.
    Kenardaki boşluk maskeyle açılır; yazı çizgiye değmez.
    """
    kal = 44.0
    dis_g = ICERIK_G * 0.96
    ic_pay = ICERIK_G * 0.06
    x0 = (TUVAL_G - dis_g) / 2
    olcu_u = font(ust.font).satir(ust.metin, ust.harf_araligi) if ust else None
    olcu_a = font(alt.font).satir(alt.metin, alt.harf_araligi) if alt else None
    olcek_u = _kucuk(olcu_u, 230, dis_g * 0.6) if olcu_u else 0
    olcek_a = _kucuk(olcu_a, 200, dis_g * 0.6) if olcu_a else 0
    h_u = olcu_u.yukseklik * olcek_u if olcu_u else 0
    h_a = olcu_a.yukseklik * olcek_a if olcu_a else 0
    ust_kenar = UST_PAY + max(h_u / 2 - kal / 2, 0)
    ic_ust = ust_kenar + kal + ic_pay + h_u / 2
    pay_alt = ic_pay + kal + h_a / 2
    c = yigin(
        ana,
        genislik=dis_g - 2 * (kal + ic_pay),
        ust=ic_ust,
        yukseklik_maks=ICERIK_Y_MAKS - (ic_ust - UST_PAY) - pay_alt - h_a / 2,
    )
    alt_kenar = c.alt + ic_pay + h_a / 2 + kal
    yuk = alt_kenar - ust_kenar
    r = kal * 3
    yol = (
        _yuvarlak_dortgen(x0, ust_kenar, dis_g, yuk, r)
        + " "
        + _yuvarlak_dortgen(x0 + kal, ust_kenar + kal, dis_g - 2 * kal, yuk - 2 * kal, r - kal)
    )
    kesikler = []
    for olcu, olcek, h, y_orta in ((olcu_u, olcek_u, h_u, ust_kenar + kal / 2), (olcu_a, olcek_a, h_a, alt_kenar - kal / 2)):
        if not olcu:
            continue
        g = olcu.genislik * olcek + 2 * h * 0.6
        kesikler.append(
            f'<rect x="{(TUVAL_G - g) / 2:.1f}" y="{y_orta - h:.1f}" width="{g:.1f}" height="{2 * h:.1f}" fill="#000"/>'
        )
        parca, h2 = _yol(olcu, olcek, TUVAL_G / 2, y_orta - h / 2)
        c.yazi(parca, h2, olcu.metin, vurgu=True)
    if kesikler:
        c.tanimlar.append(
            f'<mask id="kesik" maskUnits="userSpaceOnUse" x="0" y="0" width="{TUVAL_G}" height="{TUVAL_Y}">'
            f'<rect width="{TUVAL_G}" height="{TUVAL_Y}" fill="#fff"/>{"".join(kesikler)}</mask>'
        )
    maske = ' mask="url(#kesik)"' if kesikler else ""
    c.vurgu_parcalar.append(f'<path d="{yol}" fill-rule="evenodd"{maske}/>')
    c.alt = alt_kenar + max(h_a / 2 - kal / 2, 0)
    return c


def ayirici(ust: Yazi | None, ana: list[Yazi], alt: Yazi | None = None) -> Cizim:
    """Yığının bir çeşidi: başlığın (yoksa ilk ana satırın) altında vurgu renginde ayırıcı çizgi."""
    satirlar = ([ust] if ust else []) + ana + ([alt] if alt else [])
    if not ust and len(ana) < 2:
        raise ValueError("ayirici: başlık ya da en az iki ana satır gerekir")
    return yigin(satirlar, bosluk=0.16, ayrac_sonra=0)


def egik(satirlar: list[Yazi], aci: float = -5.0) -> Cizim:
    """Yığın bütün halinde hafifçe yukarı eğilir (spor/retro tişört): döndürülmüş blok içerik genişliğine sığacak kadar küçülür."""
    c = yigin(satirlar)
    h = c.alt - UST_PAY
    t = math.radians(abs(aci))
    g2, h2 = ICERIK_G * math.cos(t) + h * math.sin(t), ICERIK_G * math.sin(t) + h * math.cos(t)
    s = min(1.0, ICERIK_G / g2, ICERIK_Y_MAKS / h2)
    don = (
        f"translate({TUVAL_G / 2:.1f} {UST_PAY + s * h2 / 2:.1f}) rotate({aci}) scale({s:.5f}) "
        f"translate({-TUVAL_G / 2:.1f} {-(UST_PAY + h / 2):.1f})"
    )
    c.parcalar = [f'<g transform="{don}">{"".join(c.parcalar)}</g>']
    if c.vurgu_parcalar:
        c.vurgu_parcalar = [f'<g transform="{don}">{"".join(c.vurgu_parcalar)}</g>']
    c.en_kucuk_yazi *= s
    c.alt = UST_PAY + s * h2
    return c


def _kavisli_alt(satir: Satir, olcek: float, cx: float, cy: float, r: float) -> list[str]:
    """Glifleri dairenin alt yayına dik okunacak şekilde dizer: taban çizgisi r'de, harflerin tepesi merkeze bakar."""
    yay = satir.ilerleme * olcek / r
    parcalar = []
    for g in satir.glifler:
        orta = (g.x + g.ilerleme / 2) * olcek
        fi = -yay / 2 + orta / r
        px, py = cx + r * math.sin(fi), cy + r * math.cos(fi)
        parcalar.append(
            f'<path d="{g.yol}" transform="translate({px:.2f} {py:.2f}) rotate({-math.degrees(fi):.3f}) '
            f'translate({-g.ilerleme / 2 * olcek:.2f} 0) scale({olcek:.5f})"/>'
        )
    return parcalar


MADALYON_YAY = math.radians(140)  # üst ve alt yazının en geniş açısı; iki yanda ayırıcı noktalara yer kalır


def madalyon(ust: Yazi, orta: Yazi, alt: Yazi) -> Cizim:
    """Yuvarlak rozet: dış halka, üst yayda başlık, alt yayda alt satır (dik okunur), iki yanda nokta, ortada büyük kelime."""
    R = ICERIK_G * 0.47
    cx, cy = TUVAL_G / 2, UST_PAY + R
    kal = max(CIZGI_MIN + 10, R * 0.022)
    bosluk = R * 0.045
    bant = R * 0.12
    r_dis = R - kal - bosluk  # bant yazısının dış sınırı
    r_ic = r_dis - bant  # iç sınır
    c = Cizim()
    c.vurgu_parcalar.append(f'<path d="{_daire(cx, cy, R)} {_daire(cx, cy, R - kal)}" fill-rule="evenodd"/>')
    kal2 = max(CIZGI_MIN, kal * 0.65)
    c.vurgu_parcalar.append(
        f'<path d="{_daire(cx, cy, r_ic - bosluk)} {_daire(cx, cy, r_ic - bosluk - kal2)}" fill-rule="evenodd"/>'
    )
    for yazi, ustte in ((ust, True), (alt, False)):
        f = font(yazi.font)
        s = f.satir(yazi.metin, yazi.harf_araligi)
        r_taban = r_ic if ustte else r_dis
        olcek = min(bant / f.buyuk_harf, MADALYON_YAY * r_taban / s.ilerleme)
        h = f.buyuk_harf * olcek
        # Küçülen yazı bandın ortasına otursun.
        r_taban += (bant - h) / 2 * (1 if ustte else -1)
        for parca in (_kavisli if ustte else _kavisli_alt)(s, olcek, cx, cy, r_taban):
            c.yazi(parca, h, vurgu=True)
    r_nokta = bant * 0.16
    for isaret in (-1, 1):
        c.vurgu_parcalar.append(f'<circle cx="{cx + isaret * (r_ic + bant / 2):.1f}" cy="{cy:.1f}" r="{r_nokta:.1f}"/>')
    so = font(orta.font).satir(orta.metin, orta.harf_araligi)
    r_orta = (r_ic - bosluk - kal2) - R * 0.07
    oran = so.genislik / so.yukseklik
    h_o = 2 * r_orta / math.sqrt(oran**2 + 1) * orta.oran
    if h_o < R * 0.16:
        raise ValueError(f"madalyon: orta satır ({orta.metin!r}) daireye ancak {h_o:.0f} px sığıyor")
    parca, h = _yol(so, h_o / so.yukseklik, cx, cy - h_o / 2)
    c.yazi(parca, h, so.metin)
    c.alt = cy + R
    return c


def el_yazisi(ana: list[Yazi], el: Yazi, ustte: bool, aci: float = -5.0) -> Cizim:
    """Blok ana satırların üstünde ya da altında, hafif eğik el yazısı satırı (vurgu renginde).

    Eski `el_yazisi_blok` el yazısını bloğun üstüne bindiriyordu ve okunurluk kapısında tutarsızdı (S5, K-10);
    burada iki öğe çakışmaz: döndürülmüş el yazısının sınır kutusu kadar yer ayrılır.
    """
    se = font(el.font).satir(el.metin, el.harf_araligi)
    olcek = min(ICERIK_G * 0.74 * el.oran / se.genislik, 620 / se.yukseklik)
    w, h = se.genislik * olcek, se.yukseklik * olcek
    t = math.radians(abs(aci))
    h_don = h * math.cos(t) + w * math.sin(t)
    ara = h * 0.25
    blok_ust = UST_PAY + (h_don + ara if ustte else 0)
    c = yigin(ana, ust=blok_ust, yukseklik_maks=ICERIK_Y_MAKS - h_don - ara)
    yc = UST_PAY + h_don / 2 if ustte else c.alt + ara + h_don / 2
    tx = TUVAL_G / 2 - (se.x0 + se.genislik / 2) * olcek
    ty = yc - (se.y0 + se.yukseklik / 2) * olcek
    c.yazi(
        f'<path d="{se.yol}" transform="rotate({aci} {TUVAL_G / 2} {yc:.1f}) translate({tx:.2f} {ty:.2f}) scale({olcek:.5f})"/>',
        h,
        se.metin,
        vurgu=True,
    )
    if not ustte:
        c.alt = yc + h_don / 2
    return c
