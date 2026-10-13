---
proje: Matbaa
created: 2026-10-13
type: final-dokuman
status: onaylandi
---
# Matbaa — Final Doküman

Kararlar Aria'nın (Scryne 2026-10-13: "her şey sende, tüm yetki sende"). Para, hesap, kimlik ve dışarı çıkan her adım Scryne'da.
Kaynaklar: `docs/arastirma/00–06`, `docs/spike/S5–S7`, `docs/Proje-Fikri.md` (K-1…K-9).

## Özet
Matbaa, Etsy'de print-on-demand tişört/sweatshirt satan bir hattır. Niş verisiyle seçilen alıcı gruplarına (v1: balıkçılık, pickleball,
örgü/tığ işi) özgün tipografik ifadeler üretir, bunları marka/eser kapısından geçirir, kodla baskıya hazır vektör tasarıma çevirir, kalite
kapılarından geçirir, ilan metnini yazar ve Scryne'ın haftalık 10 dakikalık onayından sonra Printify üzerinden Etsy'ye yayınlar. Sipariş
gelince Printify basar ve ABD'deki alıcıya gönderir; hat takip numarasını ve gecikmeleri izler. İnsan işi: onay kuyruğu, Etsy mesajları,
iade kararı.

## Teknoloji Stack

| Katman | Seçim | Gerekçe |
| --- | --- | --- |
| Dil, paket | Python 3.12, uv | Görüntü işleme, font, veri ve API işleri tek dilde; Scryne'ın projelerinde yerleşik araç |
| Yazı → vektör | uharfbuzz + fontTools | Yazı yol olarak çizilir: ölçülebilir, fonttan bağımsız, yazım hatası imkânsız (S5) |
| SVG → PNG | resvg-py | Sistem fontu yüklemeden deterministik render, 4500x5400 ~1 sn (S5) |
| Fontlar | Google Fonts, yalnız OFL | Ticari kullanım açık; lisans dosyası fontun yanında |
| Kalite kapıları | numpy, scipy, Pillow, RapidOCR (yerel ONNX) | Hale, ince çizgi, kenar, kontrast, en küçük yazı, OCR okunurluk; mutasyonla doğrulandı (S5) |
| Marka verisi | USPTO sınıf-25 canlı markalar, DuckDB + Parquet | 402.746 marka, 7 MB, ms düzeyinde sorgu (S6); kaynak ayda bir yenilenir |
| Anlamsal karar | TypeSafe Jev (`typesafe-sdk`), model `config/modeller.toml` | Gönderme/parodi yargısı; 50 ifadede kaçan 0 (S6). Global kural: anlam kararı → TypeSafe |
| Metin üretimi | Claude, headless `claude -p` (Sonnet); yedek yerel Ollama | İfade ve ilan metni yaratıcı İngilizce ister; hacim düşük (günde ≤ 5 tasarım, ~30 aday) |
| Üretim/kargo | Printify (Free → Premium ~20 sipariş/ay'da), Comfort Colors 1717 + Gildan 18000 | API'de ürün → mockup → Etsy'ye yayın zinciri; Printful bunu yapamıyor (araştırma 02) |
| Pazar yeri | Etsy Open API v3, Seller App (kendi mağaza, otomatik onay) | Üretim ortağı bağlama, aktifleştirme, sipariş/takip okuma (araştırma 01) |
| Onay paneli | FastAPI + tek sayfa HTML, yerel (127.0.0.1) | Haftalık 10 dk; hesap/sunucu gerektirmez. Telefon bildirimi v1.1 |
| Durum | SQLite (tek dosya) | Tasarım, ifade, kapı kayıtları, ilan, sipariş; yedeklenir |
| Zamanlama | Windows Görev Zamanlayıcı, günlük | Hat Scryne'ın makinesinde koşar (Claude ve TypeSafe anahtarı yerel) |
| Kalite süreci | pytest, ruff, GitHub Actions, Dependabot | Faz 1 sağlık kuralı |

## Mimari

```
  niş kartı (config/nisler.toml)
        │
  [1] ifade üretimi (Claude) ──► [2] IP kapısı: USPTO kod katmanı → Jev anlam katmanı ──► ret / insan / temiz
        │ temiz
  [3] tasarım: şablon + font seçimi (çeşitlilik kuralı) → SVG → PNG (koyu + açık mürekkep)
        │
  [4] kalite kapıları (baskı + okunurluk) ── düşerse başka şablon/font, 3 denemede ret
        │
  [5] ilan metni (Claude) → Etsy kural doğrulayıcı (başlık, 13 etiket, AI beyanı, üretim ortağı cümlesi)
        │
  [6] onay kuyruğu (yerel panel) ── Scryne: onayla / reddet / ifadeyi düzelt
        │ onay
  [7] Printify: görsel yükle → ürün (1717, kilitli sağlayıcı, renkler, fiyat) → mockup → Etsy'ye publish
        │
  [8] Etsy Seller App: production_partner_ids + aktifleştir (günde ≤ 5)
        │
  [9] izleme: Printify/Etsy siparişleri, takip numarası, gecikme alarmı, kâr defteri
```

- **Durum makinesi:** her tasarım `aday → ip_temiz → render → kalite_ok → metin_ok → onay_bekliyor → onaylandi → printify → etsy_taslak →
  aktif` (ya da `ret:<neden>`). Her geçiş SQLite'a tarih + kanıtla yazılır; hat kaldığı yerden sürer.
- **Tekrarlanabilirlik:** Jev kararları ham olasılık + çözülen model sürümüyle kayda geçer; eşikler ilk 200 kararda kalibre edilir.
- **Çeşitlilik:** aynı mağazada ardışık 5 tasarımda aynı şablon+font çifti en çok bir kez (toplu üretim görünümüne karşı; K-4).
- **Para eşikleri** `config/` içinde sabit tavanlarla durur (Etsy Ads, Premium, API bütçesi); tavanı Scryne onaylar (K-7).
- **Gizli bilgiler** `.env`'de (git dışı): `TYPESAFE_API_KEY`, `PRINTIFY_TOKEN`, `ETSY_KEYSTRING`, `ETSY_REFRESH_TOKEN`.

## Kararlar (Proje-Fikri'ye ek)
- **K-10 Tasarım dili v1:** tipografik; 8 şablon: `yigin`, `kavis`, `rozet`, `cerceve`, `ayirici`, `egik`, `madalyon` (yay + alt yay),
  `el_yazisi`. `el_yazisi_blok` (el yazısı bloğun üstüne biner) okunurluk kapısında tutarsızdı (S5) → kaldırıldı; yerine el yazısı
  bloğun üstünde/altında çakışmasız `el_yazisi` (Faz 2). Font havuzu 28 OFL font, rol tablosu `tasarim/sec.py` `FONTLAR`'da; el yazısı
  yalnız ikincil satırda ve yalnız büyük/küçük harf karışık metinde. Şablon seçimi son 12 tasarımda en az kullanılandan başlar.
- **K-11 Ürün ve fiyat:** Comfort Colors 1717 tişört, liste fiyatı $26,99 + alıcı kargosu; Gildan 18000 sweatshirt $39,99. Maliyet ~$17 /
  ~$21 (ürün + ABD kargo). Kâr hesabı Faz 8'de gerçek ücretlerle (TR: %6,5 + %6,5 + 14 TRY + %1,67 + $0,20; S7).
- **K-12 Nişler v1:** balıkçılık (baba/dede, Aralık + Babalar Günü), pickleball (Aralık), örgü/tığ işi (yükselen). Sezon varyantları niş
  içinde (Sevgililer Günü, St. Patrick's). "Class of 2027" kişiselleştirmeyle Ocak'ta (koşullu faz).
- **K-13 IP kapısı zorunlu:** USPTO + Jev'den geçmeyen hiçbir ifade render'a girmez; "insan" sonucu onay kuyruğunda ayrıca işaretlenir.
  USPTO dosyası ayda bir yenilenir. Tazelik dosyanın tarihinden değil verideki en yeni başvurudan ölçülür (kaynak donarsa dosyayı
  yenilemek veriyi tazelemez): 45 günü geçince uyarı, 60 günü geçince ifade üretimi durur (K-21).
- **K-14 Metin üretimi Claude:** ifadeler ve ilan metni `claude -p` ile; çıktı JSON şemasıyla doğrulanır, hatalıysa bir kez yeniden üretilir.
  Gerekçe: yaratıcı İngilizce kelime oyunu yerel 4B modelin üstünde. Jev metin üretmez (global kural).
- **K-15 Hat yerelde koşar** (Windows görev). Makine kapalıysa o gün atlanır; kuyruğa bir şey olmaz.
- **K-16 Mağaza:** adı `HobbyHeartPrints` (marka kontrolü temiz; yedek KindredHobbyCo, HobbyProudGoods); para birimi USD (Printify USD,
  %2,5 kur ücreti kabul — TRY fiyat yönetimi kur riski getirir).
- **K-17 Büyütme (Scryne 2026-10-13: "pek çok ürün, büyüt"):** her tasarım 3 ürün (tişört, sweatshirt, hoodie); 7 niş; mevsim takvimi
  (`config/takvim.toml`). Hız ısınma eğrisiyle: günde 1 → 2 → 4 → 6 → 8 tasarım (`config/yayin.toml`). Üretim talebe bağlı: kuyruk iki
  haftalık yayın kapasitesinin altına inmedikçe yeni üretim yok (Claude kullanımı boşa gitmez).
- **K-18 İki renk:** tasarımın küçük satırları/yayı/çizgileri ya da bir ana satırı vurgu renginde; palet her satılan kumaş rengine karşı
  kontrast kapısından geçer (kiremit ve hardal koyulaştırıldı).
- **K-19 Harcama tavanları (K-7'nin uygulanışı):** `config/tavanlar.toml`: aylık Etsy listeleme ücreti $60 (ısınma eğrisinin ilk ayı
  ~$42), günlük IP denetimi 120 ifade (TypeSafe). Sayım olay günlüğünden; tavanda hat para harcamadan durur, ürünü hataya düşürmez.
  Değerler Scryne onayı bekliyor. Kur TCMB'den günlük (`veri/kur.json`), alınamazsa config değeri.
- **K-20 Numune yok (Scryne, 2026-10-13):** Scryne kendine numune sipariş etmeyecek; bu kalıcı. Sağlayıcıyı Aria `printify-kesif`
  çıktısından seçer (ABD'de, araştırmadaki adaylar Monster Digital / SwiftPOD önde) ve kilitler (K-2). Kartın Printify'da çalıştığı ilk
  gerçek siparişte belli olur: ödeme alınamazsa sipariş üretime girmez, takip 5 iş gününde düşmez ve gecikme alarmı yakalar.
  Baskı kalitesi ilk siparişlerin yorum ve şikâyetleriyle izlenir. Kabul edilen risk: kötü baskı ilk alıcıda görülür (araştırma 04'teki
  numunesiz mağaza anekdotu); tasarım dilinin sade, vektör ve iki renkli olması bu riski küçültür.
- **K-21 Uçtan uca denetim sonrası sağlamlaştırma (2026-10-13):** gerçek hesap öncesi tam kod denetimi ve resmî API'ye karşı doğrulama.
  - Yayın adım adım kaydedilir (`bekliyor → olusturuldu → printify → etsy_taslak → aktif`); hata düştüğü adımdan yeniden denenir.
    Printify ürün kimliği yayından önce yazılır, ürün oluşturma 5xx'te yinelenmez: mükerrer ürün/ilan ücreti açılmaz. Etsy ilanı
    48 saatte oluşmazsa aynı ürün en çok iki kez yeniden yayınlanır, sonra "elle bakılmalı" olarak panelde ve bildirimde görünür.
    Etsy eşlemesini bekleyen tasarım günlük yayın sınırından pay almaz.
  - Sipariş defteri: Printify siparişleri sayfalanır (sayfa başına en çok 10); eşleme `shop_order_id`/`label`, tutmazsa aynı Printify
    ürününü taşıyan en yakın sipariş; makbuz kalemleri tasarıma ve ürün türüne bağlanır (haftalık raporda "satan tasarımlar");
    takip numarası Etsy'den de okunur; iptal/tam iade gelire girmez; gecikme alarmı yalnız bugün değişen makbuzdan değil tüm açık
    siparişlerden.
  - Günlük koşu: her adım ayrı korunur, biri düşerse diğerleri ve haftalık rapor sürer; sonuç `calisma/gunluk/son.json`; hata ya
    da alarm varsa Windows bildirimi; hata varsa çıkış kodu 1 (Görev Zamanlayıcı'da görünür). Panelin üstünde "Dikkat" şeridi.
  - K-13'ün "insan" yolu uygulandı: Jev'in emin olmadığı ifade tasarıma girer, panelde işaretli gelir; karar Scryne'ın onayında.
  - Etsy token adresi `api.etsy.com` (resmî doküman); kurulum betikleri mağaza ve üretim ortağı kimliklerini kendisi yazar.

## Kapsam (v1)
- **Süre tavanı:** ~4 hafta (kod tarafı); mağaza ve anahtarlar Scryne'ın Faz 0 işlerine bağlı.
- **Bitti = kullanıldı:** Scryne'ın Etsy mağazası canlıyken hat en az 30 ilanı Scryne'ın onayıyla yayınlamış ve ilk gerçek siparişte Etsy → Printify → üretim → takip numarası zinciri elle dokunulmadan çalışmıştır.
  4 haftada sipariş gelmezse v1 "30 ilan canlı" ile kapanır; sipariş zinciri v1.1'in ilk kontrolüdür.

## Riskler ve Doğrulamalar
| Risk | Durum | Kanıt |
|---|---|---|
| AI/otomatik tasarımın baskı kalitesi | Azaltıldı | Kodla vektör yazı; 7 kalite kapısı; mutasyonla 6/6 kapı yakalıyor (S5). Gerçek baskı: numune yok (K-20), ilk siparişlerin yorumları |
| Marka/eser şikâyeti | Azaltıldı | USPTO + Jev, 50 ifadede kaçan 0 (S6); en yaygın POD kalıplarının tescilli olduğu bulundu |
| Etsy kuralları (AI beyanı, üretim ortağı, ücretler) | Doğrulandı | Birincil sayfalar (S7) |
| Türkiye sabit maliyeti (Bağ-Kur) | **Açık** | S1: müşavir (Scryne) — cevap "kârsız" derse model değişir |
| Printify Türk kartı | **Açık** | İlk gerçek sipariş; ödeme düşmezse gecikme alarmı (K-20) |
| Etsy API erişimi | **Açık** | S4: Seller App kaydı (mağaza açılınca) |
| Satış hiç gelmemesi | Kabul edilen risk | Öldürme kriteri: 90. gün 100 ilan / < 5 satış → niş ve tasarım dili baştan; 180. gün < $100/ay net → dur |

## Scryne'ın işleri (Faz 0)
1. **Mali müşavir** (S1): Etsy'den POD satışında mükellefiyet ne zaman, öğrenciyken şahıs şirketinde Bağ-Kur, genç girişimci istisnası.
2. **Etsy mağazası** (S2): kimlik, Türk IBAN (ad = kimlik = yasal ad), 2FA. Aria ekran ekran yönlendirir. Mağaza adı Aria'dan.
3. **Printify** (S3): hesap, yurt dışına açık kart, Etsy bağlantısı. Numune yok (K-20).
4. **Anahtarlar:** Printify kişisel token; Etsy geliştirici hesabı → Seller App (Aria adım adım). USPTO API anahtarı isteğe bağlı (v1.1).

## Kapsam Dışı
Shopify (koşullu faz), ücretli dış reklam, kişiselleştirme (koşullu faz, Ocak), kupa/poster/sticker, dijital ürün, Etsy mesaj otomasyonu
(API yok; hazır cevap şablonları var), Redbubble/TeePublic/Amazon Merch kolları, AI görsel katmanı (grafik öğe; v1.1 spike).
