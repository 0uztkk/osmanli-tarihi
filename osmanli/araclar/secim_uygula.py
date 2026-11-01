#!/usr/bin/env python3
"""Görsel aday sayfalarından yapılan seçimleri konu bankasına yazar.

    python3 secim_uygula.py <kategori> <adaylar.json> <secim.json>

secim.json: {"konu-id": {"k": "1a", "1": "2c", "2": "-", ...}}  ("k" = kanca, "-" = yazılı sahne)
Seçilen dosya, sahnenin "gorsel" listesinde tek başına kalır (yanlış olay riski olan genel aramalar silinir).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    kat, aday_yol, secim_yol = sys.argv[1:4]
    aday = json.load(open(aday_yol, encoding="utf-8"))
    secim = json.load(open(secim_yol, encoding="utf-8"))
    p = os.path.join(os.path.dirname(HERE), "konular", f"{kat}.json")
    banka = json.load(open(p, encoding="utf-8"))
    n = 0
    for k in banka:
        s = secim.get(k["id"])
        if not s:
            continue
        et = aday.get(k["id"], {})
        def dosya(lbl):
            if lbl == "-":
                return ["-"]
            if "/" in lbl:   # başka bir konunun adayı: "konu-id/2c"
                diger, lbl2 = lbl.split("/")
                return [aday[diger][lbl2]["dosya"]]
            return [et[lbl]["dosya"]]
        for i, sh in enumerate(k["sahneler"]):
            if str(i + 1) in s:
                sh["gorsel"] = dosya(s[str(i + 1)])
        if s.get("k") and s["k"] != "-":
            k["kanca_gorsel"] = dosya(s["k"])
        n += 1
    json.dump(banka, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{kat}: {n} konu güncellendi")


if __name__ == "__main__":
    main()
