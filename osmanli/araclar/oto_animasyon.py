"""Animasyonu olmayan Shorts konularına harita/takvim/mühür sahneleri ekler.

Her konu için YERLER tablosunda bir yer (ve gerekiyorsa rota) tanımlıdır:
  - 1. sahne → harita: başkentten hedefe ordu ya da filo rotası (savaşlar), ya da şehirde nabız atan işaret.
  - görselsiz ("-") sahneler → yıl ise çevrilen takvim, değilse haritada mühür.
Elle yazılmış animasyonu olan konulara (stil: animasyon) dokunmaz.
Kullanım: python osmanli/araclar/oto_animasyon.py
"""
import json, math, os, re

KOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "konular")

SOGUT, BURSA, EDIRNE, IST = (30.18, 40.02), (29.06, 40.19), (26.56, 41.68), (28.98, 41.01)
TOPKAPI = ("Topkapı Sarayı", 28.983, 41.0115)
ATMEYDANI = ("Atmeydanı", 28.975, 41.006)
DENIZ_YOLU = [[28.98, 41.0], [27.4, 40.6], [26.4, 40.1], [25.6, 39.4], [25.2, 37.6], [24.6, 36.4]]   # İstanbul → Ege çıkışı

# id: (ad, lon, lat, tür[, rota])   tür: sehir | yer | kara | deniz
YERLER = {
    # saray
    "topkapi": TOPKAPI + ("sehir",), "saray-mutfagi": TOPKAPI + ("sehir",), "kardes-katli": TOPKAPI + ("sehir",),
    "dilsizler": TOPKAPI + ("sehir",), "hirka-i-saadet": TOPKAPI + ("sehir",), "kosem": TOPKAPI + ("sehir",),
    "sultan-ibrahim": TOPKAPI + ("sehir",), "cesnigir": TOPKAPI + ("sehir",), "tugra": TOPKAPI + ("sehir",),
    "kutuphane-ahmed3": TOPKAPI + ("sehir",), "cuma-selamligi": ("Ayasofya", 28.98, 41.0086, "sehir"),
    "cinar-vakasi-1656": ATMEYDANI + ("sehir",), "sunnet-1582": ATMEYDANI + ("sehir",),
    "edirne-vakasi-1703": ("Edirne", 26.56, 41.68, "kara"),
    "lale-devri": ("Sadabad", 28.97, 41.08, "sehir"), "kahve": ("Tahtakale", 28.968, 41.016, "sehir"),
    "yeniceri-kazani": ("Et Meydanı", 28.952, 41.009, "sehir"), "ciragan-baskini-1878": ("Çırağan Sarayı", 29.017, 41.044, "sehir"),
    "mehter": ("İstanbul", 28.98, 41.01, "yer"), "surname-vehbi": ("Okmeydanı", 28.962, 41.045, "sehir"),
    "uc-padisahli-yil-1876": ("Dolmabahçe", 29.0, 41.039, "sehir"), "bostancilar": ("Boğaziçi", 29.05, 41.1, "sehir"),
    "kaftanlar": ("Bursa", 29.06, 40.19, "yer"), "yildiz-suikasti-1905": ("Yıldız Camii", 29.01, 41.05, "sehir"),
    "hurrem": ("Haseki Külliyesi", 28.94, 41.009, "sehir"), "mahya": ("Sultanahmet Camii", 28.977, 41.005, "sehir"),
    "deprem-1509": ("İstanbul", 28.98, 41.01, "yer"), "dolmabahce": ("Dolmabahçe", 29.0, 41.039, "sehir"),
    "mihrimah": ("Üsküdar", 29.016, 41.027, "sehir"),
    "bellini-portresi": ("Venedik", 12.33, 45.44, "deniz",
                         [[12.4, 45.3], [14.5, 43.8], [18.6, 40.1], [21.0, 36.9], [24.6, 36.4], [25.2, 37.6], [26.4, 40.1], [28.95, 41.0]]),
    "matbaa": ("İstanbul", 28.98, 41.01, "yer"), "yangin-1660": ("Yeni Cami", 28.971, 41.017, "sehir"),
    "saltanat-kayiklari": ("Boğaziçi", 29.05, 41.1, "sehir"), "valide-alayi": ("Eski Saray", 28.964, 41.011, "sehir"),
    "kilic-kusanma": ("Eyüp Sultan", 28.934, 41.048, "sehir"),
    # kişiler
    "osman-gazi": ("Söğüt", 30.18, 40.02, "yer"), "yavuz-babasini-indirdi": ("Çorlu", 27.8, 41.16, "yer"),
    "orhan-gazi": ("Bursa", 29.06, 40.19, "yer"),
    "ikinci-bayezid": ("İstanbul", 28.98, 41.01, "deniz",
                       [[-4.42, 36.72], [-1.0, 37.4], [5.0, 37.6], [11.0, 37.6], [16.5, 36.6], [22.0, 36.2], [24.6, 36.4], [25.2, 37.6], [26.4, 40.1], [28.95, 41.0]]),
    "yavuz-sair": ("İstanbul", 28.98, 41.01, "yer"), "kanuni-muhibbi": ("İstanbul", 28.98, 41.01, "yer"),
    "sehzade-bayezid": ("Konya", 32.48, 37.87, "kara", [[32.48, 37.87], [38.0, 38.6], [44.0, 38.0], [50.0, 36.27]]),
    "sokullu": ("Vişegrad", 19.29, 43.78, "yer"), "birinci-ahmed": ("Sultanahmet Camii", 28.977, 41.005, "sehir"),
    "genc-osman": ("Hotin", 26.49, 48.51, "kara"),
    "dorduncu-murad": ("Bağdat", 44.36, 33.31, "kara", [[28.98, 41.01], [36.0, 39.5], [44.51, 40.18], [44.4, 36.5], [44.36, 33.35]]),
    "avci-mehmed": ("Edirne", 26.56, 41.68, "yer"), "ucuncu-selim": TOPKAPI + ("sehir",),
    "ikinci-mahmud": ("Et Meydanı", 28.952, 41.009, "sehir"),
    "abdulmecid-irlanda": ("İrlanda", -6.35, 53.72, "deniz",
                           [[28.95, 41.0], [26.4, 40.1], [25.2, 37.6], [22.0, 36.0], [15.0, 36.8], [10.0, 37.8], [-5.6, 36.0], [-9.6, 38.7],
                            [-9.6, 43.2], [-5.5, 48.3], [-6.3, 51.6], [-6.3, 53.7]]),
    "patrona-halil": ("Bayezid Meydanı", 28.964, 41.0106, "sehir"),
    "abdulaziz": ("Paris", 2.35, 48.86, "yol", [[28.98, 41.01], [16.37, 48.21], [2.35, 48.86], [-0.13, 51.5]],
                  [("Viyana", 16.37, 48.21), ("Londra", -0.13, 51.5)]),
    "abdulhamid": ("Medine", 39.6, 24.47, "yol", [[36.29, 33.51], [36.1, 31.0], [36.6, 28.4], [38.0, 26.6], [39.6, 24.5]], [("Şam", 36.29, 33.51)]),
    "vahdettin": ("San Remo", 7.78, 43.82, "deniz",
                  [[28.95, 41.0], [26.4, 40.1], [25.2, 37.6], [22.0, 36.0], [14.51, 35.9], [10.5, 39.5], [7.8, 43.7]], [("Malta", 14.51, 35.9)]),
    "mimar-sinan": ("Süleymaniye", 28.964, 41.016, "sehir"), "piri-reis": ("Gelibolu", 26.67, 40.41, "yer"),
    "evliya-celebi": ("İstanbul", 28.98, 41.01, "yol", [[28.98, 41.01], [16.37, 48.21]], [("Viyana", 16.37, 48.21), ("Kahire", 31.24, 30.04), ("Bağdat", 44.36, 33.31)],
                      [[[28.98, 41.01], [31.24, 30.1]], [[28.98, 41.01], [44.3, 33.35]]]),
    "hezarfen": ("Galata Kulesi", 28.974, 41.0256, "yol", [[28.974, 41.0256], [29.0, 41.026], [29.02, 41.022]], [("Üsküdar", 29.02, 41.022)]),
    "babiali-baskini-1913": ("Babıali", 28.977, 41.012, "sehir"), "takiyuddin": ("Tophane", 28.982, 41.027, "sehir"),
    "barbaros": ("Cezayir", 3.06, 36.75, "deniz", [[26.55, 39.1], [24.8, 36.5], [20.0, 36.0], [14.0, 37.0], [10.5, 37.4], [3.1, 36.8]], [("Midilli", 26.55, 39.1)]),
    "cem-sultan": ("Rodos", 28.22, 36.43, "yol", [[29.06, 40.19], [28.22, 36.5], [12.5, 41.9]], [("Bursa", 29.06, 40.19), ("Roma", 12.5, 41.9)]),
    "matrakci-nasuh": ("İstanbul", 28.98, 41.01, "yer"), "tulumbacilar": ("İstanbul", 28.98, 41.01, "yer"),
    "tunel-1875": ("Karaköy", 28.976, 41.022, "yol", [[28.976, 41.022], [28.974, 41.03]], [("Beyoğlu", 28.974, 41.03)]),
    "sehzade-mustafa": ("Ereğli", 34.05, 37.51, "yol", [[35.83, 40.65], [34.05, 37.51]], [("Amasya", 35.83, 40.65)]),
    # savaşlar
    "istanbul-fethi": ("İstanbul", 28.98, 41.01, "kara", [[26.56, 41.68], [27.8, 41.3], [28.93, 41.03]], [("Edirne", 26.56, 41.68)]),
    "zenta-1697": ("Zenta", 20.08, 45.93, "kara"), "kosova-1389": ("Kosova", 21.17, 42.66, "kara"),
    "nigbolu": ("Niğbolu", 24.9, 43.7, "kara"), "nizip-donanma-1839": ("Nizip", 37.79, 37.01, "kara"),
    "ankara-1402": ("Ankara", 32.85, 39.93, "kara", [[29.06, 40.19], [31.0, 40.0], [32.85, 39.93]]),
    "varna": ("Varna", 27.91, 43.21, "kara"), "belgrad-1456": ("Belgrad", 20.46, 44.82, "kara"),
    "otlukbeli": ("Otlukbeli", 40.1, 40.2, "kara"), "rodos": ("Rodos", 28.22, 36.43, "deniz"),
    "malta": ("Malta", 14.51, 35.9, "deniz"), "kabakci-1807": ("Rumeli Kavağı", 29.08, 41.18, "sehir"),
    "zigetvar": ("Zigetvar", 17.8, 46.05, "kara"), "viyana-1529": ("Viyana", 16.37, 48.21, "kara"),
    "viyana-1683": ("Viyana", 16.37, 48.21, "kara"), "hacova": ("Haçova", 20.7, 47.83, "kara"),
    "alemdar-1808": ("İstanbul", 28.98, 41.01, "kara", [[25.97, 43.85], [26.3, 42.6], [26.56, 41.7], [27.8, 41.3], [28.95, 41.02]], [("Rusçuk", 25.97, 43.85)]),
    "canakkale-18-mart": ("Çanakkale", 26.4, 40.15, "deniz-dusman", [[25.3, 39.6], [25.9, 39.9], [26.25, 40.03]]),
    "kutulamare": ("Kut", 45.83, 32.5, "yer"), "trablusgarp-1551": ("Trablusgarp", 13.18, 32.89, "deniz"),
    "cerbe": ("Cerbe", 10.86, 33.8, "deniz"), "kibris-fethi": ("Kıbrıs", 33.36, 35.17, "deniz"),
    "kandiye": ("Kandiye", 25.14, 35.34, "deniz"),
    "31-mart-1909": ("İstanbul", 28.98, 41.01, "kara", [[22.94, 40.64], [24.4, 40.95], [26.0, 40.85], [27.5, 41.0], [28.9, 41.02]], [("Selanik", 22.94, 40.64)]),
    "prut": ("Prut", 28.07, 46.67, "kara"), "cesme": ("Çeşme", 26.3, 38.32, "yer"),
    "navarin": ("Navarin", 21.67, 36.91, "deniz"), "plevne": ("Plevne", 24.62, 43.42, "kara"),
    "bursa-fethi": ("Bursa", 29.06, 40.19, "kara", [[30.18, 40.02], [29.7, 40.1], [29.1, 40.18]], [("Söğüt", 30.18, 40.02)]),
    "belgrad-1521": ("Belgrad", 20.46, 44.82, "kara"),
}


