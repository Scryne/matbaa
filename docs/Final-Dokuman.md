---
proje: Matbaa
created: 2026-10-13
type: final-dokuman
status: onaylandi
---
# Matbaa — Final Doküman

Kararlar Aria'nın (Scryne 2026-10-13: "her şey sende, tüm yetki sende"). Para, hesap, kimlik ve dışarı çıkan her adım Scryne'da.
Kaynaklar: `docs/arastirma/00–06`, `docs/spike/S5–S7`, `docs/Proje-Fikri.md` (K-1…K-9).

## Özet
Matbaa, Etsy'de print-on-demand tişört/sweatshirt satan bir hattır. Niş verisiyle seçilen alıcı gruplarına (v1: balıkçılık, pickleball,
örgü/tığ işi) özgün tipografik ifadeler üretir, bunları marka/eser kapısından geçirir, kodla baskıya hazır vektör tasarıma çevirir, kalite
kapılarından geçirir, ilan metnini yazar ve Scryne'ın haftalık 10 dakikalık onayından sonra Printify üzerinden Etsy'ye yayınlar. Sipariş
gelince Printify basar ve ABD'deki alıcıya gönderir; hat takip numarasını ve gecikmeleri izler. İnsan işi: onay kuyruğu, Etsy mesajları,
iade kararı.

## Teknoloji Stack

