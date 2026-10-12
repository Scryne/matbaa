---
title: POD (Etsy + Shopify) — araştırma sentezi
created: 2026-10-12
modified: 2026-10-13
type: note
status: active
tags: [pod, etsy, shopify, printify, arastirma, fikir, gelir, otomasyon]
---
# Print-on-demand (Etsy + Shopify) — araştırma sentezi

**İstek (Scryne, 2026-10-12):** "Yeni bir para kazanma sistemi; otomasyon olacak, ben bir şey ellemeden para kazanmak hedef.
Shopify ve Etsy'de dropshipping: ürünü ürettirmeden sadece tasarımını koyup pay elde edeceğiz. En detaylı ve profesyonel
bilgileri topla, hafızanı bu fikirle doldur, eksik bırakma. Sonra nasıl devam edeceğimizi konuşuruz."

**Model:** bu klasik dropshipping değil, **print-on-demand (POD)**: biz tasarımı yükleriz; sipariş gelince Printify/Printful gibi bir
sağlayıcı basar ve alıcıya gönderir; aradaki fark bizim. Proje henüz kurulmadı (aşama: fikir). Ad konmadı.

Beş paralel `arastirmaci` kolu, erişim 2026-10-12/13. Kaynaklı ayrıntı:
[[01-platform-kurallari-ve-api]] · [[02-pod-saglayicilari]] · [[03-tr-kurulum-ve-para-akisi]] · [[04-tasarim-ve-otomasyon-hatti]] · [[05-pazar-gercekligi-ve-ekonomi]].
Ortak sınır: Etsy'nin yardım/hukuk sayfaları WebFetch'e 403 verdi, Etsy kuralları resmî sayfanın arama özetinden; Etsy API dokümanı ve OpenAPI spec doğrudan okundu.

---

## 1. Tek paragraf
Etsy, Türkiye'den şirketsiz açılabiliyor ve parayı TRY olarak Türk IBAN'ına ödüyor. Printify'ın API'si tasarımı ürüne çevirip Etsy'ye
yayınlıyor; sipariş otomatik basılıp gönderiliyor, takip numarası Etsy'ye dönüyor. Yani **tasarım → listeleme → sipariş → kargo zinciri
büyük ölçüde otomatikleşebilir.** Otomatikleşemeyen dört şey var: Etsy'de **müşteri mesajları** (API yok), **mağaza açılışı ve kimlik**
(bir kez), **üretim ortağının Etsy'ye tanıtılması** (bir kez) ve **kalite/IP kontrolü** (otomatik kapı var, güvenilir değil; insan örneklemesi
gerekiyor). Shopify Türkiye'den zor: Shopify Payments ve Stripe yok, mağazaya trafik reklamla gelir ve reklamın sipariş başı maliyeti kârı
aşıyor. Pazar gerçeği: Etsy'de ortalama aktif satıcı ayda ~$156 ciro yapıyor; yeni bir POD mağazası için 12. ayda aylık $100–600 brüt makul bant,
kâr garantisiz. Asıl sürpriz maliyet Türkiye tarafında: düzenli satış ticari kazanç sayılıyor ve şahıs şirketinin **Bağ-Kur primi (~10–12 bin TL/ay)**
küçük bir mağazanın tüm kârını yiyebilir — müşavire sorulması gereken bir numaralı soru.

