"""Bir kategorideki her konu için sahne başına 5 kamu malı görsel adayı çıkarır (seçim yapmak için).

Kullanım: python osmanli/gorsel_aday.py savaslar
Çıktı: out/aday/<kategori>/<sıra>_<konu>.jpg (konu başına tek sayfa) + adaylar.json (etiket → dosya adı)
Seçilen dosya adları konular/*.json içinde ilgili sahnenin "gorsel" listesinin başına yazılır.
"""
import io, json, os, sys, time

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gorsel import _get, ara  # noqa: E402

KUTU, ADAY = 230, 5
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def main():
    kat = sys.argv[1]
    with open(os.path.join(HERE, "konular", f"{kat}.json"), encoding="utf-8") as f:
        konular = json.load(f)
    cikis = os.path.join(ROOT, "out", "aday", kat)
    os.makedirs(cikis, exist_ok=True)
    f_k, f_b = ImageFont.truetype(FONT, 12), ImageFont.truetype(FONTB, 15)
    hepsi = {}
    for no, k in enumerate(konular):
        if any(g.startswith("File:") for sh in k["sahneler"] for g in sh["gorsel"]):
            continue   # bu konunun görselleri zaten elle seçilmiş
        sayfa = Image.new("RGB", (KUTU * ADAY, 30 + 4 * (KUTU + 44)), (28, 28, 28))
        d = ImageDraw.Draw(sayfa)
        d.text((8, 7), f"{k['id']}", font=f_b, fill=(255, 210, 110))
        gorulen, etiketler = set(), {}
        for j, sh in enumerate(k["sahneler"]):
            y0 = 30 + j * (KUTU + 44)
            adaylar = []
            sorgular = [g for g in sh["gorsel"] if not g.startswith("File:")]
            for q in sorgular:
                try:
                    sonuclar = ara(q, limit=10, genislik=330)
                except Exception as e:
                    print("  arama hatası:", q, e, flush=True); sonuclar = []
                for a in sonuclar:
                    if a["baslik"] in gorulen:
                        continue
                    adaylar.append(a); gorulen.add(a["baslik"])
                    if len(adaylar) >= (3 if q == sorgular[0] and len(sorgular) > 1 else ADAY):
                        break
                if len(adaylar) >= ADAY:
                    break
            for i, a in enumerate(adaylar[:ADAY]):
                et = f"{j + 1}{'abcde'[i]}"
                etiketler[et] = {"dosya": a["baslik"], "w": a["w"], "h": a["h"]}
                x = i * KUTU
                try:
                    im = Image.open(io.BytesIO(_get(a["url"], timeout=60))).convert("RGB")
                    im.thumbnail((KUTU - 8, KUTU - 8))
                    sayfa.paste(im, (x + (KUTU - im.width) // 2, y0 + (KUTU - im.height) // 2))
                except Exception:
                    d.text((x + 10, y0 + 100), "indirilemedi", font=f_k, fill=(255, 80, 80))
                d.rectangle([x + 3, y0 + 3, x + 36, y0 + 24], fill=(0, 0, 0))
                d.text((x + 7, y0 + 5), et, font=f_b, fill=(255, 210, 110))
                ad = a["baslik"][5:].rsplit(".", 1)[0]
                d.text((x + 4, y0 + KUTU + 2), ad[:31], font=f_k, fill=(230, 230, 230))
                d.text((x + 4, y0 + KUTU + 17), ad[31:51], font=f_k, fill=(230, 230, 230))
                d.text((x + KUTU - 68, y0 + KUTU + 17), f"{a['w']}x{a['h']}"[:10], font=f_k, fill=(150, 150, 150))
            if not adaylar:
                d.text((10, y0 + 100), f"{j + 1}: aday yok", font=f_b, fill=(255, 80, 80))
        sayfa.save(os.path.join(cikis, f"{no:02d}_{k['id']}.jpg"), quality=80)
        hepsi[k["id"]] = etiketler
        print(no, k["id"], len(etiketler), flush=True)
        with open(os.path.join(cikis, "adaylar.json"), "w", encoding="utf-8") as f:   # her konudan sonra kaydet
            json.dump(hepsi, f, ensure_ascii=False, indent=1)
        time.sleep(0.3)


if __name__ == "__main__":
    main()