def yil_bul(konu):
    for m in [s["yazi"] for s in konu["sahneler"]] + [konu["kanca"]] + konu.get("etiketler", []):
        r = re.search(r"\b(1[0-9]{3})\b", m)
        if r:
            return int(r.group(1))
    return None


def baskent(yil):
    if yil is None or yil >= 1453:
        return ("İstanbul",) + IST
    if yil >= 1365:
        return ("Edirne",) + EDIRNE
    if yil >= 1326:
        return ("Bursa",) + BURSA
    return ("Söğüt",) + SOGUT


def cerceve(noktalar, en_az):
    lons, lats = [p[0] for p in noktalar], [p[1] for p in noktalar]
    lc, la = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
    cos = math.cos(math.radians(la))
    gen = max(en_az, (max(lons) - min(lons)) * 1.5, (max(lats) - min(lats)) * 1.7 / (cos * 1.78))
    gorunen_lat = gen * cos * 1.78
    return [round(lc, 3), round(la + gorunen_lat * 0.12, 3)], round(gen, 3)


def damga_yazisi(y):
    y = y.strip()
    k = y.split()
    if len(y) > 10 and len(k) >= 2:
        orta = len(k) // 2 if len(k) > 2 else 1
        return " ".join(k[:orta]) + "\n" + " ".join(k[orta:])
    return y


