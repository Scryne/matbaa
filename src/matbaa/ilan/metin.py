"""İlan metni: başlık, 13 etiket, açıklama, görsel alt metni.

Yaratıcı kısım (başlık, etiketler, giriş paragrafı, alt metin) Claude'dan gelir; zorunlu kısımlar (ürün bilgisi, beden,
bakım, üretim ortağı ve AI beyanı) koddan, sabit metinle. Etsy kuralları: AI kullanımı ilan açıklamasında beyan edilir,
üretim ortağı belirtilir (docs/spike/S7). Her çıktı `dogrula` ile denetlenir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from matbaa import llm
from matbaa.fiyat import urunler
from matbaa.ifade.uret import nisler

SEMA = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Etsy title, max 140 characters, under 15 words, starts with the product phrase buyers search",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 16,
            "maxItems": 18,
            "description": "multi-word search phrases, each max 20 characters",
        },
        "intro": {"type": "string", "description": "2-3 warm sentences: what the design says, who it is for, gift occasion"},
        "alt_text": {
            "type": "string",
            "description": "image alt text, max 250 characters, describes the product and the printed words",
        },
    },
    "required": ["title", "tags", "intro", "alt_text"],
}

SISTEM = (
    "You write Etsy listings for an American print-on-demand gift shop (apparel, mugs, ornaments). Write natural, specific, buyer-focused copy. "
    "Never use brand names (other than the garment brand given), trademarks, celebrity, team, movie, or song references. "
    "No keyword stuffing, no ALL CAPS, no emojis, no claims you cannot verify (no 'best', no 'handmade')."
)

AI_BEYANI = (
    "About this design: the slogan was developed with the help of AI writing tools from our own prompts, then selected, edited, "
    "and laid out by us."
)
URETIM_ORTAGI = "Made to order: designed by our shop and printed and shipped by our US production partner (Printify)."
BEDEN = "Sizing: unisex fit. Size up for a relaxed or oversized look. See the size chart in the photos before ordering."
BAKIM = "Care: machine wash cold inside out, tumble dry low or hang dry, do not iron directly on the print."
URETIM_SURESI = "Production takes 3-5 business days, then ships with tracking within the US."  # Etsy işlem profili (hazirlama_profili_id) ile aynı


@dataclass
class Ilan:
    baslik: str
    etiketler: list[str]
    aciklama: str
    alt_metin: str
    sorunlar: list[str] = field(default_factory=list)


def istem(satirlar: list[str], nis: str, urun: str) -> str:
    k, u = nisler()[nis], urunler()[urun]
    return "\n".join(
        [
            f"Design text printed on the {u.get('yuzey', 'garment')}: {' / '.join(satirlar)}",
            f"Product: {u['ad']} ({u['etsy_turu']})",
            f"Niche and buyer: {k['ad']}. {k['alici']}",
            f"Useful search vocabulary: {', '.join(k['jargon'][:10])}; roles: {', '.join(k['roller'])}",
            "",
            f"Write the Etsy title (start with the main search phrase such as 'Funny Fishing Grandpa {u['etsy_turu']}', include the gift angle, "
            "max 140 characters, under 15 words), 16 tags (distinct multi-word phrases buyers type, each at most 20 characters, "
            "no repeats, no brand names including the garment brand), a short intro, and image alt text.",
            *([u["istem_notu"]] if u.get("istem_notu") else []),
        ]
    )


def olustur(satirlar: list[str], nis: str, urun: str) -> Ilan:
    ham = llm.yapilandirilmis(istem(satirlar, nis, urun), SISTEM, SEMA)
    u = urunler()[urun]
    aciklama = "\n\n".join(
        [
            ham["intro"].strip(),
            f"Printed text: {' / '.join(satirlar)}",
            f"{u.get('govde_etiketi', 'Garment')}: {u['ad']}. {u['detay']}",
            u.get("beden_metni", BEDEN),
            u.get("bakim_metni", BAKIM),
            URETIM_SURESI,
            URETIM_ORTAGI,
            AI_BEYANI,
        ]
    )
    ilan = Ilan(ham["title"].strip(), [t.strip() for t in ham["tags"]], aciklama, ham["alt_text"].strip()[:250])
    from matbaa.ilan.dogrula import dogrula

    return dogrula(ilan)
