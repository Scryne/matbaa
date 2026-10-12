---
title: POD araştırması 03 — Türkiye'den kurulum ve para akışı
created: 2026-10-12
modified: 2026-10-13
type: note
status: active
tags: [pod, etsy, shopify, arastirma, odeme, vergi]
---
# 03 — Türkiye'den operasyonel kurulum ve para akışı

`arastirmaci` kolu, erişim 2026-10-12. Etsy sayfaları WebFetch'e 403 verdi; Etsy rakamları arama özetinden ("Etsy özeti").
Vergi/SGK kısmı operasyonel çerçevedir, **mali müşavire teyit ettirilecek**. Sentez: [[00-sentez]].

## Özet
- **Etsy Türkiye'den şirketsiz kurulabiliyor.** TR, Etsy Payments ülkelerinde; para TRY olarak Türk IBAN'a geliyor. PayPal yok.
- **Shopify zor.** Shopify Payments TR'de yok, Stripe TR'de yok. Gerçekçi iki yol: şahıs şirketi + iyzico/PayTR, ya da ABD LLC + Stripe (üçüncü taraf ağ geçidi).
- Kolun önerisi: **önce yalnız Etsy**, Shopify satış kanıtlanınca.
- İşletme sermayesi: POD hemen karttan çeker, Etsy ~14 gün (+rezerv) sonra öder → 300–500 $ tampon (çıkarım).
- Düzenli satış ticari kazanç sayılıyor; şahıs şirketinin asıl sabit yükü muhasebeciden çok **Bağ-Kur primi** olabilir.

