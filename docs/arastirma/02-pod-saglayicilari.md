---
title: POD araştırması 02 — üretim/fulfillment sağlayıcıları
created: 2026-10-12
modified: 2026-10-13
type: note
status: active
tags: [pod, printify, printful, gelato, arastirma]
---
# 02 — POD sağlayıcıları (Printify, Printful, Gelato ve diğerleri)

`arastirmaci` kolu, erişim 2026-10-12/13. Arama bütçesi bitti: Printify branding/reprint ve Printful reprint resmî kaynaktan doğrulanmadı;
Printify ürün fiyatları giriş istiyor. Sentez: [[00-sentez]].

## Özet
- **Tam otomasyon için en sağlam aday Printify:** API'de ürün oluşturma → görsel → Etsy/Shopify'a publish → sipariş → webhook tek zincir.
- **Printful:** kalite ve mockup API'si güçlü, ama **Etsy/Shopify mağazasında API ile ürün oluşturulamıyor** (resmî doküman).
- **Gelato:** Türkiye'de üretim ortağı var (Shopify kaynak listesi), Etsy/Shopify entegrasyonu çalışıyor; ürün oluşturma API'si doğrulanmadı.
- Türk kartı/hesap kısıtına dair hiçbir sağlayıcıda resmî ifade yok → **test siparişiyle doğrulanmalı**.

