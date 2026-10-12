---
proje: Matbaa
created: 2026-10-13
type: roadmap
status: aktif
---
# Matbaa — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı / ⛔ Engelli.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 0 | Hesaplar ve para (Scryne) | 🔄 Devam Ediyor | S1 müşavir cevabı yazıldı; Etsy mağazası açık (kimlik + banka doğrulandı); Printify hesabı + kart çalışıyor; 2 numune elde ve fotoğraflı değerlendirildi; Printify token + Etsy Seller App anahtarı `.env`'de |
| 1 | İskelet ve sağlık | ✅ Tamamlandı | Private repo GitHub'da; CI (ruff + pytest) varsayılan dalda yeşil; `.github/dependabot.yml`; model kimlikleri `config/modeller.toml`'da; `.env.example`; SQLite şeması + durum makinesi testli |
| 2 | Tasarım motoru v1 | 🔄 Devam Ediyor | En az 6 şablon, 20+ OFL font, çeşitlilik kuralı; 3 niş × 10 ifade → 30 tasarımın hepsi kapılardan geçiyor ve göz kontrolünde 30/30 yayınlanabilir; mutasyon testleri yeşil |
| 3 | İfade üretimi + IP kapısı | 🔄 Devam Ediyor | Niş kartları `config/nisler.toml`'da; Claude ile niş başına 30 aday → USPTO + Jev kapısı; 90 adayın kapı kayıtları SQLite'ta; Aria'nın kör örneklemesinde (30 temiz ifade) riskli kaçak 0; USPTO verisi 35 günlük tazelik kontrolüyle |
| 4 | İlan metni | ⏳ Bekliyor | Başlık, 13 etiket (≤ 20 karakter), açıklama (AI beyanı + üretim ortağı + beden/bakım), öznitelikler; Etsy kural doğrulayıcı testli; 30 ilan metni doğrulayıcıdan geçiyor |
| 5 | Onay paneli | ⏳ Bekliyor | Yerel panel: tasarım önizleme (koyu/açık kumaş), ifade, kapı nedenleri, ilan metni; onayla/reddet/düzelt durum makinesine yazıyor; 30 tasarımlık kuyruk 10 dakikada bitirilebiliyor (Scryne'ın ilk kullanımı) |
| 6 | Printify entegrasyonu | ⏳ Bekliyor | Faz 0 sonrası: görsel yükle → 1717/18000 ürün (kilitli sağlayıcı, renkler, varyant fiyatları) → mockup; Etsy'ye publish; 429/hata yeniden denemesi; gerçek hesapta 3 ürün oluşturuldu ve Etsy'de taslak göründü |
| 7 | Etsy entegrasyonu | ⏳ Bekliyor | Seller App OAuth (refresh token yenileme); `production_partner_ids` + `state=active`; günde ≤ 5 tavanı; receipts + takip okuma; gerçek mağazada 3 ilan aktif ve kurallara uygun |
| 8 | Fiyat ve kâr defteri | ⏳ Bekliyor | Fiyatlar `config/`'te; sipariş başına gerçek net (Etsy TR ücretleri + Printify maliyeti + kur) hesaplanıyor; aylık özet; harcama tavanları kodla korunuyor |
| 9 | Zamanlama ve izleme | ⏳ Bekliyor | Günlük Windows görevi uçtan uca koşuyor; takip numarası 5 iş gününde düşmeyen sipariş için alarm; haftalık rapor (ilan, görüntülenme, satış, net); USPTO aylık yenileme görevi |
| 10 | Gerçek kullanım (v1) | ⏳ Bekliyor | 30 ilan Scryne onayıyla canlı; numune kalitesi doğrulandı; ilk gerçek siparişte Etsy → Printify → takip zinciri elle dokunulmadan çalıştı (ya da 4 hafta dolup v1 "30 ilan + numune" ile kapandı); bulgular roadmap'e işlendi |
| 11 | Kişiselleştirme — Class of 2027 (koşullu) | ⏳ Bekliyor | v1 kapandıysa ve Ocak 2027 geldiyse: Etsy kişiselleştirme alanı → sipariş anında tasarım → Printify API siparişi; 5 test siparişi doğru basıldı |
| 12 | Shopify (koşullu) | ⏳ Bekliyor | Etsy'de ≥ 30 satış ve TR ödeme yolu (iyzico ya da LLC) netleştiyse: aynı Printify kataloğu Shopify'a; ilk sipariş zinciri çalıştı |

## Faz Detayları

### Faz 0: Hesaplar ve para (Scryne)
- **İşler:** S1 müşavir; S2 Etsy mağazası (Aria ekran ekran yönlendirir); S3 Printify + kart + 2 numune; Printify token; Etsy geliştirici
  hesabı ve Seller App kaydı (Aria yönlendirir).
- **Bitti Kriteri:** tablodaki gibi.
- **Notlar:** Kod fazları (1–5, 8) buna bağlı değil, paralel ilerler. Faz 6–7 ve 10 buna bağlı.

### Faz 1: İskelet ve sağlık ✅ (2026-10-13)
- **Yapılan:** private `Scryne/matbaa`, `main`; CI (ruff check + format + pytest) main'de yeşil; Dependabot (uv + actions), güvenlik uyarıları açık;
  `.env.example`; `src/matbaa/db.py` SQLite şeması + durum makinesi + olay günlüğü (6 test: onaysız yayın yok, temiz olmayan ifadeden tasarım yok).
- **Notlar:** `gh` token'ında `workflow` kapsamı yok; push Git Credential Manager ile çalışıyor (`gh repo create --push` workflow dosyasında reddedildi).

### Faz 2: Tasarım motoru v1
- **Durum (10-13):** `tasarim/sec.py` slogan yapısından (üst/ana/alt) şablon + font seçiyor, çeşitlilik penceresi 5; yığında ana satır yükseklik
  tavanı (en kısa ana satırın 1,5 katı) ve `dengeli_bol` (modelin satır sonları tercihli, kısa yalnız kelime / pankart en-boy cezası).
  İlk 30 tasarımın panosu (`calisma/pano30b.png`) göz kontrolünde kabul edilebilir taban; eksik: ikinci renk/vurgu, yeni şablonlar, font havuzu.
- **İşler:** yeni şablonlar (çerçeveli rozet, iki satır + ayırıcı ikon yok/çizgi, eğik blok, yay + alt yay); font havuzu 20+ OFL; şablon–font
  uyum tablosu (el yazısı yalnız ikincil satırda); çeşitlilik kuralı; `el_yazisi_blok` düzeltme ya da çıkarma.
- **Notlar:**

### Faz 3: İfade üretimi + IP kapısı
- **Durum (10-13):** `config/nisler.toml` (3 niş kartı), `ifade/uret.py` (`claude -p`, JSON şeması, ~5–20 sn/12 slogan), `hat.py` (`matbaa uret`,
  `matbaa durum`). İlk koşu: 36 slogan → 5 USPTO reddi (THIRD SHOT DROP, PADDLE ADDICT, OPEN PLAY, HOOKED ON, ONE MORE) → 30 tasarım.
  IP kapısında satır/slogan ayrımı: tam-marka ve baskınlık kuralları yalnız sloganın tamamına ve ana mesaja (satır düzeyi 11 temiz sloganı düşürüyordu).
- **İşler:** niş kartı (alıcı, ton, kaçınılacaklar, örnek iyi/kötü ifadeler); `claude -p` istemi + JSON şeması; aday → kapı → kayıt;
  ret nedenlerinden geri besleme (aynı kalıbı tekrar üretme).
- **Notlar:** S6 eşikleri 50 ifadeyle seçildi; ilk 200 kararda kalibrasyon.

### Faz 10: Gerçek kullanım
- **Notlar:** `urun-dogrulama` ile kapanır: gerçek mağaza, gerçek ilan, gerçek baskı fotoğrafı.
