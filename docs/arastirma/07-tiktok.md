---
proje: Matbaa
created: 2026-10-15
type: arastirma
---
# 07 — TikTok: ABD erişimi, link, API, format (2026-10-15)

K-34'ün kaynağı. Birincil kaynak (TikTok'un kendi sayfaları) öncelikli; satıcı çıkarı olan ikincil kaynaklar ayrıca işaretli.
TikTok yardım sayfalarının çoğu JS ile yüklendiği için bazı bulgular arama özetinden; o yüzden "doğrulanamadı" notları var.

## Karar belirleyen bulgular

1. **ABD erişimi belirsiz.** TikTok'un öneri açıklaması ülke ayarını ve "izleyici ile yaratıcı aynı ülkede mi" sinyalini düşük
   ağırlıklı sayıyor; SIM/IP/hashtag listede yok
   (https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you/). Hesap ülkesi kayıtta SIM ya da IP'den belirleniyor
   (https://www.tiktok.com/support/faq_detail?id=7543896418571033093, arama özeti). ABD ortak girişimi (Ocak 2026) ABD dışı içeriğin
   ABD akışındaki payı hakkında açıklama yapmadı
   (https://newsroom.tiktok.com/announcement-from-the-new-tiktok-usds-joint-venture-llc?lang=en). "Dağıtım yerelleşir, ABD SIM/proxy
   kullan" diyenler hesap/araç satan firmalar (viral.app 2026-10-02, TokPortal 2026-03-04): taraflı; VPN'i onlar da "ban riski"
   sayıyor. **Sonuç:** hile yok, ölçülür (ilk 10 videonun ülke dağılımı).
2. **Profil linki:** 1.000 takipçi ya da kayıtlı işletme hesabı (https://www.tiktok.com/support/faq_detail?id=7581821550328896012,
   arama özeti; bir blog eşiğin kalktığını iddia ediyor, çelişkili). Etsy linkini yasaklayan metin bulunamadı. İşletme hesabında
   müzik ticari kütüphaneyle (CML) sınırlı (ikincil: Soundstripe, Stan Store 2026-09-16).
3. **API:** Onaysız istemcide Direct Post yalnız `SELF_ONLY`; denetimde "kendi hesabını yöneten yükleme aracı" kabul edilmiyor
   (https://developers.tiktok.com/doc/content-sharing-guidelines). Upload (taslak) modunun onaysız çalışıp çalışmadığı resmî
   sayfada yazmıyor. **Sonuç:** elle yükleme (TikTok Studio), API yok.
4. **Format:** video, fotoğraf karuselinden gönderi başına ~5,6 kat izlenme, ~7,8 kat etkileşim (Metricool, 2,3 milyon gönderi,
   Ocak-Şubat 2025→2026; https://www.netinfluencer.com/tiktok-content-volume-up-nearly-80-percent-in-early-2026-as-per-post-performance-declined-report-finds/).
   Buffer (45M+ gönderi, 2026): video medyan etkileşim %3,39, karusel %1,92 (https://buffer.com/resources/data-best-content-format-social-media/).
   "Gift idea", POV gibi POD'a özgü formatların satış etkisine dair vaka/veri bulunamadı.
5. **Zamanlama:** TikTok Studio masaüstünde 15 dk – 10 gün ileri (ikincil: Hootsuite). Studio'da karusel ve masaüstünde ses ekleme
   konusunda kaynaklar çelişkili.
6. **Ücretli:** hedeflenebilir ülkeler Ads Manager hesabının kayıt ülkesine bağlı; Türkiye kayıtlı hesapla ABD hedeflemesi
   doğrulanamadı (https://ads.tiktok.com/help/article/placements-available-locations). Günlük bütçe tabanı kampanya $50, reklam
   grubu $20 (https://ads.tiktok.com/help/article/budget).

## Sıklık ve hashtag

Karşılaştırmalı veri yok. Etsy Seller Handbook ilk 1-2 hafta günde en az bir video öneriyor (öneri, kanıt değil). Hashtag için
blogların ortak görüşü 3-5 ilgili etiket; erişimi artırmaktan çok kategorize ediyor (iddia). Uygulama: günde bir video, 4-6 hashtag.