## 2. Zincir: ne otomatik, ne elle
| Adım | Otomatik mi | Nasıl / neden |
|---|---|---|
| Niş/trend bulma | **Yarı** | Google Trends API (alpha, başvurulu), Pinterest Trends (partner odaklı). Etsy niş araçlarının (eRank, Alura, EverBee, Marmalead) API'si yok; Etsy autocomplete scraping'i ToS riski. Haftalık insan onayı mantıklı |
| Tasarım üretimi | Evet | Recraft (vektör SVG, ~$0,08), Ideogram 4.0 (tipografi + şeffaf, ~$0,03–0,10), gpt-image-2.5 (şeffaf belgeli). Midjourney'in API'si yok, ToS otomasyonu yasaklıyor → hatta yok |
| Baskıya hazırlama | Evet | 4500x5400 px @300 DPI (tişört), sRGB PNG; upscale (Topaz ~$0,08–0,16, Recraft Crisp $0,004), arka plan (rembg/BiRefNet yerelde), **yarı saydam piksel = beyaz kutu/halo** → alfa eşiği şart |
| Kalite + IP kapısı | **Yarı** | OCR (yazım), vision LLM rubriği, alfa/kontrast/güvenli alan kontrolleri otomatik; marka/karakter tespiti güvenilir değil → riskli sınıf insana |
| Başlık, 13 etiket, açıklama | Evet | LLM; Etsy: başlık kısa ve ürün adıyla başlar, 13 farklı çok kelimeli etiket, öznitelikler etiket gibi çalışır |
| Ürün + mockup | Evet | Printify `products.json` → mockup'lar ürünle ücretsiz gelir |
| Etsy'ye yayın | Evet | Printify `publish.json` (200 istek/30 dk). Sonra kendi Etsy Seller App'imizle `updateListing`: `production_partner_ids` + AI beyanı açıklamada + `state=active` |
| Üretim ortağını Etsy'ye tanıtma | **Elle, bir kez** | API'de yalnız GET var; Shop Manager'dan eklenir, ID'si API'yle ilanlara bağlanır |
| Sipariş → üretim → kargo | Evet | Printify Etsy siparişini çeker; onay 1 saat/24 saat/belirli saat; karttan USD çeker; takip Etsy'ye döner. Etsy'de SKU/varyant elle düzenlenirse eşleme bozulur |
| Müşteri mesajları | **Hayır** | Etsy'de conversations API yok (Etsy'nin resmî hesabı, 14.07.2026). Var olan: satış sonrası otomatik mesaj, tatil otomatik yanıtı. Yanıt oranı aramaya ve Star Seller'a giriyor → günde birkaç dakika insan |
| İade/reprint/hasar | **İnsan onaylı** | Printify/Printful yanlış beden ve cayma iadesi yapmaz; hasar/üretim hatasında 30 gün içinde reprint |
| Mağaza açılışı, kimlik, banka | **Elle, bir kez** | ID = banka adı = yasal ad; banka ülkesi sonradan değişmiyor |
| Numune siparişi | **Elle, birkaç kez** | Her ürün tipi için; 2024'teki tam otomatik mağaza anekdotu numune vermediği için kötü baskıya düştü |

**Gerçekçi tarif:** "ben hiç ellemeden" değil, **"kurulumdan sonra günde ~10 dakika"**: mesajlara bakmak, haftalık niş/tasarım onayı,
arada bir iade kararı. Bu, Otomat'ın 10-02 araştırmasındaki ölçülmüş dersle aynı: sıfır emek kol yok, kol başına periyodik onarım var.

