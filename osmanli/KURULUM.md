# Osmanlı kanalı – kurulum adımları

Sırayla yapılacak. Her adımın sonunda ne göreceğin yazılı; takılırsan o adımın numarasını söylemen yeterli.

## 1. Depo ✅
`0uztkk/osmanli-tarihi` açıldı, kod burada. Mina ile Efe'nin koduna dokunulmadı.

## 2. YouTube kanalını aç (5 dk)
YouTube → profil resmi → **Kanal oluştur** (Mina'yı açtığın Google hesabıyla, "marka hesabı" olarak).
- Ad önerileri: "Osmanlı Hikâyeleri", "Bir Osmanlı Hikâyesi", "Tarihin Kaosu" – istediğini seç.
- YouTube Studio → Ayarlar → Yükleme varsayılanları → Kitle: **Hayır, çocuklara özel değil**.
- Ayarlar → Topluluk → yorumlar **açık** (yorum raporu buna göre çalışıyor).

## 3. Google Cloud'u kontrol et (2 dk)
Mina'nın kullandığı **aynı** Google Cloud projesi kullanılacak (yeni proje açma; yeni projeler denetimden
geçene kadar videoları "özel" kilitleyebiliyor, kota da yetiyor).
- console.cloud.google.com → doğru proje → **APIs & Services → OAuth consent screen**
- Yayın durumu **In production** olmalı. "Testing" yazıyorsa **Publish app** de; yoksa token 7 günde bir ölür.

## 4. Yeni kanal için token al (5 dk)
Mina için token'ı nasıl aldıysan aynısını yap, tek fark: hesap/kanal seçme ekranında **yeni kanalı** seç.
İzinler: `youtube.upload`, `youtube.readonly`, `youtube.force-ssl` (sonuncusu yorum raporu için).
Nasıl aldığını hatırlamıyorsan söyle, birlikte adım adım yaparız.

## 5. Secret'ları ekle (3 dk)
Yeni depo → **Settings → Secrets and variables → Actions**
- Secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `GCP_TTS_KEY` (Mina'dakilerle aynı değerler; GitHub eski
  değeri göstermez, Google Cloud → Credentials sayfasından kopyalarsın), `YT_REFRESH_TOKEN` (4. adım, YENİ kanalın token'ı).
- Variables sekmesi: `KANAL_ADI` = kanalın adı (token yanlış kanala aitse yükleme durur).

## 6. Deneme (5 dk)
Actions → **Osmanli tarihi video** → Run workflow → `privacy: private` → çalıştır.
YouTube Studio'da özel video görünecek. Beğenirsen hiçbir şey yapma; zamanlanmış çalıştırmalar
her gün 11:40 (saray), 17:25 (portreler), 20:10 (savaşlar/isyanlar) herkese açık yükler.

## Neler hazır
- 107 konu: 35 savaş/isyan, 38 saray/İstanbul, 34 portre. 16'sı az bilinen kaotik olaylar
  (Alemdar, Zenta, 1876, Çırağan baskını, Babıali baskını...), bilinen konuların arasına serpiştirilmiş.
- Her sahnenin görseli elle seçilmiş kamu malı eser; uygun görsel olmayan 26 sahne süslü yazılı sahne.
- YouTube Agent Skill kuralları: Türkçe kanca puanlama (`araclar/hookscore_tr.py`), başlık + kapak yazısı
  denetimi (`araclar/title_tr.py`), aranan kelimeleri taşıyan açıklama, yorum raporu (`yorumlar.py`,
  her gün 21:37), uzun video gelirse bölüm doğrulayıcı (`araclar/bolumler.py`), ses profili (`voice.md`).