def giris_haritasi(konu, kat, yer):
    ad, lon, lat, tur = yer[:4]
    yil = yil_bul(konu)
    bas = {"ust": str(yil) if yil else ad.upper(), "alt": ad if yil else ""}
    etiket = [{"ad": ad, "lon": lon, "lat": lat, "bas": 0.15}]
    a = {"tip": "harita", "baslik": bas, "zoom": 1.08, "odak": [lon, lat], "etiketler": etiket}
    if tur == "sehir":
        a.update(merkez=[lon, lat + 0.06], genislik=0.75, vurgu={"lon": lon, "lat": lat, "bas": 0.2, "renk": [176, 34, 34]})
        return a
    if tur == "yer":
        a.update(merkez=[lon, lat + 0.5], genislik=6, vurgu={"lon": lon, "lat": lat, "bas": 0.2, "renk": [176, 34, 34]})
        if kat == "savaslar":
            a["carpisma"] = {"lon": lon, "lat": lat, "bas": 0.55}
        return a
    ek = yer[5] if len(yer) > 5 else []
    for ead, elon, elat in ek:
        etiket.append({"ad": ead, "lon": elon, "lat": elat, "bas": 0.05})
        if elon > lon and abs(elat - lat) < abs(elon - lon) * 0.6:   # yan yana etiketler çakışmasın
            etiket[0]["yan"] = "sol"
    if len(yer) > 4 and yer[4]:
        rota = yer[4]
    elif tur.startswith("deniz"):
        rota = DENIZ_YOLU + [[lon, lat]]
        if lon < 24:   # Batı Akdeniz: Mora'nın güneyinden dolaş
            rota = DENIZ_YOLU + [[21.5, 36.2], [lon + 0.4, lat + 0.3]]
    else:
        b = baskent(yil)
        rota = [[b[1], b[2]], [lon, lat]]
        if b[0] != ad:
            etiket.insert(0, {"ad": b[0], "lon": b[1], "lat": b[2]})
    if tur.startswith("deniz") and not (len(yer) > 4 and yer[4]) and "İstanbul" != ad:
        etiket.insert(0, {"ad": "İstanbul", "lon": IST[0], "lat": IST[1]})
    noktalar = rota + [[e["lon"], e["lat"]] for e in etiket]
    sehir_ici = max(p[0] for p in noktalar) - min(p[0] for p in noktalar) < 0.3
    merkez, gen = cerceve(noktalar, 0.5 if sehir_ici else 3.0)
    a.update(merkez=merkez, genislik=gen, zoom=1.05, odak=[lon, lat])
    taraf = "dusman" if tur == "deniz-dusman" else "osmanli"
    ikon = "ordu" if tur == "kara" else ("yok" if tur == "yol" else None)
    r = {"yol": rota, "taraf": taraf, "bas": 0.05, "bit": 0.8, "boy": 85}
    if ikon:
        r["ikon"] = ikon
    else:
        r["gemi"] = 3
    a["rotalar"] = [r]
    for diger in (yer[6] if len(yer) > 6 else []):
        a["rotalar"].append({"yol": diger, "taraf": "osmanli", "ikon": "yok", "bas": 0.2, "bit": 0.85})
    if kat == "savaslar" and tur in ("kara", "deniz", "deniz-dusman"):
        a["carpisma"] = {"lon": lon, "lat": lat, "bas": 0.85}
    return a


