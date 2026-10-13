"""Yayın öncesi marka kontrolü: ifade, ABD'de giyim sınıfında (25) canlı bir markaya çarpıyor mu?

Veri: `veri/uspto_25_canli.parquet` (scripts/uspto_guncelle.py; USPTO bulk türevi, kamu malı). Bu bir hukuki
değerlendirme değil, platform riskini düşüren bir filtredir: Etsy marka bildirimiyle ilanı kaldırır, tekrarında
mağazayı kapatır (docs/arastirma/06).

Kod kesin durumları reddeder. Kararı bağlama bağlı olanları iki listede döner:
- `adaylar`: ifadede geçen tek kelimelik yaygın kelime markaları (PICKLEBALL, NIKE) ve ifadenin küçük parçası
  olan gündelik çok kelimeli markalar (IN MY) — anlamsal katman bakar.
- `benzerler`: ifadeden tek kelimesi farklı canlı markalar (JUST DINK IT ↔ JUST DO IT) — ünlü olanın parodisi
  mi, anlamsal katman karar verir (S6: kod ünlülüğü bilemez, kanıtı verir).
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import duckdb
from wordfreq import zipf_frequency

from matbaa.ayar import VERI

DOSYA = VERI / "uspto_25_canli.parquet"
UYDURMA_ESIK = 1.0  # zipf; altı sözlükte yok demek (BOYMOM 0, GIRLDAD 0). PICKLEBALL 1.6 gerçek kelime
BASKIN_ORAN = 0.5  # marka ifadenin kelimelerinin en az yarısıysa mesajın kendisidir → ret
SESTES_ESIK = 0.6  # iki kelimelik markada yalnız sesteş takas sayılır (PEARL → PURL 0.67)
TAKAS_KELIME = (2, 6)
DURAK = frozenset("THE A AN OF AND OR TO IN ON IT IS MY I AM BE DO FOR WITH AT YOU ME WE ARE".split())


def normal(metin: str) -> str:
    return " ".join(re.findall(r"[A-Z0-9]+", metin.upper().replace("&", " AND ").replace("'", "")))


@dataclass
class Sonuc:
    ifade: str
    reddet: list[tuple[str, str, str]] = field(default_factory=list)  # (marka, neden, seri no)
    adaylar: list[str] = field(default_factory=list)
    benzerler: list[str] = field(default_factory=list)

    @property
    def temiz(self) -> bool:
        return not self.reddet


class MarkaDizini:
    def __init__(self, markalar: list[tuple[str, str]]):
        """`markalar`: (marka metni, seri no) çiftleri."""
        self.tam: dict[str, str] = {}
        self.bitisik: dict[str, str] = {}
        self.cok_kelime: dict[str, str] = {}
        self.joker: dict[str, list[str]] = defaultdict(list)  # "JUST * IT" → ["JUST DO IT", ...]
        for marka, seri in markalar:
            n = normal(marka)
            if not n:
                continue
            self.tam.setdefault(n, seri)
            self.bitisik.setdefault(n.replace(" ", ""), seri)
            k = n.split()
            if len(k) >= 2:
                if n not in self.cok_kelime and TAKAS_KELIME[0] <= len(k) <= TAKAS_KELIME[1]:
                    for i in range(len(k)):
                        self.joker[" ".join(k[:i] + ["*"] + k[i + 1 :])].append(n)
                self.cok_kelime.setdefault(n, seri)

    @classmethod
    def dosyadan(cls, dosya: Path = DOSYA) -> MarkaDizini:
        if not dosya.exists():
            raise FileNotFoundError(f"{dosya} yok: önce `uv run python scripts/uspto_guncelle.py`")
        return cls(duckdb.sql(f"SELECT marka, serial_no FROM '{dosya.as_posix()}'").fetchall())

    def _takas(self, kelimeler: list[str]) -> list[str]:
        bulunan: set[str] = set()
        for i in range(len(kelimeler)):
            for m in self.joker.get(" ".join(kelimeler[:i] + ["*"] + kelimeler[i + 1 :]), ()):
                mk = m.split()
                eski, yeni = mk[i], kelimeler[i]
                if eski == yeni:
                    continue
                benzer = difflib.SequenceMatcher(None, eski, yeni).ratio()
                anlamli = [x for j, x in enumerate(mk) if j != i and x not in DURAK]
                if len(mk) == 2 and benzer < SESTES_ESIK:
                    continue
                if len(mk) >= 3 and benzer < 0.5 and len(anlamli) < 2 and len(mk) != 3:
                    continue
                bulunan.add(m)
        return sorted(bulunan)

    def satir_kontrol(self, satir: str) -> Sonuc:
        """Tasarımın tek bir satırı: yalnız kendisi çok kelimeli bir marka olan satır ya da uydurma kelime marka reddedilir.

        "MOM", "CLUB", "WITH LOVE" gibi bir satır sloganın mesajı değildir; tam-eşleşme ve baskınlık kuralları sloganın
        tamamına ve ana mesaja uygulanır (S7 sonrası Faz 3: satır düzeyi kural 11 temiz sloganı düşürdü).
        """
        s = Sonuc(satir)
        n = normal(satir)
        k = n.split()
        if len(k) >= 2 and not set(k) <= DURAK and (n in self.cok_kelime or n.replace(" ", "") in self.bitisik):
            s.reddet.append((n, "satırın kendisi canlı marka", self.cok_kelime.get(n) or self.bitisik[n.replace(" ", "")]))
        for kelime in k:
            if kelime in self.tam and kelime not in DURAK and zipf_frequency(kelime.lower(), "en") < UYDURMA_ESIK:
                s.reddet.append((kelime, "uydurma tek kelime canlı marka", self.tam[kelime]))
        return s

    def kontrol(self, ifade: str) -> Sonuc:
        s = Sonuc(ifade)
        n = normal(ifade)
        kelimeler = n.split()
        if not kelimeler:
            return s
        bitisik = n.replace(" ", "")
        if len(kelimeler) == 1 and zipf_frequency(n.lower(), "en") >= UYDURMA_ESIK and n in self.tam:
            s.adaylar.append(n)  # tek yaygın kelimelik ifade ("KNIT"): bağlam kararı
        elif n in self.tam:
            s.reddet.append((n, "ifadenin tamamı canlı marka", self.tam[n]))
        elif bitisik in self.bitisik:
            s.reddet.append((bitisik, "ifade bitişik yazılınca canlı marka", self.bitisik[bitisik]))
        gorulen = {r[0] for r in s.reddet}
        for i in range(len(kelimeler)):
            for j in range(i + 1, len(kelimeler) + 1):
                parca = " ".join(kelimeler[i:j])
                if parca == n or parca in gorulen:
                    continue
                if j - i >= 2:
                    seri = self.cok_kelime.get(parca) or self.bitisik.get(parca.replace(" ", ""))
                    if seri and set(parca.split()) <= DURAK:
                        continue  # "IS A", "IN THE": yalnız bağlaçtan oluşan marka mesaj taşımaz
                    if seri:
                        # "IN MY", "ONE MORE" gibi gündelik çiftler her ifadeyi kilitlemesin.
                        if (j - i) / len(kelimeler) >= BASKIN_ORAN:
                            s.reddet.append((parca, "çok kelimeli canlı marka ifadenin baskın kısmı", seri))
                        else:
                            s.adaylar.append(parca)
                        gorulen.add(parca)
                elif parca in self.tam and parca not in DURAK:
                    if zipf_frequency(parca.lower(), "en") < UYDURMA_ESIK:
                        s.reddet.append((parca, "uydurma tek kelime canlı marka", self.tam[parca]))
                    else:
                        s.adaylar.append(parca)
                    gorulen.add(parca)
        if s.temiz:
            s.benzerler = self._takas(kelimeler)
        return s


@cache
def dizin() -> MarkaDizini:
    return MarkaDizini.dosyadan()


@cache
def veri_tarihi(dosya: Path = DOSYA):
    """Verideki en yeni başvuru tarihi (`date`): verinin gerçek tazeliği. Dosya yoksa None."""
    if not dosya.exists():
        return None
    return duckdb.sql(f"SELECT max(filing_dt) FROM '{dosya.as_posix()}'").fetchone()[0]
