---
proje: Matbaa
created: 2026-10-13
type: roadmap
status: aktif
---
# Matbaa — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı / ⛔ Engelli.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 0 | Hesaplar ve para (Scryne) | ✅ Tamamlandı | Etsy mağazası açık (kimlik + banka doğrulandı); Printify hesabı + kart eklendi; Printify token + Etsy Seller App anahtarı `.env`'de |
| 1 | İskelet ve sağlık | ✅ Tamamlandı | Private repo GitHub'da; CI (ruff + pytest) varsayılan dalda yeşil; `.github/dependabot.yml`; model kimlikleri `config/modeller.toml`'da; `.env.example`; SQLite şeması + durum makinesi testli |
| 2 | Tasarım motoru v1 | ✅ Tamamlandı | En az 6 şablon, 20+ OFL font, çeşitlilik kuralı; 3 niş × 10 ifade → 30 tasarımın hepsi kapılardan geçiyor ve göz kontrolünde 30/30 yayınlanabilir; mutasyon testleri yeşil |
| 3 | İfade üretimi + IP kapısı | ✅ Tamamlandı | Niş kartları `config/nisler.toml`'da; Claude ile niş başına 30 aday → USPTO + Jev kapısı; 90 adayın kapı kayıtları SQLite'ta; Aria'nın kör örneklemesinde (30 temiz ifade) riskli kaçak 0; USPTO verisi 35 günlük tazelik kontrolüyle |
| 4 | İlan metni | ✅ Tamamlandı | Başlık, 13 etiket (≤ 20 karakter), açıklama (AI beyanı + üretim ortağı + beden/bakım), öznitelikler; Etsy kural doğrulayıcı testli; 30 ilan metni doğrulayıcıdan geçiyor |
| 5 | Onay paneli | ✅ Tamamlandı | Yerel panel: tasarım önizleme (koyu/açık kumaş), ifade, kapı nedenleri, ilan metni; onayla/reddet/düzelt durum makinesine yazıyor; 30 tasarımlık kuyruk 10 dakikada bitirilebiliyor (Scryne'ın ilk kullanımı) |
| 6 | Printify entegrasyonu | ✅ Tamamlandı | Faz 0 sonrası: görsel yükle → 1717/18000 ürün (kilitli sağlayıcı, renkler, varyant fiyatları) → mockup; Etsy'ye publish; 429/hata yeniden denemesi; gerçek hesapta 3 ürün oluşturuldu ve Etsy'de taslak göründü |
| 7 | Etsy entegrasyonu | 🔄 Devam Ediyor | Seller App OAuth (refresh token yenileme); `production_partner_ids` + `state=active`; günde ≤ 5 tavanı; receipts + takip okuma; gerçek mağazada 3 ilan aktif ve kurallara uygun |
| 8 | Fiyat ve kâr defteri | 🔄 Devam Ediyor | Fiyatlar `config/`'te; sipariş başına gerçek net (Etsy TR ücretleri + Printify maliyeti + kur) hesaplanıyor; aylık özet; harcama tavanları kodla korunuyor |
| 9 | Zamanlama ve izleme | 🔄 Devam Ediyor | Günlük Windows görevi uçtan uca koşuyor; takip numarası 5 iş gününde düşmeyen sipariş için alarm; haftalık rapor (ilan, görüntülenme, satış, net); USPTO aylık yenileme görevi |
| 10 | Gerçek kullanım (v1) | ⏳ Bekliyor | 30 ilan Scryne onayıyla canlı; ilk gerçek siparişte Etsy → Printify → takip zinciri elle dokunulmadan çalıştı (ya da 4 hafta dolup v1 "30 ilan canlı" ile kapandı); bulgular roadmap'e işlendi |
| 11 | Kişiselleştirme — isimli süs (K-31), Class of 2027 Ocak'ta | 🔄 Devam Ediyor | İsimli süs ilanları uygun tasarımlara otomatik açılıyor; ilk gerçek isimli sipariş insansız açıldı, doğru isim ve varyantla basıldı (alıcı şikâyeti yok), takip Etsy'ye yazıldı; Class of 2027 Ocak'ta aynı altyapıyla (K-20: test siparişi yok, ilk gerçek sipariş doğrular) |
| 12 | Shopify (koşullu) | ⏳ Bekliyor | Etsy'de ≥ 30 satış ve TR ödeme yolu (iyzico ya da LLC) netleştiyse: aynı Printify kataloğu Shopify'a; ilk sipariş zinciri çalıştı |
| 13 | Performansa göre üretim | 🔄 Devam Ediyor | Günlük üretim niş seçimini görüntülenme/favori/satış verisinden yapıyor (ölü niş kısılır, satan niş büyür); satan ifadenin benzerleri üretiliyor; fiyat testi satış verisiyle; mağaza açılmadan sahte veriyle testli, açıldıktan 30 gün sonra raporda niş dağılımı veriyle değişmiş |
| 14 | Kupa (ikinci ürün ailesi, koşullu) | ⏳ Bekliyor | İlk 30 gün verisinde ≥ 1 satış: tasarım motoru yatay kupa yerleşimi üretiyor (kapılardan geçiyor), satan tasarımlar önce kupaya da açılıyor; net > 0 fiyatla |
| 15 | Niş radarı (koşullu) | 🔄 Devam Ediyor | Faz 13 çalışınca: Etsy arama önerileri + mevsim takviminden yükselen hobi/meslek nişleri aday listesi; marka kapısından geçen niş kartı otomatik taslaklanıyor, ilk 2 yeni niş canlı |
| 16 | Yılbaşı süsü (Q4, K-30) | 🔄 Devam Ediyor | Uygun tasarımlara süs ilanı otomatik açılıyor (pencere 09-15 → 12-10); ilk süs Etsy'de aktif ve kurallara uygun; 10 Aralık'a kadar ≥ 20 süs canlı; 26 Aralık'tan sonra süs ilanları pasif; sezon sonu raporunda süs satışı ve neti |

## Faz Detayları

### Durum notu (2026-10-13, ikinci tur)
- Faz 3 ✅: 7 niş, mevsim takvimi, talebe bağlı üretim; ilk iki günlük koşuda 72 slogan → 44 tasarım (6 USPTO reddi).
- Faz 4 ✅: 132 ilan (44 tasarım × 3 ürün) doğrulayıcıdan geçti; etiketler marka süzgecinden, eksik etiket niş yedekleriyle.
- Faz 5 🔄: panel hazır ve görsel doğrulamadan geçti (4 genişlik, 0 sorun). 2026-10-13: Scryne seçimi Aria'ya bıraktı; 44 tasarımdan 17 onay (yayın sırası 3,18,28,38,35,4,31,23,40,5,17,21,34,2,25,14,30), 10 ret (gerekçeli), 17 yedek. Yayın, Etsy kilidi (üretim ortağı + kargo profili) açılınca başlar. Aynı gün ikinci tur (K-26 çizimli motor): 34 aday yeniden çizildi (22'si çizimli), onay geri alınıp yeniden seçildi: 20 onay (yayın sırası 2,21,18,40,31,4,25,15,42,33,9,28,14,38,35,5,23,34,3,44), 14 yedek, 10 ret. 16 ilanda 20 karaktere kesilip edatla biten etiket ("christmas gift for") düzeltildi; doğrulayıcı artık asılı kelimeyi atıyor.
- Faz 5 ✅ / Faz 6 ✅ (2026-10-13): kuyruk iki turda Aria tarafından elendi (Scryne yetkiyi devretti; bitti kriterindeki "Scryne'ın ilk kullanımı" bu yüzden Aria'nın turlarıyla karşılandı). Printify: gerçek ürünler oluşturuldu, Etsy'de 3 ilan aktif (K-27 elle mod).
- Faz 8–9 (K-27, API'siz): `siparis.izle_printify` siparişleri Printify'ın Etsy'den içe aktardığı kayıtlardan okur (brüt = kalem fiyatı, maliyet = Printify toplamı, net `fiyat.hesap`), 5 iş günü takipsiz sipariş alarm; günlük hatta elle modda çalışır. İlk gerçek siparişte kalem `metadata.price` alanının mağaza fiyatı olduğu doğrulanacak (yoksa ilan fiyatı kullanılır).
- Faz 0 ✅ / Faz 7 🔄 (2026-10-13 21:20): Etsy kişisel uygulamayı onayladı (destek talebi #27809529, aynı gün). OAuth alındı (`.etsy_token.json`, git-ignore), ETSY_SHOP_ID 68579480, üretim ortağı 5837094 (API vitrin başlığıyla döndürüyor; `etsy_yetki.py` tek ortağı seçecek şekilde düzeltildi), kargo profili 317951156022 API'den doğrulandı. `mod = "api"`. Canlı 3 ilan API'den denetlendi: active, Free US shipping, ortak bağlı, i_did / made_to_order, işlem 3–5 gün. Sipariş okuma, görüntülenme kaydı ve eşleme gerçek mağazada hatasız. Faz 7'nin kalanı: ilk gerçek siparişte makbuz + takip okumasının doğrulanması. 2026-10-14 ilk API modu günlük koşu (202 sn, hata/alarm 0): 1 tasarım (#21 knitting) → 3 ürün, eşleme 2. turda 3 ilan aktif, galeri tamam. API denetimi: kargo profili ve üretim ortağı (`production_partners`) doğru; Printify tişörtü kendi "2-5 days" işlem profiline bağlamıştı (mağaza vaadi 3-5). İşlem profili ilanda değil varyant tekliflerinde: eşleme artık `updateListingInventory` ile `hazirlama_profili_id`'ye çekiyor (SKU/fiyat/adet aynen); canlı tişört düzeltildi, 6 ilan 3-5 gün.
- İlan fotoğrafları (2026-10-13): Printify yalnız renk mockup'ı koyuyordu, vitrin/ilanda vaat edilen beden tablosu yoktu. `ilan/gorsel.py`: vitrin rengindeki mockup başa (tişört Butter, sweatshirt/hoodie Sand; renk ölçülerek seçilir), baskı yakın planı 2. sırada, sonra diğer renkler, beden tablosu (CC 1717 teknik föyü, Gildan tablosu, ±1 inç notu), renk kartı, güven kartı. Etsy tek görselin rank'ini değiştirince diğerlerini kaydırmıyor: sıra her ilanda baştan kurulur (`sira_kur`). Etsy 11+ görsel kabul ediyor. Günlük hatta `gorselleri_tamamla`; canlı 3 ilan tamamlandı ve gözle doğrulandı.
- Faz 15 🔄 (2026-10-13, K-28): radar Etsy API'siyle 50 adayı ölçtü; band mom ve bowling nişe alındı (kart, çizim, ilk üretim). Bitti kriteri "ilk 2 yeni niş canlı": iki nişin ilk tasarımları onaylanıp yayınlanınca kapanır. Radar haftalık rapora bağlı. İlk üretim: band mom 10, bowling 7 tasarım; 13 onay, 3 ret (basılı satırda ilan dili: üretici istemi ve biçim kontrolü düzeltildi), 1 yedek. Onaylı kuyruk 32 tasarım, yeni nişler serpiştirildi (ilk band mom 3., ilk bowling 6. sırada; 'Gobble Gobble' Şükran Günü'nden önce). Metin adımı bir kez sessizce takıldı (claude -p çağrısı, 1 saat çıktı yok): yeniden başlatınca tamamlandı, izlenecek.
- Faz 6–7 ⛔ Faz 0'a bağlı: istemciler resmî dokümandan doğrulanmış uç noktalarla yazıldı, sahte HTTP ile test edildi (mükerrer ürün
  koruması dahil); gerçek hesapta 3 ürün oluşturulunca ✅.
- Faz 8 🔄 (üçüncü tur): kod tamam: sipariş defteri, TCMB kuru (`veri/kur.json`, günlük), aylık özet (`matbaa ozet`: sipariş neti −
  listeleme ücreti), harcama tavanları (`config/tavanlar.toml`, K-19; tavanda yayın para harcamadan durur). Tavan değerleri K-22 ile karara bağlandı (onay
  beklemiyor). Kalan: ilk gerçek siparişte netin Etsy/Printify ekstresiyle tutması.
- Faz 9 🔄 (üçüncü tur): `Matbaa-Gunluk` Windows görevi kurulu (her gün 10:30); haftalık rapor (`matbaa rapor`, haftanın ilk koşusunda
  otomatik; ilan, Etsy görüntülenme farkı, satış, net, gecikme/hata en üstte); USPTO 30. günde yenilenir; verideki en yeni başvuru 60 günü geçerse üretim durur (K-21).
  Kalan: Faz 0 anahtarlarıyla günlük koşunun yayın + Etsy + sipariş adımlarını gerçek hesapta uçtan uca koşması.
- Denetim turu (K-21, 2026-10-13): tam kod denetimi + resmî API doğrulaması. Düzeltilen: yayın düşünce mükerrer Printify ürünü,
  Etsy eşlemesi bekleyen tasarımın günlük sınırı tıkaması, Printify siparişlerinin yalnız ilk 10'unun okunması, sipariş eşlemesinin
  belgelenmemiş alana dayanması, iptallerin gelire girmesi, gecikme alarmının değişmeyen siparişte kaybolması, tek adım hatasının
  günlük koşuyu (ve haftalık raporu) düşürmesi, onay panelinin hiç açılmaması, Etsy yetki betiğinin `.env` okumaması, yanlış Etsy token
  adresi. Eklenen: Windows bildirimi, panelde Dikkat şeridi, satan tasarımlar, K-13 "insan" yolu, kimliklerin kendiliğinden yazılması.

- Denetim turu 2 (2026-10-13 gece, `mod = "api"` geçişinden sonra): Düzeltilen: yayından sonra Etsy ilanı bir gün ücretli kargo
  profiliyle ve üretim ortağısız kalıyordu (günlük koşu artık ilan düşene kadar ≤ 15 dk bekleyip aynı koşuda eşliyor); iki günlük
  koşu aynı anda mükerrer Printify ürünü açabiliyordu (OS dosya kilidi); bir tasarımın `claude -p` zaman aşımı tüm metin adımını
  düşürüyordu; Etsy yenileme token'ı atomik yazılmıyordu ve her `Etsy()` yeni yenileme yapıyordu (erişim token'ı paylaşılıyor);
  makbuzlar 100'de kesiliyordu (sayfalama); kalıcı Etsy hatası her gün sessizce yineleniyordu (3. denemede "elle bakılmalı" alarmı);
  yayın fiyatı metin anındaki kayıttan geliyordu (artık güncel katalog); yarıda kalan görsel yüklemesi ertesi gün mükerrer
  görsel ekliyordu (alt metinle tanınıyor); başlıkta ikinci `& : + %` Etsy'de reddediliyordu; `kar_30g` adımı korumasızdı; radar
  rapor düşünce her gün koşuyordu; USPTO yenilemesi yarıda kalırsa marka dosyasını bozuyordu (geçici dosya + satır sayısı kontrolü);
  panel bağlantıları kapanmıyordu, başka sitelerden POST/DNS rebinding'e açıktı, eksik dosyada 500 veriyordu. Eklenen: günlük
  tutarlı DB yedeği (14 gün, `MATBAA_YEDEK_DIZINI`), SQLite WAL + 30 sn bekleme (panel ve koşu aynı anda yazabilir), panelde
  "düzelt" (Faz 5 bitti kriterindeki eksik parça: başlık/etiket, doğrulayıcı + marka süzgeciyle), adet başına yenileme ücreti.