| Katman | Seçim | Gerekçe |
| --- | --- | --- |
| Dil, paket | Python 3.12, uv | Görüntü işleme, font, veri ve API işleri tek dilde; Scryne'ın projelerinde yerleşik araç |
| Yazı → vektör | uharfbuzz + fontTools | Yazı yol olarak çizilir: ölçülebilir, fonttan bağımsız, yazım hatası imkânsız (S5) |
| SVG → PNG | resvg-py | Sistem fontu yüklemeden deterministik render, 4500x5400 ~1 sn (S5) |
| Fontlar | Google Fonts, yalnız OFL | Ticari kullanım açık; lisans dosyası fontun yanında |
| Kalite kapıları | numpy, scipy, Pillow, RapidOCR (yerel ONNX) | Hale, ince çizgi, kenar, kontrast, en küçük yazı, OCR okunurluk; mutasyonla doğrulandı (S5) |
| Marka verisi | USPTO sınıf-25 canlı markalar, DuckDB + Parquet | 402.746 marka, 7 MB, ms düzeyinde sorgu (S6); kaynak ayda bir yenilenir |
| Anlamsal karar | TypeSafe Jev (`typesafe-sdk`), model `config/modeller.toml` | Gönderme/parodi yargısı; 50 ifadede kaçan 0 (S6). Global kural: anlam kararı → TypeSafe |
| Metin üretimi | Claude, headless `claude -p` (Sonnet); yedek yerel Ollama | İfade ve ilan metni yaratıcı İngilizce ister; hacim düşük (günde ≤ 5 tasarım, ~30 aday) |
| Üretim/kargo | Printify (Free → Premium ~20 sipariş/ay'da), Comfort Colors 1717 + Gildan 18000 | API'de ürün → mockup → Etsy'ye yayın zinciri; Printful bunu yapamıyor (araştırma 02) |
| Pazar yeri | Etsy Open API v3, Seller App (kendi mağaza, otomatik onay) | Üretim ortağı bağlama, aktifleştirme, sipariş/takip okuma (araştırma 01) |
| Onay paneli | FastAPI + tek sayfa HTML, yerel (127.0.0.1) | Haftalık 10 dk; hesap/sunucu gerektirmez. Telefon bildirimi v1.1 |
| Durum | SQLite (tek dosya) | Tasarım, ifade, kapı kayıtları, ilan, sipariş; yedeklenir |
| Zamanlama | Windows Görev Zamanlayıcı, günlük | Hat Scryne'ın makinesinde koşar (Claude ve TypeSafe anahtarı yerel) |
| Kalite süreci | pytest, ruff, GitHub Actions, Dependabot | Faz 1 sağlık kuralı |

## Mimari

```
  niş kartı (config/nisler.toml)
        │
  [1] ifade üretimi (Claude) ──► [2] IP kapısı: USPTO kod katmanı → Jev anlam katmanı ──► ret / insan / temiz
        │ temiz
  [3] tasarım: şablon + font seçimi (çeşitlilik kuralı) → SVG → PNG (koyu + açık mürekkep)
        │
  [4] kalite kapıları (baskı + okunurluk) ── düşerse başka şablon/font, 3 denemede ret
        │
  [5] ilan metni (Claude) → Etsy kural doğrulayıcı (başlık, 13 etiket, AI beyanı, üretim ortağı cümlesi)
        │
  [6] onay kuyruğu (yerel panel) ── Scryne: onayla / reddet / ifadeyi düzelt
        │ onay
  [7] Printify: görsel yükle → ürün (1717, kilitli sağlayıcı, renkler, fiyat) → mockup → Etsy'ye publish
        │
  [8] Etsy Seller App: production_partner_ids + aktifleştir (günde ≤ 5)
        │
  [9] izleme: Printify/Etsy siparişleri, takip numarası, gecikme alarmı, kâr defteri
```

- **Durum makinesi:** her tasarım `aday → ip_temiz → render → kalite_ok → metin_ok → onay_bekliyor → onaylandi → printify → etsy_taslak →
  aktif` (ya da `ret:<neden>`). Her geçiş SQLite'a tarih + kanıtla yazılır; hat kaldığı yerden sürer.
- **Tekrarlanabilirlik:** Jev kararları ham olasılık + çözülen model sürümüyle kayda geçer; eşikler ilk 200 kararda kalibre edilir.
- **Çeşitlilik:** aynı mağazada ardışık 5 tasarımda aynı şablon+font çifti en çok bir kez (toplu üretim görünümüne karşı; K-4).
- **Para eşikleri** `config/` içinde sabit tavanlarla durur (Etsy Ads, Premium, API bütçesi); tavanı Scryne onaylar (K-7).
- **Gizli bilgiler** `.env`'de (git dışı): `TYPESAFE_API_KEY`, `PRINTIFY_TOKEN`, `ETSY_KEYSTRING`, `ETSY_REFRESH_TOKEN`.

## Kararlar (Proje-Fikri'ye ek)
- **K-10 Tasarım dili v1:** tipografik; 8 şablon: `yigin`, `kavis`, `rozet`, `cerceve`, `ayirici`, `egik`, `madalyon` (yay + alt yay),
  `el_yazisi`. `el_yazisi_blok` (el yazısı bloğun üstüne biner) okunurluk kapısında tutarsızdı (S5) → kaldırıldı; yerine el yazısı
  bloğun üstünde/altında çakışmasız `el_yazisi` (Faz 2). Font havuzu 28 OFL font, rol tablosu `tasarim/sec.py` `FONTLAR`'da; el yazısı
  yalnız ikincil satırda ve yalnız büyük/küçük harf karışık metinde. Şablon seçimi son 12 tasarımda en az kullanılandan başlar.
- **K-11 Ürün ve fiyat:** Comfort Colors 1717 tişört, liste fiyatı $26,99 + alıcı kargosu; Gildan 18000 sweatshirt $39,99. Maliyet ~$17 /
  ~$21 (ürün + ABD kargo). Kâr hesabı Faz 8'de gerçek ücretlerle (TR: %6,5 + %6,5 + 14 TRY + %1,67 + $0,20; S7).
- **K-12 Nişler v1:** balıkçılık (baba/dede, Aralık + Babalar Günü), pickleball (Aralık), örgü/tığ işi (yükselen). Sezon varyantları niş
  içinde (Sevgililer Günü, St. Patrick's). "Class of 2027" kişiselleştirmeyle Ocak'ta (koşullu faz).
- **K-13 IP kapısı zorunlu:** USPTO + Jev'den geçmeyen hiçbir ifade render'a girmez; "insan" sonucu onay kuyruğunda ayrıca işaretlenir.
  USPTO dosyası ayda bir yenilenir. Tazelik dosyanın tarihinden değil verideki en yeni başvurudan ölçülür (kaynak donarsa dosyayı
  yenilemek veriyi tazelemez): 45 günü geçince uyarı, 60 günü geçince ifade üretimi durur (K-21).
- **K-14 Metin üretimi Claude:** ifadeler ve ilan metni `claude -p` ile; çıktı JSON şemasıyla doğrulanır, hatalıysa bir kez yeniden üretilir.
  Gerekçe: yaratıcı İngilizce kelime oyunu yerel 4B modelin üstünde. Jev metin üretmez (global kural).
- **K-15 Hat yerelde koşar** (Windows görev). Makine kapalıysa o gün atlanır; kuyruğa bir şey olmaz.
- **K-16 Mağaza:** adı `HobbyHeartPrints` (marka kontrolü temiz; yedek KindredHobbyCo, HobbyProudGoods); para birimi USD (Printify USD,
  %2,5 kur ücreti kabul — TRY fiyat yönetimi kur riski getirir).
- **K-17 Büyütme (Scryne 2026-10-13: "pek çok ürün, büyüt"):** her tasarım 3 ürün (tişört, sweatshirt, hoodie); 7 niş; mevsim takvimi
  (`config/takvim.toml`). Hız ısınma eğrisiyle: günde 1 → 2 → 4 → 6 → 8 tasarım (`config/yayin.toml`). Üretim talebe bağlı: kuyruk iki
  haftalık yayın kapasitesinin altına inmedikçe yeni üretim yok (Claude kullanımı boşa gitmez).
- **K-18 İki renk:** tasarımın küçük satırları/yayı/çizgileri ya da bir ana satırı vurgu renginde; palet her satılan kumaş rengine karşı
  kontrast kapısından geçer (kiremit ve hardal koyulaştırıldı).
- **K-19 Harcama tavanları (K-7'nin uygulanışı):** `config/tavanlar.toml`: aylık Etsy listeleme ücreti $60 (ısınma eğrisinin ilk ayı
  ~$42), günlük IP denetimi 120 ifade (TypeSafe). Sayım olay günlüğünden; tavanda hat para harcamadan durur, ürünü hataya düşürmez.
  Değerler K-22 ile karara bağlandı. Kur TCMB'den günlük (`veri/kur.json`), alınamazsa config değeri.
- **K-20 Numune yok (Scryne, 2026-10-13):** Scryne kendine numune sipariş etmeyecek; bu kalıcı. Sağlayıcıyı Aria `printify-kesif`
  çıktısından seçer (ABD'de, araştırmadaki adaylar Monster Digital / SwiftPOD önde) ve kilitler (K-2). Kartın Printify'da çalıştığı ilk
  gerçek siparişte belli olur: ödeme alınamazsa sipariş üretime girmez, takip 5 iş gününde düşmez ve gecikme alarmı yakalar.
  Baskı kalitesi ilk siparişlerin yorum ve şikâyetleriyle izlenir. Kabul edilen risk: kötü baskı ilk alıcıda görülür (araştırma 04'teki
  numunesiz mağaza anekdotu); tasarım dilinin sade, vektör ve iki renkli olması bu riski küçültür.
- **K-21 Uçtan uca denetim sonrası sağlamlaştırma (2026-10-13):** gerçek hesap öncesi tam kod denetimi ve resmî API'ye karşı doğrulama.
  - Yayın adım adım kaydedilir (`bekliyor → olusturuldu → printify → etsy_taslak → aktif`); hata düştüğü adımdan yeniden denenir.
    Printify ürün kimliği yayından önce yazılır, ürün oluşturma 5xx'te yinelenmez: mükerrer ürün/ilan ücreti açılmaz. Etsy ilanı
    48 saatte oluşmazsa aynı ürün en çok iki kez yeniden yayınlanır, sonra "elle bakılmalı" olarak panelde ve bildirimde görünür.
    Etsy eşlemesini bekleyen tasarım günlük yayın sınırından pay almaz.
  - Sipariş defteri: Printify siparişleri sayfalanır (sayfa başına en çok 10); eşleme `shop_order_id`/`label`, tutmazsa aynı Printify
    ürününü taşıyan en yakın sipariş; makbuz kalemleri tasarıma ve ürün türüne bağlanır (haftalık raporda "satan tasarımlar");
    takip numarası Etsy'den de okunur; iptal/tam iade gelire girmez; gecikme alarmı yalnız bugün değişen makbuzdan değil tüm açık
    siparişlerden.
  - Günlük koşu: her adım ayrı korunur, biri düşerse diğerleri ve haftalık rapor sürer; sonuç `calisma/gunluk/son.json`; hata ya
    da alarm varsa Windows bildirimi; hata varsa çıkış kodu 1 (Görev Zamanlayıcı'da görünür). Panelin üstünde "Dikkat" şeridi.
  - K-13'ün "insan" yolu uygulandı: Jev'in emin olmadığı ifade tasarıma girer, panelde işaretli gelir; karar Scryne'ın onayında.
  - Etsy token adresi `api.etsy.com` (resmî doküman); kurulum betikleri mağaza ve üretim ortağı kimliklerini kendisi yazar.
- **K-22 Karar yetkisi ve kendini finanse eden tavan (Scryne, 2026-10-13):** Scryne kararları "kazanılabilecek en yüksek para" hedefiyle
  Aria'ya bıraktı; Aria karar verir, kayda yazar, sonra bildirir. Scryne'da yalnız kimlik/hesap/para hareketi isteyen adımlar kalır.
  İlk karar: aylık ilan ücreti tavanı = $60 taban + son 30 günün sipariş neti × 0,5. Satış yokken kayıp sınırlı, satış geldikçe
  kazancın yarısı yeni ilana döner. IP denetimi 120 ifade/gün. Tavanda durmak alarm değildir (beklenen davranış), kayıtta görünür.
- **K-23 Ücretsiz kargo, fiyat aynı toplam (2026-10-13):** Etsy ABD aramasında ücretsiz ya da < $6 kargoyu öne alıyor (Seller Handbook,
  1 Eki 2024; ABD dışı satıcı muafiyeti yalnız ikincil kaynakta). Kargo fiyata gömüldü: tişört $33.99, sweatshirt $48.99, hoodie
  $55.99, kargo $0; alıcının ödediği toplam ve sipariş neti eskisiyle aynı ($9.28 / $11.38 / $11.66). Etsy'de "Free US shipping"
  profili API ile açılır (`matbaa etsy-kargo-profili`) ve her ilana eşlemede bağlanır. Piyasa medyanına (tişört ~$22, sweatshirt
  ~$37, RankHero 2026) inmek TR ücret yığınıyla (~%25) zarar: fiyatı tahmin değil satış verisi düşürür (Faz 13). Offsite Ads açık
  kalır: atfedilen satışta net hâlâ pozitif ($1.6–3.2) ve yeni mağazaya trafik getirir; net negatife dönerse kapatılır.
- **K-24 Sağlayıcılar gerçek maliyetle (2026-10-13, Printify hesabı açıldı):** 7 ABD sağlayıcısı geçici (yayınlanmamış, sonra silinen)
  ürünle tarandı. Her ürüne en ucuz ve renkleri tutan: tişört **Monster Digital** ($13.04, kargo $4.49; SwiftPOD $15.65), sweatshirt
  **SwiftPOD** ($18.70, kargo $7.99), hoodie **Printful** ($19.86, kargo $7.99; Monster $23.55). Monster'da "True Navy" ve "Sage" yok:
  Navy onun yerine, Sage çıktı ($2.61/tişört farkı bir renge değmez). Büyük beden eki maliyet farkı / 0,75. Satış başına net:
  tişört ~$8.8, sweatshirt ~$11.4, hoodie ~$15.5. Proje koduyla gerçek hesapta üç ürün oluşturuldu (36/42/30 varyant, 13 etiket,
  doğru fiyat), mockup'larda baskı yeri ve mürekkep doğru; ürünler silindi. Renk eşleme tam ada çekildi ("Heather Sport Dark Navy"
  "Navy" sanılıyordu), katalog araması "Comfort Colors®" yazımına dayanıklı.


- **K-26 Çizimli şablonlar (2026-10-13):** İlk onay turunda yalnız yazılı tasarımların %23'ü reddedildi, Scryne 15'ten 6'sına "çirkin" dedi;
  Etsy'de satan retro tişört dili (gün batımı amblemi, kavisli başlık, niş simgesi) motorda yoktu. Aria'nın kendi inşası 16 vektör çizim
  (`tasarim/ikon.py`, stok/ikon seti değil: lisans sorusu yok) ve üç şablon (`ikon_yigin`, `gunes`, `kavis_ikon`) eklendi; nişin çizimi
  varsa çizimli şablonlar önce denenir, yazılı şablonlar sırada +2 kullanım cezalı (çeşitlilik sürer). Noel kelimesi geçen ifadede ağaç/kar/
  hediye öne gelir. Çizimler en küçük boyda ince çizgi kapısından, şablonlar tek ve iki renkte bütün kapılardan geçer (testli).
  Kanıt: aynı 44 ifade yeniden çizildi, 34 aday tasarımın 22'si çizimli; ret 0.

- **K-27 API'siz yedek yol, şimdi (2026-10-13):** Etsy kişisel uygulamayı elle inceliyor (destek talebi #27809529, "birkaç iş günü");
  Q4 hediye sezonunda her gün değerli. Araştırma (Printify yardım sayfaları): Etsy'de "Printify" adlı üretim ortağı varsa Printify onu her
  yeni ilana kendisi bağlar (bizde var); siparişler ve takip Printify'ın kendi Etsy bağlantısıyla akar. Elle modda (`[etsy] mod = "elle"`)
  ilanlar Etsy'de elle kurulan "Free US shipping" profilini kullanır (ilk yayında `shipping_template = false` işe yaramadı, Printify yine kendi ücretli
  profillerini bağladı; çözüm Printify → Publishing preferences → Shipping profile = "Free US shipping"), `elle_kargo_hazir = true` olunca yayın açılır. İlk ilan elle denetlenir (aktif/taslak, kargo profili, ortak, who_made). API onayı
  gelince `mod = "api"`: `etsy-kargo-profili` aynı adlı profili yeniden kullanır, `etsy-esle` mevcut ilanları eşler; kayıp yok. Elle modda
  sipariş defteri ve görüntülenme verisi (Faz 8/13) yok, o yüzden API yolu hâlâ hedef.

- **K-28 Niş radarı ve ilk iki yeni niş (2026-10-13, Faz 15):** Kaynak yalnız resmî Etsy API'si (`findAllListingsActive`): Etsy sitesinden
  kazıma mağaza riski. Aday başına "<kelime> shirt": rekabet = aktif ilan sayısı, talep = score sıralı üst 100 ilanın günlük görüntülenme
  hızı medyanı (14 günden genç ilan dışarıda), fırsat = talep / log10(rekabet). Marka kapısı ve "giysi mi" süzgeci (medyan fiyat < $12 →
  desen/dijital; "crochet shirt" $5.99 çıktı). İlk tarama: mevcut nişlerin fırsat medyanı 0.0185; band mom 0.46 (9.7 bin ilan, sezon
  sonbahar), bowling 0.25 (12 bin ilan, yıl boyu). İkisi nişe alındı (kart + çizim: trampet, lobut). Radar haftalık raporla yenilenir
  (`calisma/radar/`); seçim Aria'nın, radar yalnız sıralar.

- **K-29 İlan tamlığı: öznitelik, otomatik yenileme, mağaza bölümü (2026-10-14):** Canlı API denetimi Printify'ın ilanı üç eksikle
  açtığını gösterdi: öznitelik yok (hoodie kategorisinde "Clothing closure" zorunlu), `should_auto_renew` false (ilan 4 ayda sona
  erer; tavanlar.toml yenilemeyi zaten varsayıyordu), mağaza bölümü yok. Günlük hatta iki adım: `oznitelik` (renk = vitrin rengi,
  kol, yaka, kapanış, malzeme, baskı türü "Humorous saying"; tatil: basılı satır → açık hediye mevsimi → başlık → niş kartı;
  vesile: metin → niş kartı; istenen değişince yeniden yazılır, mevsimi geçen tatil silinir) ve `vitrin` (yenileme açık, niş bölümü).
  Kurallı, LLM yok: değerler ürün ve takvim gerçeği. Varyantlar Custom1/2'de olduğu için renk öznitelik olarak çakışmadan yazılır.
  Bölüm açmak `shops_w` ister (yetki kapsamına eklendi, 2026-10-14 yeniden alındı); yetki yoksa yalnız yenileme yazılır. Onaylı kuyruk 5 günlük yayından
  azalır ve onay bekleyen varsa günlük alarm (yayın sessizce durmasın).

- **K-30 Yılbaşı süsü, Q4 için ikinci ürün ailesi (2026-10-14):** Scryne'ın paylaştığı Etsy/POD videolarındaki süs örneği Etsy
  API'siyle ölçüldü (üst 100 ilan, `radar.olc` ürün ekiyle): süsün talebi tişörtün fishing 3,7×, running 1,8×, knitting 2,8× katı;
  kupada talep her nişte tişörtün altında (Faz 14 koşulu sürer). Medyan süs fiyatı ~$20, çoğu ayrı kargolu. Üst sıralar
  kişiselleştirilmiş (isim/yıl); isimsiz yıllı süs de satıyor (örgüde en çok görülen "2025 Christmas Ornament", ~94 bin görüntülenme).
  Ürün: Printify 1632 "Ceramic Decoration Ornament (1pc)", SwiftPOD (sweatshirt/kupa ile aynı sağlayıcı), UV, altın ip; geçici
  ürünle maliyet Round $4.93, hediye kutulu $7.06, ABD kargo ≤ $5.89. Tasarım motoru: tişört tasarımı daireye sığar, alt yayda
  "CHRISTMAS <yıl>" (`tasarim/susleme.py`). **Tek yüz:** canlı ilk iki süste arka baskı maliyeti $6.57'ye çıkardı; çift yüzü aynı
  nete taşımak $23.99 ister. Fiyat $21.99 ücretsiz kargo (net $5.94, Offsite $1.98; alıcı toplamı rakip + kargodan düşük), hediye
  kutusu +$3. Kimlere: fishing/running/knitting + metninde Noel kelimesi geçen her tasarım; pencere 09-15 → 12-10 (sonrası Noel'e
  yetişmez), 12-26'dan sonra aktif süs ilanları Etsy'de pasife alınır (yıllı ürün Ocak'ta satmaz, yenileme ücreti boşa gitmez).
  Süsü olan onaylı tasarım yayın sırasında öne geçer; yayındaki tasarıma sonradan eklenen süs tasarım sınırını yemez (günde ≤ 3).
  İlk iki süs (#2, #21; çift yüzlü, net $4.30) 2026-10-14 canlı. Kişiselleştirme (isimli süs) araştırıldı: otomatik yol var ama
  ağır (Printify'da manuel onay + içe aktarılan siparişi iptal edip API ile yeniden açma + takibi Etsy'ye `createReceiptShipment`
  ile yazma; Etsy kişiselleştirme API'si 2026'da çoklu soruya geçti); Faz 11'e taşındı, süs satışı gelirse öne alınır.
- **K-31 İsimli süs, Faz 11 öne alındı (2026-10-15):** Scryne "her şeyi sana bırakıyorum, en iyi halinle çalış" dedi; Q4'e 8 hafta
  kala en büyük kaldıraç isimli süs (üst sıralardaki süslerin çoğu kişiselleştirilmiş). Satış beklemeden açıldı. **Yol:** ilan
  Printify'a bağlanmadan doğrudan Etsy API'siyle açılır (taslak → iki varyantlı envanter, SKU = Printify varyantı → isim sorusu
  `updateListingPersonalization`, eski `personalization_*` alanları 2026'da kalktı → Printify'ın örnek isimli geçici ürününden
  mockup'lar, arka yüz kameraları hariç → isim ve güven kartları → `etsy_esle` aktifleştirir). Sipariş: makbuzdaki isim
  (`variations[].property_id == 54`) ön yüze el yazısıyla (Pacifico) basılır, Printify'da tek seferlik ürün + API siparişi
  (`external_id` = makbuz → `metadata.shop_order_id`; `siparis.izle` buradan eşler, mükerrer denetimi de), on-hold olunca üretime,
  kargo takibi `createReceiptShipment` ile Etsy'ye. **Neden bu yol:** Printify'ın kendi Etsy kişiselleştirmesi her siparişi panelde
  elle onay bekletiyor ve katmanı API'den tanımlatmıyor; Printify'a bağlı olmayan ilanın siparişi Printify'a otomatik aktarılmıyor
  ("Other orders"), çift üretim yok. **Canlı doğrulama:** Etsy'ye bağlı Printify mağazasında API siparişi açıldı ve iptal edildi
  (2 kez; boş alıcı e-postası kabul), `createReceiptShipment` uygulamamıza açık (sahte makbuzla 404, 403 değil). **Fiyat** $24.99
  ücretsiz kargo, hediye kutusu +$3; net $7.90 (Offsite $3.41). **Ölçülen:** süs kargosu gerçek siparişte $6.29 (katalog $5.89);
  düz süsün neti $5.54'e indi, kural (> $5) tutuyor. İlk isimli ilan #2 (fishing grandpa) 2026-10-15 canlı (4595906587).
  **Videolar:** Whisper ile yazıya döküldü (2026-10-15); konuşmada yeni taktik yok, yalnız 7. video süsü, 6. video bebek
  battaniyesini (Printify, iyi görsel) anlatıyor; battaniye sonraki ürün ailesi adayı.
- **K-32 Trafik kanalı: Pinterest (CSV), TikTok/heliosgen değil (2026-10-15; TikTok kısmı K-34 ile değişti):** Scryne TikTok'ta AI videolu mağaza hesabı ve
  heliosgen önerdi, kararı bana bıraktı. heliosgen kendisi üretmiyor (ücretli kie.ai kredisi), Windows sürümü yok, lisans dosyası
  yok; görselden video modelleri tişörtteki sloganı bozabilir. TikTok'ta denetimsiz API gönderisi yalnız sahibine görünür, profil
  linki işletme doğrulaması ister, TikTok Shop Türkiye'den ABD'ye açılamaz, TikTok → Etsy dönüşümüne güvenilir veri yok.
  **Seçilen:** Pinterest'in kendi toplu pin CSV'si (API onayı gerekmez; görsel Etsy'nin herkese açık ilan görseli): ilan başına bir
  pin, niş panosu, günde 3 pin, 14 gün ileri (`pinterest.py`, panoda "CSV indir"). Etsy Ads açılıştan 15 gün sonra (~10-28)
  günde $1-3 ile denenir. TikTok, satış verisi gelince gerçek ürün görselleriyle elle küçük deney olarak yeniden değerlendirilir.
  2026-10-15: Pinterest işletme hesabı açıldı (HobbyHeartPrints, ülke Türkiye, profil mağaza adıyla); ilk CSV (13 pin, 10-16 → 10-20)
  Pinterest'e yüklendi ("Yükleme başarılı"). Pinlerin hepsinin oluştuğu 10-16'da profilden doğrulanacak.

- **K-33 Üçüncü tam denetim (2026-10-15):** Scryne projeyi baştan sona denetleyip eksikleri kapatmayı, iyileştirmeyi bıraktı.
  - **Dayanıklılık:** HTTP katmanı ağ hatasını yineler: bağlantı kurulamadıysa her istek, kurulup düştüyse yalnız kaynak
    oluşturmayan istek (oluşturma işlenmiş olabilir, mükerrer ürün/sipariş riski). Etsy 401 dönerse erişim token'ı zorla
    yenilenip istek bir kez yinelenir (önce süresi dolmamış görünen geçersiz token günü düşürürdü). Adım dışında düşen günlük
    koşu da `son.json`'a ve bildirime yazılır. Elle `yayinla`, `etsy-esle`, `isimli` günlük koşunun kilidini alır.
  - **İzleme:** bizde `aktif` olup o günün Etsy aktif ilan anlık görüntüsünde olmayan ilan günlük alarmdır: Etsy marka
    bildirimiyle ilanı kendisi kaldırır, tekrarında mağazayı kapatır; bunu gün içinde görmek gerekir. Pinterest kuyruğunda
    yayından kalkmış ilanın pini dosyaya girmez.
  - **İsimli süs (Faz 11):** alıcının "Name: Emma" ya da tırnaklı yazdığı isim temizlenir; basılamayan isim için panoda
    elle isim ("İsimle aç", basılabilirlik aynı denetimle) ve "Elle hallettim"; Printify'ın iptal ettiği ya da üretimdeyken
    iade edilen sipariş `elle` durumuna düşer ve otomatik yeniden açılmaz (çift üretim riski), panelden kapatılana kadar her
    gün hatırlatılır. Haftalık rapor bunları "Dikkat"e yazar.
  - **Tasarım motoru:** `gunes` şablonunun çizim çevresindeki boşluk SVG `feMorphology` süzgeciyle açılıyordu; resvg onu
    naif uyguluyor, tek render 68 sn sürüyordu (test süresinin 3,5 dakikası, üretimde şablon başına dakikalar) ve dağ
    çiziminin zirvesinde bulanık bozulma bırakıyordu. Genişleme artık çizim tek başına render edilip numpy'de gerçek Öklid
    uzaklığıyla yapılır, iç boşluklar doldurulur (trampet baklavalarından şerit kırıntısı görünmez): 1,8 sn, 16 çizimin
    hepsi gözle doğrulandı. Canlı ve onaylı 12 gunes tasarımında bozulma yoktu, yeniden basılmadı.
  - **Bilinen sınır:** süs ürün satırı tasarım başına tek (`urun` birincil anahtarı); 2027 sezonunda "CHRISTMAS 2027" süsleri
    için kapanan (`kaldirildi`) süs satırının yeniden açılması gerekecek. Eylül 2027'den önce roadmap'te.

- **K-34 TikTok, K-32'nin yerine (2026-10-15):** Scryne "mağaza bilinirliği hiç yok, bekleyerek olmayacak" dedi ve TikTok'u
  istedi; K-32'deki iki çekinceden biri yöntemle kalktı. Videolar yapay zekâyla değil kodla üretilir (`tiktok.py`): her kare
  gerçek ürün (Etsy ilanındaki Printify mockup'ları, kendi baskı dosyamızın kumaş üstü yakın planı, marka kapanış kartı), yazı
  fonttan yola: slogan bozulmaz. 9:16, ~13-15 sn, sert kesme + hafif yakınlaşma; kanca/açıklama/hashtag Claude'dan (son kancalar
  verilir, tekrar etmez; güncel hediye sezonu verilir), hashtag'ler marka süzgecinden ("dadlife" tescilli çıktı). Günlük koşu
  yayındaki her tasarıma bir video hazırlar (günde ≤ 2); pano videoyu, açıklamayı ve önerilen saati verir (günde bir, ABD doğu
  19:00 = TR 02:00/03:00; Studio 10 gün ileri zamanlar), Scryne TikTok Studio'dan yükler, "Zamanladım"a basar.
  **Araştırma (2026-10-15, kaynaklar `docs/arastirma/07-tiktok.md`):** video fotoğraf karuselinden gönderi başına ~5,6 kat izlenme
  alıyor (Metricool, 2,3 milyon gönderi): karusel yok. Onaysız Content Posting API yalnız "sadece ben" paylaşıyor ve kendi
  hesabını yöneten araç denetimden geçmiyor: otomatik paylaşım yok, elle yükleme. İşletme hesabında profil linki takipçi eşiği
  olmadan (resmî yardım özeti), bedeli müziğin ticari kütüphaneyle sınırlı olması. Hesap açılışında (2026-10-15) link
  alanı "İşletmenizi doğrulayın" formu istedi (şirket sertifikası, yasal şirket adı, işletme ruhsatı): şirket yok, form
  doldurulmaz. Link 1.000 takipçide açılır; o zamana kadar bio ve videonun kapanış kartı "Search HobbyHeartPrints on Etsy".
  **Açık risk:** Türkiye'den açılan hesabın videolarının ABD akışına ne kadar düştüğü için resmî kural yok; VPN/ABD SIM gibi
  yöntemler hesap kapatma riski (kullanılmaz). Ölçüm: ilk 10 videodan sonra TikTok Studio → Analiz → İzleyiciler'de ülke
  dağılımı. ABD payı düşükse karar yeniden açılır (ücretli TikTok reklamı Türkiye kayıtlı hesapla ABD'yi hedefleyebiliyor mu
  doğrulanamadı; kampanya tabanı günlük $50).

- **K-35 Giyilmiş ürün videosu, yerel ve ücretsiz (2026-10-15, deneme):** Scryne: ürünü insan üstünde görmek alıcıya güven
  veriyor; ComfyUI ile yerelde üretilsin. Kurulum `C:\Users\scryn\ComfyUI` (git + uv venv, torch cu130; RTX 4060 8 GB),
  `scripts/comfy_baslat.ps1`. Modeller: RealVisXL V5 (fotoğraf, OpenRAIL++), Wan 2.2 TI2V 5B (video, Apache-2.0), SAM 2.1
  (tişört bölütleme, Apache-2.0); kıyafet bölütleyici segformer_b2_clothes lisansı belirsiz olduğu için kullanılmadı.
  **Yöntem (`giyim.py`, `matbaa giyim --tasarim N`):** model baskıyı çizmez (yerel modeller yazıyı harf harf koruyamıyor):
  baskısız vitrin renginde tişörtlü insan → SAM ile tişört → kendi baskı dosyamız göğse, kumaşın ışığı ve kırışıklığıyla →
  OCR → Wan 2.2 ile hafif hareket → örnek karelerde OCR (tutmazsa fotoğrafta kamera yakınlaşması) → kanca yazısı + kapanış
  kartı. Renk eşiğiyle tişört bulma ilk denemede gün batımı göğünü tişört sandı, baskı yüze kaydı: SAM'e geçildi.
  **İlk deneme (#2 Grandpa's Fishing Crew):** 4 aday 83 sn, dördünde slogan birebir; video 81 kare 18,6 dk, örnek karelerin
  %100'ünde slogan birebir; çıktı 6,5 sn. Gerçekçi AI insanı içerdiği için TikTok'ta "AI ile oluşturulmuş içerik" açık
  paylaşılır; Etsy ilanına girmez. Scryne "gayet güzel olmuş" dedi (2026-10-15): günlük hatta `giyim` adımı her gün bir
  tasarıma giyilmiş video üretir (ComfyUI'yi gerekirse açar, iş bitince kapatır; üretilemeyen tasarım `hata` kalır, her gün
  20 dk boşa denenmez). Videolar `tiktok_video` tablosunda ürün videolarıyla tek sırada; her tasarım iki video verdiği için
  paylaşım takvimi günde iki saat (ABD doğu 12:00 ve 19:00). Giyilmiş videonun kendi kancası olur (aynı cümle iki kez gitmez).

- **K-36 Görünürlük: duraklatma kalktı, hız ve trafik kanalları (2026-10-18):** Scryne "beni kazanca çıkaracak her şeyi yap, tüm
  yetki sende" dedi. **Ölçüm (Etsy API):** mağaza 5 günlük, 20 aktif ilan ama yalnız 4 tasarım; toplam 6 görüntülenme, 0 favori,
  0 satış. İlanlar indekste (dört ifadenin her biriyle arama ilanlarımızı getiriyor) ve API `score` sıralamasında orta-kuyruk
  etiketlerin çoğunda ilk 30'da (ör. "funny runner hoodie" 736 ilanda 1., "fishing crew sweater" 440'ta 2.). Sorun indeks ya da
  etiket değil: bu aramaların hacmi düşük, yüksek hacimli aramalarda yorumsuz yeni mağaza görünmüyor, 4 tasarım dar bir anahtar
  kelime ağı. **Araştırma** (arastirmaci, 2026-10-18): doğrulanmış "yeni mağaza sandbox" kuralı yok; 5 günde birkaç görüntülenme
  yeni mağaza için olağan; Etsy Ads mağaza açılışından 15 gün sonra (~10-28), en az $1/gün; Pinterest yeni POD mağazasına en çok
  önerilen dış kanal, ilan başına birkaç farklı görselli pin; başlık/indirim etkisine ölçülmüş veri yok.
  **Kararlar:** (1) Günlük görev yeniden açık. (2) Isınma ilk 21 gün 3 tasarım/gün (önce 1→2): onaylı 39 tasarım (~190 ilan)
  Ekim sonuna yayında, Kasım'ın hediye aramalarına girer; ilan ücreti tavanı ($60/ay) aynı. (3) Pinterest ilan başına 3 pin
  (vitrin mockup'ı, baskı yakın planı, başka renk; başlıklar döndürülür), günde 6 pin; önce her ilanın ilk pini. (4) Etsy Ads
  10-28'de açılır: $2/gün, tüm ilanlar; $30 harcayıp sipariş yoksa kapanır, sipariş gelirse ROAS < 2'de kısılır (Etsy Ads'in API'si
  yok, Scryne Shop Manager'dan açar; tavan `tavanlar.toml`'da kayıt). (5) Hedefli teklifler: terk edilen sepet ve yeni favori %10
  (yalnız dönüşen alıcıya maliyet; tişört neti ~$8.8 → ~$6.3, pozitif). (6) Başlık, etiket ve fiyat değişmez: ilanlar zaten
  sıralanıyor, değişikliğin etkisine kanıt yok; 30 günlük veriyle (Faz 13) karar verilir. Öldürme kriteri aynı (90. gün).

- **K-37 Çizimli hat, yazılı motor durdu, harcama sıfırlandı (2026-10-18):** Scryne: "bu ürettiğin tasarımları kimse almaz, globalde
  trend olan şeyler üretmemiz lazım"; ardından bakiye −602,95 TL ("batıyoruz"). **Bakiye:** ilan başı $0.20 + %20 KDV ≈ 11,9 TL;
  35 ilan + bugünkü açılışlar. Ücret ilan başına bir kez, 4 ay geçerli; satıştan düşülür. **Durdurulan:** `Matbaa-Gunluk` kapalı,
  ilan ücreti tavanı 0 (süs/isimli ek ürünler dahil her açılış durur, kodla doğrulandı), ısınma 0, yazılı (tipografik) üretim
  kapalı (`tipografik_uretim = false`), yayına yalnız `yayin_nisleri` (`cozy_christmas`). Eski 36 onaylı tasarım yerinde, yayınlanmaz.
  **Trend ölçümü (Etsy API, `findAllListingsActive`, 49 + 29 sorgu):** son 90 günde en hızlı görüntülenen yeni giyim ilanları ve en
  çok favorilenen Noel giyimi: sevimli çizimli karakter (hayalet rakun kahve 301 görüntülenme/gün, hayalet kahve bardağı 175,
  nakışlı balkabağı-kahve-kitap 170, "Code Boo" hemşire 139, kardan adam sweatshirt 1.237/gün, "Always Cold" 170), kış/Noel +
  kahve/kitap/köpek/kedi/meslek esprisi, alıcı çoğunlukla kadın. Üst sıralardaki Disney/Snoopy/Dolly Parton/Star Wars ilanları telifli:
  alınmaz (mağaza kapanır). **Yöntem (`cizim.py`, `config/cizim.toml`):** çizim yerel FLUX.2 [klein] 4B distilled (Apache-2.0,
  makinede kurulu; 9B/dev ticari değil) ile yazısız üretilir; model yazıyı bozuyordu ("MERY BRIGCUT"), yazıyı motor fonttan yol
  olarak dizer (üst kavisli, alt düz, dolgu + çizimin çizgi rengiyle kontur). Kenara bağlı beyaz zemin silinir (kalın dış çizgi iç
  beyazı korur). Eleme: kırpık konu, konu alanı %8-60 dışı, parçalı konu, çizimde OCR'la okunan yazı; baskı kapısı: 4500x5400,
  kenar payı ≥ 60 px, düz alt satır OCR ≥ 0,8 (kavisli satır `kavis` şablonundaki gibi OCR'a girmez). Aday başına ~13 sn çizim
  + ~10 sn kompozisyon/OCR; 12 kavram × 4 aday 13 dk. IP kapısı aynı (USPTO + Jev): ilk partide 4 ret (TRASH PANDA ve HOLLY JOLLY
  canlı marka, DECK THE PAWS ve OH CHRISTMAS TREE şarkı göndermesi); yazıları değiştirildi. Adayı Aria seçer (`matbaa cizim-sec`).
  **Ürün ve fiyat:** `tisort_cizim` $29.99 (net $5.54) ve `sweatshirt_cizim` $42.99 (net $6.63, Offsite −$1.11), yalnız açık
  renkler (çizimin koyu çizgisi koyu kumaşta kaybolur); eski $33.99/$48.99 rakip bandının üstündeydi. Tasarım başına 2 ilan (önce
  5): ilan ücreti tasarım başına ~24 TL. **İlk parti kuralı:** ~10 tasarım × 2 = ~20 ilan (~240 TL); her ilan Pinterest'e 3 pin;
  2 hafta görüntülenme ölçülür, tutmazsa parti büyümez. Etsy ilan açıklamasında çizim için ayrı AI beyanı.

- **K-38 Çok platformlu otomatik paylaşım, Zernio (2026-10-20):** Scryne: "tüm ilanlar tüm platformlarda olmalı", her şey otomatik,
  "hiçbir sınır tanımıyorum". **Veri:** 7 günde 59 ilan 9 görüntülenme; TikTok'ta 8 video 516 izlenme, 49 takipçi; erişim 4. videodan
  sonra açıldı (2-7 → 77-217 izlenme), ama en çok izlenen 4 videonun tasarımları Etsy'de 1 görüntülenme aldı (link 1.000 takipçide).
  Ülke dağılımı TikTok'ta görünmüyor: kanallar Etsy "Traffic sources"la ölçülür. **Araştırma (`docs/arastirma/08`):** TikTok ve
  Pinterest kendi denetimsiz uygulamamızın gönderisini yalnız sahibine gösteriyor; Instagram/Facebook/YouTube'un resmî API'si kendi
  hesaba açık ama Meta ve Google geliştirici uygulaması, token yenileme ve IG için zamanlama yok (bilgisayar o saatte açık olmalı).
  Apify/RapidAPI/GitHub'daki resmî olmayan yükleyiciler şifre ya da çerez istiyor, platform kurallarına aykırı, kırılgan (en çok
  kullanılan TikTok aracı %79 başarı, instagrapi'de Ekim 2026 askıya alma vakası): **elendi**, hesaplar tek trafik kaynağımız.
  **Seçilen:** Zernio (eski Late) beş platformu tek API'yle, kendi denetlenmiş uygulamasıyla ve sunucu tarafı zamanlamayla veriyor;
  ilk 2 hesap ücretsiz, sonrası hesap başı 6 $/ay (beş hesap 18 $/ay). **Kurallar:** video tasarım başına bir (bütün ilanlarını
  gösterir; aynı tasarımın beş benzer videosu tekrar içerik), ilanların kendisi Pinterest'te linkli pin. Her platform günde iki video,
  ABD doğu saatleriyle (`config/paylasim.toml`), 7 gün ileri zamanlı (Zernio medyayı 7 gün tutar). Çizimli ve yazılı tasarım sırayla
  (tanıtım tek hatta yığılıp Faz 18 kıyasını bozmasın). TikTok: herkese açık, yorum/duet/stitch açık, ticari içerik "brand_organic"
  (kendi ürünümüz), AI insanlı video `video_made_with_ai`; AI insanlı video yalnız TikTok'a. Açıklama platformun link kuralına göre:
  TikTok'ta link yok, Instagram "link in bio", Facebook/YouTube ilan adresi, Pinterest pinin kendisi. Gönderilemeyen 3 kez denenir,
  sonra alarm; zamanlı gönderinin sonucu ertesi koşuda yoklanır. 10-18'de (K-37) sıradan çıkarılan 92 eski ilan pini yeniden sırada.
  **Ölçüm:** bağlantıdan 2 hafta sonra Etsy "Traffic sources"ta platform başına ziyaret; ziyaret getirmeyen kanal kapanır (hesabı
  Zernio'dan çıkarılır, ücreti düşer).
  **Aynı gün:** Scryne YouTube kanalı açmıyor; kapsam TikTok, Instagram, Facebook, Pinterest (4 hesap, 12 $/ay). Kod bağlı
  hesaplara gönderdiği için değişiklik gerekmedi; kanal açılırsa Zernio'ya bağlamak yeter.
  **İki Zernio hesabı (10-20, şartlar 10-23 okundu):** ücretsiz katman "ilk 2 bağlı hesap"; iki hesap (`ZERNIO_API_KEY_2`) ile 4 bağlantı
  0 $. Şartlarda (zernio.com/tos ve /content-guidelines, 2026-10-09) çoklu hesap ya da ücretsiz katmanı bölme maddesi yok, ama Zernio
  hesabı sebepsiz askıya alabilir. Karar: iki hesapla devam. Hesap kapanırsa geri dönüş tek hesapta 3. ve 4. bağlantı (12 $/ay); kod
  anahtar sayısından bağımsız. Aynı videonun platformlara gitmesi Zernio'nun asıl kullanımı, açıklamalar zaten platforma göre ayrışıyor.

- **K-39 11-02 kıyas kuralı önceden yazıldı (2026-10-23):** **Veri (10. gün):** 59 ilan, toplam 11 görüntülenme, 0 favori,
  0 sipariş. `matbaa kiyas` (4/14 gün) ilan başına çizimli 0.04, süsleme 0.14, yazılı 0.19: sayılar 1, 2 ve 4 görüntülenme.
  Bu büyüklükte fark gürültüdür. Darboğaz katalog değil, trafik.
  **Kıyas kuralı (Faz 18 kriterinin uygulanışı):** (1) Pencere yalnız kıyaslanan iki giyim hattından hesaplanır; sonradan
  açılan bir süs kararı ertelemez, pencereden genç süs ilanı süsleme grubuna girmez. (2) İki hattın toplamı 20 görüntülenmenin
  altındaysa karar "yetersiz veri" olur. (3) Hat, ilan sayısıyla orantılı görüntülenme alır (eşit oran varsayımı); çizimlinin
  payına tek yönlü Poisson (koşullu binom) testi uygulanır, eşik p ≤ 0,10. "İlan başı yüksek" tek başına yetmez: 21'e 20 şansla
  açıklanır.
  **Kod düzeltmeleri (ilan açmaz):** `mevsimlik_ac` sonradan eklenen ürünün metnine çizimin konusunu geçmiyordu (çizimli
  tasarımın ek ürünü yazılı AI beyanıyla yazılırdı); süs baskısı çizimli tasarımda yay rengini çizimin dış çizgisinden alır
  (`susleme.tasarim_vurgu`), `cizimli_de` bayrağı bir ürünü iki hatta açabilir. Bayrak hiçbir üründe açık değil (K-40).
  **11-02 karar tablosu (K-40'tan sonra: hiçbir sonuç ilan açtırmaz):**
  | Sonuç | Yapılan |
  |---|---|
  | çizimli yüksek | Ücretsiz paylaşım sırası çizimli tasarımlara ağırlık verir (Zernio, `config/paylasim.toml`) |
  | fark yok / yetersiz veri | Bir şey değişmez; kanallar sürer |
  | çizimli düşük | Paylaşım sırası yazılı tasarımlara ağırlık verir |
  | herhangi bir satış | Scryne'a bildirilir; yeni ilan yine Scryne'ın açık kararı olmadan açılmaz |
  **Aynı dönemin diğer tarihleri:** 11-03 kanal ölçümü (Faz 19, Etsy Stats → Traffic sources; Open API'de yok, Shop
  Manager'dan okunur). 11-10 mağaza 4 haftalık: sipariş yoksa v1 "30 ilan canlı" ile kapanır (Faz 10; 59 ilan canlı).

- **K-40 Yeni ilan yok, harcama donduruldu (Scryne, 2026-10-23):** "ilan vermiycez artık", "sakın ilan verme", "zaten paramız
  eksi", "dondurmuştuk". K-39 taslağındaki 24 süs ilanı (12 çizimli tasarım × düz + isimli, $4.80) açılmadan geri alındı:
  metni yazılmış 8 süs satırı silindi, Printify/Etsy'ye hiçbir şey gitmedi. `tavanlar.toml`: `aylik_ilan_ucreti_usd = 0`,
  `yeniden_yatirim_orani = 0` (satış gelse de net yeni ilana dönmez); süs ve isimli süs dahil her açılış durur, Kasım ve
  Aralık başında da kapalı (`tavan.ilan_kontrol` ile doğrulandı). 10-18'de "harcama sıfırlandı" denmişti, tavan ise $12'de
  bırakılmıştı; bu oturumda o $12 ilan açılabilir sanıldı. Tek doğru değer 0'dır. Sürenler (para harcamaz): 59 canlı ilan,
  ücretsiz Zernio paylaşımı, günlük sipariş/görüntülenme okuma. Etsy Ads (K-36, 10-28) açılmaz.
  **Otomatik yenileme kapalı (Scryne "kapat", 2026-10-23):** `yayin.toml` [etsy] `otomatik_yenileme = false`; `vitrin_esitle`,
  `etsy_esle` ve isimli ilan bu değeri yazar, günlük koşunun `yenileme` adımı Etsy'deki her aktif ilanı ayara çeker (kaynak Etsy,
  bizde kaydı olmayan ilan da kapsanır). Canlıda 59/59 ilan kapatıldı ve geri okundu. İlanlar 2027-02-13 → 02-18 arasında sona
  erer; o tarihten sonra mağazada ilan kalmaz (Faz 10'un "30 ilan canlı" kapanışı 11-10'da, bundan önce).

## Kapsam (v1)
- **Süre tavanı:** ~4 hafta (kod tarafı); mağaza ve anahtarlar Scryne'ın Faz 0 işlerine bağlı.
- **Bitti = kullanıldı:** Scryne'ın Etsy mağazası canlıyken hat en az 30 ilanı Scryne'ın onayıyla yayınlamış ve ilk gerçek siparişte Etsy → Printify → üretim → takip numarası zinciri elle dokunulmadan çalışmıştır.
  4 haftada sipariş gelmezse v1 "30 ilan canlı" ile kapanır; sipariş zinciri v1.1'in ilk kontrolüdür.

## Riskler ve Doğrulamalar
| Risk | Durum | Kanıt |
|---|---|---|
| AI/otomatik tasarımın baskı kalitesi | Azaltıldı | Kodla vektör yazı; 7 kalite kapısı; mutasyonla 6/6 kapı yakalıyor (S5). Gerçek baskı: numune yok (K-20), ilk siparişlerin yorumları |
| Marka/eser şikâyeti | Azaltıldı | USPTO + Jev, 50 ifadede kaçan 0 (S6); en yaygın POD kalıplarının tescilli olduğu bulundu |
| Etsy kuralları (AI beyanı, üretim ortağı, ücretler) | Doğrulandı | Birincil sayfalar (S7) |
| Printify Türk kartı | **Açık** | İlk gerçek sipariş; ödeme düşmezse gecikme alarmı (K-20) |
| Etsy API erişimi | Kapandı | Kişisel uygulama 2026-10-13'te onaylandı (K-27), `mod = "api"`; token 401'de kendiliğinden yenilenir |
| Etsy'nin ilanı kaldırması (marka bildirimi, kural) | Azaltıldı | Günlük koşu bizde aktif olup Etsy'de aktif olmayan ilanı alarmlar (K-33) |
| Satış hiç gelmemesi | Kabul edilen risk | Öldürme kriteri: 90. gün 100 ilan / < 5 satış → niş ve tasarım dili baştan; 180. gün < $100/ay net → dur |

## Scryne'ın işleri (Faz 0)
1. **Etsy mağazası** (S2): kimlik, Türk IBAN (ad = kimlik = yasal ad), 2FA. Aria ekran ekran yönlendirir. Mağaza adı Aria'dan.
2. **Printify** (S3): hesap, yurt dışına açık kart, Etsy bağlantısı. Numune yok (K-20).
3. **Anahtarlar:** Printify kişisel token; Etsy geliştirici hesabı → Seller App (Aria adım adım). USPTO API anahtarı isteğe bağlı (v1.1).

## Kapsam Dışı
Shopify (koşullu faz), ücretli dış reklam, isimli süs dışındaki kişiselleştirme (K-31; Class of 2027 Ocak'ta), poster/sticker (kupa Faz 14'te koşullu; süs K-30 ile Q4'te açık), dijital ürün,
fabrika ürünü/trend oyuncak yeniden satışı (Etsy'de yasak; ayrı iş modeli), Etsy mesaj otomasyonu
(API yok; hazır cevap şablonları var), Redbubble/TeePublic/Amazon Merch kolları, AI görsel katmanı (grafik öğe; v1.1 spike).
