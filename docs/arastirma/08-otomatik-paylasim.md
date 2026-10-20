---
proje: Matbaa
created: 2026-10-20
type: arastirma
---
# 08 — Platformlara otomatik paylaşım: resmî yollar, aracılar, resmî olmayan araçlar (2026-10-20)

Soru (Scryne): mağazadaki ürünleri TikTok, Pinterest, Instagram ve diğer platformlara insan dokunmadan atan bir sistem kurulabilir mi?
Resmî olmayan API'ler (Apify, RapidAPI, public-apis, GitHub) de soruldu. İki ayrı araştırma (arastirmaci), birincil kaynak öncelikli.

Tetikleyen veri (2026-10-20): TikTok'ta 8 video 516 izlenme, 49 takipçi; en çok izlenen 4 videonun (501 izlenme) tasarımları Etsy'de
toplam 1 görüntülenme aldı. Etsy linki 1.000 takipçide açılıyor; bio'daki adres tıklanmıyor. Mağaza toplamı 59 ilan, 9 görüntülenme.

## Karar belirleyen bulgular

| Platform | Yol | Herkese açık otomatik yayın | Şart | Maliyet |
|---|---|---|---|---|
| Instagram Reels | Kendi Meta uygulamamız (Instagram API with Instagram Login) | Evet | Profesyonel hesap; video **herkese açık URL**'den alınır | 0 $ |
| Facebook Sayfası Reels | Graph API `/{page}/video_reels` | Evet | Sayfa token'ı; dosya doğrudan yüklenebilir; 24 saatte 30 | 0 $ |
| YouTube Shorts | Data API `videos.insert` | Büyük olasılıkla (aşağıda çelişki) | OAuth uygulaması "In production" (Testing'de token 7 günde ölür) | 0 $ |
| TikTok | Kendi uygulamamız | **Hayır**: denetimsiz istemci yalnız SELF_ONLY | — | — |
| TikTok | Onaylı aracı: Zernio (eski Late), Buffer, Upload-Post | Evet | Aracının kendi denetlenmiş uygulaması | 0–24 $ |
| Pinterest | Kendi uygulamamız | **Hayır**: trial erişimde pin yalnız sahibine görünür | — | — |
| Pinterest | Onaylı aracı (aynı üçü) ya da mevcut CSV | Evet | board_id | 0 $ |

- **Meta:** yalnız kendi hesabına yayın yapan uygulamaya Standard Access yeter; App Review ve Business Verification başkasının
  hesabına hizmet eden uygulama içindir ([overview](https://developers.facebook.com/documentation/instagram-platform/overview),
  [access levels](https://developers.facebook.com/docs/graph-api/overview/access-levels)). Token 60 gün, `refresh_access_token` ile
  yenilenir. IG günlük yayın limiti dokümanda hem 100 hem 50 yazıyor; gerçeği `content_publishing_limit` verir.
  "Development modu + Tester rolüyle App Review'suz yayın" birincil sayfada açık yazmıyor (çıkarım), ilk testte doğrulanır.
- **Aracılar (fiyat sayfaları, 2026-10-20):** Zernio ilk 2 hesap ücretsiz, sonrası hesap başı 6 $, gönderi sınırsız, API her planda;
  TikTok yeni bağlantıda yalnız public ([fiyat](https://zernio.com/pricing), [TikTok](https://docs.zernio.com/platforms/tiktok)).
  Buffer ücretsiz 3 kanal, kanal başı 10 zamanlı gönderi, API dahil ([fiyat](https://buffer.com/pricing)). Upload-Post TikTok'u
  ücretsizde vermiyor, Basic 24 $/ay. Postiz self-host'ta kendi TikTok/Pinterest onayın gerekir (aynı duvar). Ayrshare 149 $,
  Metricool API'si 53 $, Blotato 29 $: bütçe dışı.
- **TikTok'un üçüncü taraf gönderi kuralları** ([guidelines](https://developers.tiktok.com/doc/content-sharing-guidelines)): günlük
  ~15 gönderi tavanı, filigran yok, AI içerik için `is_aigc`. Buffer günde 1–3 TikTok öneriyor.
- **Tekrar paylaşım:** Instagram başka uygulamanın logosunu taşıyan içeriği önermiyor; bizim videolar filigransız, sorun yok.
  Pinterest yinelenen pine karşı (başlık/açıklama/URL kıyaslanır): `b8c17ab`'deki başlık döndürme sürer.

## Resmî olmayan araçlar: elendi

| Araç | Yöntem | Bulgu |
|---|---|---|
| Apify `tiktok-poster` | Tarayıcı otomasyonu, çerez/şifre, residential proxy şart | 25 kullanıcı, son 30 günde %79 başarı |
| Apify `instagram-poster`, `pinterest-poster` | Aynı | Yalnız görsel (Reels/video yok), 14–21 kullanıcı |
| instagrapi | Instagram'ın özel mobil API'si, şifre/oturum | Ekim 2026'da `challenge_required` döngüsü ve askıya alma vakası ([#2890](https://github.com/subzeroid/instagrapi/issues/2890)); README "üretimde kırılgan" |
| tiktok-uploader, TiktokAutoUploader | Selenium/Playwright, çerez | Captcha kırılmaları; README'leri ban riskini kendileri yazıyor |
| RapidAPI | — | Paylaşım yapan ilan yok, yalnız okuma/indirme |
| public-apis | — | Paylaşım yapan kayıt bulunamadı |

TikTok Topluluk Kuralları (yürürlük 2026-09-24) ve Hizmet Şartları sistemleri atlatan otomasyonu ve şifrenin üçüncü kişiye verilmesini
yasaklıyor; Pinterest şartları izinsiz otomatik erişimi ve şifre paylaşımını yasaklıyor. Hesaplar tek trafik kaynağımız olduğu için
kısıtlanma riski operasyonel olarak kabul edilmez: bu yol kullanılmaz.

## Açık noktalar (ilk testte doğrulanacak)

- Zernio ücretsiz katmanında TikTok gerçekten public yayınlıyor mu; Türkiye'den hesap bağlama engeli var mı.
- IG için video URL'si: Zernio'nun medya adresi kullanılabilir mi, yoksa ücretsiz bir depolama (ör. Cloudflare R2) mı gerekir.
- YouTube: resmî `videos.insert` sayfası (2026-10-20) unverified projedeki yüklemelerin private'a kilitlenmediğini söylüyor; eski
  2020 notu ve satıcı rehberleri kilidi anlatıyor. Tek test yüklemesiyle doğrulanır.

## Sonuç (K-38, aynı gün)

Üçüncü araştırma (Zernio API dokümanı) Zernio'nun Instagram Reels, Facebook Reels ve YouTube Shorts'u da desteklediğini, medya
yüklemeyi (presign) ve sunucu tarafı zamanlamayı verdiğini gösterdi. Aşağıdaki plandaki "Meta API'si bizde" yolu bu yüzden
uygulanmadı: tek entegrasyon, Scryne'da Meta/Google geliştirici uygulaması yok, bilgisayar kapalıyken de yayın. Bedeli beş hesapta
18 $/ay (ilk 2 hesap ücretsiz). Uygulama: `paylasim.py`, `entegrasyon/zernio.py`, `pinterest.zernio_gonder`.

## İlk plan (Zernio'nun tam kapsamı öğrenilmeden önce)

Hedef: Scryne'ın günlük işi sıfır; tek seferlik iş yalnız hesap açma ve bağlama.

| Adım | Ne | Kim | Maliyet |
|---|---|---|---|
| 1 | Video üretimi yeniden açılır: çizimli tasarımlar, tutan kanca formatı (baba/balık 217–125 izlenme); platforma göre açıklama/hashtag | Aria | 0 |
| 2 | Pinterest: kalan 35 ilanın pinleri (CSV, sonra adım 4'teki aracıya geçer) | Aria; Scryne CSV yükler | 0 |
| 3 | Instagram profesyonel hesap + Facebook sayfası + Meta geliştirici uygulaması; `paylasim.py` IG ve FB Reels'i API'yle basar, ilk video elle denetlenir | Scryne hesapları açar, Aria kodlar | 0 |
| 4 | Zernio: TikTok + Pinterest bağlanır (ücretsiz 2 hesap); günlük koşu TikTok'a 1–2, Pinterest'e 6 gönderi; AI insanlı videoda `is_aigc` | Scryne bağlar, Aria kodlar | 0 (yedek: Buffer ücretsiz) |
| 5 | Ölçüm: Etsy → Stats → Traffic sources, platform başına; 2 hafta Etsy'ye ziyaret getirmeyen kanal kapanır | Aria | 0 |
| — | YouTube Shorts: Shorts açıklamasındaki link tıklanmıyor; IG tutarsa eklenir | — | 0 |
