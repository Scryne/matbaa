---
title: POD araştırması 04 — tasarım ve otomasyon hattı
created: 2026-10-12
modified: 2026-10-13
type: note
status: active
tags: [pod, etsy, shopify, arastirma, otomasyon]
---
# 04 — Tasarım ve otomasyon hattının teknik bileşenleri

`arastirmaci` kolu, erişim 2026-10-12. [B] = birincil (resmî doküman/fiyat sayfası okundu), [İ] = ikincil.
Kolun arama bütçesi sonda bitti: §8 ve Etsy kuralları kısmen eksik. Etsy sayfaları WebFetch'e 403 verdi.
Sentez: [[00-sentez]].

## Özet
Ucuz ve otomatikleşebilen kısım: görsel üretimi, arka plan kaldırma, upscale, metin → tasarım başına ~0,10–0,50 $.
Tam otomasyonu kıran üç yer: (1) Etsy API ile yalnız **taslak** listeleme; "AI generator" işareti API'den atanamıyor
(etsy-engine README); (2) Etsy'de **mesaj API'si yok**; (3) Etsy niş araçlarının (eRank, Alura, EverBee, Marmalead)
hiçbirinde açık API yok. Printful mockup API'si yeni mağazada **2 istek/dk**. Midjourney'in resmî API'si yok, ToS otomasyonu yasaklıyor.

## 1. Görsel üretim API'leri
| Model | Fiyat/görsel | Maks. çözünürlük | Şeffaf arka plan | Yazı | Not |
|---|---|---|---|---|---|
| OpenAI gpt-image-2 (Nis 2026) | 1024² düşük/orta/yüksek 0,006/0,053/0,211 $ (yüksek [B]) | uzun kenar 3840, ≤8,29 MP | çelişkili: "preview" [İ], resmî rehber yalnız 2.5'te yazıyor | "hassas yerleşimde zorlanabilir" [B] | çıktı hakkı kullanıcıda [İ] |
| gpt-image-2.5 sunburst/flare | token fiyatı aynı (çıktı 30 $/M); görsel başı tablo yok | aynı | **evet, belgeli** [B] | geliştirildi | xhigh/max kalite |
| Nano Banana 2.1 | 1K 0,034 / 2K 0,050 / 4K 0,113 $ (batch yarısı) [B] | 4K | bulunamadı | veri yok | |
| Nano Banana 2 (Gemini 3.1 Flash Image) | 1K 0,067 / 4K 0,151 $ [B] | 4K | bulunamadı | | |
| Nano Banana Pro | 1K/2K 0,134 / 4K 0,24 $ [B] | 4K | bulunamadı | | |
| Gemini 2.5 Flash Image | 0,039 $ | 1K | | | **02.10.2026'da kapandı** [B] |
| Imagen 4 | 0,02–0,06 $ | 2K | | | **Gemini API'de 17.08.2026'da kapatıldı** [İ] |
| Ideogram 4.0 (03.06.2026, açık ağırlık) | Turbo 0,03 / Default 0,06 / Quality 0,10 $ [İ] | native 2K | 25.08.2026'da eklendi, 0,03–0,42 $ [İ] | tipografide en çok övülen; "%97 OCR" iddiası doğrulanmadı | açık ağırlığı kendin çalıştırmak ücretli lisans [B] |
| Ideogram 3.0 | 0,03 / 0,06 / 0,09 $ | | Transparent 1X 0,04/0,07/0,10 $ [İ] | | |
| Recraft | V4.1 Flash 0,007; V4.1 ~0,035; Pro 0,21 $. **SVG**: V4 Styles 0,05, V4.1 0,08, Pro 0,33 $. Vectorize 0,01, Remove BG 0,01, Crisp upscale 0,004 $ [B] | raster 1536x768–3072x1536; **SVG ölçeksiz** | ayrı Remove BG | veri yok | ücretli plan ticari hak verir [B]; 100 görsel/dk |
| FLUX 3 | 1K 0,048 / 2K 0,10 / 4K 0,607 $ [B] | 4K | bulunamadı | | |
| FLUX.2 | pro 0,03 $'dan, max 0,07 $'dan [B] | | | | klein 9B ve dev ağırlıkları non-commercial [İ] |
| Midjourney | **resmî API yok** | | | | ToS (27.05.2026) otomasyonu yasaklar; wrapper'lar ihlal [İ] |
| SD 3.5 yerel | ücretsiz ağırlık | | yerel pipeline | | Community License: yıllık gelir <1 M$ ücretsiz [B] |

