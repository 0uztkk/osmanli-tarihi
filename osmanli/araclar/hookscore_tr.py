#!/usr/bin/env python3
"""hookscore_tr.py – yt-script/hookscore.py'nin Türkçe uyarlaması.

Aynı beş özellik (0-100) ve aynı karar: ortalamanın %60'ı + en zayıf özelliğin %40'ı. En zayıf halka
ağırlığı bilinçli: dört özelliği güçlü, biri ölü bir kanca o ölü yerden izleyici kaybeder.
Orijinal betik İngilizce kelime listeleri kullandığı için Türkçe metinde anlamsız puan verir;
bu sürüm aynı ölçütleri Türkçe kelimelerle uygular.

    python3 hookscore_tr.py --hook "Bir gecede yetmiş gemi karadan yürüdü."
    python3 hookscore_tr.py --banka            # bütün konu bankasının kancalarını puanlar
    python3 hookscore_tr.py --banka --json

Düşük puan "tekrar bak" demektir; yüksek puan başarı garantisi değildir.
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANKA = os.path.join(os.path.dirname(HERE), "konular")

DOLGU = {"aslında", "yani", "sadece", "gerçekten", "çok", "şey", "bugün", "video", "videoda",
         "abone", "kanal", "kanala", "merhaba", "arkadaşlar", "sizlere", "hepinize"}
BELIRSIZ = {"inanılmaz", "şok", "çılgın", "akılalmaz", "müthiş", "harika", "efsanevi", "gizli",
            "devasa", "büyüleyici", "olağanüstü", "korkunç"}
SOMUT = re.compile(r"\b(\d[\d.,]*|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yirmi|otuz|kırk|elli|"
                   r"altmış|yetmiş|seksen|doksan|yüz|bin)\b", re.I)
SEN = re.compile(r"\b(sen|sana|seni|senin|sence|bil|bilir|biliyor|düşün|hayal|izle|bak)\w*", re.I)
BEDEL = re.compile(r"(öl|öldür|kaybet|kayb|yenil|yık|yan(dı|gın)|kaç|esir|idam|boğul|isyan|ihanet|"
                   r"teslim|vur|hançer|patla|felaket|kıyamet|bozgun|kan|son\b|sonu|tahttan|yok ol|"
                   r"çök|sürgün|zehir|suikast|baskın|darbe|kriz|yasak|rehin|tehlike|korku|düşman)", re.I)
MERAK = re.compile(r"\b(neden|nasıl|kim|ne|hangi|niye|ama|fakat|oysa|meğer|sonra|hiç|bile|"
                   r"kimse|yalnızca|sadece|tek)\b|\?", re.I)
KAPANAN = re.compile(r"\b(çünkü|bu yüzden|yani|dolayısıyla)\b", re.I)

FORMULLER = [  # hooks.json'daki 21 formülün bu kanala uyan Türkçe karşılıkları
    ("İstatistik", [r"\b\d{2,}\b", r"\b(yüz|bin|binlerce|yüzlerce)\b"]),
    ("Sonuçla açılış", [r"(öldü|yenildi|düştü|teslim|tahttan|esir|battı|yandı)"]),
    ("Açık soru", [r"\?$", r"\b(nasıl|neden|kim)\b"]),
    ("Tersine çevirme", [r"\b(ama|fakat|oysa|meğer|bile)\b"]),
    ("Zaman baskısı", [r"\b(bir gecede|günler içinde|dakika|saat|hafta|bir yılda|iki dakika)\b"]),
    ("İsimli sonuç", [r"\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]+\b.*\b(oldu|aldı|yaptı|yendi)\b"]),
]
COZUM = {
    "SOMUTLUK": "bir sıfatı sayı, isim ya da tarihle değiştir",
    "HİTAP": "ilk altı kelimede izleyiciye dön (sence, hayal et, biliyor musun)",
    "BEDEL": "neyin kaybedildiğini ya da kimin bedel ödediğini söyle",
    "MERAK": "cümlenin kendini cevaplayan yarısını kes, bir soru açık kalsın",
    "KISALIK": "9-24 kelime; yüksek sesle oku, nefesin bittiği yerde dur",
}


def kelimeler(t): return re.findall(r"[\wçğıöşüâîû']+", t.lower())


def somutluk(t):
    w = kelimeler(t)
    if not w: return 0
    s = 34 + 22 * len(SOMUT.findall(t)) - 16 * sum(x in BELIRSIZ for x in w) - 5 * sum(x in DOLGU for x in w)
    s += min(18, 6 * sum(1 for x in t.split()[1:] if x[:1].isupper()))
    return max(0, min(100, s))


def hitap(t):
    n = len(SEN.findall(t))
    ilk = 30 if SEN.search(" ".join(t.split()[:6])) else 0
    return max(0, min(100, 26 + 20 * n + ilk))


def bedel(t):
    return max(0, min(100, 22 + 26 * len(BEDEL.findall(t)) + (14 if SOMUT.search(t) else 0)))


def merak(t):
    n = len(MERAK.findall(t))
    return max(0, min(100, 24 + 17 * n + (18 if t.strip().endswith("?") else 0) - (18 if KAPANAN.search(t) else 0)))


def kisalik(t):
    n = len(kelimeler(t))
    if n == 0: return 0
    if 9 <= n <= 24: return 100
    return max(30, 100 - (9 - n) * 11) if n < 9 else max(10, 100 - (n - 24) * 7)


OZELLIK = [("SOMUTLUK", somutluk), ("HİTAP", hitap), ("BEDEL", bedel), ("MERAK", merak), ("KISALIK", kisalik)]


def formul(t):
    en, isabet = "Sınıflanmadı (özet gibi duruyor)", 0
    for ad, desen in FORMULLER:
        n = sum(1 for p in desen if re.search(p, t))
        if n > isabet: en, isabet = ad, n
    return en


def puanla(t):
    p = {ad: fn(t) for ad, fn in OZELLIK}
    v = list(p.values())
    karar = round(0.6 * sum(v) / len(v) + 0.4 * min(v))
    return {"kanca": t, "ozellik": p, "karar": karar,
            "bant": "GÜÇLÜ" if karar >= 72 else "İDARE EDER" if karar >= 55 else "ZAYIF",
            "formul": formul(t), "zayif": min(p, key=p.get)}


def rapor(r):
    print(f"\n  {r['kanca']}")
    for k, v in r["ozellik"].items():
        print(f"    {k:<10} {v:3d}  {'#' * (v // 5)}")
    print(f"    KARAR      {r['karar']:3d}  {r['bant']}   formül: {r['formul']}")
    print(f"    en zayıf   {r['zayif']} – {COZUM[r['zayif']]}")


def main():
    a = sys.argv[1:]
    js = "--json" in a
    if "--hook" in a:
        sonuc = [puanla(a[a.index("--hook") + 1])]
    elif "--banka" in a:
        sonuc = []
        for kat in ("savaslar", "saray", "kisiler"):
            for k in json.load(open(os.path.join(BANKA, f"{kat}.json"), encoding="utf-8")):
                r = puanla(k["kanca"]); r["id"] = k["id"]; r["kategori"] = kat
                sonuc.append(r)
    else:
        print(__doc__); sys.exit(1)
    sonuc.sort(key=lambda r: -r["karar"])
    if js:
        print(json.dumps(sonuc, ensure_ascii=False, indent=1)); return
    for r in sonuc: rapor(r)


if __name__ == "__main__":
    main()
