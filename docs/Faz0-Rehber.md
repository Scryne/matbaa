---
title: Faz 0 — Scryne'ın yapacakları (hesaplar, para, anahtarlar)
created: 2026-10-13
type: rehber
status: aktif
---
# Faz 0 — senin yapacakların

Kod tarafı hazır: üretim, marka kapısı, tasarım, ilan metni, onay paneli, Printify/Etsy yayını, sipariş defteri ve günlük görev
(`Matbaa-Gunluk`, her gün 10:30). Aşağıdakiler senin kimliğin, kartın ya da kararın olmadan yapılamıyor. Sıra önemli.
Her adımın sonunda bana "X tamam" yazman yeter; gerisini ben bağlarım.

## 1. Mali müşavir (en önce — proje bu cevaba göre devam eder)
Şunu sor:
1. "Etsy'den yurt dışına print-on-demand satış yapacağım (ürün ABD'de üretilip oradan gönderiliyor, para TL olarak Etsy'den hesabıma
   geliyor). Hangi noktadan itibaren vergi mükellefi olmam gerekir?"
2. "Öğrenciyim. Şahıs şirketi açarsam Bağ-Kur primi ödemek zorunda mıyım, öğrencilik bunu değiştirir mi?"
3. "Genç girişimci kazanç istisnası (GVK mük. 20) bu işe uygulanır mı?"
4. "Bu satışlar ihracat sayılır mı, KDV durumu ne olur?"
Cevabı bana yaz; `docs/spike/S1-mukellefiyet.md` olarak kaydederim. Bağ-Kur ayda ~10–12 bin TL çıkarsa beklenen kârı aşabilir;
o durumda modeli birlikte değiştiririz.

## 2. Etsy mağazası (~30 dk)
1. etsy.com/sell → "Get started". E-postayla hesap aç (kişisel e-postan olabilir; mağaza adı kamuya açık olan tek şey).
2. **Shop preferences:** dil English, ülke **Türkiye**, para birimi **USD** (Printify fiyatları USD; %2,5 kur ücretini kabul ediyoruz — K-16).
3. **Shop name:** `HobbyHeartPrints` (marka kontrolünden geçti). Alınmışsa sırayla: `KindredHobbyCo`, `HobbyProudGoods`.
4. **Stock your shop** (açılış en az bir ilan ister): `calisma\ilk_ilan_kiti\` klasörünü kullan.
   - Fotoğraflar: `1-prova-ivory.jpg`, `2-prova-navy.jpg`
   - Başlık, 13 etiket, açıklama, fiyat: `ilan.txt` (kopyala-yapıştır)
   - Kategori: Clothing → Gender-Neutral Adult Clothing → Tops & Tees → T-shirts
   - "Who made it?": **I did** · "What is it?": **A finished product** · "When was it made?": **Made to order**
   - Kargo (Shipping): **Free shipping** seç, işlem süresi **2–5 business days**; Etsy başka bir şey sorarsa varsayılanı bırak.
     Kalıcı ücretsiz kargo profilini sonra ben API ile kuruyorum.
   - Bu ilan sadece mağazayı açmak için. **Mağaza açılır açılmaz Shop Manager → Listings → bu ilanı seç → Deactivate:** ürün henüz
     Printify'a bağlı değil, sipariş gelirse elle karşılanamaz. Printify bağlanınca silinir.
5. **How you'll get paid:** "Individual/Sole proprietor", Türk banka hesabın (IBAN). **Ad soyad kimlikteki ve bankadaki ile birebir aynı.**
6. **Billing:** kartın (açılış ücreti çıkarsa buradan alınır; Etsy ekranda gösterir).
7. **Security:** iki adımlı doğrulamayı aç. Etsy kimlik doğrulaması isterse yükle.
8. Açılınca **Shop Manager → Settings → Production partners → Add a production partner**:
   - Name: `Printify` · Location: United States · "About": *"Prints and ships our original designs on demand."*
9. **Policies:** iadeler: *"Made to order: no returns or exchanges, but we replace or refund any item that arrives damaged or misprinted
   (contact us within 30 days with a photo)."* — Printify'ın politikasıyla aynı.

## 3. Printify (~20 dk)
1. printify.com → Sign up (Free plan). **My account → Billing:** yurt dışı ve internet alışverişine açık kart ekle.
2. **My stores → Add new store → Etsy** → Etsy hesabınla bağla.
   **Store settings:** Order approval: **automatic (1 hour)**; "Publish as draft" kapalı kalsın (aktifleştirmeyi kod yapıyor).
3. **API token:** My account → **Connections** → Generate token → ad `matbaa`, tüm kapsamlar. Token'ı bana yazma;
   `Projeler\Matbaa\.env` dosyasında `PRINTIFY_TOKEN=` satırına yapıştır (dosya hazır: `notepad .env`).
4. Bana "Printify açıldı" de. `matbaa printify-kesif` Printify mağaza kimliğini `.env`'e kendisi yazar; ABD sağlayıcısını ben seçerim.
   Numune sipariş etmiyoruz (K-20): kartın çalıştığı ilk gerçek siparişte belli olur, ödeme düşmezse gecikme alarmı bildirim olarak gelir.

## 4. Etsy geliştirici uygulaması (~10 dk)
1. etsy.com/developers/register → uygulama oluştur:
   - Name: `HHP Shop Tools` (adda "Etsy" geçemez) · "Who will be the users": **Just myself or colleagues** · commercial: **No**
   - Callback URL: `http://localhost:3003/callback`
2. **Your apps** sayfasındaki **Keystring** ve **Shared secret** → `.env`: `ETSY_KEYSTRING=`, `ETSY_SHARED_SECRET=`
3. Bana "Etsy anahtarı hazır" de. Ben `scripts/etsy_yetki.py`'yi çalıştırırım; tarayıcıda Etsy izin sayfası açılır, **Allow Access**
   dersin. Betik mağaza kimliğini `.env`'e, Printify üretim ortağı kimliğini `config/yayin.toml`'a kendisi yazar.

## 5. Sonra ne olur
- Panelden ilk 10 tasarımı onaylarsın (`uv run matbaa panel` → http://127.0.0.1:8766, A onay / R ret).
- Günlük görev ısınma eğrisiyle yayınlar: ilk hafta günde 1 tasarım (3 ilan: tişört, sweatshirt, hoodie), sonra 2, 4, 6, 8.
- Etsy mesajları telefonuna gelir (Etsy Seller uygulamasını kur); hazır cevaplar `docs/hazir-cevaplar.md`'de.
- Haftada bir: panelde 10 dakika onay. Panelin üstündeki sarı **Dikkat** şeridi geciken sipariş, takılan ürün ve günlük koşu hatalarını gösterir.
- Günlük koşu bir hata ya da alarm bulursa ekranının köşesine Windows bildirimi düşer; her şey yolundaysa sessizdir.