Kaynaklar: developers.openai.com/api/docs/pricing · ai.google.dev/gemini-api/docs/pricing · docs.bfl.ai/quick_start/pricing.md ·
recraft.ai/pricing?tab=api · developer.puter.com/tutorials/ideogram-api-pricing/ · the-decoder.com (Ideogram 4.0) ·
docs.midjourney.com/docs/terms-of-service · karşılaştırmalı yazı benchmark'ı img.ly/ai-benchmarks (skorlar okunamadı).

## 2. Baskıya hazırlama
- Tişört tuvali 4500x5400 px @300 DPI (Printify bilgi bankası; zorunlu spek değil) [İ]. Printful: giyimde ≥150 DPI, DTG'de 300'ü aşma, şablonları indir [B].
- **Halo:** yarı saydam piksel beyaz alt baskıyı tetikler; tuval dolgusu beyaz kutu basar (Printify). Gelato: DTG'de düşük opaklık yerine halftone [İ].
- Upscale: Topaz (fal.ai) ≤24 MP 0,08 $, ≤48 MP 0,16 $ [B] — 4500x5400 = 24,3 MP → 0,16 $ dilimi. Recraft Crisp 0,004 $ (girdi ≤16 MP, ≤4096 px). Real-ESRGAN/Clarity Replicate ~0,01–0,016 $ [İ].
- BG kaldırma: Recraft/Ideogram 0,01 $; BiRefNet ucuz/yerel; rembg yerelde bedava. **Bria RMBG-2.0 CC BY-NC (ticari değil)**.
- Vektörleştirme: Recraft 0,01 $; vtracer (MIT, renkli girdi).

## 3. Mockup
| Araç | Fiyat | Otomasyon |
|---|---|---|
| Printful Mockup API v2 | doğrulanamadı | asenkron task + `mockup_task_finished` webhook; genel 120 istek/dk; **mockup: yeni mağaza 2/dk, ≥10 $ fulfilled sipariş sonrası 10/dk, 20.000 dosya/gün** [B] |
| Printify | ayrı ücret yok | ürün oluşturma yanıtındaki `images` = mockup'lar; genel 600/dk, katalog 100/dk, **publish 200/30 dk** [B]; AI mockup yalnız panelde doğrulandı |
| Dynamic Mockups | Free 50 kredi filigranlı; Pro 15–19 $/ay (3.600 kredi/yıl), ek 0,051 $ [B] | REST, toplu |
| Mediamodifier | 499 $/ay = 5.000 render [İ] | REST |
| Placeit / Smartmockups | açık API bulunamadı | |

## 4. Trend ve niş
- eRank (5,99–29,99 $/ay), Alura (yıllık 7,99–29,99 $), EverBee, Marmalead: **açık API yok**.
- Etsy autocomplete: resmî API yok; scraping ToS açısından riskli [İ].
- **Google Trends API**: resmî alpha, 24.07.2025'te açıldı, başvuruyla, ~1.800 gün veri [B].
- **Pinterest Trends API** (v5 trending keywords): var, ama partner/enterprise odaklı; bireysel erişim belirsiz [B].
- TikTok Creative Center: resmî API yok.
- Sezon: listeleme 6–12 hafta önce. Ekim ortası → Noel sıralama penceresi büyük ölçüde geçti; Sevgililer Günü (Ara–Oca listele), Anneler Günü (Şub–Mar) sıradaki hedefler (çıkarım).
- Etsy Open API v3 erişim türleri: Seller App (yalnız kendi mağaza, uygun satıcıya otomatik onay), Personal App, Commercial Access (manuel inceleme); limit QPS + kayan 24 saat QPD, artış developer@etsy.com [B].

## 5. Etsy SEO
- 13 etiketi farklı, çok kelimeli ifadelerle doldur; kategori ve öznitelikler etiket gibi çalışır, en spesifik alt kategori [B kısmi].
- Başlık kısa, ürün adıyla başlasın, "15 kelimeden az"; Etsy ifadenin başlıktaki konumunun sıralamayı etkilemediğini söylüyor [B kısmi].
- Sıralamaya mağaza puanı, **mesaj yanıt oranı** ve son 3 aydaki case oranı da giriyor [B kısmi].
- "Listing quality score" resmî terim değil; engagement (tık, sepet, favori, satış) belirleyici [İ]. 140 karakter başlık sınırı doğrulanmadı.
- LLM başlık/etiket: n8n şablonu (Printify + gpt-4o-mini) var; kaliteyi ölçen bağımsız veri yok.

