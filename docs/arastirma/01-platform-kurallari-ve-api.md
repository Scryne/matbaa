---
title: POD araştırması 01 — Etsy ve Shopify kuralları, ücretleri, API'leri
created: 2026-10-12
modified: 2026-10-13
type: note
status: active
tags: [pod, etsy, shopify, arastirma, api]
---
# 01 — Platform kuralları, ücretleri ve API'leri

`arastirmaci` kolu, erişim 2026-10-12/13. [B] birincil doğrudan okundu · [B-dolaylı] resmî sayfa, arama özetiyle (etsy.com/legal,
help.etsy.com, seller-handbook WebFetch'e 403) · [İ] ikincil · [A] anekdot. Etsy OpenAPI spec JSON'u (~911k karakter) doğrudan tarandı.
Sentez: [[00-sentez]].

## 1. Etsy

### Ücretler
| Kalem | Değer |
|---|---|
| Listeleme | $0,20; 4 ayda ya da satışta yenilenir; çok adetli ilanda her satılan adet için tekrar |
| Transaction | %6,5 (ürün + kargo + hediye paketi) |
| Ödeme işleme (TR) | **%6,5 + 14 TRY** (08.07.2024'ten) [B-dolaylı]; 600 TRY altı yatırmada 42 TRY |
| Regulatory operating fee (TR) | **çelişkili:** %1,67 (Etsy özeti, 22.06.2026) / %2,24 / %2,27 (ikincil) |
| Kur dönüşümü | %2,5 (ilan para birimi ≠ hesap para birimi) |
| Offsite Ads | <$10k/365 gün: %15, kapatılabilir; ≥$10k: %12, **kapatılamaz**; sipariş başı tavan $100 |
| Etsy Ads | CPC ort. $0,20–0,50 [İ] |
| Etsy Plus | ~$10/ay |
| Kurulum ücreti | konuma göre $0–20 (Printify, 12.10.2026); diğer bloglar $15 / $15–29; **TR için kesin değer yok** |
| KDV | Etsy ücretlerine ekleniyor [İ]; güncel oran doğrulanmadı |
TR toplam: ≈ **%17,2–17,8 + 14 TRY + $0,20 + KDV**; offsite satışında +%12–15.

### POD ve Creativity Standards
- **Üretim ortağı [B-dolaylı]:** başkasının, **senin özgün tasarımından** ürettiği iş; her ilgili ilanda belirtmek zorunlu; kriteri karşılamayan ortakla ilan kaldırılabilir. POD = "Designed by" kategorisi.
- **AI [B-dolaylı]:** satıcının kendi prompt'larıyla üretilen AI görseli "Designed by a seller" sayılır; **ilan açıklamasında AI kullanımını belirtmek zorunlu**; prompt paketi satışı yasak.
- **API'de AI beyan alanı yok** [B, spec] → beyan açıklama metninde yapılır.
- **10.06.2025 sıkılaşması [İ]:** standartlardan "or using a templated design or pattern" ifadesi duyurusuz çıkarıldı → satın alınmış şablon/clip-art/hazır grafik, ticari lisansla bile risk. 15.07.2025 sonrası kaldırılan ilanlara itiraz mümkün. Kaldırma e-postaları genel, otomatik bayrak hataları var [A].
- **Printify'a göre en sık askı nedeni:** Printify'ı production partner olarak eklememek ve rolünü ilanda anlatmamak. **Printify bunu yayında otomatik ekleyemiyor**, Etsy'de elle düzenlenmeli [İ].
- POD'a özgü sıralama değişikliği doğrulanmadı; 2024'ten beri POD gösterim düşüşü bildirimleri [A]. "ABD içi kargo >$6 → görünürlük kaybı" iddiası Seller Handbook 1293023712519'a atıf yapıyor, okunamadı.

### Yeni mağaza riskleri
- **Ödeme rezervi [B-dolaylı, 2023]:** tetikleyiciler — ani sipariş artışı, eksik takip, geç kargo, iade artışı, **yeni mağaza olmak**. Rezerv takipli kargoda serbest kalır. Star Seller muaf. ("90 günden genç mağazada kazancın %75'i rolling 90 gün" iddiası tek kaynak, doğrulanmadı.)
- Kurulum: banka hesabı, birey/şirket beyanı, 2FA, erken kimlik doğrulama; mağaza açmak için en az 1 ilan.
- **Birden fazla mağaza izinli:** her biri ayrı Etsy hesabı + ayrı e-posta; tümü Public Profile'da listelenmeli; bir hesaptaki ihlal ilişkili hesapları etkileyebilir.
- **IP yaptırımı:** sabit sayı yok; "tekrarlı veya çoklu bildirim" → Etsy'nin takdiriyle satış yetkisi sonlandırılır; kapanış sonrası yeni mağaza ilişkili hesap olarak reddedilebilir; karşı bildirimden 10 iş günü sonra ilan geri gelebilir. ("12 ayda 2 doğrulanmış IP askısı = kalıcı kapanma" kaynaksız.)
- Toplu listelemeye dair resmî belge yok; "50 iyi ilan > 500 zayıf ilan" yazar görüşü.

### Etsy Open API v3 [B]
| Seviye | İçerik |
|---|---|
| **Seller App** | yalnız kendi mağaza; onay otomatik, "light and straightforward" |
| Personal App | kendi mağazanın ötesi, sınırlı ölçek, derin inceleme |
| Commercial | önce onaylı Personal App; manuel inceleme; her satıcıya hizmet |
- Commercial onayı fiilen güvenilmez: 2 hafta–aylar, gerekçesiz red, Ağu–Eki 2026'da cevapsız destek [A, GitHub #1060/#1278/#1361/#1699]. **Kendi mağazamız için Seller App yeterli.**
- Kurallar: screen-scraping yasak; uygulama adında "etsy" geçmesi red sebebi; "Etsy" ticari marka uyarısı gerekli.
- **Rate limit:** anahtar başına QPS + kayan 24 saat QPD; sayfadaki 150 QPS / 100k QPD yalnız örnek; eski kaynaklar yeni uygulamaya 10 QPS / 10k QPD diyor; 429 + `retry-after`.
- **Auth:** access token 1 saat, refresh 90 gün; scope'lar `listings_r/w/d`, `transactions_r/w`, `shops_r/w`, `profile`, `address`, `email_r`.
- **Listeleme akışı:** `createDraftListing` (zorunlu: quantity, title, description, price, who_made, when_made, taxonomy_id; fizikselde shipping_profile_id + readiness_state_id) → `updateListingInventory` ile varyasyonlar (1 varyasyonda 70, 2'de 4900 ürün) → `uploadListingImage` (≥1 görsel) → `updateListing state=active`.
- **Production partner:** `createDraftListing`'te `production_partner_ids` var; partnerler için yalnız GET → **ortak Shop Manager'dan bir kez elle eklenir, ID'si API'yle ilanlara bağlanır** (çıkarım).
- Not: 04'teki "API'yle yalnız taslak" bulgusu buna göre düzeltilir: `updateListing state=active` ile aktifleştirme API'de var; tek eksik **AI beyanının yapılandırılmış alanı** (açıklama metniyle yapılıyor). etsy-engine'in elle yayınlama gerekçesi Shop Manager'daki "With an AI generator" seçeneği.
- **Siparişler:** `getShopReceipts`; **webhook'lar** `order.paid/canceled/shipped/delivered` (personal + commercial), HMAC-SHA256, 8 kademeli yeniden deneme. İlan/mesaj webhook'u yok.
- **Takip numarası:** `createReceiptShipment`; Preferred Partner bölgelerinde yalnız onaylı fulfillment uygulamaları + **satıcının kendi kişisel uygulaması** + eski yetkililer. Printify/Printful bu yolu kullanıyor.
- **Mesaj API'si yok** — Etsy'nin resmî `openapi-support` hesabı 14.07.2026'da doğruladı (#1645). Var olanlar: `sale_message`, `digital_sale_message`, `vacation_autoreply`.
- API Terms güncel metni okunamadı; 2020 arşivi Etsy içeriğinin ML'de kullanımını yasaklıyordu.

### Printify/Printful ↔ Etsy
- Printify: sipariş otomatik provider'a; takip otomatik itiliyor (eşleşme detayı yok). **Etsy tarafında SKU/varyant düzenlemek eşlemeyi bozar**; düzenleme Printify'dan.
- Takibin Etsy'ye düşmemesi → Star Seller kaybı vakaları [A]; sorumluluk mağazada.
- Printful: ürün ve sipariş senkronu otomatik, white-label; Etsy'de canlı kargo oranı yok.
- **Printify Premium $29 → $39/ay (17.02.2026)**, yıllık $299.
- TR kartıyla Printify/Printful ödemesi için resmî kaynak yok.

### Satıcı performansı (Star Seller, ikincil)
Üç aylık dönemde: ilk mesaja 24 saatte yanıt ≥%95; zamanında kargo + takip ≥%95; ort. puan ≥4,8; ≥5 sipariş; ilk satıştan ≥90 gün.

## 2. Shopify
| Plan (ABD sayfası, 12.10.2026) | Aylık | Yıllık (aylık) | 3. taraf ödeme ek ücreti |
|---|---|---|---|
| Basic | $27 | $19 | %2 |
| Grow | $72 | $54 | %1 |
| Advanced | $399 | $299 | %0,6 |
- Deneme: 3 gün ücretsiz + 3 ay $1/ay. Starter ABD sayfasında yok. Bloglar Basic $39/$29 diyor (birincil kazanır). TR fiyatı bulunamadı.
- **Shopify Payments TR'de yok, Stripe TR'de yok** [B]. TR gateway'leri: PayTR, Garanti POS, iyzico; 2023 forumu iyzico'nun dropshipping'i reddettiğini yazıyor [A].
- **Admin GraphQL (2026-10):** `productCreate` (unpublished; medya `originalSource` URL, asenkron) → `productVariantsBulkCreate`/`productSet` → `publishablePublish`. Ürün başı 2048 varyant. Maliyet Standard 100 puan/sn. Büyük mağaza günlük varyant sınırları iki resmî sayfada çelişiyor.
- **01.01.2026'dan yeni legacy custom app yok;** Dev Dashboard + client credentials, token 24 saat [İ/A].
- Sidekick (Winter '26): görsel düzenleme, Flow iş akışı, özel uygulama üretimi; POD'dan söz yok. Agentic Storefronts: ürünler ChatGPT/Copilot/Perplexity'de keşfedilebilir.
- Shopify'a organik trafik verisi bulunamadı.

## 3. Diğer POD pazar yerleri (zayıf kaynak)
| Platform | Bulgu |
|---|---|
| **Spring (eski Teespring)** | **Kapanıyor** [B]: 15.09.2026 satış araçları kapandı, 15.10.2026 hesap erişimi bitiyor |
| Amazon Merch on Demand | 01.06.2026'dan 3 kademe royalty ($19,99 tişörtte $2,44 / $4,88 / $5,27; kademe organik olmayan trafik payına göre) [İ]; manuel başvuru 2–8 hafta; API yok; TR uygunluğu bulunamadı; Haziran 2026'da tüketiciye AI tasarım aracı eklendi |
| Redbubble / TeePublic | Articore Group; sanatçı markup'ı (varsayılan %20); AI yasak değil, toplu düşük kalite "Marketplace Integrity" incelemesi; API yok; ücret modeli kaynaklarda çelişkili. 10-02 notu: Payoneer'le ödüyorlar |
| Society6 | %10 royalty; sahiplik/güncel durum belirsiz |
| Zazzle | royalty standart %5, azami %50 (01.04.2025) [B] |
| Spreadshirt | 2026 verisi yok; 10-02 notunda TR'den "kapalı" |

## Kolun kritik 10 bulgusu
1. Etsy'de mesaj API'si yok (resmî, 14.07.2026).
2. Commercial Access güvenilmez; kendi mağaza için Seller App (otomatik onay) yeterli.
3. Takip gönderimi koşullu; satıcının kendi uygulaması ve Printify/Printful yetkili.
4. AI yasak değil, beyan zorunlu (açıklamada); yalnız seller-prompted AI "Designed by"; şablon/clip-art riskli; toplu otomatik üretim "özgün tasarım" şartını tartışmalı kılabilir (yorum).
5. Production partner her ilanda şart, API'den eklenemiyor (bir kez elle).
6. TR ücret yükü ≈ %17+ (+14 TRY + $0,20 + KDV); offsite'ta +%12–15.
7. Yeni mağaza rezerv/askı riski; hızlı toplu listeleme + geç/takipsiz kargo riski artırır; Star Seller ≥90 gün + 5 sipariş.
8. Shopify'da Payments ve Stripe TR'de yok → yerel gateway (+%2 Basic ek ücret); POD'a şüpheyle bakabilirler.
9. Shopify Admin API otomasyona uygun; kurulum Dev Dashboard'a geçti.
10. Alternatif pazar yerleri daralıyor (Spring kapandı, Amazon Merch royalty'yi organik satıcıya düşürdü, Society6 belirsiz).

## Çelişkili / doğrulanamayan
TR ROF oranı; Etsy kurulum ücreti; Offsite resmî metni; yeni uygulama varsayılan rate limit; API Terms güncel metni; 2026 rezerv oranı;
"$6 kargo" eşiği; Star Seller resmî sayfa; Shopify fiyatları (birincil $27 vs blog $39); Shopify varyant eşikleri; Amazon Merch kademe/erişim;
Redbubble ücret modeli; lisanslı tasarımın "designed by" sayılması; üretim ortağı izninin yılı (2014/2016).

## Kaynaklar (seçme)
developers.etsy.com (documentation, rate-limits, authentication, webhooks, tutorials/listings, fulfillment, shopmanagement) ·
etsy.com/openapi/generated/oas/3.0.0.json · github.com/etsy/open-api/discussions/1645, 1699, 1278, 1361, 1060 ·
community.etsy.com (CEO mesajı) · valueaddedresource.net (payment reserves) · printful.com/uk/blog/how-much-does-etsy-take-per-sale ·
printify.com/guide/how-to-sell-on-etsy · printify.com/knowledge-hub/etsy-print-on-demand-sync-errors · printful.com/integrations/etsy ·
blog.marmalead.com/etsy-print-on-demand · listadum.com/blog/etsy-creativity-standards · iscompliant.app · craftybase.com ·
shopify.com/pricing · help.shopify.com (supported-countries) · stripe.com/global · shopify.dev (productCreate, rate-limits) ·
shopify.com/editions/winter2026 · amazecommerce.com/spring-update · merchtitans.com · zazzle.com/hc/article/-30810357489175.
