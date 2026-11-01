"""Aramalar için Commons'taki kamu malı adayları numaralı küçük resim sayfaları olarak çıkarır.

Kullanım: python osmanli/gorsel_ara.py aramalar.txt   (her satır bir arama)
Çıktı: out/ara/NN.jpg (her arama için bir sayfa) + out/ara/sonuc.json (dosya adları)
Beğenilen görselin dosya adı ("File:...") konular/*.json içinde "gorsel" listesinin başına yazılır.
"""
import json, os, sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gorsel import _get, ara  # noqa: E402

KUTU = 300


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        aramalar = [s.strip() for s in f if s.strip() and not s.startswith("#")]
    cikis = os.path.join(ROOT, "out", "ara")
    os.makedirs(cikis, exist_ok=True)
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    sonuc = {}
    for n, q in enumerate(aramalar):
        adaylar = ara(q, limit=12)[:8]
        sonuc[q] = [{"no": i + 1, "dosya": a["baslik"], "w": a["w"], "h": a["h"], "sanatci": a["sanatci"]}
                    for i, a in enumerate(adaylar)]
        sayfa = Image.new("RGB", (KUTU * 4, 40 + (KUTU + 30) * 2), (30, 30, 30))
        d = ImageDraw.Draw(sayfa)
        d.text((10, 10), q, font=fnt, fill=(255, 220, 120))
        for i, a in enumerate(adaylar):
            try:
                im = Image.open(__import__("io").BytesIO(_get(a["url"], timeout=60))).convert("RGB")
            except Exception:
                continue
            im.thumbnail((KUTU - 8, KUTU - 8))
            x, y = (i % 4) * KUTU, 40 + (i // 4) * (KUTU + 30)
            sayfa.paste(im, (x + (KUTU - im.width) // 2, y + (KUTU - im.height) // 2))
            d.text((x + 6, y + KUTU + 4), f"{i + 1}) {a['w']}x{a['h']}", font=fnt, fill=(255, 255, 255))
            d.rectangle([x + 4, y + 4, x + 34, y + 30], fill=(0, 0, 0))
            d.text((x + 10, y + 7), str(i + 1), font=fnt, fill=(255, 220, 120))
        sayfa.save(os.path.join(cikis, f"{n:02d}.jpg"), quality=82)
        print(f"{n:02d} {q}: {len(adaylar)} aday", flush=True)
    with open(os.path.join(cikis, "sonuc.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