- İlan tamlığı (2026-10-14, K-29): canlı 6 ilan API'den denetlendi; Printify özniteliksiz, otomatik yenilemesi kapalı ve bölümsüz
  açıyordu (hoodie'de zorunlu "Clothing closure" boştu). Günlük hatta `oznitelik` ve `vitrin` adımları; 6 ilana yazıldı ve geri okundu
  (renk, kol, yaka/kapanış, malzeme, "Humorous saying", Holiday = Christmas; `should_auto_renew` true). Aynı gün `shops_w` ile
  yeniden yetki alındı: "Fishing" ve "Knitting & Crochet" bölümleri açıldı, 6 ilan yerleşti. Onaylı kuyruk alarmı eklendi.

### Faz 11: İsimli süs (K-31) 🔄 (2026-10-15)
- **Yapılan:** `isimli.py` (ilan doğrudan Etsy API: taslak, envanter, isim sorusu, mockup + kartlar; sipariş: isimli baskı dosyası,
  Printify tek seferlik ürün + API siparişi, üretime gönderme, takip Etsy'ye, iptal edilen makbuzda Printify iptali; her hata
  günlük alarm), `susleme.on_yuz(isim=...)` + `isim_temizle` (14 karakter, glifi olmayan isim basılmaz), `gorsel.isim_karti`,
  `isimli_siparis` tablosu, günlük hatta `isimli` adımı. 8 yeni test. Canlı: Printify API siparişi açılıp iptal edildi (uçtan uca
  `_ac`), ilk isimli ilan #2 aktif (4595906587): $24.99/$27.99, zorunlu "Name", 10 görsel.
- **Kalan:** ilk gerçek isimli siparişte baskıyı (isim, varyant) ve takip yazımını görmek; Ocak'ta Class of 2027.

### Faz 16: Yılbaşı süsü (K-30) 🔄 (2026-10-14)
- **Yapılan:** `tasarim/susleme.py` (daireye sığan tasarım + alt yayda yıl; arka yüz kodu duruyor, `iki_yuz = false`),
  `fiyat.urun_uygun/tasarim_urunleri/mevsimde/mevsim_bitti`, `yayin.mevsimlik_ac` (önceden üretilmiş tasarımlara süs),
  `yayin.mevsim_kapat`, yayın sırasında süs önceliği ve ek ürün sınırı (`EK_URUN_GUNLUK = 3`), Printify gövdesinde şekil seçeneği ve
  arka baskı alanı, süs ilan görseli (tek yüz kartı + güven kartı). Günlük hatta `mevsimlik` ve `mevsim_kapat` adımları. 8 yeni test,
  öncelik kuralı bilerek bozulunca 2 test düşüyor.
- **Canlı (2026-10-14):** #2 (fishing) ve #21 (knitting) süsleri Etsy'de aktif (4595395920, 4595396016), ücretsiz kargo, üretim ortağı,
  Holiday = Christmas, niş bölümünde. 20 süs metni kuyrukta; onaylı tasarımlar yayınlandıkça süsleriyle birlikte çıkar.
- **Galeri düzeltmesi (2026-10-15):** Printify iki varyantın mockup setini ayrı yüklüyordu; ilk iki süste 20 görselin 8-9'u
  birebir kopyaydı, kartlara yer kalmıyordu. `gorsel.ilana_ekle` artık kopyaları siler, yer yetmezse sondaki mockup'ları kartlar
  için siler. Ayrıca Etsy sıralama isteğinde gelmeyen `alt_text`'i boşaltıyordu: tüm canlı ilanlarda alt metinler silinmişti.
  Sıralama alt metni yeniden gönderir, alt metni silinmiş eski kart görüntü imzasından tanınır (kart 0.2-0.6, yabancı ≥ 12.2).
  12 canlı ilan yeniden kuruldu: #2 ve #21 süsleri 13 görsel (çift yüzlü basıldıkları için "both sides" kartıyla), #2 sweatshirt'te
  çift yakın plan silindi ve eksik renk kartı eklendi. #31 süsü (2026-10-15 koşusu) tek yüzlü, $4.93 maliyetle canlı.
- **Kalan:** ilk süs siparişinde baskının tek yüz ve doğru konumda geldiğini (müşteri yorumu/şikâyet) ve netin ekstreyle tuttuğunu görmek.

### Faz 13: Performansa göre üretim 🔄 (kod 2026-10-13)
- **Yapılan:** `performans.py`: niş puanı = ilan başına beklenen satış (görüntülenme × yumuşatılmış dönüşüm, önsel %2, favori 0,1 satış),
  boş nişe keşif payı; 30 aktif ilandan azken kuyruk dengesi. Satan ifadeler Claude istemine "aynı açı, yeni söz" örneği olarak girer.
  Etsy görüntülenmesi günlük alınır. Fiyat testi satış hacmi gelince (haftada ≥ 10 satış) eklenecek.
- **Kalan:** mağaza açıldıktan 30 gün sonra raporda niş dağılımının veriyle değiştiğini görmek.

### Faz 0: Hesaplar ve para (Scryne)
- **İşler:** S2 Etsy mağazası (Aria ekran ekran yönlendirir); S3 Printify + kart (numune yok, K-20); Printify token; Etsy geliştirici
  hesabı ve Seller App kaydı (Aria yönlendirir).
- **Bitti Kriteri:** tablodaki gibi.
- **Notlar:** Kod fazları (1–5, 8) buna bağlı değil, paralel ilerler. Faz 6–7 ve 10 buna bağlı.
- **Durum (2026-10-13 17:11):** Etsy hesabı açıldı, ödeme/IBAN bilgisi girildi, kimlik onaylandı; billing tamam (kurulum ücreti $19 ödendi, Etsy Plus teklifi reddedildi:
  6 ay × $10 ile 937 TL kredi zararlı); **mağaza 16:40 açıldı (HobbyHeartPrints)**. Printify hesabı + kart + token tamam (`.env`); Printify mağazası "My new store"
  (29308592) Etsy'ye bağlandı (API: sales_channel=etsy, PRINTIFY_SHOP_ID `.env`'de). 2FA açık; ilk ilan yok (deaktive gerekmedi); production partner (Printify, "Partners you work with") ve iade politikası ("No returns or exchanges") kuruldu. Printify ayarları: mağaza adı HobbyHeartPrints, sipariş otomatik (1 saat), Printify Choice ve order routing kapalı, gecikmeli sipariş otomatik üretime, GPSR Non-EU. Etsy geliştirici uygulaması "hhp-shop-tools" oluşturuldu (17:11), durum **Pending Personal Approval**: araştırmadaki "Seller App otomatik onay" bu hesapta tutmadı, Etsy elle inceliyor, red bildirilmiyor; keystring `.env`'de. Kalan: shared secret `.env`'e (Scryne) + Callback URL `http://localhost:3003/callback` → onay beklenir. Seller App denemesi reddedildi ("You already have a developer app. Seller apps are only available for shops that have not previously registered a developer app"); developer@etsy.com'a dönüştürme/silme/onay talebi gönderildi (destek talebi #27809529, 17:34; otomatik cevap: "birkaç iş günü"). Mağaza logosu hazır (`varliklar/marka/etsy-shop-icon.png`, "Stamp Heart": lacivert pul + mercan kalp, krem zemin), Etsy'ye yüklendi →
  onay gelince (Aria) `scripts/etsy_yetki.py`, `matbaa etsy-kargo-profili` → Printify Publishing preferences'ta kargo profilini "otomatik ata ve güncelle"den bu profile çevir (şu an Etsy'de profil olmadığı için listede tek seçenek var; otomatik kalırsa Printify ücretsiz kargo profilini ezebilir),
  ilk 3 ilan. Panel ilk turu yapıldı (Faz 5 notu). Vitrin kuruldu (kapak, tagline, duyuru, About, 7 SSS; docs/vitrin.md). K-27 elle mod açık (2026-10-13 20:35): Etsy'de "Free US shipping" (33014) + "Made to order (3-5 days)", Printify Publishing preferences kargo = Free US shipping. **İlk tasarım (#2 Grandpa's Fishing Crew) Etsy'de aktif: 3 ilan** (4594624757/869/5011); Printify ilk yayında kendi ücretli profillerini bağladı, toplu düzenlemeyle düzeltildi. Günlük hat elle modda `elle_denetle`: Etsy'ye düşen ilanı kaydeder, kargo profili yanlışsa alarm.