def metin_sahnesi(konu, kat, yer, sh):
    ad, lon, lat, tur = yer[:4]
    yazi = sh.get("yazi", "")
    if re.fullmatch(r"[\d\s\-–.,]*1[0-9]{3}[\d\s\-–.,]*", yazi) or re.search(r"\b1[0-9]{3}\b", yazi) and len(yazi) <= 14:
        return {"tip": "takvim", "filo": kat == "savaslar" and tur.startswith("deniz"), "yil": ad if len(ad) <= 16 else "",
                "aylar": [yazi]}
    gen = 0.6 if tur == "sehir" else 3.5
    a = {"tip": "harita", "merkez": [lon, lat + (0.05 if tur == "sehir" else 0.25)], "genislik": gen, "zoom": 1.1, "odak": [lon, lat],
         "etiketler": [{"ad": ad, "lon": lon, "lat": lat}], "vurgu": {"lon": lon, "lat": lat, "bas": 0.1, "renk": [176, 34, 34]}}
    if len(yazi) <= 18:
        a["damga"] = {"yazi": damga_yazisi(yazi), "lon": lon, "lat": lat, "bas": 0.35}
    else:
        a["rozetler"] = [{"yazi": yazi, "x": 540, "y": 560, "bas": 0.2}]
    return a


