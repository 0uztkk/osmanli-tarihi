"""DENEME: aynı Shorts'u HyperFrames (HTML + GSAP → MP4) ile kurar. Üretim hattına dokunmaz.

Önce normal build.py aynı KONU/KATEGORI/SEED ile çalışmış olmalı: seslendirme önbelleği (out/tts),
görseller (out/img) ve son ses (out/audio.wav, müzikli) oradan alınır; böylece iki video aynı sesi kullanır.
Çıktı: out/hf/ (index.html + assets) → sonra `npx hyperframes render` ile MP4.
Kullanım: KONU=cem-sultan KATEGORI=kisiler SEED=20261116 python osmanli/deneme/hyperframes_shorts.py
"""
import html, json, os, shutil, subprocess, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.dirname(HERE)
ROOT = os.path.dirname(OSM)
sys.path.insert(0, OSM)
import build as B   # noqa: E402

OUT = os.path.join(ROOT, "out")
HF = os.path.join(OUT, "hf")
W, H = 1080, 1920


def harita_klibi(spec, sure, yol):
    """Mevcut Python animasyonunu (harita/takvim/...) kısa bir MP4 klibe çevirir; HTML'de <video> olarak oynar."""
    import animasyon
    animasyon.ayarla(W, H)
    o = animasyon.hazirla(spec, sure)
    n = int(sure * 30)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                           "-pix_fmt", "yuv420p", yol], stdin=subprocess.PIPE)
    for fr in range(n):
        u = fr / max(1, n - 1)
        ff.stdin.write(o.kare(u, u * sure).convert("RGB").tobytes())
    ff.stdin.close()
    ff.wait()