### Faz 1: İskelet ve sağlık ✅ (2026-10-13)
- **Yapılan:** private `Scryne/matbaa`, `main`; CI (ruff check + format + pytest) main'de yeşil; Dependabot (uv + actions), güvenlik uyarıları açık;
  `.env.example`; `src/matbaa/db.py` SQLite şeması + durum makinesi + olay günlüğü (6 test: onaysız yayın yok, temiz olmayan ifadeden tasarım yok).
- **Notlar:** `gh` token'ında `workflow` kapsamı yok; push Git Credential Manager ile çalışıyor (`gh repo create --push` workflow dosyasında reddedildi).

### Faz 2: Tasarım motoru v1 ✅ (2026-10-13)
- **Yapılan:** 8 şablon (`yigin`, `kavis`, `rozet` + yeni `cerceve`, `ayirici`, `egik`, `madalyon`, `el_yazisi`); `el_yazisi_blok` kaldırıldı
  (yerine çakışmasız `el_yazisi`). Font havuzu 28 OFL (google/fonts, lisans dosyalarıyla); rol tablosu `sec.FONTLAR` (ana / küçük / yay /
  el yazısı; el yazısı yalnız ikincil satırda ve yalnız karışık harfli metinde). Çeşitlilik: (şablon, ana font) çifti 5 tasarımda bir kez,
  şablonlar son 12 tasarımda en az kullanılandan başlar. Küçük satır en kısa ana satırın 0,45 katını aşmaz.