def main():
    toplam = 0
    for kat in ("saray", "kisiler", "savaslar"):
        yol = os.path.join(KOK, f"{kat}.json")
        with open(yol, encoding="utf-8") as f:
            L = json.load(f)
        for k in L:
            if k.get("stil") == "animasyon" or k["id"] not in YERLER:
                continue
            yer = YERLER[k["id"]]
            if not k.get("kanca_gorsel"):   # kanca, eskiden 1. sahnenin tablosunu kullanıyordu
                k["kanca_gorsel"] = k["sahneler"][0]["gorsel"]
            k["sahneler"][0]["anim"] = giris_haritasi(k, kat, yer)
            k["sahneler"][0]["gorsel"] = ["-"]
            for sh in k["sahneler"][1:]:
                if sh.get("gorsel") == ["-"] and not sh.get("anim"):
                    sh["anim"] = metin_sahnesi(k, kat, yer, sh)
            k["stil"] = "animasyon"
            k["oto_animasyon"] = True
            toplam += 1
        with open(yol, "w", encoding="utf-8") as f:
            json.dump(L, f, ensure_ascii=False, indent=2)
    eksik = [i for kat in ("saray", "kisiler", "savaslar") for i in
             [k["id"] for k in json.load(open(os.path.join(KOK, f"{kat}.json"), encoding="utf-8")) if k.get("stil") != "animasyon"]]
    print(toplam, "konuya animasyon eklendi. Eksik:", eksik)


if __name__ == "__main__":
    main()