def main():
    kategori = os.environ.get("KATEGORI", "kisiler")
    seed = int(os.environ.get("SEED") or "20261116")
    konu = B.konu_sec(kategori, seed, os.environ.get("KONU", "cem-sultan"))
    from gorsel import bul
    kapanis, _, _ = B.kapanis_sec(konu, kategori, seed)
    # build.py ile aynı parçalar ve aynı zamanlama (seslendirme önbellekten gelir)
    metinler = [konu["kanca"]] + [s["metin"] for s in konu["sahneler"]] + [m for m, _ in kapanis]
    kartlar = [None] * (1 + len(konu["sahneler"])) + [k for _, k in kapanis]
    ses, zaman = B.ses_uret(metinler, os.path.join(OUT, "tts"))
    toplam_ham = len(ses) / B.SR
    oran = max(1.0, toplam_ham / B.MAKS_SURE)
    zaman = [(a / oran, b / oran) for a, b in zaman]
    with wave.open(os.path.join(OUT, "audio.wav")) as w:
        toplam = w.getnframes() / w.getframerate()

    shutil.rmtree(HF, ignore_errors=True)
    os.makedirs(os.path.join(HF, "assets"))
    shutil.copy(os.path.join(OUT, "audio.wav"), os.path.join(HF, "assets", "audio.wav"))
    gsap_yerel = os.path.join(ROOT, "node_modules", "gsap", "dist", "gsap.min.js")
    if os.path.exists(gsap_yerel):   # CDN'e bağlı kalmasın
        shutil.copy(gsap_yerel, os.path.join(HF, "assets", "gsap.min.js"))
    for paket, ad in (("playfair-display", "playfair"), ("inter", "inter")):
        kaynak = os.path.join(ROOT, "node_modules", "@fontsource", paket)
        if os.path.isdir(kaynak):
            shutil.copytree(kaynak, os.path.join(HF, "assets", ad))

    # her parçanın görseli: kanca → kanca_gorsel (yoksa ilk sahne), sahneler → kendi görseli/animasyonu, kapanış → son sahne
    kullanilan, gorsel = set(), {}

    def gorsel_yolu(liste, ad):
        g = bul(liste, kategori, os.path.join(OUT, "img"), kullanilan)
        if not g:
            return None
        hedef = os.path.join(HF, "assets", ad + os.path.splitext(g["yol"])[1])
        shutil.copy(g["yol"], hedef)
        return "assets/" + os.path.basename(hedef)

    sahne_gorsel = []
    for j, s in enumerate(konu["sahneler"]):
        sahne_gorsel.append(("anim", s["anim"]) if s.get("anim") else ("img", gorsel_yolu(s["gorsel"], f"s{j}")))
    kg = gorsel_yolu(konu["kanca_gorsel"], "kanca") if konu.get("kanca_gorsel") else None
    kaynak = [("img", kg) if kg else sahne_gorsel[0]] + sahne_gorsel + [sahne_gorsel[-1]] * len(kapanis)

    n = len(metinler)
    bas = [0.0] + [max(0.0, zaman[k][0] - 0.2) for k in range(1, n)]
    son = [bas[k + 1] if k + 1 < n else toplam for k in range(n)]
    GECIS = 0.45
    klipler, tl, altyazi = [], [], []
    for k in range(n):
        tur, deger = kaynak[k]
        sure = min(toplam, son[k] + (GECIS if k + 1 < n else 0)) - bas[k]
        z = 10 + k
        if tur == "anim":
            ad = f"anim{k}.mp4"
            harita_klibi(deger, sure, os.path.join(HF, "assets", ad))
            icerik = f'<video class="fill" src="assets/{ad}" muted></video>'
        elif deger:
            icerik = (f'<div class="blur" style="background-image:url({deger})"></div>'
                      f'<div class="kb" id="kb{k}" style="background-image:url({deger})"></div>')
        else:
            icerik = '<div class="parsomen"></div>'
        klipler.append(f'<section id="s{k}" class="clip sahne" style="z-index:{z}" data-start="{bas[k]:.3f}" '
                       f'data-duration="{sure:.3f}" data-track-index="1">{icerik}<div class="vinyet"></div></section>')
        if k:   # yumuşak geçiş + ışık parlaması
            tl.append(f'tl.fromTo("#s{k}", {{opacity:0, scale:1.06}}, {{opacity:1, scale:1, duration:{GECIS}, ease:"power2.out"}}, {bas[k]:.3f});')
            tl.append(f'tl.fromTo("#flash", {{opacity:0}}, {{opacity:0.55, duration:0.12, yoyo:true, repeat:1, ease:"sine.inOut"}}, {bas[k]:.3f});')
        if tur == "img" and deger:   # Ken Burns: kayma + yakınlaşma, yönü sahneden sahneye değişir
            yon = ("0% 50%", "100% 50%") if k % 2 == 0 else ("100% 50%", "0% 50%")
            tl.append(f'tl.fromTo("#kb{k}", {{backgroundPosition:"{yon[0]}", scale:1.12}}, '
                      f'{{backgroundPosition:"{yon[1]}", scale:1.0, duration:{sure:.3f}, ease:"none"}}, {bas[k]:.3f});')
        # sahne etiketi
        yazi = konu["sahneler"][k - 1].get("yazi") if 1 <= k <= len(konu["sahneler"]) else None
        if yazi and tur != "anim":
            altyazi.append(f'<div class="etiket" id="et{k}">{html.escape(B.tr_buyuk(yazi))}</div>')
            tl.append(f'tl.fromTo("#et{k}", {{autoAlpha:0, x:-80}}, {{autoAlpha:1, x:0, duration:0.5, ease:"back.out(1.6)"}}, {bas[k] + 0.25:.3f});')
            tl.append(f'tl.to("#et{k}", {{autoAlpha:0, duration:0.25}}, {son[k] - 0.1:.3f});')
        # kapanış kartı
        if kartlar[k]:
            altyazi.append(f'<div class="kart" id="kart{k}">{html.escape(kartlar[k])}</div>')
            tl.append(f'tl.fromTo("#kart{k}", {{autoAlpha:0, scale:0.6}}, {{autoAlpha:1, scale:1, duration:0.6, ease:"back.out(1.8)"}}, {bas[k] + 0.2:.3f});')
        # kelime kelime altyazı (build.py ile aynı parçalara bölünür)
        a, b = zaman[k]
        for i, (p0, p1, parca) in enumerate(B.kutu_parcalari(metinler[k])):
            t0, t1 = a + p0 * (b - a), a + p1 * (b - a)
            kel = parca.split()
            spans = "".join(f'<span class="w">{html.escape(w)}</span> ' for w in kel)
            cid = f"c{k}_{i}"
            altyazi.append(f'<div class="alt" id="{cid}">{spans}</div>')
            tl.append(f'tl.set("#{cid}", {{autoAlpha:1}}, {t0:.3f});')
            tl.append(f'tl.from("#{cid} .w", {{y:40, scale:0.7, autoAlpha:0, duration:0.22, stagger:{(t1 - t0) / max(1, len(kel)) * 0.6:.3f}, ease:"back.out(2)"}}, {t0:.3f});')
            for wi in range(len(kel)):   # konuşulan kelime altın renge döner
                tw = t0 + (t1 - t0) * wi / len(kel)
                tl.append(f'tl.to("#{cid} .w:nth-child({wi + 1})", {{color:"#ffd36b", duration:0.12}}, {tw:.3f});')
            tl.append(f'tl.set("#{cid}", {{autoAlpha:0}}, {t1:.3f});')

    kapak = html.escape(B.tr_buyuk(konu.get("kapak") or ""))
    harfler = "".join(f'<span class="h">{c if c != " " else "&nbsp;"}</span>' for c in kapak)
    tl.append('tl.from("#kapak .h", {y:-120, autoAlpha:0, rotation:-8, duration:0.5, stagger:0.04, ease:"back.out(2.2)"}, 0.15);')
    tl.append(f'tl.to("#kapak", {{autoAlpha:0, y:-40, duration:0.4}}, {max(1.0, son[0] - 0.3):.3f});')
    tl.append(f'tl.fromTo("#ilerleme", {{scaleX:0}}, {{scaleX:1, duration:{toplam:.3f}, ease:"none"}}, 0);')
    kat = html.escape(B.KATEGORI_ADI.get(kategori, ""))

    gsap_etiket = ('<script src="assets/gsap.min.js"></script>' if os.path.exists(os.path.join(HF, "assets", "gsap.min.js"))
                   else '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>')
    sayfa = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/playfair/700.css"><link rel="stylesheet" href="assets/inter/800.css">
{gsap_etiket}
<style>
html,body{{margin:0;background:#000}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:#120c08;font-family:'Inter','DejaVu Sans',sans-serif}}
.clip{{position:absolute;inset:0;overflow:hidden}}
.fill{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.blur{{position:absolute;inset:-60px;background-size:cover;background-position:center;filter:blur(38px) brightness(.45) saturate(1.3)}}
.kb{{position:absolute;inset:0;background-size:cover;background-repeat:no-repeat;transform-origin:50% 45%;filter:contrast(1.08) saturate(1.12)}}
.parsomen{{position:absolute;inset:0;background:radial-gradient(circle at 50% 40%,#e9d6a8,#b89660 70%,#6b5132)}}
.vinyet{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 45%,transparent 45%,rgba(0,0,0,.72) 100%),linear-gradient(to bottom,rgba(0,0,0,.55),transparent 22%,transparent 62%,rgba(0,0,0,.75))}}
#flash{{position:absolute;inset:0;z-index:90;background:radial-gradient(circle at 70% 30%,rgba(255,226,170,.95),rgba(255,180,90,.35) 45%,transparent 75%);opacity:0;pointer-events:none}}
#ust{{position:absolute;top:150px;width:100%;text-align:center;z-index:95;color:#e8be69;font-weight:800;font-size:34px;letter-spacing:6px;text-shadow:0 3px 10px #000}}
#ilerleme{{position:absolute;top:0;left:0;width:100%;height:8px;background:#e8be69;transform-origin:0 50%;z-index:96}}
#kapak{{position:absolute;top:230px;width:100%;text-align:center;z-index:95;font-family:'Playfair Display','DejaVu Serif',serif;font-weight:700;font-size:118px;line-height:1.05;color:#ffe9a8;text-shadow:0 0 30px rgba(255,190,90,.55),0 6px 0 #2a1608,0 10px 30px #000;padding:0 50px}}
.h{{display:inline-block}}
.etiket{{position:absolute;top:225px;left:60px;z-index:95;padding:14px 30px;background:rgba(25,15,10,.88);border:3px solid #e8be69;border-radius:14px;color:#e8be69;font-family:'Playfair Display',serif;font-weight:700;font-size:54px;visibility:hidden}}
.alt{{position:absolute;top:1330px;left:60px;right:60px;z-index:97;text-align:center;font-weight:800;font-size:78px;line-height:1.15;color:#fff;text-shadow:0 0 6px #000,0 5px 0 #000,0 8px 24px rgba(0,0,0,.9);visibility:hidden}}
.w{{display:inline-block}}
.kart{{position:absolute;top:760px;left:90px;right:90px;z-index:96;text-align:center;padding:40px 20px;background:linear-gradient(#b3241f,#7d1512);border:5px solid #e8be69;border-radius:28px;color:#fff3cf;font-family:'Playfair Display',serif;font-weight:700;font-size:76px;box-shadow:0 20px 60px rgba(0,0,0,.7);visibility:hidden}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{toplam:.3f}" data-width="{W}" data-height="{H}">
{chr(10).join(klipler)}
<section id="ust-katman" class="clip" style="z-index:94" data-start="0" data-duration="{toplam:.3f}" data-track-index="3">
<div id="ilerleme"></div><div id="ust">{kat}</div><div id="kapak">{harfler}</div>
{chr(10).join(altyazi)}
<div id="flash"></div>
</section>
<audio id="ses" src="assets/audio.wav" data-start="0" data-duration="{toplam - 0.05:.3f}" data-track-index="2" data-volume="1"></audio>
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(tl)}
window.__timelines = window.__timelines || {{}};
window.__timelines.main = tl;
</script>
</body></html>
"""
    with open(os.path.join(HF, "index.html"), "w", encoding="utf-8") as f:
        f.write(sayfa)
    print(f"HyperFrames projesi hazır: {HF} · {toplam:.1f} sn · {n} parça · {len(tl)} animasyon adımı")


if __name__ == "__main__":
    main()
