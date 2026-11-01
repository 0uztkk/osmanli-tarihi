"""yt-comment: son videolardaki yorumları ayırır ve yanıt TASLAKLARI üretir. Hiçbir şey yayınlamaz.

Kurallar (Jakeschincariol/youtube-agent-skill › yt-comment):
- Önce ayır, sonra yaz: Sorular / Düzeltmeler / Övgüler / Kışkırtma. Her yığının sayısı söylenir.
- Sorular yanıtlanır ve tekrar eden sorular sonraki video konusu olarak not edilir.
- Düzeltmeler: haklıysa açıkça teşekkür edilir. Doğrulanamayan bir olgu üzerine tartışılmaz.
- Övgü: birkaçına, yorumdaki somut bir şeye değinerek kısa yanıt. Hepsine aynı "teşekkürler" yazılmaz.
- Kışkırtma: yanıt verilmez.
- Yanıt 30 kelimenin altında; söz verilmemiş video için söz verilmez.
- Sabitlenecek tek yorum: en çok kişinin sorduğu soru (en güzel yorum değil).

Kullanım: python osmanli/yorumlar.py [gün=3]
Çıktı: GitHub Actions özet sayfası + out/yorum_raporu.md
Not: Okumak için youtube.readonly izni yeterli; yanıtları sen YouTube Studio'dan gönderirsin.
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "ortak"))

SORU = re.compile(r"\?|\b(neden|niye|nasıl|kim|hangi|ne zaman|nerede|kaç|mı|mi|mu|mü)\b", re.I)
DUZELTME = re.compile(r"\b(yanlış|hata|aslında|doğrusu|değil|o değil|yanlis|hatalı|kaynak|uydurma|öyle değil)\b", re.I)
OVGU = re.compile(r"\b(harika|güzel|süper|mükemmel|eline sağlık|emeğine sağlık|teşekkür|bayıldım|çok iyi|devam|efsane)\b", re.I)
KISKIRTMA = re.compile(r"\b(aptal|salak|yalancı|hain|rezil|siktir|amk|aq|gerizekalı|mal|şerefsiz|ibne)\b", re.I)
DUR = set("bir bu şu ve ile de da ki mi mı mu mü ne çok daha en için gibi ama o ben sen biz siz onlar var yok".split())


def ayir(metin):
    if KISKIRTMA.search(metin):
        return "kiskirtma"
    if DUZELTME.search(metin):
        return "duzeltme"
    if SORU.search(metin):
        return "soru"
    if OVGU.search(metin):
        return "ovgu"
    return "diger"


def anahtar(metin):
    return frozenset(w for w in re.findall(r"[a-zçğıöşü]{4,}", metin.lower()) if w not in DUR)


def taslak(yigin, metin, konu_basligi):
    """30 kelimenin altında, ilk cümlede cevap; bilgi uydurmaz, cevabı bilinmeyen soruyu işaretler."""
    if yigin == "duzeltme":
        return ("[KONTROL ET] Haklıysa: 'Haklısın, düzelttiğin için teşekkürler; açıklamaya not düştük.' "
                "Kaynağını doğrulayamıyorsan yanıt verme.")
    if yigin == "soru":
        return f"[CEVABI SEN YAZ, ≤30 kelime] Soru '{konu_basligi}' videosuyla ilgili. İlk cümlede doğrudan cevap ver."
    if yigin == "ovgu":
        kelime = next((w for w in re.findall(r"[a-zçğıöşü]{5,}", metin.lower()) if w not in DUR), "")
        return f"Çok sevindik! {kelime.capitalize() + ' kısmını' if kelime else 'Bu kısmı'} biz de çok sevmiştik."
    return ""


def main():
    gun = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", cache_discovery=False, credentials=Credentials(
        token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"]))
    kanal = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    yuklenen = kanal["contentDetails"]["relatedPlaylists"]["uploads"]
    videolar = yt.playlistItems().list(part="snippet", playlistId=yuklenen, maxResults=gun * 3).execute()["items"]

    rapor, tekrar = ["# Yorum raporu (yt-comment)\n"], collections.Counter()
    toplam = collections.Counter()
    for v in videolar:
        vid, baslik = v["snippet"]["resourceId"]["videoId"], v["snippet"]["title"]
        try:
            yorumlar = yt.commentThreads().list(part="snippet", videoId=vid, maxResults=100,
                                                order="relevance", textFormat="plainText").execute()["items"]
        except Exception as e:
            rapor.append(f"\n## {baslik}\nYorumlar okunamadı: {e}\n"); continue
        yiginlar = collections.defaultdict(list)
        for y in yorumlar:
            s = y["snippet"]["topLevelComment"]["snippet"]
            metin, begeni = s["textDisplay"].strip(), s.get("likeCount", 0)
            yg = ayir(metin)
            yiginlar[yg].append((begeni, metin, s.get("authorDisplayName", "")))
            toplam[yg] += 1
            if yg == "soru":
                tekrar[anahtar(metin)] += 1 + begeni
        rapor.append(f"\n## {baslik}\nhttps://youtube.com/shorts/{vid}\n")
        rapor.append(f"Soru: {len(yiginlar['soru'])} · Düzeltme: {len(yiginlar['duzeltme'])} · "
                     f"Övgü: {len(yiginlar['ovgu'])} · Kışkırtma (yanıtlama): {len(yiginlar['kiskirtma'])} · "
                     f"Diğer: {len(yiginlar['diger'])}\n")
        sorular = sorted(yiginlar["soru"], reverse=True)
        if sorular:
            rapor.append(f"**Sabitle:** “{sorular[0][1][:160]}” – en çok beğenilen soru; başkaları da merak ediyor.\n")
        for yg, n in (("duzeltme", 10), ("soru", 8), ("ovgu", 3)):
            for begeni, metin, kim in sorted(yiginlar[yg], reverse=True)[:n]:
                rapor.append(f"- [{yg}] ({begeni}👍) {kim}: “{metin[:200]}”\n  - Taslak: {taslak(yg, metin, baslik)}")
    konu_onerisi = [" ".join(sorted(k)) for k, n in tekrar.most_common(5) if n >= 2 and k]
    rapor.insert(1, f"Toplam – Soru: {toplam['soru']}, Düzeltme: {toplam['duzeltme']}, Övgü: {toplam['ovgu']}, "
                    f"Kışkırtma: {toplam['kiskirtma']}\n")
    if konu_onerisi:
        rapor.insert(2, "**Tekrar eden sorular (sonraki video konusu olabilir):** " + " | ".join(konu_onerisi) + "\n")
    rapor.append("\n---\nHiçbir yanıt otomatik gönderilmez. Gönder mi, değiştir mi?\n")
    metin = "\n".join(rapor)
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out", "yorum_raporu.md"), "w", encoding="utf-8") as f:
        f.write(metin)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(metin)
    print(metin)


if __name__ == "__main__":
    main()
