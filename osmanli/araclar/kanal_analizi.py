"""Kanal izlenme analizi: bütün yüklemeleri konu bankasıyla eşleştirir ve neyin işe yaradığını özetler.

Veri:
- YouTube Data API (youtube.readonly, mevcut token): izlenme, beğeni, yorum, yayın zamanı, süre.
- YouTube Analytics API (yt-analytics.readonly): izlenme süresi, ortalama izlenme yüzdesi, abone kazancı.
  Token bu izni içermiyorsa bu kısım atlanır ve raporda belirtilir.

Kıyaslamalar: Shorts ↔ uzun, kategori, bilinen ↔ az bilinen, video sonu (kapanış) türü,
Osmanlı ↔ Osmanlı dışı, kanca puanı, yayın günü. Ham sayılar küçük örneklemde yanıltıcıdır;
rapor her grubun video sayısını da yazar.

Çıktı: out/analiz/rapor.md, out/analiz/<tarih>.json (sonraki çalıştırmalarla kıyas için anlık görüntü)
Kullanım: python osmanli/araclar/kanal_analizi.py
"""
import datetime, json, os, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.dirname(HERE)
ROOT = os.path.dirname(OSM)
sys.path.insert(0, OSM)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "ortak"))
OUT = os.path.join(ROOT, "out", "analiz")
TR = datetime.timezone(datetime.timedelta(hours=3))
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
OSMANLI_DISI = re.compile(r"bizans|selçuklu|roma|memlük|timur|haçlı|selahaddin|hıttin|malazgirt|nika|justinianos|"
                          r"nizamülmülk|kubadabad|keykubad|porfir", re.I)


def norm(t):
    return re.sub(r"[^\w]+", " ", t.casefold()).strip()


def banka():
    """Başlık (emojisiz, küçük harf) → konu bilgisi."""
    import build as B
    eslesme = {}
    for kat in ("saray", "kisiler", "savaslar"):
        for k in json.load(open(os.path.join(OSM, "konular", f"{kat}.json"), encoding="utf-8")):
            for b in k["baslik"]:
                eslesme[norm(B.emojisiz(b))] = ("shorts", kat, k)
    for ad in os.listdir(os.path.join(OSM, "uzun")):
        if ad.endswith(".json") and ad != "sira.json":
            k = json.load(open(os.path.join(OSM, "uzun", ad), encoding="utf-8"))
            for b in k["baslik"]:
                eslesme[norm(b)] = ("uzun", "uzun", k)
    return eslesme


