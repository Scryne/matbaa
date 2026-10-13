# Matbaa

Etsy + Printify print-on-demand hattı: niş → ifade → IP kapısı (USPTO + TypeSafe) → kodla tipografik tasarım → kalite kapıları →
ilan metni → onay → Printify → Etsy.

- Doküman: `docs/Proje-Fikri.md`, `docs/Final-Dokuman.md`, `docs/Roadmap.md`, araştırma `docs/arastirma/`, spike'lar `docs/spike/`.
- Kurulum: `uv sync`; `cp .env.example .env`; marka verisi `uv run python scripts/uspto_guncelle.py`.
- Test: `uv run pytest -q`.
- Komutlar: `uv run matbaa gunluk` (Windows görevi bunu çağırır), `panel` (onay paneli), `durum`, `yeniden-ciz`, `ozet [--ay YYYY-MM]`
  (aylık kâr), `rapor` (haftalık rapor → `calisma/rapor/`). Para harcayan adımların tavanı `config/tavanlar.toml`.
