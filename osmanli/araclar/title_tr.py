#!/usr/bin/env python3
"""title_tr.py – yt-package/title.py kurallarının Türkçe uyarlaması (başlık + kapak yazısı birlikte).

Kurallar: ≤60 karakter (masaüstü arama), konu ilk 40 karakterde (mobil akış), en fazla 2 büyük harfli
kelime, belirsiz sıfat yerine sayı/isim/tarih, ilk üç kelime dolgu olmamalı, kapak yazısı başlığı
tekrar etmemeli ve en fazla 3 kelime olmalı.

    python3 title_tr.py --title "..." --kapak "70 GEMİ KARADAN"
    python3 title_tr.py --banka            # bütün bankayı denetler
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANKA = os.path.join(os.path.dirname(HERE), "konular")
MASAUSTU, MOBIL, SINIR = 60, 40, 100
BELIRSIZ = {"inanılmaz", "şok", "çılgın", "akılalmaz", "müthiş", "harika", "efsanevi", "gizli",
            "devasa", "büyüleyici", "olağanüstü", "korkunç", "muhteşem", "sırları", "sırrı"}
DOLGU = {"bir", "bu", "şu", "ve", "ile", "de", "da", "ne", "neden", "nasıl", "kim", "mi", "mı",
         "mu", "mü", "için", "en", "çok"}


def kelimeler(t): return re.findall(r"[0-9a-zçğıöşüâîû]+", t.replace("I", "ı").replace("İ", "i").lower())


def kok(w): return w[:5]   # Türkçe ekler için kaba kök karşılaştırması


def denetle(baslik, kapak=None, konu_kelimeleri=()):
    t = re.sub(r"[^\w\s'?!:.,–-]", "", baslik).strip()   # emoji hariç ölç
    n = len(baslik.strip())
    sorun, iyi = [], []
    if n > SINIR: sorun.append(("uzunluk", f"{n} karakter – YouTube sınırı {SINIR}"))
    elif n > MASAUSTU: sorun.append(("uzunluk", f"{n} karakter – masaüstü arama {MASAUSTU}'ta keser"))
    else: iyi.append(f"{n} karakter")
    if konu_kelimeleri and n > MOBIL:   # 40'tan kısa başlık mobilde kesilmez
        bas = {kok(w) for w in kelimeler(baslik[:MOBIL])}
        if not any(kok(w) in bas for w in konu_kelimeleri if len(w) > 2):
            sorun.append(("mobil", f'konu ilk {MOBIL} karakterde yok: "{baslik[:MOBIL]}"'))
    buyuk = [w for w in t.split() if len(w) > 2 and w.isupper()]
    if len(buyuk) > 2: sorun.append(("bağırma", f"{len(buyuk)} büyük harfli kelime"))
    b = [w for w in kelimeler(t) if w in BELIRSIZ]
    if b: sorun.append(("belirsiz", ", ".join(sorted(set(b))) + " – sayı, isim ya da tarihle değiştir"))
    if re.search(r"\d", t) or any(w[:1].isupper() for w in t.split()[1:]):
        iyi.append("sayı/isim/tarih var")
    else:
        sorun.append(("somut-yok", "sayı, tarih ya da özel isim yok"))
    if not [w for w in kelimeler(t)[:3] if w not in DOLGU]:
        sorun.append(("öne-al", "ilk üç kelime dolgu"))
    if kapak is not None:
        kk = kelimeler(kapak)
        if len(kk) > 3: sorun.append(("kapak-uzun", f"kapak {len(kk)} kelime – en fazla 3"))
        ortak = {kok(w) for w in kk if w not in DOLGU and len(w) > 2} & {kok(w) for w in kelimeler(t) if w not in DOLGU and len(w) > 2}
        if ortak: sorun.append(("kapak-tekrar", f"kapak başlığı tekrar ediyor ({', '.join(sorted(ortak))})"))
    puan = max(0, min(100, 100 - 14 * len(sorun) + 4 * len(iyi)))
    return {"baslik": baslik, "puan": puan, "sorun": sorun, "iyi": iyi}


def main():
    a = sys.argv[1:]
    if "--title" in a:
        r = denetle(a[a.index("--title") + 1], a[a.index("--kapak") + 1] if "--kapak" in a else None)
        print(json.dumps(r, ensure_ascii=False, indent=1)); return
    if "--banka" not in a:
        print(__doc__); sys.exit(1)
    toplam = sorunlu = 0
    for kat in ("savaslar", "saray", "kisiler"):
        for k in json.load(open(os.path.join(BANKA, f"{kat}.json"), encoding="utf-8")):
            konu = [w for e in k.get("etiketler", []) for w in kelimeler(e)] + kelimeler(k["kanca"])[:0]
            for b in k["baslik"]:
                toplam += 1
                r = denetle(b, k.get("kapak"), konu)
                if r["sorun"]:
                    sorunlu += 1
                    print(f"{k['id']:<24} {r['puan']:3d}  {b}")
                    for s, m in r["sorun"]: print(f"{'':30}x {s}: {m}")
    print(f"\n{toplam} başlık, {sorunlu} sorunlu")


if __name__ == "__main__":
    main()
