"""Anlamsal IP katmanı (TypeSafe/Jev): ifade bir markaya, esere, ünlüye, takıma ya da şarkıya gönderme yapıyor mu?

S6 ölçümü (docs/spike/S6-ip-kapisi.md, 50 etiketli ifade): tek bir "kaynak" Choice'u deyim kelime oyunlarını
gönderme sanmıyor ama kelimesi değiştirilmiş parodileri kaçırıyor; dört Noul onu tamamlıyor; tek-kelime-takası
yapılmış markalar için kanıtlı "ünlü mü" sorusu kalan parodileri ayırıyor. Kural kodda, eşikler burada.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cache

from matbaa.ayar import modeller

RISKSIZ = ("original_or_generic", "everyday_idiom_pun")
KAYNAK_RET = 0.5  # 1 - P(özgün) - P(deyim)
NOUL_RET = 0.5
UNLU_RET = 0.65
UNLU_INSAN = 0.45  # bu ile UNLU_RET arası insana

KAYNAK = {
    "original_or_generic": "An original slogan or a plain description made of ordinary words; it does not echo any specific existing work, brand, or person.",
    "everyday_idiom_pun": "A pun or play on a common idiom, proverb, or everyday expression that no one owns (for example 'pearl of wisdom', 'stuff happens', 'born to X forced to work', 'sorry I can't, I have plans', 'hooked on', 'kitchen queen').",
    "song_or_band": "Quotes or parodies a specific song title, song lyric, album, or band name.",
    "screen_or_book": "Quotes or parodies a specific movie, TV show, video game, book, fictional character, or entertainment franchise, including its catchphrases.",
    "brand_or_ad_slogan": "Names, mimics, or parodies a specific company, store, product, or a company's advertising slogan.",
    "real_person": "References a specific real celebrity or public figure, their name, nickname, or fan group name.",
    "team_or_school": "References a specific professional or college sports team, league, school, or branded event.",
}
NOULLAR = {
    "brand": "Does `phrase` name, mimic, or pun on a specific company, brand, store, or commercial product? Ordinary generic words (fishing, yarn, coffee) are not brands.",
    "character": "Does `phrase` reference or parody a specific fictional character, movie, TV show, video game, book series, or entertainment franchise, including its catchphrases?",
    "person": "Does `phrase` reference a specific real celebrity or public figure, their name, nickname, or their fan group name?",
    "team": "Does `phrase` reference a specific professional or college sports team, league, school, or branded event?",
}
UNLU = (
    "`phrase` is a T-shirt slogan. `similar_registered_marks` lists registered trademarks that differ from it by one word. "
    "Is `phrase` a recognizable parody of one of these marks that a typical American shopper would know as a famous brand "
    "name, advertising slogan, song, band, movie, or TV show? Answer no if the similar marks are obscure small-business "
    "phrases or generic sayings that many sellers use."
)


@dataclass
class Yargi:
    karar: str  # "temiz" | "ret" | "insan"
    nedenler: list[str] = field(default_factory=list)
    olasiliklar: dict[str, float] = field(default_factory=dict)
    model: str = ""


@cache
def _istemci():
    import httpx2
    import typesafe_sdk

    ayar = modeller()["typesafe"]
    # IPv4'e zorla: bu makinede AAAA'sız alan adında DNS ~12 sn sürüyor (vault: dns-aaaa-tuzagi).
    return typesafe_sdk.TypeSafeClient(
        api_key=os.environ["TYPESAFE_API_KEY"],
        model=ayar["model"],
        timeout=ayar["zaman_asimi_sn"],
        transport=httpx2.HTTPTransport(local_address="0.0.0.0"),
    )


def yargila(ifade: str, baglam: str, benzerler: list[str] | None = None) -> Yargi:
    from typesafe_sdk import Choice, Noul

    sorular = {k: Noul(instructions=v) for k, v in NOULLAR.items()}
    sorular["kaynak"] = Choice(
        instructions="What is the main source of `phrase`, a T-shirt slogan? Pick the single best description.", criteria=KAYNAK
    )
    y = _istemci().system_one(state={"phrase": ifade, "context": baglam}, questions=sorular)
    c = y.choices["kaynak"]
    p = {f"kaynak.{k}": round(float(v), 3) for k, v in c.probabilities.items()}
    p |= {k: round(float(y.nouls[k].noul), 3) for k in NOULLAR}
    model = str(getattr(y, "model", ""))
    risk = 1 - sum(p.get(f"kaynak.{k}", 0) for k in RISKSIZ)
    nedenler = []
    if risk >= KAYNAK_RET:
        nedenler.append(f"kaynak={c.choice} (risk {risk:.2f})")
    nedenler += [f"{k}={p[k]:.2f}" for k in NOULLAR if p[k] >= NOUL_RET]
    if nedenler:
        return Yargi("ret", nedenler, p, model)
    if benzerler:
        u = _istemci().system_one(
            state={"phrase": ifade, "similar_registered_marks": benzerler[:15]}, questions={"unlu": Noul(instructions=UNLU)}
        )
        p["unlu"] = round(float(u.nouls["unlu"].noul), 3)
        if p["unlu"] >= UNLU_RET:
            return Yargi("ret", [f"ünlü markanın parodisi ({p['unlu']:.2f}): {', '.join(benzerler[:3])}"], p, model)
        if p["unlu"] >= UNLU_INSAN:
            return Yargi("insan", [f"benzer marka, ünlülük belirsiz ({p['unlu']:.2f}): {', '.join(benzerler[:3])}"], p, model)
    return Yargi("temiz", [], p, model)
