"""S6 spike: ifade bir markaya / karaktere / ünlüye / takıma / şarkı sözüne gönderme yapıyor mu? (Jev)

Etiketli 30 ifade: 1 = riskli gönderme var, 0 = özgün/jenerik. Çıktı: soru başına olasılık, birleşik karar, isabet.
"""

import json, os, time
import httpx2, typesafe_sdk
from typesafe_sdk import Choice, Noul

ORNEKLER = [
    # (ifade, niş, etiket)
    ("Swiftie Grandma", "family", 1),
    ("Just Keep Swimming And Fishing", "fishing", 1),
    ("May The Yarn Be With You", "knitting", 1),
    ("Hakuna Matata Knitter", "knitting", 1),
    ("Shake It Off Pickleball", "pickleball", 1),
    ("Purl Jam", "knitting", 1),
    ("Let It Go Crochet Club", "crochet", 1),
    ("Bass Pro Grandpa", "fishing", 1),
    ("Stanley Cup Of Coffee Fisherman", "fishing", 1),
    ("Go Packers Fishing Team", "fishing", 1),
    ("Yarn Of Thrones", "knitting", 1),
    ("The Office Of Pickleball", "pickleball", 1),
    ("Hogwarts Knitting Society", "knitting", 1),
    ("Dink Different", "pickleball", 1),
    ("I Am The Dinker Who Knocks", "pickleball", 1),
    ("Knit Happens", "knitting", 0),
    ("Dink Responsibly", "pickleball", 0),
    ("Pickleball Is My Therapy", "pickleball", 0),
    ("Born To Fish Forced To Work", "fishing", 0),
    ("Reel Grandpas Fish All Day", "fishing", 0),
    ("Crochet Club Since 2026", "crochet", 0),
    ("Sorry I Can't I Have Pickleball", "pickleball", 0),
    ("Yarn Over Everything", "knitting", 0),
    ("Fueled By Coffee And Yarn", "knitting", 0),
    ("Weekend Forecast: Fishing", "fishing", 0),
    ("Kitchen Line Kitchen Queen", "pickleball", 0),
    ("One More Cast", "fishing", 0),
    ("Hooked On Grandkids", "fishing", 0),
    ("Purl Of Wisdom", "knitting", 0),
    ("Dad Joke Loading Fish Edition", "fishing", 0),
]

KAYNAK = {
    "original_or_generic": "An original slogan or a plain description made of ordinary words; it does not echo any specific existing work, brand, or person.",
    "everyday_idiom_pun": "A pun or play on a common idiom, proverb, or everyday expression that no one owns (for example 'pearl of wisdom', 'stuff happens', 'born to X forced to work', 'sorry I can't, I have plans', 'hooked on', 'kitchen queen').",
    "song_or_band": "Quotes or parodies a specific song title, song lyric, album, or band name.",
    "screen_or_book": "Quotes or parodies a specific movie, TV show, video game, book, fictional character, or entertainment franchise, including its catchphrases.",
    "brand_or_ad_slogan": "Names, mimics, or parodies a specific company, store, product, or a company's advertising slogan.",
    "real_person": "References a specific real celebrity or public figure, their name, nickname, or fan group name.",
    "team_or_school": "References a specific professional or college sports team, league, school, or branded event.",
}
RISKSIZ = ("original_or_generic", "everyday_idiom_pun")
SORULAR = {
    "brand": Noul(
        instructions="Does `phrase` name, mimic, or pun on a specific company, brand, store, or commercial product? Ordinary generic words (fishing, yarn, coffee) are not brands."
    ),
    "character": Noul(
        instructions="Does `phrase` reference or parody a specific fictional character, movie, TV show, video game, book series, or entertainment franchise, including its catchphrases?"
    ),
    "person": Noul(
        instructions="Does `phrase` reference a specific real celebrity or public figure, their name, nickname, or their fan group name?"
    ),
    "team": Noul(
        instructions="Does `phrase` reference a specific professional or college sports team, league, school, or branded event?"
    ),
    "parody": Noul(
        instructions="Is `phrase` a word-swap parody of a famous advertising slogan, famous brand or company name, famous song or band, or famous movie or TV title, where one or two words are replaced with a hobby word? Puns on everyday idioms and proverbs that no one owns do not count."
    ),
    "kaynak": Choice(
        instructions="What is the main source of `phrase`, a T-shirt slogan? Pick the single best description.", criteria=KAYNAK
    ),
}

YENI = [
    ("Eye Of The Tiger Fisherman", "fishing", 1),
    ("Keep Calm And Knit On", "knitting", 0),
    ("Nacho Average Grandpa", "fishing", 0),
    ("Yoda Best Knitter", "knitting", 1),
    ("Pickle Rick Ball", "pickleball", 1),
    ("Life Is Better At The Lake", "fishing", 0),
    ("Just Dink It", "pickleball", 1),
    ("Sweet Home Alabama Bass", "fishing", 1),
    ("Hook Line And Sinker Champ", "fishing", 0),
    ("Netflix And Knit", "knitting", 1),
    ("Paddle Battle Royale", "pickleball", 0),
    ("Stitch Please", "knitting", 0),
    ("Bob Ross Of Crochet", "crochet", 1),
    ("I Like Big Bobbers And I Cannot Lie", "fishing", 1),
    ("Older Than Dirt Still Fishing", "fishing", 0),
    ("Kitchen Is For Cooking Not Standing", "pickleball", 0),
    ("Knot Your Average Knitter", "knitting", 0),
    ("Gone Fishin Back Never", "fishing", 0),
    ("Dallas Cowboys Grandpa Angler", "fishing", 1),
    ("Crochet Is My Cardio", "crochet", 0),
]
import sys

if len(sys.argv) > 1 and sys.argv[1] == "yeni":
    ORNEKLER = YENI


def main():
    istemci = typesafe_sdk.TypeSafeClient(
        api_key=os.environ["TYPESAFE_API_KEY"],
        model="jev-latest",
        timeout=30,
        transport=httpx2.HTTPTransport(local_address="0.0.0.0"),
    )
    dogru = 0
    kayit = []
    for ifade, nis, etiket in ORNEKLER:
        t = time.time()
        y = istemci.system_one(state={"phrase": ifade, "context": f"T-shirt slogan for a {nis} niche shop"}, questions=SORULAR)
        c = y.choices["kaynak"]
        p = {k: round(float(v), 2) for k, v in c.probabilities.items()}
        n = {k: round(float(y.nouls[k].noul), 2) for k in ("brand", "character", "person", "team", "parody")}
        risk = round(1 - sum(p.get(k, 0) for k in RISKSIZ), 3)
        karar = 1 if risk >= 0.5 else 0
        dogru += karar == etiket
        kayit.append(
            {
                "ifade": ifade,
                "etiket": etiket,
                "risk": risk,
                "secim": c.choice,
                "guven": float(c.confidence),
                **p,
                **{"n_" + k: v for k, v in n.items()},
            }
        )
        print(
            f"{'✓' if karar == etiket else '✗'} {etiket} risk={risk:.2f} güven={float(c.confidence):.2f} {ifade!r:40} {c.choice} {n}"
        )
    print(f"isabet {dogru}/{len(ORNEKLER)}  model={getattr(y, 'model', '?')}")
    json.dump(kayit, open(f"calisma/S6_jev_{sys.argv[1] if len(sys.argv) > 1 else 'ilk'}.json", "w"), indent=1)


main()
