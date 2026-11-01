"""Konu bankasındaki her sahne için Commons'ta hangi görselin seçileceğini gösterir (yükleme yapmaz).

Kullanım: python osmanli/gorsel_kontrol.py [savaslar|saray|kisiler|hepsi]
Sonuç: GitHub Actions özet sayfasında küçük resimli tablo + out/gorsel_raporu.md
Alakasız görsel çıkan sahnenin "gorsel" aramalarını konular/*.json içinde değiştirmek yeterli.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from gorsel import YEDEK, ara  # noqa: E402


def main():
    secim = (sys.argv[1] if len(sys.argv) > 1 else "hepsi").strip().lower()
    kategoriler = ["savaslar", "saray", "kisiler"] if secim in ("", "hepsi") else [secim]
    satirlar, eksik = [], 0
    for kat in kategoriler:
        with open(os.path.join(HERE, "konular", f"{kat}.json"), encoding="utf-8") as f:
            konular = json.load(f)
        satirlar.append(f"\n## {kat}\n\n| Konu | Sahne | Seçilen görsel | Arama |\n|---|---|---|---|")
        for k in konular:
            kullanilan = set()
            for j, sh in enumerate(k["sahneler"]):
                secilen, hangi = None, ""
                for q in sh["gorsel"] + YEDEK[kat]:
                    for a in ara(q, limit=8):
                        if a["baslik"] not in kullanilan:
                            secilen, hangi = a, q
                            break
                    if secilen:
                        break
                if secilen:
                    kullanilan.add(secilen["baslik"])
                    yedek = " ⚠️ yedek" if hangi in YEDEK[kat] else ""
                    hucre = f'<img src="{secilen["url"]}" width="110"><br>[{secilen["baslik"][5:60]}]({secilen["sayfa"]})'
                else:
                    eksik += 1
                    yedek, hucre = "", "❌ bulunamadı (yazılı sahne)"
                satirlar.append(f"| {k['id']} | {j + 1}. {sh.get('yazi', '')} | {hucre} | {hangi}{yedek} |")
            print(k["id"], "tamam", flush=True)
    rapor = "# Görsel kontrol raporu\n" + f"\nBulunamayan sahne: {eksik}\n" + "\n".join(satirlar) + "\n"
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    with open(os.path.join(ROOT, "out", "gorsel_raporu.md"), "w", encoding="utf-8") as f:
        f.write(rapor)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(rapor[:900_000])
    print(f"Bitti. Bulunamayan sahne: {eksik}")


if __name__ == "__main__":
    main()
