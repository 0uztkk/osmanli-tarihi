# Osmanlı tarihi – otomatik YouTube Shorts

Her gün 3 Shorts: 11:40 saray ve İstanbul, 17:25 tarihten portreler, 20:10 savaşlar ve isyanlar (TR saati).
Google TTS seslendirme, Wikimedia Commons'tan elle seçilmiş kamu malı tablolar, YouTube Data API ile yükleme.

- `osmanli/konular/*.json` – 107 konu (kanca, 4 sahne, kapak yazısı, başlık kalıpları, seçilmiş görseller)
- `osmanli/build.py` – videoyu üretir (`out/video.mp4`, `out/meta.json`)
- `osmanli/yukle.py` – "çocuklara yönelik değil" olarak yükler; yanlış kanal ve sessiz videoya karşı korumalı
- `osmanli/yorumlar.py` – günlük yorum raporu (yt-comment), hiçbir yanıtı kendisi göndermez
- `osmanli/araclar/` – Türkçe kanca puanlama, başlık/kapak denetimi, bölüm doğrulayıcı, görsel seçim aracı
- `osmanli/voice.md` – kanalın ses profili
- `ortak/` – seslendirme ve YouTube yükleme modülleri (Mina ile Efe deposundan uyarlandı)

Kurulum: `osmanli/KURULUM.md`