## 1. Abonelikler
| Sağlayıcı | Plan |
|---|---|
| Printify | Free $0 (5 mağaza). Premium $39/ay (17.02.2026'da $29'dan çıktı) ya da $299,88/yıl; "%20'ye kadar / yeni ürünlerde %33'e kadar" indirim. Enterprise "custom API integration" |
| Printful | Free; Growth $24,99/ay (%33'e kadar ürün, %9 branding indirimi); yıllık $12K satışta ücretsiz |
| Gelato | Free; Gelato+ $29,99/ay ya da $239,88/yıl |
| CustomCat | Lite ücretsiz; Pro $30/ay |
| Apliiq | Free; VIP $39,99/ay |
| SPOD/Spreadconnect, Prodigi, Gooten | abonelik yok |

## 2. Baz fiyatlar
**Printful (katalog API'sinden, birincil; plan etiketsiz, muhtemelen Free):**
| Ürün | Baz (USD) | ABD kargo ilk / ek |
|---|---|---|
| Bella+Canvas 3001 | S–XL $11,92–12,25; 2XL ~$13,8; 3XL ~$15,5 | $4,95 / +$2,20 |
| Gildan 18500 hoodie | $22,63–30,63 | $8,79 / +$2,50 |
| Gildan 18000 sweatshirt | $17,25–27,17 | $8,79 / +$2,50 |
| 11 oz kupa | $6,75 | $6,69 / +$3,50 |
| Poster (mat) | 12x16 $11,95; 18x24 $13,75; 24x36 $19,25 | $4,99–7,99 / +$0,40 |
| Canvas | 12x16 $24,95; 16x20 $30,50 | $6,79–10,39 |
| iPhone clear case | $11,50 | $5,19 / +$1,00 |
| Tote | $15,25 | $4,69 / +$2,00 |
| Kiss-cut sticker | $2,50–2,75 | $4,49 / +$0,05 |
Ekler: arka baskı +$5,95, kol +$2,49/$5,95, iç etiket $0,99, dış etiket $2,49.

**Printify (ikincil):** Gildan 18500 $23,11 / Premium $17,00; 18000 $17,33–19,47; 3001 kargo $4,75–5,19. Gerçek maliyet giriş yapınca katalog API'sinden okunur.
Aynı sağlayıcıdan ek ürün "additional" kargo; farklı ürün tipi/sağlayıcı her biri tam "first item" öder.
**Diğer (ikincil):** Gooten 3001 $8,65'ten, kargo $4,95, üretim ~1,5 gün; CustomCat tişört $9,58–15,58; Prodigi A3 print $14.

## 3. Süre ve lokasyon
- Printful: üretim 2–5 iş günü; ABD teslim 3–4, AB/UK 5–20 iş günü. Tesisler: AU, CA, JP, LV, MX, ES, US. DTG, DTF, nakış; kupa sublimasyon.
- Printify: üretim 2–7 gün (provider'a bağlı); lokasyonlar AU, CA, CZ, DE, LV, PL, UK, US. Monster Digital / SwiftPOD (ABD) 1–2 gün, kaliteli (affiliate/anekdot).
- **Gelato:** 25–32 ülke, **Türkiye listede**; hangi ürün ve yurt dışı gönderim doğrulanmadı.
- Spreadconnect: CZ/DE/PL/US, %95 48 saatte (kendi iddiası). Prodigi: UK/AB/ABD, ABD toplam teslim 9–13 gün.

## 4. Kalite (Trustpilot, anekdot)
| Sağlayıcı | Skor / yorum | Tekrarlayan şikâyet |
|---|---|---|
| Printify | 4,5 / 7.675 | gecikme, "shipped" ama üretilmemiş, kayıp paket, takılan reprint |
| Printful | 4,2 / 7.929 | gecikme, stok iptali, Etsy sync hataları, AI destek |
| Gelato | 4,2 / 3.404 | destek, takip, **Etsy'den senkronlanan siparişte sales tax kesilmesi** |
| Gooten | 3,1 / 226 | gecikme, yanlış ürün |
| Prodigi 4,0 · CustomCat 2,5 · SPOD 2,6 | az yorum | |
- Printful reshipment oranı %0,19–0,24 (ikincil). Printify Quality paneli reprint oranını yalnız son 30 günde ≥20 siparişi olan mağazaya gösteriyor.
- Printify'da otomatik yönlendirme yerine **Monster Digital/SwiftPOD'a kilitlemek** Printful'a yakın kalite veriyor (anekdot).

## 5. API
| | Printful | Printify | Gelato | Prodigi | Spreadconnect |
|---|---|---|---|---|---|
| Rate limit | 120/dk; mockup yeni mağaza 2/dk, yerleşik 10/dk | 600/dk; katalog 100/dk; **publish 200/30 dk** | yayımlanmamış | — | 60/dk |
| Ürün oluşturma | **Etsy/Shopify mağazasında yok** | `POST products.json` | doğrulanmadı | yok | `POST /articles` |
| Etsy/Shopify'a yayın | — | `publish.json` | — | — | — |
| Mockup | Mockup Generator (async + webhook) | ürün nesnesinde salt-okunur görseller | yalnız arayüz | — | önizleme |
| Webhook | sipariş, paket, ürün, stok, mockup | `order:created/updated/sent-to-production`, `shipment:created/delivered`, `product:*`, `shop:disconnected` | var | callback | HMAC |
- Printify auth: kişisel token 1 yıl; OAuth token 6 saat; her istekte `User-Agent`; sunucu tarafı; 5 MB üstü base64 yükleme kalkacak (URL ile yükle).
- Printful private token mağaza düzeyinde, süresi doluyor; v2'de sync products yok.
- API ücreti hiçbirinde geçmiyor (ücretsiz olduğu da açıkça yazmıyor).

## 6. Sipariş akışı ve ödeme
- **Printify:** onay Manuel / 1 saat / 24 saat (varsayılan) / belirli saat. **Ödeme sipariş üretime girerken bakiye ya da karttan; mağaza gelirini beklemez.** API'yle oluşturulan siparişte `send_to_production.json` var (test edilmeli).
- **Printful:** "Manually confirm all imported orders" kapatılınca otomatik; cüzdan + düşük bakiyede kart/PayPal auto-recharge. Etsy'ye ürünler genelde taslak gelir; takip senkronu sayfada yazmıyor.
- **Gelato:** onay sonrası kayıtlı karttan.
- **Printify faturalama: AUD/CAD/EUR/GBP/USD — TRY yok.** Premium daima USD. Bakiye yalnız USD, min $10. **Otomatik ödeme yalnız kartla** (PayPal/Payoneer/Google Pay ile otomatik yok); Payoneer'la yüklenen bakiye çekilemez.
- Türk kartı: resmî ifade yok; Printful başarısızlık nedenleri arasında ABD dışı kartlarda sahtecilik önleme engelleri. Türk bankasında internet/yurt dışı kullanım + 3D Secure açılmalı.
- Hesap: Printify ToS'ta sanksiyon listesi yok, "herhangi bir nedenle reddedebiliriz" maddesi var. Gönderim yasak listelerinde Türkiye yok.
- **ABD sales tax:** Printful ve Printify, eyalet izni + resale certificate yoksa satıcıdan sales tax alır. TR'den eyalet izni almak pratikte zor → **vergiyi baz maliyete gömülü kabul et**. Printful AB/UK'de VAT kayıtlı.

## 7. Marka
Printful iç etiket $0,99 / dış $2,49, pack-in ve packing slip; Gelato insert + etiket yalnız Gelato+; Printify Premium'da branding indirimi (neck label/insert detayı doğrulanmadı);
Apliiq özel etikette en iddialı.

## 8. Baskı dosyası
| | Printful | Printify |
|---|---|---|
| Format | PNG, JPEG | JPEG, PNG, SVG |
| DPI | giyim 150 (150–300), kupa/kılıf 300 | 300 önerilir |
| Renk | sRGB, CMYK değil | — |
| Maks | 200 MB, 20.000 px | PNG/JPG 100 MB, SVG 20 MB |
| Tişört alanı | 12x16 in (3600x4800 @300), bazı DTG'de 15x18 in (4500x5400) | 4500x5400 px |
Sık hatalar: düşük çözünürlük, siyah üstüne siyah arka plan (gri dikdörtgen basılır), yarı saydam alanlar, kenar artık pikseli.
Printify düşük çözünürlüklü dosyayı otomatik iyileştiriyor. Gerçek ürün ölçüsü Printful `mockup-generator/printfiles` ucunda.

## Kolun önerisi (öneri)
- **Birincil: Printify** (Free ile başla; Premium ~15–20 sipariş/ay'da kendini öder), provider'ı Monster Digital/SwiftPOD'a kilitle, önce numune sipariş.
- **Yedek: Printful** — kalite-kritik ürünler ya da Printify provider kalitesi kötü çıkarsa.
- **Gelato:** poster/wall art ve AB/UK yerel üretim için; API ve Etsy vergi şikâyeti önce test.

## Tam otomasyon için 8 kritik bulgu
1. Printful'da Etsy/Shopify ürünü API ile oluşturulamaz; Printify'da `products.json` + `publish.json`.
2. Printify publish 200/30 dk → toplu yüklemeyi kuyrukla.
3. Printful mockup yeni mağazada 2/dk; Printify mockup'ları ürünle hazır geliyor.
4. Onay adımı kapatılabiliyor.
5. Ödeme satıcının kartından/bakiyesinden; bakiye bitince siparişler durur → Printify'da kart şart.
6. Printify'da TRY yok, Türk kartı doğrulanmamış → **en büyük operasyonel risk, gerçek test**.
7. ABD sales tax satıcıdan alınıyor → fiyata göm.
8. 429 geri-çekilme ve webhook idempotency tasarımda şart.

## Doğrulanamayan / çelişkili
Printify resmî baz fiyatları; Türk kartı (Printify/Printful/Gelato); Printify branding ve reprint/iade; Printful resmî reprint süreleri; Gelato ürün API'si ve limitleri;
Gelato TR ortağının yurt dışı gönderimi; Printful 3001 fiyatı ($9,25–12,95 arası kaynaklar; birincil API $12,25); Printful kargo (tarihsiz sayfa $4,95 / Mart 2026 ikincil $4,69);
Printify indirim oranı (%20/%33); Monster Digital konumu (Miami/Detroit); Fourthwall ve Inkedjoy (tek affiliate kaynak).

## Kaynaklar (seçme)
printify.com/pricing · developers.printify.com · printify.com/terms-of-service · help.printify.com (4483601124113, 4483625253265, 12203416543505, 4483617936657,
4483601178897, 4483616795281, 22264181985809) · printful.com/pricing · printful.com/shipping · developers.printful.com/docs (v1, v2-beta) ·
api.printful.com/products/71 · printful.com/integrations/etsy · apps.shopify.com (printify, printful, gelato-print-on-demand, gooten, customcat-fulfillment, apliiq) ·
support.gelato.com · prodigi.com/print-api/docs · api.spreadconnect.app/docs · bootstrappingecommerce.com/printful-vs-printify · michaelessek.com · trustpilot.com.