## 3. Para
### Birim ekonomisi (tişört, $24,99 + $4,99 kargo = $29,98)
| Senaryo | ABD tarzı ücret + Printify | Türkiye'ye özgü kalemlerin hepsi geçerliyse |
|---|---|---|
| Reklamsız | **$13,19 net (%44)** | $10,02 (%33) |
| Offsite Ads %15 (Etsy'nin dış reklamından gelen satış) | $8,69 (%29) | $4,76 (%16) |
| Etsy Ads, ROAS 3x | $3,20 | ~$0 |
| Başabaş Etsy Ads ROAS | 2,3x | 3,0x |
Kupa ($24,98): reklamsız $10,16 / TR $7,50. Kişiselleştirilmiş sweatshirt ($50,98) dolar olarak en iyisi (~$15,7 net).
Shopify'da aynı tişört: başabaş reklam maliyeti/sipariş $12–15, piyasa ortalaması $17–54 → **ilk satış zarar**.

### Etsy ücretleri (TR satıcı)
$0,20 listeleme · %6,5 işlem · %6,5 + 14 TRY ödeme işleme · regulatory fee %1,67 (kaynaklar %2,24–2,27 de diyor) · USD mağaza/TRY banka ise %2,5 kur ·
Etsy ücretlerine KDV (oran doğrulanmadı) · Offsite Ads <$10k/yıl %15 (kapatılabilir), ≥$10k %12 (zorunlu), tavan $100 · kurulum ücreti $0–29 (TR değeri bilinmiyor).
**Toplam ≈ %17–18 + 14 TRY + $0,20 (+ KDV).** ABD satış vergisi ve AB KDV'sini (≤150 €) Etsy kendisi topluyor.

### Para akışı
Alıcı kartla öder → Etsy keser → ~14 gün bekleme (yeni mağazada rezerv olabilir, çoğu ≤90 gün, Star Seller muaf) → **TRY olarak Türk IBAN'a**.
Ters yönde: Printify sipariş anında **karttan USD** çeker (TRY yok; otomatik ödeme yalnız kartla). Nakit satıştan önce çıkar →
**300–500 $ işletme sermayesi tamponu**. Printify'ın Türk kartını kabul ettiği hiçbir resmî kaynakta yok → ilk test.

### Başlangıç bütçesi (Etsy-only)
Kurulum $0–29 · 100 listing $20 (4 ayda yenilenir) · numune ~$60–120 · Printify Free (Premium $39/ay ya da $299/yıl, ~15–20 sipariş/ay'da kendini öder) ·
tasarım API'si tasarım başına ~$0,20–0,50 · Etsy Ads testi $15–45. **İlk 3 ay ~$100–250; gerçekçi 6 ay $300–600** (+ işletme sermayesi).
Shopify + reklam ile anlamlı test $1.000–3.000.

### Türkiye'de resmî yapı (operasyonel; mali müşavire teyit ettirilecek)
- Etsy şirket istemiyor; vergi Etsy'den bağımsız. Düzenli satış ticari kazanç → mükellefiyet gerekiyor (ikincil kaynak).
- Şahıs şirketi kuruluş ~9.500–13.500 TL; muhasebe ~3.600 TL/ay'dan; **Bağ-Kur en düşük ~10.157–11.808 TL/ay**, kazançtan bağımsız.
  18–29 yaş Bağ-Kur genç girişimci prim desteği 01.01.2026'da kalkmış. Öğrenci durumuna özel düzenleme bulunamadı.
- Genç girişimci kazanç istisnası (29 yaş altı, 3 yıl, 2026 ~400.000 TL) gelir vergisini kaldırır, Bağ-Kur'u kaldırmaz.
- Esnaf muafiyeti üretim şartı istiyor → POD'a büyük olasılıkla uymuyor. Mikro ihracat/ETGB/e-ihracat: mal Türkiye'den çıkmadığı için zayıf.
- 20/B (YouTube/Play istisnası) e-ticareti kapsamıyor (10-02 notu).
- **Sonuç:** aylık sabit yük ~14–15 bin TL (~$300) olabilir. Bu, 12. ay beklenti bandının üstünde. Mükellefiyetin ne zaman zorunlu olduğu,
  öğrenciyken Bağ-Kur durumu ve ilk ayların nasıl yürütüleceği **projeye başlamadan müşavire sorulmalı.**

## 4. Pazar gerçekliği
- **Etsy:** 2025 marketplace cirosu $10,46 milyar (−%4); Q2 2026 +%7,5; aktif satıcı 7M zirveden 5,6M'ye indi, alıcı ~87M yatay.
  Take rate %25,9 ve artış Etsy Ads'ten → reklam baskısı artıyor (10-K ve Q2'26 hissedar mektubu).
- **Ortalama satıcı ~$1.868/yıl (~$156/ay) ciro**; medyan bunun altında. Yaygın "medyan $574/ay" iddiası aritmetik olarak imkânsız.
- **Etsy'nin yönü:** "handmade'e yaslan", Star Seller "distinctive inventory"yi ödüllendirecek, arama tazelik sinyali ekledi.
  Creativity Standards 10.06.2025'te sıkılaştı: şablon/clip-art/hazır grafik ticari lisansla bile risk. POD yasak değil:
  "Designed by" + her ilanda üretim ortağı. AI yasak değil: satıcının kendi prompt'u + **ilan açıklamasında AI beyanı zorunlu**.
- **Kişiselleştirme:** Etsy cirosunun ~%30'u custom/made-to-order; alıcıların %31'i kişiselleştirilmiş ürün arıyor (10-K).
- **Dönüşüm:** Etsy genel %2,5–3,5 (model tahmini). İlk satış: bağımsız veri yok; tek AI deneyi 30 listing → ilk satış 22. gün, ayda 6 satış, $73.
  "100 listing kuralı"nın kanıtı yok; listing sayısı–satış ilişkisi zayıf.
- **Sezon:** Q4 yıllık cironun ~%30'u. Bugün (13 Ekim) açılan mağazanın Noel penceresi ~8 hafta ve yorumu yok → Q4 öğrenme ve ilk yorum
  içindir, gelir için değil. Sonraki hedefler: Sevgililer Günü (Aralık–Ocak'ta listele), Anneler Günü (Şubat–Mart). Ocak–Mart zayıf aylar.
  Printful 2026 ABD son sipariş: 11 Aralık (standart).
- **Rekabet:** Amazon Haziran 2026'da Merch on Demand'e alıcı tarafı AI tasarım ekledi; "jenerik AI mockup'lı mağazalar sıfır satış" anekdotu yaygın.
  ABD de minimis muafiyetinin 29.08.2025'te kalkması ABD'de basılan POD'u Çin'den gelene karşı korur (çıkarım).

### Beklenti bandı (kolun yargısı; yayımlanmış dağılım yok)
| Ufuk | Sipariş | Brüt | Net (araç, numune, reklam dahil; Bağ-Kur hariç) |
|---|---|---|---|
| 3 ay | 0–10, tipik 0–5 | $0–300 | −$150 / +$50 |
| 6 ay | 5–50 | $150–1.500 | −$100 / +$400 |
| 12 ay | aylık 3–25 | aylık $100–600 | kâr mümkün, garantisiz |

## 5. Riskler (öncelik sırası)
1. **Türkiye sabit maliyeti** (Bağ-Kur + muhasebe) beklenen kârı aşabilir.
2. **Uzun süre sıfır satış** ve ücret yığını (offsite, Etsy Ads baskısı, TR kalemleri).
3. **Etsy politika/hesap riski:** yeni mağaza rezervi, Creativity Standards, AI beyanı, toplu listeleme; askıda fon tutulur, itiraz sınırlı.
   Otomat dersi: **çoğaltma = ceza** — aynı motorla yüzlerce benzer listing basmak, YouTube'un "inauthentic content" dalgasının Etsy karşılığına çarpar.
4. **IP şikâyeti:** sabit eşik yok, tekrarlayan bildirim → mağaza kapanır, yeni mağaza "ilişkili hesap" diye reddedilebilir. Ünlü karakter/marka/slogan kaçağı bir kez bile pahalı.
5. **Ödeme altyapısı:** Printify'ın Türk kartı kabulü doğrulanmadı; TRY yok; çift kur kaybı.
6. **Platform bağımlılığı:** Etsy arama değişiklikleri, gösterim düşüşü anekdotları, Commercial API erişiminin aylarca beklemesi.
7. **Operasyon:** POD gecikmesi/hatalı baskı → kötü yorum → yeni mağazada orantısız hasar.

## 6. Shopify'ın yeri
- Shopify Payments ve Stripe Türkiye'de yok. Yollar: (A) şahıs şirketi + iyzico/PayTR (yurt dışı kart ~%6, iyzico'nun dropshipping'i reddettiği 2023 anekdotu),
  (B) ABD LLC + Stripe (Atlas $500 + $100/yıl, her yıl Form 5472, eksikse $25.000 ceza). Shopify ayrıca 3. taraf ödemede +%2 (Basic) alır.
- Plan: Basic $27/ay ($19 yıllık), 3 gün deneme + 3 ay $1. Admin GraphQL API otomasyona uygun; yeni uygulamalar Dev Dashboard'da, token 24 saat.
- Shopify'ın kendi trafiği yok; Meta reklamında sipariş başı maliyet ($17–54) başabaşın ($12–15) üstünde.
- **Önerim:** Shopify'ı ilk faza koyma. Etsy'de satan tasarımlar ve ödeme yolu kanıtlanınca, aynı Printify kataloğuyla ikinci kanal olarak ekle.
  Karar Scryne'ın: o "Shopify ve Etsy" dedi.

## 7. Alternatif ve ek kanallar
- **Redbubble / TeePublic:** sadece tasarım yüklenir, üretim + müşteri hizmeti + trafik onlarda, ödeme Payoneer'la (10-02). API yok, toplu düşük kalite incelemeye girer. "Hiç ellememe"ye en yakın model, ama royalty düşük.
- **Amazon Merch on Demand:** 01.06.2026'dan kademeli royalty ($19,99 tişörtte $2,44–5,27); manuel başvuru; TR uygunluğu doğrulanmadı.
- **Spring (Teespring) kapanıyor** (15.10.2026). Society6 durumu belirsiz. Zazzle %5 standart royalty. Spreadshirt TR'den kapalı (10-02).
- **Etsy dijital ürün (printable, SVG, sticker sheet):** kargo/iade/POD maliyeti yok, ücret yükü $5'lık üründe %18,5. Jenerik clip art ve Notion şablonu 2026'da soğuyor.
  etsy-engine (açık kaynak, MIT) bu modelde trend → tasarım → mockup → SEO → Etsy taslağı zincirini kurmuş.

## 8. Önerim (karar Scryne'da)
1. **Etsy-önce, Printify ile.** Shopify sonraki faz.
2. **Ürün tipi:** düz grafik ve tipografik tişört/sweatshirt (otomasyona en uygun, vektör yol ucuz ve temiz baskı), kupa ikincil.
   Kişiselleştirme (isim/tarih) en büyük farklılaştırıcı: Etsy cirosunun %30'u. Etsy `order.paid` webhook'u → kişiye özel tasarım → Printify API siparişi
   zinciri teknik olarak kurulabilir; sipariş başına iş yükünü artırır, spike ister.
3. **Niş az ama derin:** birkaç net alıcı grubu, her birinde özgün seri. Toplu jenerik listing yok.
4. **İnsan kapıları kalsın:** haftalık niş/tasarım onayı, riskli IP sınıfı, mesajlar, iadeler.
5. **Sıra:** önce para ve hesap, sonra kod. Otomat dersi: **ödeme yolu üründen önce.**

## 9. Spike adayları (finalizasyondan önce)
| # | Soru | Nasıl |
|---|---|---|
| S1 | Mükellefiyet ve Bağ-Kur (öğrenci) gerçek maliyeti ne? | Mali müşavir, tek görüşme |
| S2 | Etsy mağazası TR'den açılıyor mu, kurulum ücreti, kimlik ve banka doğrulaması | Gerçek açılış (tek ilanla) |
| S3 | Printify Türk kartını kabul ediyor mu; numune kalitesi | Hesap + 2 tişört + 1 kupa numune siparişi |
| S4 | Etsy Seller App onayı; API'yle `production_partner_ids` + aktifleştirme; Printify publish → Etsy akışı | Uygulama kaydı + 1 test listing |
| S5 | Tasarım hattı kalitesi | 10 tasarım (vektör + tipografi), otomatik kapılar, numuneyle baskı kontrolü |
| S6 | Kalite/IP kapısı | Gerekirse TypeSafe (Jev) ile "riskli içerik mi" sınıflandırması — global kural gereği önce `ts.py` spike'ı |

## 10. Açık sorular (Scryne'a)
- Etsy-önce mi, ikisi aynı anda mı?
- Bütçe: ilk 6 ay için ne kadar ayrılabilir (bu işte sermaye şart: numune + işletme tamponu)?
- Mükellefiyet: müşavire danışma kararı.
- Niş fikri ya da ilgi alanı var mı, yoksa niş seçimini veri mi yapsın?
- Kişiselleştirme ilk fazda mı?
- Hesaplar kimin adına (Etsy kimliği = banka hesabı adı)?

## Bu araştırmadan önceki notlarla ilişki
- 10-02 gelir kolları sentezi (`Projeler\Otomat\docs\arastirma\01-gelir-kollari-sentez.md`): Etsy "TRY IBAN, ikincil" ve POD "Payoneer" olarak geçiyordu.
  Bu tur ikisini de derinleştirdi. **Düzeltme:** Payoneer'in $29,95 yıllık ücreti için eşik ücret sayfasında 12 ayda <$6.000 alım (10-02 notu <$2.000 diyordu).
- Yeni proje Otomat'ın yapısını kopyalamaz (Kurallar, 2026-10-06); oradan yalnız adıyla anılan ölçülmüş dersler alınır: sıfır emek yok, çoğaltma = ceza, ödeme yolu üründen önce.
