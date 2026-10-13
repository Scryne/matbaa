"""İfade üretimi: niş kartı → Claude (başsız `claude -p`) → yapılandırılmış slogan adayları.

Çıktı yapısı tasarım şablonlarıyla eşleşir: `ust` (küçük üst satır), `ana` (1–3 büyük satır), `alt` (küçük alt satır).
Üretilen her aday IP kapısından geçmeden tasarıma girmez (K-13); burada yalnız üretim ve biçim doğrulaması var.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date
from functools import cache

from matbaa import llm
from matbaa.ayar import CONFIG

MAKS_SATIR_KARAKTER = 18  # şablonlarda büyük satırın okunur kalması için
MAKS_KELIME = 12  # toplam (küçük satırlar dahil)
MAKS_ANA_KELIME = 8  # büyük yazılan ana mesaj

SEMA = {
    "type": "object",
    "properties": {
        "slogans": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "top": {
                        "type": "string",
                        "description": "optional small printed line above (role, year, place), max 22 chars, or empty; never a gift label or occasion description",
                    },
                    "main": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
                    "bottom": {"type": "string", "description": "optional small line below, max 30 chars, or empty"},
                    "why": {"type": "string", "description": "one short sentence: who buys it and why it lands"},
                },
                "required": ["top", "main", "bottom", "why"],
            },
        }
    },
    "required": ["slogans"],
}

SISTEM = (
    "You write original, sellable T-shirt slogans for an Etsy print-on-demand shop that sells to American buyers. "
    "Every slogan must be your own wording: never reuse a famous slogan, song lyric, band name, movie or TV line, brand name, "
    "team name, or celebrity reference, and never parody them with a word swap. Puns on everyday idioms are fine. "
    "Keep it kind and gift-friendly; no crude, sexual, political, or alcohol-centered jokes. "
    "Every line is printed on the shirt: never write shop or listing language such as 'Gift for Dad', 'Thank-You Gift', "
    "'Pregnancy Reveal' or 'Christmas Present' as a line; the gift angle belongs in the joke, not in a label."
)
# Basılı satırda ilan dili: ilk iki turda "PREGNANCY REVEAL" ve "Booster Thank-You Gift" tişörte basılacaktı (2026-10-13).
ILAN_DILI = re.compile(r"\b(gift|gifts|present|reveal|announcement|shirt|tee|t-shirt)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Aday:
    ust: str
    ana: tuple[str, ...]
    alt: str
    neden: str

    @property
    def satirlar(self) -> list[str]:
        return [s for s in (self.ust, *self.ana, self.alt) if s]

    def bicim_hatasi(self) -> str | None:
        if not self.ana:
            return "ana satır yok"
        if any(len(s) > MAKS_SATIR_KARAKTER for s in self.ana):
            return f"ana satır > {MAKS_SATIR_KARAKTER} karakter"
        if len(self.ust) > 22 or len(self.alt) > 30:
            return "küçük satır uzun"
        if sum(len(s.split()) for s in self.ana) > MAKS_ANA_KELIME:
            return f"ana mesaj > {MAKS_ANA_KELIME} kelime"
        if sum(len(s.split()) for s in self.satirlar) > MAKS_KELIME:
            return f"> {MAKS_KELIME} kelime"
        if any(ILAN_DILI.search(s) for s in (self.ust, self.alt)):
            return "küçük satırda ilan dili (gift/reveal/shirt): tişörte basılacak yazı değil"
        return None


@cache
def takvim() -> dict:
    return tomllib.loads((CONFIG / "takvim.toml").read_text(encoding="utf-8"))


def aktif_mevsimler(nis: str, gun: date | None = None) -> list[dict]:
    """Bugün açık mevsim pencereleri (yıl dönümünü aşan pencere dahil: 12-01 → 02-07)."""
    g = (gun or date.today()).strftime("%m-%d")
    sonuc = []
    for m in takvim().values():
        if m.get("nisler") and nis not in m["nisler"]:
            continue
        acik = m["bas"] <= g <= m["son"] if m["bas"] <= m["son"] else (g >= m["bas"] or g <= m["son"])
        if acik:
            sonuc.append(m)
    return sonuc


@cache
def nisler() -> dict:
    return tomllib.loads((CONFIG / "nisler.toml").read_text(encoding="utf-8"))


def istem(nis: str, adet: int, kacinilacak: list[str], gun: date | None = None, satanlar: list[str] | None = None) -> str:
    k = nisler()[nis]
    satirlar = [
        f"Niche: {k['ad']}",
        f"Buyer: {k['alici']}",
        f"Tone: {k['ton']}",
        f"Useful vocabulary: {', '.join(k['jargon'])}",
        f"Family/role words that work well: {', '.join(k['roller'])}",
        f"Avoid: {'; '.join(k['kacin'])}",
        f"Tone examples (do not copy): {' | '.join(k['ornek_ton'])}",
        "",
        f"Write {adet} different slogans. Rules:",
        f"- 'main' is the big text: 1 to 3 short lines, each at most {MAKS_SATIR_KARAKTER} characters.",
        "- 'top' and 'bottom' are optional small lines (use empty string when not needed); a year like 'EST. 2026' or a role works there.",
        f"- The big 'main' text has at most {MAKS_ANA_KELIME} words; at most {MAKS_KELIME} words in total. Clear at a glance from across a room.",
        "- Vary structure and angle: role jokes, hobby obsession, insider jargon, gentle self-roast, gift-for-someone framing.",
    ]
    for m in aktif_mevsimler(nis, gun):
        n = max(1, round(adet * m["pay"]))
        satirlar.append(
            f"- Make about {n} of them gift slogans for the upcoming {m['ad']}, still clearly for this niche's buyer."
        )
    if satanlar:  # Faz 13: mağazada gerçekten satanlar; kopya değil, aynı açıdan yeni fikir
        satirlar.append(
            f"- These slogans from this shop are selling: {' | '.join(satanlar)}. Write about {max(1, adet // 3)} fresh slogans "
            "that hit the same buyer and angle with different wording and jokes; never reuse their key phrase."
        )
    if kacinilacak:
        satirlar.append("- Do not repeat or closely echo these earlier or rejected slogans: " + " | ".join(kacinilacak[:80]))
    return "\n".join(satirlar)


def uret(
    nis: str, adet: int = 15, kacinilacak: list[str] | None = None, satanlar: list[str] | None = None
) -> tuple[list[Aday], list[tuple[Aday, str]]]:
    """(geçerli adaylar, [(biçim hatalı aday, neden)])."""
    ham = llm.yapilandirilmis(istem(nis, adet, kacinilacak or [], satanlar=satanlar), SISTEM, SEMA)
    gecerli, hatali = [], []
    for s in ham.get("slogans", []):
        a = Aday(
            s.get("top", "").strip(),
            tuple(x.strip() for x in s.get("main", []) if x.strip()),
            s.get("bottom", "").strip(),
            s.get("why", ""),
        )
        (hatali.append((a, h)) if (h := a.bicim_hatasi()) else gecerli.append(a))
    return gecerli, hatali
