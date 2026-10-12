---
proje: Matbaa
created: 2026-10-13
type: proje-fikri
status: denetim
---
# Matbaa — Proje Fikri

**Kaynak:** Scryne, 2026-10-12: "ben bir şey ellemeden para kazanalım; Shopify/Etsy'de ürettirmeden sadece tasarım koyarak pay elde
edelim." 2026-10-13: "hedefim para kazanmak, en kazançlı şekilde; her şeyi sana bırakıyorum." Bu dokümandaki kararlar bu yetkiyle
Aria'nındır; para hareketi, hesap açma ve kimlik gerektiren adımlar Scryne'ındır.
Araştırma: `docs/arastirma/00-sentez.md` (+ 01…05, erişim 2026-10-12/13).

## Problem
Scryne'ın sermayesi ve zamanı az; pasif gelir istiyor. Print-on-demand'de (POD) üretim, stok, kargo ve ödeme altyapısı başkasında:
Etsy alıcıyı ve ödemeyi getiriyor, Printify basıp gönderiyor. Bize kalan iş tasarım, ilan ve sipariş takibi; bunların çoğu otomatikleşebilir.
Gerçekçi hedef "hiç ellemeden" değil, **kurulumdan sonra günde ~10 dakika insan**: mesajlar, haftalık onay kuyruğu, arada bir iade kararı.

## Hedef kullanıcı
- **Alıcı:** ağırlıkla ABD'li Etsy alıcısı; belirli bir topluluğa, mesleğe ya da hobiye ait olduğunu gösteren, özgün tipografik/grafik giyim arayan kişi.
- **Operatör:** Scryne — haftada bir onay kuyruğuna bakan, Etsy mesajlarına cevap veren kişi.

## Kararlar (K)
- **K-1 Kanal: Etsy önce.** Etsy Türkiye'den şirketsiz açılıyor, TRY IBAN'a ödüyor, alıcıyı kendisi getiriyor. Shopify (TR'de Payments/Stripe yok,
  trafik reklam ister, reklam maliyeti başabaşın üstünde) **koşullu faz**: Etsy'de satan tasarımlar ve TR ödeme yolu kanıtlanınca aynı katalogla eklenir.
- **K-2 Sağlayıcı: Printify (Free plan).** API'de ürün oluşturma + Etsy'ye yayın + sipariş + webhook tek zincir. Printful Etsy ürününü API'yle oluşturamıyor,
  yedek kalır. Baskı sağlayıcısı otomatik yönlendirmeye bırakılmaz; numuneyle seçilen bir ABD sağlayıcısına (aday: Monster Digital, SwiftPOD) kilitlenir.
  Premium ($24,99/ay yıllık) ancak ~20 sipariş/ay'da.
- **K-3 Ürün:** v1'de tipografik ve düz grafik **tişört + sweatshirt** (otomasyona en uygun, vektör yol ucuz ve temiz basılır). Kupa ve kişiselleştirme v2.
- **K-4 Az niş, derin seri; toplu jenerik ilan yok.** Niş veriyle seçilir (en çok 3); her nişte özgün bir seri. Yayın hızı tavanı günde ≤5 ilan
  (yeni mağaza rezervi ve Creativity Standards riskine karşı; Otomat'ın ölçülmüş dersi: çoğaltma = ceza).
- **K-5 İnsan kapıları kalır:** haftalık onay kuyruğu (niş + tasarım + riskli IP sınıfı), Etsy mesajları (API yok), iade/reprint kararı.
  Kuyruk tek ekranda, telefon ekranında 10 dakikada bitecek boyutta.
- **K-6 Platform kurallarına uyum koddadır:** her ilanda üretim ortağı (`production_partner_ids`), açıklamada AI beyanı, "Designed by" kategorisi.
  Marka/karakter/ünlü adı içeren tasarım otomatik elenir; şüpheli olan kuyruğa düşer.
- **K-7 Para ve hesap Scryne'ın:** Etsy hesabı, banka (ID = banka adı = yasal ad) ve Printify kartı Scryne adına. Kodda para harcayan her eşik
  (reklam, Premium, API bütçesi) yapılandırmada sabit tavanla durur; tavanı Scryne onaylar.
- **K-8 Tasarım üretimi API ile**, tasarım başına tavan $0,50. Model kimlikleri `config/`'te (model ömrü kısa: Imagen 4 ve Gemini 2.5 Flash Image 2026'da kapandı).
- **K-9 Mükellefiyet sorusu projeden bağımsız ama satıştan önce:** Bağ-Kur (~10–12 bin TL/ay) kârı aşabilir; Faz 0'da müşavire sorulur. Cevap
  "bu iş bu ölçekte kârsız" çıkarsa proje durur ya da modeli değişir (ör. Redbubble/TeePublic royalty). Hukuki analiz yapılmaz; bu operasyonel maliyet kalemidir.