- **Kanıt:** onay kuyruğundaki 44 tasarım yeniden çizildi, 44/44 kapılardan geçti (ret 0); dağılım cerceve 10, ayirici 10, egik 9, yigin 8,
  el_yazisi 6, kavis 1 (önce 43/44 `yigin`). Göz kontrolü panosu iki kumaşta `calisma/faz2/pano_{koyu,acik}_{0,1}.png`: üç tur, bulunan
  üç kusur (çizgi yazıya yapışık, büyük harfli el yazısı, kısa küçük satırın devleşmesi) düzeltildi, testle bağlandı. 18 yeni test;
  yeni tavan/rapor/şablon testleri kod bilerek bozulunca düşüyor (mutasyon kontrolü).
- **Sonra (K-26, 2026-10-13):** 16 vektör niş çizimi + üç çizimli şablon (`ikon_yigin`, `gunes`, `kavis_ikon`); bkz. Final-Dokuman K-26.
- **Notlar:** `madalyon` yalnız başlık + tek kısa ana satır + alt satır yapısında aday; kuyrukta henüz çıkmadı. Son göz Scryne'ın panel
  kullanımında (Faz 5). Yeniden çizim 44 tasarımda ~9 dk (OCR kapısı).

### Faz 3: İfade üretimi + IP kapısı
- **Durum (10-13):** `config/nisler.toml` (3 niş kartı), `ifade/uret.py` (`claude -p`, JSON şeması, ~5–20 sn/12 slogan), `hat.py` (`matbaa uret`,
  `matbaa durum`). İlk koşu: 36 slogan → 5 USPTO reddi (THIRD SHOT DROP, PADDLE ADDICT, OPEN PLAY, HOOKED ON, ONE MORE) → 30 tasarım.
  IP kapısında satır/slogan ayrımı: tam-marka ve baskınlık kuralları yalnız sloganın tamamına ve ana mesaja (satır düzeyi 11 temiz sloganı düşürüyordu).
- **İşler:** niş kartı (alıcı, ton, kaçınılacaklar, örnek iyi/kötü ifadeler); `claude -p` istemi + JSON şeması; aday → kapı → kayıt;
  ret nedenlerinden geri besleme (aynı kalıbı tekrar üretme).
- **Notlar:** S6 eşikleri 50 ifadeyle seçildi; ilk 200 kararda kalibrasyon.

### Faz 10: Gerçek kullanım
- **Notlar:** `urun-dogrulama` ile kapanır: gerçek mağaza, gerçek ilan, gerçek baskı fotoğrafı.
