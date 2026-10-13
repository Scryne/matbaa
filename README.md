# Matbaa

Etsy + Printify print-on-demand hattı: niş → ifade → IP kapısı (USPTO + TypeSafe) → kodla tipografik tasarım → kalite kapıları →
ilan metni → onay → Printify → Etsy.

- Doküman: `docs/Proje-Fikri.md`, `docs/Final-Dokuman.md`, `docs/Roadmap.md`, araştırma `docs/arastirma/`, spike'lar `docs/spike/`.
- Kurulum: `uv sync`; `cp .env.example .env`; marka verisi `uv run python scripts/uspto_guncelle.py`; Etsy yetkisi
  `uv run python scripts/etsy_yetki.py`; günlük görev `powershell -ExecutionPolicy Bypass -File scripts\gorev_kur.ps1`.
- Test: `uv run pytest -q` (~5 dk; OCR kapısı yavaş). Testler geçici dizinde koşar, gerçek veritabanına ve `calisma/`'ya dokunmaz.

## Komutlar (`uv run matbaa <komut>`)

| Komut | Ne yapar |
|---|---|
| `gunluk` | Günlük koşu (Windows görevi bunu çağırır): DB yedeği → USPTO tazeliği → kur → üretim (talebe bağlı) → ilan metni → yayın → Etsy eşleme → görseller → görüntülenme → siparişler → haftalık rapor ve radar. Aynı anda ikinci koşu başlamaz. |
| `panel [--port 8766]` | Yerel onay paneli: onayla (A), reddet (R + 1–6), düzelt (E: başlık ve etiketler), geri al (U). |
| `uret --nis <niş> [--adet 12]` | İfade üret → IP kapısı → tasarım → kalite kapıları. |
| `metin [--sinir 50]` | `kalite_ok` tasarımlara ilan metni → onay kuyruğu. |
| `yeniden-ciz` | Onaylanmamış tasarımları güncel motorla yeniden çizer. |
| `yayinla` / `etsy-esle` | Onaylıları Printify'a açar (ısınma eğrisi + harcama tavanı) / Etsy ilanına üretim ortağı, kargo profili, aktif. |
| `durum`, `ozet [--ay YYYY-MM]`, `rapor` | Kuyruk özeti, aylık kâr, haftalık rapor (`calisma/rapor/`). |
| `printify-kesif`, `etsy-kargo-profili` | Kurulum: Printify katalog/sağlayıcı eşlemesi, Etsy ücretsiz ABD kargo profili. |

## İşletim notları

- Para harcayan adımların tavanı `config/tavanlar.toml`; ısınma eğrisi `config/yayin.toml`.
- Durum tek SQLite dosyasında (`matbaa.db`, git dışı). Günlük koşu her gün tutarlı bir kopyasını alır, son 14 gün kalır:
  varsayılan `calisma/yedek/gunluk/`; `.env`'de `MATBAA_YEDEK_DIZINI` verilirse (ör. OneDrive klasörü) oraya.
- Sonuç `calisma/gunluk/son.json` ve panelin Dikkat şeridi; hata ya da alarm varsa Windows bildirimi düşer.
- Etsy token'ı `.etsy_token.json`'da (git dışı); yenileme reddedilirse hata mesajı `scripts/etsy_yetki.py`'yi gösterir.