## v1: Kapsam ve "Bitti" Tanımı
- **Süre tavanı:** ~4 hafta.
- **Bitti = kullanıldı:** Scryne'ın Etsy mağazası canlıyken hat **en az 30 ilanı** Scryne'ın haftalık onayıyla yayınlamış, numune siparişi baskı kalitesini
  doğrulamış ve **ilk gerçek siparişte** Etsy → Printify → üretim → takip numarası Etsy'ye zinciri insan dokunmadan çalışmıştır. İlk sipariş 4 haftada
  gelmezse v1 "30 ilan canlı + numune doğrulandı" ile kapanır, sipariş zinciri v1.1'in ilk kontrolüdür.
- **Temel özellikler:**
  1. Niş kartı: veriyle seçilmiş en çok 3 niş, her biri için alıcı, anahtar kelime ve tasarım dili.
  2. Tasarım hattı: prompt → görsel (vektör/şeffaf) → 4500x5400 baskı dosyası → otomatik kalite kapıları (OCR, alfa/halo, kontrast, güvenli alan, IP filtresi).
  3. İlan metni: başlık, 13 etiket, açıklama (AI beyanı dahil), öznitelikler.
  4. Onay kuyruğu: Scryne'ın haftalık 10 dakikalık ekranı; onaylanan ilan yayına girer.
  5. Yayın: Printify ürün + mockup → Etsy'ye publish → Etsy API ile üretim ortağı + aktifleştirme; günlük tavan.
  6. Sipariş izleme: Etsy `order.paid` / Printify webhook'ları; takip numarası düşmeyen ya da geciken sipariş için uyarı.
  7. Gösterge: ilan sayısı, görüntülenme, satış, net kâr (Etsy ücretleri + Printify maliyeti + kur), harcama tavanları.

## Kapsam dışı (v1)
- Shopify (koşullu faz), Etsy Ads ve Offsite dışında ücretli reklam.
- Kişiselleştirilmiş ürün (isim/tarih) — Etsy cirosunun ~%30'u; v2'nin en güçlü adayı, sipariş anında tasarım üreten ayrı bir zincir ister.
- Kupa, poster, sticker gibi ek ürün tipleri; dijital ürün (printable).
- Müşteri mesajlarının otomasyonu (Etsy'de API yok); yalnız hazır cevap şablonları.
- Redbubble/TeePublic/Amazon Merch kolları.

## Başarı ve öldürme kriteri
- **Ölçü:** net kâr (tüm kesintilerden sonra), TL olarak, aylık.
- **90. gün kontrolü (mağaza açılışından):** ≥100 ilan ve <5 satış → niş/tasarım dili baştan; 180. gün ≤ ayda $100 net → proje durur ya da model değişir.
- **Beklenti (araştırma, kanıta dayalı bant):** 3. ay 0–10 sipariş; 12. ay aylık $100–600 brüt; kâr garantisiz. Bu proje sermayesiz değil:
  ilk 6 ay ~$300–600 + ~$300 işletme tamponu (Printify siparişte karttan çeker, Etsy ~14 gün sonra öder).

## Spike'lar (finalizasyondan önce)
| # | Soru | Kim |
|---|---|---|
| S1 | Mükellefiyet ve Bağ-Kur (öğrenci) maliyeti | Scryne + müşavir |
| S2 | Etsy mağazası TR'den açılış, kurulum ücreti, kimlik/banka | Scryne (Aria adım adım yönlendirir) |
| S3 | Printify Türk kartını kabul ediyor mu; numune kalitesi (2 sağlayıcı × tişört) | Scryne ödeme, Aria sipariş hazırlığı |
| S4 | Etsy Seller App kaydı; API ile `production_partner_ids` + aktifleştirme; Printify publish → Etsy akışı | Aria (anahtar Scryne'ın hesabından) |
| S5 | Tasarım hattı: 10 tasarım, otomatik kapılar, maliyet/tasarım | Aria |
| S6 | IP/risk kapısı: kural tabanlı liste mi, Jev mi (global kural: önce `ts.py` spike'ı) | Aria |
| S7 | ✅ 2026-10-13 Etsy'nin birincil sayfaları doğrulandı: TR %6,5+14 TRY, ROF %1,67, AI beyanı açıklamada, POD = Designed by + üretim ortağı → `docs/spike/S7-etsy-birincil-kaynak.md` | Aria |

## Açık sorular
- Niş seçimi için kullanılabilir veri kaynağı: Google Trends API (alpha başvurusu), Pinterest Trends, Etsy'nin kendi arama sayfası (scraping yasak) — S5 öncesi.
- Etsy mağaza para birimi: USD (+%2,5 dönüşüm) mi, TRY mi (kur riski)?
- Printify'ın Etsy'ye ilanı taslak mı aktif mi yayınladığı ve AI beyanının Shop Manager'da ayrı bir alan isteyip istemediği (S4, S7).
- Mağaza adı ve marka (kamusal yüzde Scryne'ın kişisel verisi olmaz; Etsy'nin yasal ad gereksinimi ayrı).