## 1. Etsy, Türkiye (Etsy özeti)
- Ödeme işleme: **%6,5 + 14 TRY** (08.07.2024'ten, KDV hariç). Eski kaynaklardaki 3 TRY bayat.
- **Regulatory Operating Fee (TR): %1,67** (22.06.2026'dan; önce %2,27), ürün + kargo üzerinden.
- Listing 0,20 $, transaction %6,5.
- Mağaza para birimi ≠ banka para birimi → **%2,5 kur dönüşüm**. TRY mağaza para birimi seçilebilir mi doğrulanmadı (seçilirse USD maliyetli POD'a karşı kur riski).
- Mevduat: 600 TL altı için 42 TRY ücret, min 50 TRY. TR mevduat sıklığı doğrulanmadı ("bazı satıcılar yalnız haftalık").
- Para bekleme: yeni satıcıda sipariş ~**14 gün** sonra uygun; ilk satış rezerv tetikleyebilir, çoğunda ≤90 gün, tavan 180 gün; Star Seller muaf.
- Kimlik: geçerli ID, banka hesabı adı = yasal ad = vergi bilgisi; doğrulama test mevduatı veya son 6 aylık kaşeli banka belgesi. **Banka ülkesi sonradan değişmiyor** → yeni mağaza gerekir.
- Şirket şartı Etsy kaynaklarında yok.
- "Ships from" kargo profilinin origin country'sinden gelir; Printful ABD profilleri iter (varsayılan "Ships from: United States"). Mağaza yine TR sayılır. Arama/güvene etkisi için kaynak yok.
- Üretim ortağı beyanı gerekli; "14.01.2026 Seller Policy güncellemesiyle AI beyanı" iddiası tek blogdan.

## 2. Shopify, Türkiye
- Shopify Payments 40 ülke listesinde **TR yok** [birincil]. Stripe global listesinde TR yok (Paddle blogunun "Stripe TR'de kullanılabilir" iddiası çelişiyor; birincil kaynak esas).
- **A — Şahıs şirketi + iyzico/PayTR:** iyzico yurt dışı kart ~%3,99 + %2,10 kur çevrimi (tarihsiz, ikincil) ≈ %6; müşteri iyzico sayfasına yönlendirilir; Amex reddi vakası; belge talebi anekdotları. TRY'ye çevrilip hesaba.
- **B — ABD LLC + Stripe:** Shopify Payments yabancı sahipli LLC'de SSN/ITIN istiyor (EIN yetmiyor) → Stripe üçüncü taraf ağ geçidi.
- Elenen: Paddle/Lemon Squeezy (dijital ürün içindir), Shopier (iç pazar), Payoneer (Shopify ağ geçidi değil), 2Checkout (TR bireye açıklık doğrulanmadı).

## 3. ABD LLC (kısa)
- Stripe Atlas 500 $ tek sefer (Delaware, EIN, ilk yıl registered agent), sonra 100 $/yıl. doola Starter 297 $/yıl + eyalet; vergi paketi 1.999 $/yıl.
- Yabancı sahipli tek üyeli LLC → her yıl **Form 5472**, hareket olmasa da; eksik/geç cezası 25.000 $.
- Mercury yabancı kurucuya açık; registered agent adresini iş adresi saymıyor.
- Stripe'ın TR vatandaşının LLC'sine hesap açtığı birincil kaynakla doğrulanmadı.

## 4. POD sağlayıcıya ödeme ve nakit akışı
- Printify kart veya Printify Balance; başarısız ödemede bakiye + "Retry payment".
- **Türk kartı kabulü güvenilir kaynakla doğrulanmadı** → küçük test siparişiyle doğrulanmalı. Printify Pop-Up Store ülkelerinde TR yok (TR'nin hassas ülke olduğuna işaret olabilir).
- Çıkarım: ayda 20 sipariş × ~20 $ ≈ 400 $; 14–30 gün gecikmeyle sürekli 300–500 $ işletme sermayesi.

## 5. Türkiye'de resmî yapı (teyit edilecek)
- Düzenli Etsy satışı ticari kazanç; mükellefiyet gerekiyor (shipentegra, ikincil).
- Şahıs şirketi kuruluş: toplam ~9.500–13.500 TL (noter imza beyanı, vekaletname, açılış), mali mühür ~1.740 TL.
- Aylık muhasebe: 2026 SMMM asgari tarifesi şahıs şirketi tabanı **~3.593 TL/ay** (ikincil).
- **Bağ-Kur 4/b 2026: en düşük ~10.157–11.808 TL/ay** (kaynaklar çelişiyor). 18–29 yaş genç girişimci prim desteği 01.01.2026'da 7566 sayılı Kanun'la kaldırılmış. Öğrenciye özel düzenleme bulunamadı. Kazançtan bağımsız sabit yük → **SGK/müşavirden mutlaka teyit**.
- **Genç girişimci istisnası (GVK mük. 20):** sürüyor; 29 yaş altı, ilk kez mükellef, 3 dönem, 2026 ~400.000 TL. Gelir vergisini kaldırır, Bağ-Kur'u kaldırmaz. E-ticaret kapsamı için özel kaynak yok.
- **Esnaf muafiyeti (GVK 9/10):** üretim şartı var, al-sat dışı → POD'da büyük olasılıkla uygulanmaz (çıkarım). Limit (1,9 / ~1,98 M TL) ve stopaj (%1 / %4) kaynaklarda çelişkili.
- **Mikro ihracat / ETGB / e-ihracat KDV istisnası:** mal fiziksel olarak TR'den çıkmalı → POD'da uygulanması zayıf (çıkarım).
- Önceki not (10-02): 20/B istisnası sosyal içerik + mobil uygulama içindir, e-ticareti kapsamaz.

## 6. Alıcı tarafı vergiler
- **ABD satış vergisi:** Etsy marketplace facilitator olarak her satıcı adına toplayıp öder; satıcıya iş yok.
- **AB KDV:** Etsy AB dışından ≤150 € fiziksel siparişte KDV'yi ödemede alır (IOSS); satıcı Etsy'nin IOSS numarasını kargoya elektronik iletir (POD sağlayıcı entegrasyonu bunu yapıyor olmalı — doğrulanacak). **01.07.2026'dan ≤150 € kolilere kalem başı 3 € sabit gümrük vergisi.**
- **Shopify:** vergiyi satıcı yönetir; IOSS kendiliğinden yok (aracı gerekir); ABD nexus eyalete göre. Printful, yeniden satış sertifikası yoksa kayıtlı eyaletlerde satıcıdan sales tax alır. → Etsy-önce stratejisi vergi yükü açısından da hafif.

## 7. Hesap güvenliği
- VPN/çoklu hesap nedeniyle TR satıcı kapanması için kaynak yok. Mart 2025 genel doğrulama dondurmaları var (TR'ye özgü değil).
- Genel kural (kaynaksız): kayıtta Türk IP/cihaz, ID = banka adı, VPN'le giriş yok, tek mağaza.

## Para akışı (Etsy yolu)
1. Alıcı öder (kart, Apple Pay; PayPal yok).
2. Etsy keser: 0,20 $ listing + %6,5 transaction + %6,5 + 14 TRY işleme + %1,67 ROF ≈ **%14,67 + 14 TRY + 0,20 $** (Offsite Ads ayrı; Etsy ücretlerine KDV doğrulanmadı).
3. Mağaza USD / banka TRY → %2,5 kur.
4. ~14 gün bekleme (+ olası rezerv).
5. TRY olarak Türk IBAN'a (600 TL altı mevduatta 42 TRY).
6. Ters yönde: Printify/Printful sipariş anında karttan USD çeker — nakit satıştan **önce** çıkar.

## Kurulum kontrol listesi
- [ ] Etsy: Türk IBAN, ID = banka adı = yasal ad.
- [ ] Mağaza para birimi kararı (USD + %2,5 / TRY + kur riski).
- [ ] Printify/Printful hesabı + Etsy entegrasyonu; kargo profili origin ABD.
- [ ] Üretim ortağı beyanı (+ AI beyanı).
- [ ] Yurt dışına açık kart; Printify'ın Türk kartını kabulünü test siparişiyle doğrula.
- [ ] 300–500 $ sermaye tamponu.
- [ ] Mali müşavir: şahıs şirketi, Bağ-Kur (öğrenci durumu), genç girişimci, esnaf muafiyeti, POD'un KDV/ihracat statüsü.
- [ ] Shopify sonraya: ağ geçidi (iyzico / LLC + Stripe), IOSS ve ABD nexus planı.

## Çelişkili / doğrulanamayan
- Wise TR alma kısıtı (31.08.2026, önceki not) bu turda doğrulanamadı; vergimerkezi (01.02.2026) Wise'ı TR'de sorunsuz gösteriyor.
- **Payoneer yıllık 29,95 $:** ücret sayfası eşiği 12 ayda **<6.000 $** alım diyor (önceki notumuzdaki "<2.000 $" yanlış olabilir). ABD alıcı hesabı %1 (min 1 $), TRY çekim %1,2–4.
- Payoneer'in ABD hesabı Etsy'ye banka olarak girilebilir mi: kaynaklar çelişiyor (banka ülkesi = mağaza ülkesi kuralı).
- Esnaf muafiyeti limit/stopaj, Bağ-Kur alt sınırı çelişkili.
- Doğrulanmadı: Etsy kurulum ücreti, TR mevduat sıklığı, Etsy ücretlerine KDV, Shopify üçüncü taraf ağ geçidi komisyonu, Printify Türk kartı, Stripe'ın TR sahipli LLC'ye açılışı, shop location etkisi, POD için GİB özelgesi.

## Kaynaklar (seçme)
help.shopify.com/en/manual/payments/shopify-payments/supported-countries · stripe.com/atlas · doola.com/pricing · payoneer.com/legal/fees ·
custombull.com/en/blog/getting-paid-on-etsy-from-turkey · mukellef.co/blog/sahis-sirketi-kurma-maliyeti · kobitime.com/aylik-muhasebeci-ucretleri-2026 ·
vergimerkezi.com.tr/2026-bagkur-primi-ne-kadar · ideasoft.com.tr/evden-eticaret-vergi-muafiyeti · shipentegra.com/blog/sahis-sirketi ·
help.printify.com (4483601909393, 19768094570385) · help.printful.com (4626998446492) · support.printful.com (41396654298769) ·
sdocpa.com/form-5472-foreign-owned-business-guide · crowe.com/uk/news/eu-agrees-fixed-customs-duty-on-small-parcels ·
Etsy (yalnız arama özeti): help.etsy.com 115015710408, 115015628847, 1500011073202, 115015775908, 360058722214, 360000343968, 360000337247; etsy.com/legal/etsy-payments.
