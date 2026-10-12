---
title: S7 — Etsy'nin birincil sayfaları (ücret, AI, üretim ortağı, rezerv)
created: 2026-10-13
type: spike
status: tamamlandi
---
# S7 — Etsy'nin birincil sayfaları

**Soru:** Araştırmada Etsy'nin yardım/politika sayfaları WebFetch'e 403 verdi, bu yüzden kurallar arama özetinden gelmişti. Birincil metin ne diyor?
**Yöntem:** `curl_cffi` (tarayıcı TLS imzası) ile sayfalar çekildi, metne çevrildi (2026-10-13). Chrome eklentisi bağlı değildi.
Bir kısmı ilk denemede 403 verdi, bekleyip tekrar denenince açıldı. `offsite` (360041838234) ve üretim ortağı yardım makalesi (34707360607511) 404.

## Doğrulananlar (birincil)
| Konu | Etsy'nin metni | Kaynak |
|---|---|---|
| TR ödeme işleme | **%6,5 + 14 TRY** | help 115015628847 |
| TR mevduat | min **50 TRY**; ücret eşiği **600 TRY** | aynı |
| TR regulatory operating fee | **%1,67** (ikincil kaynakların %2,24/%2,27'si bayat) | help 1500011073202 |
| Etsy Payments | Türkiye uygun ülke; **PayPal TR satıcısında yok**, mağazada PayPal kabul edilemez | help 115015710408 |
| Listeleme | $0,20; 4 ayda otomatik yenileme ($0,20) | legal/fees (son güncelleme **05.10.2026**) |
| Transaction | %6,5 (ürün + kargo + hediye paketi) | aynı |
| Kurulum ücreti | "may be required", tek seferlik; onboarding'de gösterilir, **karta yerel para biriminde** çekilir (Payoneer'la USD) | aynı |
| Kur dönüşümü | ilan para birimi ≠ ödeme hesabı para birimi → %2,5; Etsy aynı para biriminde listelemeyi öneriyor; alıcı fiyatı kendi para biriminde görür | aynı |
| Offsite Ads | <$10k/365 gün %15, opt-out mümkün; ≥$10k %12; ürün + kargo (+ hediye paketi) üzerinden. **ABD dışı satıcıda ilan fiyatına dahil vergilere de uygulanır**; kişiselleştirme ek ücreti de dahil | aynı |
| Etsy Plus | $10/ay | aynı |
| KDV | tüm ücretler KDV hariç; konuma ve işletme durumuna göre Etsy ücretlere KDV ekleyebilir | aynı |
| Creativity Standards | son güncelleme **10.06.2025** | legal/creativity |
| POD kategorisi | "Designed by a seller — sellers' original designs produced by a production partner"; **üretim ortağını beyan etmek ve nereden gönderildiğini doğru vermek zorunlu**; Etsy üretim yardımına **2016'dan** beri izin veriyor | aynı |
| AI | "Seller-prompted AI creations" izinli; **"Sellers must disclose within their listing description if an item is created with the use of AI."** Prompt paketi satışı yasak | aynı + seller-handbook 1275449912004 |
| Kişiselleştirilmiş POD | "Buyer-personalized items produced by a production partner" → **"Sourced by a seller"** kategorisi; ilk görsel kişiselleştirilmiş bitmiş ürünü göstermeli, boş ürün ya da "Your Text Here" değil | legal/creativity |
| Rezerv | yeni satıştan bir yüzde tutulur; **yüzde ve süre hesaba göre değişir, Payment account'ta gösterilir**; takip numarası taşımada görünürse anında serbest; Star Seller'a konmaz; tetikleyiciler arasında eksik takip | help 360058722214 |
| Çok mağaza | her mağaza ayrı hesap + ayrı e-posta; aynı kart/banka kullanılabilir, **aynı vergi no ve adres zorunlu**; tümü Public Profile'da listelenir; mağazalar birleştirilemez | help 360017604474 |
| AB | ≤150 € ve AB dışından → Etsy'nin IOSS numarası kargo firmasına elektronik iletilir; **01.07.2026'dan ≤150 € siparişte kalem başı 3 € gümrük vergisi** (KDV'ye ek) | help 360000337247 |
| IP | Etsy hukuki değerlendirme yapmaz, uygun bildirimde içeriği kaldırır; DMCA karşı bildirimi yalnız ABD telif bildirimlerinde, 10 iş günü; "Repeat Infringement" bölümü var (sayı yok) | legal/ip (son güncelleme 15.06.2023) |

## Projeye etkisi
- **Ücret modeli kesinleşti:** TR satıcı için listeleme $0,20 + %6,5 + (%6,5 + 14 TRY) + %1,67 (+ varsa KDV) + offsite satışında %15. Kod bu oranları `config/`'ten okur.
- **Mağaza para birimi:** Etsy aynı para biriminde listelemeyi öneriyor (TRY → %2,5 yok). Alıcı fiyatı kendi para biriminde görür. Maliyet USD olduğu için
  fiyat TRY'de tutulursa kur hareketinde marj kayar → fiyat güncelleyicisi gerekir. Karar finalizasyonda (açık soru kapandı sayılmaz, veri eklendi).
- **AI beyanı açıklama metninde** — ayrı bir API alanı gerekmiyor; şablon her açıklamaya sabit bir cümle ekler. (Shop Manager'da ayrıca bir onay
  kutusu olup olmadığı S4'te görülecek.)
- **Kişiselleştirme (v2)** "Sourced by a seller" kategorisinde izinli; ilk görsel kişiselleştirilmiş örnek olmalı.
- Offsite ücreti ABD dışı satıcıda vergiye de uygulanıyor → Offsite'tan gelen satışta marj araştırmadaki hesabın biraz altında.
