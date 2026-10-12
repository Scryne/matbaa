---
title: Araştırma 06 — niş adayları, blank seçimi, marka filtresi kaynakları
created: 2026-10-13
type: arastirma
status: tamamlandi
---
# 06 — Niş, blank ve marka/IP filtresi

`arastirmaci` kolu, erişim 2026-10-13. [PAZARLAMA] = araç/POD satıcısı kaynağı. Niş rakamları RankHero'dan [PAZARLAMA]:
hacimler Google Keyword Planner kovalarına benziyor (muhtemelen genel arama, Etsy içi değil), metodoloji açıklanmıyor, sayfalarda iç
tutarsızlık var. **Yön sinyali olarak kullanılır, ölçüm olarak değil.** Oran = hacim ÷ listing × 1000.

## 1. Niş adayları
| Niş | Hacim/ay | Listing | Zorluk | Medyan fiyat | Tepe | Oran | Kişiselleştirme |
|---|---|---|---|---|---|---|---|
| knitting shirt | 14.800 | 28.111 | 36 | $23,99 | Eyl | 526 | zayıf |
| fishing shirt | 40.500 | 91.352 | 44 | $26,99 | Ara + Haz | 443 | orta (Papa/Grandpa + yıl) |
| running shirt | 18.100 | ~45–53K | 41 | — | Mar–Ağu | ~340–400 | orta |
| pickleball shirt | 6.600 | 31.198 | 39 | $24,99 | Ara | 212 | orta |
| st patricks day shirt | 33.100 | 170.882 | 48 | $18,98 | Mar | 194 | orta |
| 50th birthday shirt | 1.900 | 27.770 | 41 | $18,57 | Oca | 68 | güçlü (Est./Vintage yıl) |
| senior mom shirt | 1.600 | 27–43K | 42 | — | Ağu | 37–58 | güçlü (Class of 2027 + isim) |
| aunt shirt | 2.900 | 77.747 | 51 | — | Ara | 37 | güçlü |
| valentines day shirt | 9.900 | 250–585K | 54 | $19,99 | Şub | 17–39 | orta |
| mama sweatshirt | 6.600 | 227.056 | 55 | $32,90 | Ara | 29 | çok güçlü |
| teacher / nurse / dad / grandma / dog mom | — | 221K–899K | 55–62 | $21–26 | — | 7–35 | **doymuş** |
| book club / bookish | 1.300 / 4.400 | 21–189K | 43 | ~$29 | Mar, Ağu | 18–61 | zayıf |
| plant mom / gardening | 140 / 720 | 42–62K | 62–66 | ~$25 | Nis–May | 3–12 | zayıf |
- Etsy'nin kendi Bahar/Yaz 2026 raporu grafik tişörtten söz etmiyor (crochet giyim büyüyor).
- eRank Q1–Q3 2026: "shirt"/"tshirt" Etsy aramalarının ilk sıralarında; "crochet" ve "crochet pattern" yükselen; Anneler Günü aramaları
  "mom"dan "mother"a kayıyor; "graduation stole" yüksek CTR.
- EtsyHunt (01.10.2026): en çok satan 10 tişörtün 5'i fotoğraf/evcil hayvan kişiselleştirmeli, salt tipografik kişiselleştirmesiz ürün yok.
- Genel "komik kedi", genel ilham sözü, meslek nişleri: doymuş (birden çok kaynak).

## 2. Blank
- **Comfort Colors 1717** Etsy'de baskın: EtsyHunt anlık görüntüsünde en çok satan 10 başlığın 6'sında "Comfort Colors"; "comfort colors shirt"
  aramasının %97'si ABD; alıcı blank markasını arama terimi olarak kullanıyor; garment-dyed yıkanmış görünüm retro tipografiyle örtüşüyor.
- Printify'da 1717: ~$12,65'ten (Premium ~$10,93), 10–12 sağlayıcı (SwiftPOD, Monster Digital dahil), 61 renk, ABD kargo ~$4,29–4,99 / ek ~$2,69.
- Gildan 18000 (sweatshirt): Printify ~$15,5–17,9'dan (Premium ~$12,7), 17–18 sağlayıcı, 38 renk. Etsy'de baskınlığına dair veri yok.
  Comfort Colors 1566 sweatshirt ~€35,8 (pahalı).
- Fiyat bandı: tişört medyanı $19–27; sweatshirt $33–42; maliyetin 2,5–3 katı önerisi.
- Stil (2026, [PAZARLAMA]): retro/bootleg düzenler, yıkanmış palet, "Established [yıl]" arması, yay metni, bol boşluklu düzen.

## 3. Marka/IP filtresi
| Kaynak | Ne verir | Engel |
|---|---|---|
| USPTO Trademark Search (tmsearch) | web arayüzü | belgelenmiş API yok, bot koruması |
| **TSDR API** | seri/tescil no ile durum | **anahtar zorunlu** (anahtarsız 401, 13.10.2026 canlı); metinle arama yok; 60 istek/dk |
| **ODP bulk** (`TRTDXFAP` günlük, `TRTYRAP` yıllık backfill) | tüm başvurular XML; kelime markası, sınıf, durum kodu | yerel filtre (sınıf 025 + canlı durum) kendimiz; anahtar gerekliliği kaynaklarda çelişkili; `bulkdata.uspto.gov` DNS'te yok |
| HF `illeatmyhat/uspto-trademarks` | Parquet, 14,3M dosya, sınıf tablosu, 30.09.2026'ya kadar | resmî değil, lisansı belirtilmemiş → yalnız prototip |
- Bilinen tuzaklar (Justia özetinden, USPTO'da teyit edilmedi): **BOYMOM** (sınıf 25, tescilli, sahibi GIRLMOM/BOYDAD başvurularına da sahip),
  **GIRLDAD** (sınıf 25), MAMA BEAR (durum belirsiz), Taylor Swift şarkı sözü ifadeleri.
- Etsy'nin son sayısal IP dökümü (2019): bildirimlerin %54'ü telif, %44'ü marka; 13.906 mağaza tekrar ihlalden kapandı.
- En çok kaldırılan türler (ikincil): film/oyun karakterleri, şarkı sözü ve kitap alıntısı, izinsiz logo, başlık/etikette marka adı
  ("inspired by" dahil), fan art, gerçek kişi yüzleri, başkasının tasarımının hafif değiştirilmişi.

## Doğrulanamayanlar
Etsy'nin Sonbahar/Tatil 2026 raporu; niş bazında satış verisi (eRank/EverBee panelleri giriş ister); Printify'da 1717 sağlayıcı bazında tam fiyat
ve üretim yeri (arayüz JS); ODP rate limit ve ID.me gerekliliği; durum kodu → "live" tam eşlemesi; Justia kayıtlarının güncel USPTO durumu.

## Kaynaklar (seçme)
rankhero.com/keywords/* · community.etsy.com (Spring/Summer 2026 trend raporu) · help.erank.com/blog (Q1, Q2 2026, Mother's Day 2026) ·
kittl.com/blogs/2026-t-shirt-design-ideas-trends-dsi · etsyhunt.com/best-etsy-tee-shirts · printify.com/pricing · printify.com/blog/gildan-sweatshirts ·
printify.com/blog/how-to-avoid-copyright-infringement-with-t-shirts · uspto.gov (trademark-bulk-data) · tsdrapi.uspto.gov (401) ·
github.com/patent-dev/uspto-odp · pyuspto.readthedocs.io · huggingface.co/datasets/illeatmyhat/uspto-trademarks · trademarks.justia.com ·
extfiles.etsy.com/advocacy/Etsy_2019_Transparency_Report.pdf · cohnlg.com.