def sure_sn(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    return sum(int(x or 0) * c for x, c in zip(m.groups(), (3600, 60, 1))) if m else 0


def videolari_al(yt):
    kanal = yt.channels().list(part="contentDetails,statistics,snippet", mine=True).execute()["items"][0]
    pl = kanal["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, tok = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=pl, maxResults=50, pageToken=tok).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        tok = r.get("nextPageToken")
        if not tok:
            break
    videolar = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,contentDetails,status", id=",".join(ids[i:i + 50])).execute()
        videolar += r["items"]
    return kanal, videolar


def analytics_al(ids, bas, bit):
    """Video başına izlenme süresi verisi; izin yoksa (None, hata)."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        cr = Credentials(token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                         client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
        ya = build("youtubeAnalytics", "v2", credentials=cr, cache_discovery=False)
        sonuc = {}
        for i in range(0, len(ids), 40):
            r = ya.reports().query(ids="channel==MINE", startDate=bas, endDate=bit,
                                   metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,shares",
                                   dimensions="video", filters="video==" + ",".join(ids[i:i + 40]), maxResults=200).execute()
            basl = [h["name"] for h in r["columnHeaders"]]
            for satir in r.get("rows", []):
                d = dict(zip(basl, satir))
                sonuc[d["video"]] = d
        return sonuc, None
    except Exception as e:
        return None, str(e)[:300]


def ilk_30sn_al(uzunlar):
    """Uzun videolarda 30. saniyede hâlâ izleyenlerin oranı (audienceWatchRatio, elapsedVideoTimeRatio)."""
    sonuc = {}
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        cr = Credentials(token=None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                         client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"])
        ya = build("youtubeAnalytics", "v2", credentials=cr, cache_discovery=False)
        for k in uzunlar:
            if not k.get("sure_sn"):
                continue
            r = ya.reports().query(ids="channel==MINE", startDate=k["yayin"][:10],
                                   endDate=datetime.date.today().isoformat(), metrics="audienceWatchRatio",
                                   dimensions="elapsedVideoTimeRatio", filters=f"video=={k['id']}").execute()
            satirlar = sorted(r.get("rows", []))
            hedef = 30 / k["sure_sn"]
            uygun = [s for s in satirlar if s[0] >= hedef]
            if uygun:
                sonuc[k["id"]] = round(uygun[0][1] * 100)
    except Exception as e:
        print("İlk 30 sn verisi alınamadı:", str(e)[:200])
    return sonuc


def ozet(liste, anahtar="izlenme"):
    v = [x[anahtar] for x in liste]
    if not v:
        return "–"
    return f"{len(v)} video · ort. {statistics.mean(v):,.0f} · medyan {statistics.median(v):,.0f}".replace(",", ".")


def grup_tablosu(baslik, kayitlar, fn, anahtar="izlenme"):
    gruplar = {}
    for k in kayitlar:
        g = fn(k)
        if g is not None:
            gruplar.setdefault(g, []).append(k)
    satir = [f"\n### {baslik}\n", "| Grup | Video | Ortalama | Medyan | Gün başı (medyan) |", "|---|---|---|---|---|"]
    for g, l in sorted(gruplar.items(), key=lambda x: -statistics.median([k[anahtar] for k in x[1]])):
        satir.append(f"| {g} | {len(l)} | {statistics.mean([k[anahtar] for k in l]):,.0f} | "
                     f"{statistics.median([k[anahtar] for k in l]):,.0f} | {statistics.median([k['gunluk'] for k in l]):,.1f} |".replace(",", "."))
    return satir


def main():
    from upload import youtube
    import build as B
    from hookscore_tr import puanla
    yt = youtube()
    kanal, videolar = videolari_al(yt)
    eslesme = banka()
    simdi = datetime.datetime.now(datetime.timezone.utc)
    kayitlar = []
    for v in videolar:
        sn, st = v["snippet"], v["statistics"]
        yay = datetime.datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        gun = max(0.5, (simdi - yay).total_seconds() / 86400)
        seri = re.search(r"\s*\|\s*([^|]*#\d+)\s*$", sn["title"])   # "... | Saray Sırları #22"
        bilgi = eslesme.get(norm(B.emojisiz(sn["title"][:seri.start()] if seri else sn["title"])))
        sure = sure_sn(v["contentDetails"].get("duration"))
        tur = bilgi[0] if bilgi else ("shorts" if sure <= 180 else "uzun")
        k = {"id": v["id"], "baslik": sn["title"], "yayin": yay.astimezone(TR).strftime("%Y-%m-%d %H:%M"),
             "gun_adi": GUNLER[yay.astimezone(TR).weekday()], "saat": yay.astimezone(TR).strftime("%H"),
             "tur": tur, "kategori": bilgi[1] if bilgi else "?", "konu": bilgi[2]["id"] if bilgi else None,
             "sure_sn": sure, "izlenme": int(st.get("viewCount", 0)), "begeni": int(st.get("likeCount", 0)),
             "yorum": int(st.get("commentCount", 0)), "gun": round(gun, 1), "seri": bool(seri)}
        k["gunluk"] = k["izlenme"] / gun
        if bilgi:
            konu = bilgi[2]
            k["bilinirlik"] = konu.get("tur", "-") if tur == "shorts" else "-"
            k["osmanli_disi"] = bool(OSMANLI_DISI.search(" ".join(konu.get("etiketler", [])) + " " + konu["baslik"][0]))
            k["kanca_puani"] = puanla(" ".join(re.split(r"(?<=[.!?])\s+", konu["kanca"])[:2]))["karar"]
            if tur == "shorts":
                seed = int(yay.astimezone(TR).strftime("%Y%m%d"))
                try:
                    k["kapanis"] = B.kapanis_sec(konu, bilgi[1], seed)[2]
                except Exception:
                    k["kapanis"] = "?"
                k["animasyonlu"] = sum(1 for s in konu["sahneler"] if s.get("anim"))
        kayitlar.append(k)
    kayitlar.sort(key=lambda k: k["yayin"])

    ilk = min((k["yayin"][:10] for k in kayitlar), default=simdi.strftime("%Y-%m-%d"))
    an, hata = analytics_al([k["id"] for k in kayitlar], ilk, simdi.strftime("%Y-%m-%d"))
    if an:
        for k in kayitlar:
            a = an.get(k["id"], {})
            k["izlenme_yuzdesi"] = round(a.get("averageViewPercentage", 0), 1)
            k["ort_izlenme_sn"] = round(a.get("averageViewDuration", 0))
            k["abone"] = int(a.get("subscribersGained", 0))
            k["paylasim"] = int(a.get("shares", 0))
            k["abone_1000"] = round(k["abone"] * 1000 / k["izlenme"], 2) if k["izlenme"] else 0
        ilk30 = ilk_30sn_al([k for k in kayitlar if k["tur"] == "uzun"])
        for k in kayitlar:
            if k["id"] in ilk30:
                k["ilk_30sn"] = ilk30[k["id"]]

    sh = [k for k in kayitlar if k["tur"] == "shorts"]
    uz = [k for k in kayitlar if k["tur"] == "uzun"]
    ks = kanal["statistics"]
    r = [f"# Sarayın Gölgesi – kanal analizi ({simdi.astimezone(TR).strftime('%d.%m.%Y %H:%M')})\n",
         f"Abone: **{ks.get('subscriberCount', '?')}** · Toplam izlenme: **{ks.get('viewCount', '?')}** · "
         f"Video: **{len(kayitlar)}** ({len(sh)} Shorts, {len(uz)} uzun)\n",
         f"- Shorts: {ozet(sh)}", f"- Uzun: {ozet(uz)}",
         f"- Eşleşmeyen video: {sum(1 for k in kayitlar if not k['konu'])}"]
    if an:
        if sh:
            r.append(f"- Shorts ortalama izlenme yüzdesi: %{statistics.mean([k['izlenme_yuzdesi'] for k in sh]):.0f}")
        if uz:
            r.append(f"- Uzun video ortalama izlenme yüzdesi: %{statistics.mean([k['izlenme_yuzdesi'] for k in uz]):.0f}, "
                     f"ortalama izlenme {statistics.mean([k['ort_izlenme_sn'] for k in uz]) / 60:.1f} dk")
        r.append(f"- Videolardan gelen abone: {sum(k['abone'] for k in kayitlar)}")
        for ad, l in (("Shorts", sh), ("Uzun", uz)):
            iz = sum(k["izlenme"] for k in l)
            if iz:
                r.append(f"- {ad}: 1.000 izlenme başına abone **{sum(k['abone'] for k in l) * 1000 / iz:.2f}**")
        otuz = [k["ilk_30sn"] for k in uz if "ilk_30sn" in k]
        if otuz:
            r.append(f"- Uzun videolarda 30. saniyede kalan izleyici: medyan %{statistics.median(otuz):.0f}")
    else:
        r.append(f"\n> İzlenme süresi / izlenme yüzdesi alınamadı (YouTube Analytics izni yok): `{hata}`\n"
                 "> Bunun için YT_REFRESH_TOKEN'ı `yt-analytics.readonly` izniyle yeniden almak gerekir.")
    # 2 günden genç videolar karşılaştırmayı bozar: gruplarda yalnızca ≥2 günlük Shorts
    olgun = [k for k in sh if k["gun"] >= 2]
    r.append(f"\n## Shorts kıyasları (en az 2 günlük {len(olgun)} Shorts)")
    r += grup_tablosu("Kategori", olgun, lambda k: k["kategori"])
    r += grup_tablosu("Bilinen ↔ az bilinen", olgun, lambda k: k.get("bilinirlik"))
    r += grup_tablosu("Osmanlı ↔ Osmanlı dışı", olgun, lambda k: ("Osmanlı dışı" if k.get("osmanli_disi") else "Osmanlı") if k["konu"] else None)
    r += grup_tablosu("Video sonu (kapanış)", olgun, lambda k: k.get("kapanis"))
    r += grup_tablosu("Kanca puanı", olgun, lambda k: None if "kanca_puani" not in k else
                      ("72+ GÜÇLÜ" if k["kanca_puani"] >= 72 else "55-71 İDARE EDER" if k["kanca_puani"] >= 55 else "<55 ZAYIF"))
    r += grup_tablosu("Animasyonlu sahne sayısı", olgun, lambda k: None if "animasyonlu" not in k else
                      ("0" if not k["animasyonlu"] else "1-2" if k["animasyonlu"] <= 2 else "3-4"))
    r += grup_tablosu("Yayın günü", olgun, lambda k: k["gun_adi"])
    if an:
        r += grup_tablosu("Kategori – izlenme yüzdesi", olgun, lambda k: k["kategori"], "izlenme_yuzdesi")
        r += grup_tablosu("Kategori – 1.000 izlenme başına abone", olgun, lambda k: k["kategori"], "abone_1000")
        r += grup_tablosu("Seri etiketi (Saray Sırları #N vb.)", olgun, lambda k: "seri" if k.get("seri") else "serisiz")

    def tablo(liste, baslik):
        s = [f"\n## {baslik}\n", "| Yayın | Başlık | İzlenme | Gün başı | Beğeni | Yorum" + (" | İzlenme % | Abone" if an else "") + " |",
             "|---|---|---|---|---|---" + ("|---|---" if an else "") + "|"]
        for k in liste:
            s.append(f"| {k['yayin'][5:]} | [{k['baslik'][:48]}](https://youtu.be/{k['id']}) | {k['izlenme']} | {k['gunluk']:.0f} | "
                     f"{k['begeni']} | {k['yorum']}" + (f" | {k['izlenme_yuzdesi']} | {k['abone']}" if an else "") + " |")
        return s
    r += tablo(sorted(olgun, key=lambda k: -k["gunluk"])[:8], "En iyi Shorts (gün başı izlenme)")
    r += tablo(sorted(olgun, key=lambda k: k["gunluk"])[:8], "En zayıf Shorts (gün başı izlenme)")
    r += tablo(uz, "Uzun videolar")
    if any("ilk_30sn" in k for k in uz):
        r += ["\n### Uzun videolar – ilk 30 saniye\n", "| Yayın | Başlık | 30. saniyede kalan | Ort. izlenme |", "|---|---|---|---|"]
        r += [f"| {k['yayin'][5:]} | {k['baslik'][:48]} | %{k['ilk_30sn']} | {k['ort_izlenme_sn'] / 60:.1f} dk |"
              for k in uz if "ilk_30sn" in k]
    r += tablo(sorted(kayitlar, key=lambda k: k["yayin"], reverse=True), "Bütün videolar (yeniden eskiye)")

    os.makedirs(OUT, exist_ok=True)
    metin = "\n".join(r) + "\n"
    with open(os.path.join(OUT, "rapor.md"), "w", encoding="utf-8") as f:
        f.write(metin)
    with open(os.path.join(OUT, simdi.astimezone(TR).strftime("%Y-%m-%d") + ".json"), "w", encoding="utf-8") as f:
        json.dump({"zaman": simdi.isoformat(), "kanal": ks, "analytics": bool(an), "videolar": kayitlar}, f, ensure_ascii=False, indent=1)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(metin)
    print(metin)


if __name__ == "__main__":
    main()