## 6. Uçtan uca araçlar
- **oguzhankayan/etsy-engine** (MIT, 16 yıldız, 3 commit): trend → skor → Etsy talep doğrulama → tasarım (gpt-image-2.5) → mockup → SEO (Claude) → Etsy **taslak**. Dijital printable odaklı, POD değil. README: "With an AI generator" API'den ayarlanamıyor, elle açılıp yayınlanıyor.
- Printify MCP (TSavo), Printful MCP (Purple-Horizons): ürün oluşturma/yönetme [İ].
- Printify panel içi AI Image Generator + AI Mockups [B]; API erişimi doğrulanmadı.
- n8n: görsel üretimi + Etsy publish'i kapsayan şablon yok.
- Anekdot: tam otomatik all-over-print mağaza (2024 Substack) — neon/siyah AI tasarımlar kötü basıldı, numune sipariş edilmemişti; sonuç: 2–3 renkli sade tasarımlar otomasyona uygun.

## 7. Müşteri hizmeti
- **Etsy: mesaj API'si yok.** Webhook'lar: order.paid/canceled/shipped/delivered [İ]. Etsy'nin kendi otomatik yanıtı ve sipariş bildirimleri var. Yanıt oranı ilk mesaja göre ölçülür ve sıralamaya girer.
- Tarayıcı otomasyonu ToS açısından riskli kabul edilmeli; e-posta bildirimi parse etmek öneri, doğrulanmadı.
- Shopify: Inbox AI agent (opt-in) ürün/kargo/iade/beden sorularını katalog ve politikadan yanıtlıyor [İ].
- Otomatik: "siparişim nerede", kargo süresi, beden tablosu, politika. İnsan: iade, reprint, hasar, şikâyet.
- Printify/Printful yanlış beden ve cayma iadesini desteklemiyor; hasar/üretim hatasında teslimden 30 gün içinde ücretsiz reprint/iade [B].

## 8. Kalite kapıları (kısmi)
- Baskı hatalarının çoğu görsel hazırlıktan: temiz kesilmeyen görüntü, ekranda parlak/baskıda sönük renk [İ].
- OpenAI `moderation_blocked` bir marka filtresi değil.
- Marka/karakter tespiti araçları (Hive Likeness, VISUA, Roboflow trademark) bulundu, doğruluk/fiyat doğrulanmadı.
- Önerilen kapılar (kolun tasarımı): beklenen metne karşı OCR + edit-distance; vision LLM rubriği (anatomi, kesilme, kompozisyon); kenarda yarı saydam piksel sayımı; koyu/açık kumaşa karşı kontrast; güvenli alan kutusu; tersine görsel arama; riskli sınıf için insan kuyruğu.

## Kolun önerisi (öneri)
- Yol A (düz grafik): Recraft V4.1 vector → SVG'yi 4500x5400'e rasterize, upscale/halo yok → ~0,08 $.
- Yol B (tipografi): Ideogram 4.0 transparent ya da gpt-image-2.5 transparent + gerekirse Topaz.
- Mockup: Printify ürün yanıtındaki `images` (ücretsiz).
- Tasarım başına toplam (tahmin, retry dahil): Yol A ~0,19–0,25 $; Yol B ~0,35–0,50 $; premium ~0,50–0,80 $.

## En sert 5 darboğaz
1. Etsy AI işareti + taslak sınırı → her listelemede insan tıklaması; API erişim onayı ayrı kapı.
2. Etsy mesaj API'si yok → müşteri hizmeti tam otomatik değil; yanıt oranı sıralamada.
3. Printful mockup throttle (2/dk) ve Printify publish sınırı (200/30 dk).
4. Otomatik kalite/IP kapısı güvenilir değil → insan örneklemesi şart.
5. Etsy niş verisinde API yok → niş seçimi yarı manuel.
Ek: model ömrü kısa (Gemini 2.5 Flash Image, Imagen 4 kapandı) → model ID'leri yapılandırmadan okunmalı.

## Doğrulanamayanlar
Creativity Standards ve API ToS metni (403); 140 karakter sınırı; Etsy "AI disclosure" alanının API karşılığı; "11.08.2026 orijinal tasarım kuralı"
iddiası (asıl kural Creativity Standards'ta 10.06.2025'ten beri var gibi, kaynaklar çelişiyor); gpt-image-2 şeffaflığı; Ideogram resmî API fiyatı ve
şartları; FLUX şeffaflık/ticari şart; Printful mockup fiyatı; EverBee/Marmalead/Kittl/Creative Fabrica/Podly; Shopify Inbox AI resmî doküman;
"12.000 mağaza bot yüzünden askıya alındı" iddiası (satıcı pazarlaması).
