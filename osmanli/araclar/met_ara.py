"""The Met açık arşivinde (Open Access, kamu malı) aramalar yapar ve seçim için numaralı küçük resim sayfaları çıkarır.

Kullanım: python osmanli/araclar/met_ara.py "Ottoman miniature" "Janissary" ...
          (argüman yoksa osmanli/met_istek.txt satırları; boşsa varsayılan Osmanlı aramaları)
Çıktı: out/met/NN.jpg (her arama için bir sayfa, eser kimliği ve tarihiyle) + out/met/sonuc.json
Seçilen eser konular/*.json ya da uzun/*.json içinde "gorsel" listesine "Met:<kimlik>" diye yazılır.
Yalnızca isPublicDomain=true eserler listelenir. Görselin gösterdiği olay/kişi mutlaka kontrol edilir:
başka bir olayın tablosu o olayın görseli olarak kullanılmaz (voice.md).
"""
import io, json, os, sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.dirname(HERE)
ROOT = os.path.dirname(OSM)
sys.path.insert(0, OSM)
from gorsel import _get, met_ara  # noqa: E402

VARSAYILAN = ["Ottoman sultan", "Ottoman miniature", "Janissary", "Ottoman court", "Constantinople",
              "Topkapi", "Ottoman manuscript painting", "Turkish costume album", "Ottoman battle", "Suleyman"]
KUTU, SUTUN, ADET = 300, 5, 20


def main():
    aramalar = sys.argv[1:]
    istek = os.path.join(OSM, "met_istek.txt")
    if not aramalar and os.path.exists(istek):
        aramalar = [s.strip() for s in open(istek, encoding="utf-8") if s.strip() and not s.startswith("#")]
    aramalar = aramalar or VARSAYILAN
    cikis = os.path.join(ROOT, "out", "met")
    os.makedirs(cikis, exist_ok=True)
    fb = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    fk = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    sonuc, gorulen = {}, set()
    for n, q in enumerate(aramalar):
        adaylar = [a for a in met_ara(q, limit=ADET * 2) if a["baslik"] not in gorulen][:ADET]
        gorulen |= {a["baslik"] for a in adaylar}
        sonuc[q] = [{"gorsel": a["baslik"], "eser": a["eser"], "tarih": a["tarih"], "sanatci": a["sanatci"], "sayfa": a["sayfa"]}
                    for a in adaylar]
        satir = (len(adaylar) + SUTUN - 1) // SUTUN or 1
        sayfa = Image.new("RGB", (KUTU * SUTUN, 44 + (KUTU + 46) * satir), (28, 28, 28))
        d = ImageDraw.Draw(sayfa)
        d.text((10, 12), f"{q}  ({len(adaylar)} kamu malı eser)", font=fb, fill=(255, 220, 120))
        for i, a in enumerate(adaylar):
            x, y = (i % SUTUN) * KUTU, 44 + (i // SUTUN) * (KUTU + 46)
            try:
                url = a["url"].replace("/original/", "/web-large/")   # sayfa için küçük sürüm yeter
                im = Image.open(io.BytesIO(_get(url, timeout=60))).convert("RGB")
                im.thumbnail((KUTU - 10, KUTU - 10))
                sayfa.paste(im, (x + (KUTU - im.width) // 2, y + (KUTU - im.height) // 2))
            except Exception as e:
                d.text((x + 10, y + 10), f"indirilemedi: {e}"[:40], font=fk, fill=(255, 120, 120))
            d.text((x + 6, y + KUTU + 2), a["baslik"], font=fb, fill=(255, 255, 255))
            d.text((x + 6, y + KUTU + 22), (a["tarih"] + " · " + a["eser"])[:42], font=fk, fill=(200, 200, 200))
        sayfa.save(os.path.join(cikis, f"{n + 1:02d}.jpg"), quality=85)
        print(f"{q}: {len(adaylar)} eser", flush=True)
    with open(os.path.join(cikis, "sonuc.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
