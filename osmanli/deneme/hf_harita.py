"""DENEME: HyperFrames ile yeni nesil harita animasyonu (Mohaç 1526 sefer haritası).

Mevcut Python haritasından farkları: eğik (3B) kamera, orduyu takip eden kamera, yolda yürüyen asker birlikleri ve
dalgalanan sancak, ardında toz, ayağa kalkan şehir iğneleri, kâğıt dokulu kara, Tuna nehri, bulut katmanı,
çarpışmada duman/ışık/sarsıntı, ay sayacı. Ses yok; sadece görüntü denemesi.
Çıktı: out/hfh/index.html (+ assets) → npx hyperframes render
"""
import json, math, os, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OSM = os.path.dirname(HERE)
ROOT = os.path.dirname(OSM)
OUT = os.path.join(ROOT, "out", "hfh")
W, H = 1080, 1920
LON0, LAT0, LAT_REF, K = 13.0, 51.5, 44.0, 190.0
COS = math.cos(math.radians(LAT_REF))
MW, MH = int((33.5 - LON0) * K * COS), int((LAT0 - 37.5) * K)
SURE = 22.0


def xy(lon, lat):
    return ((lon - LON0) * K * COS, (LAT0 - lat) * K)


def kara_yolu():
    veri = json.load(open(os.path.join(OSM, "assets", "harita_kara.json")))
    parcalar = []
    for h in veri:
        xs = [a for a, _ in h]; ys = [b for _, b in h]
        if max(xs) < 12 or min(xs) > 34 or max(ys) < 36 or min(ys) > 52:
            continue
        nok = [xy(a, b) for a, b in h]
        parcalar.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in nok) + "Z")
    return " ".join(parcalar)


def catmull(noktalar, adim=14):
    """Köşeleri yumuşatılmış, yoğun nokta dizisi (ordu, çizgi ve toz aynı yolu kullanır)."""
    p = [noktalar[0]] + noktalar + [noktalar[-1]]
    cikti = []
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(adim):
            t = s / adim
            t2, t3 = t * t, t * t * t
            cikti.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                      (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    cikti.append(p[-2])
    return cikti


def uzunluk_noktasi(yol, f):
    """Yolun uzunluğunun f oranındaki nokta."""
    parcalar = [math.dist(yol[i], yol[i + 1]) for i in range(len(yol) - 1)]
    hedef = sum(parcalar) * f
    for i, l in enumerate(parcalar):
        if hedef <= l:
            a = hedef / l if l else 0
            return (yol[i][0] + (yol[i + 1][0] - yol[i][0]) * a, yol[i][1] + (yol[i + 1][1] - yol[i][1]) * a)
        hedef -= l
    return yol[-1]


def d_yolu(yol):
    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in yol)


def ordu_svg(renk, koyu, sancak):
    """Yandan bakış: üç sıra asker (miğfer + mızrak) ve önde dalgalanan sancak."""
    askerler = []
    for sira in range(3):
        for i in range(5):
            x, y = 14 + i * 15 + sira * 7, 44 + sira * 11
            askerler.append(f'<circle cx="{x}" cy="{y - 10}" r="4.2" fill="{koyu}"/>'
                            f'<rect x="{x - 4}" y="{y - 6}" width="8" height="12" rx="2" fill="{renk}" stroke="{koyu}" stroke-width="1.2"/>'
                            f'<line x1="{x + 5}" y1="{y + 6}" x2="{x + 8}" y2="{y - 22}" stroke="#3a2a1a" stroke-width="1.6"/>')
    return (f'<svg width="110" height="90" viewBox="0 0 110 90">'
            f'<ellipse cx="50" cy="80" rx="48" ry="9" fill="rgba(0,0,0,.35)"/>'
            f'{"".join(askerler)}'
            f'<line x1="90" y1="70" x2="90" y2="6" stroke="#2a1a0e" stroke-width="3"/>'
            f'<g class="bayrak"><path d="M90,7 Q104,4 118,10 Q104,16 90,22 Z" fill="{renk}" stroke="{koyu}" stroke-width="1.5"/>'
            f'{sancak}</g></svg>')


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(os.path.join(OUT, "assets"))
    for dosya in ("gsap.min.js", "MotionPathPlugin.min.js"):
        k = os.path.join(ROOT, "node_modules", "gsap", "dist", dosya)
        if os.path.exists(k):
            shutil.copy(k, os.path.join(OUT, "assets", dosya))
    for paket, ad in (("playfair-display", "playfair"), ("inter", "inter")):
        k = os.path.join(ROOT, "node_modules", "@fontsource", paket)
        if os.path.isdir(k):
            shutil.copytree(k, os.path.join(OUT, "assets", ad))

    SEHIR = {"İstanbul": (28.98, 41.01), "Edirne": (26.56, 41.68), "Filibe": (24.75, 42.15), "Sofya": (23.32, 42.7),
             "Niş": (21.9, 43.32), "Belgrad": (20.46, 44.82), "Petervaradin": (19.87, 45.25), "Mohaç": (18.68, 45.99),
             "Budin": (19.04, 47.5)}
    osm = catmull([xy(*SEHIR[s]) for s in ("İstanbul", "Edirne", "Filibe", "Sofya", "Niş", "Belgrad", "Petervaradin", "Mohaç")])
    osm[-1] = (osm[-1][0] + 18, osm[-1][1] + 10)   # Mohaç'ın hemen güneydoğusunda dursun
    mac = catmull([xy(*SEHIR["Budin"]), xy(19.0, 46.9), xy(18.82, 46.35), xy(18.7, 46.05)])
    tuna = catmull([xy(*p) for p in ((18.95, 48.0), (19.05, 47.5), (18.92, 46.8), (18.85, 46.3), (18.75, 45.95), (18.95, 45.55),
                                     (19.5, 45.25), (19.9, 45.25), (20.45, 44.83), (21.4, 44.65), (22.5, 44.55), (22.7, 44.2),
                                     (23.6, 43.8), (25.0, 43.65), (26.0, 43.9), (27.2, 44.1), (28.0, 44.2), (28.3, 45.3), (29.6, 45.2))], 10)

    # zamanlama (sn)
    YURU = (2.0, 11.5)      # Osmanlı yürüyüşü
    MAC = (9.0, 13.0)       # Macar ordusu
    CARP = 13.6             # çarpışma
    tl = []

    def kamera(t, sure, nokta, s, ease="power2.inOut"):
        tx, ty = W / 2 - nokta[0] * s, H * 0.56 - nokta[1] * s
        tl.append(f'tl.to("#kamera", {{x:{tx:.1f}, y:{ty:.1f}, scale:{s}, duration:{sure}, ease:"{ease}"}}, {t});')

    # başlangıç kamerası: İstanbul
    p0 = xy(*SEHIR["İstanbul"])
    tl.append(f'tl.set("#kamera", {{x:{W / 2 - p0[0] * 1.25:.1f}, y:{H * 0.56 - p0[1] * 1.25:.1f}, scale:1.25}}, 0);')
    tl.append('tl.fromTo("#egim", {rotationX:62}, {rotationX:40, duration:2.4, ease:"power3.out"}, 0);')
    # orduyu takip et
    for f in (0.12, 0.3, 0.48, 0.66, 0.84):
        t = YURU[0] + (YURU[1] - YURU[0]) * f
        kamera(t - 1.6, 1.9, uzunluk_noktasi(osm, min(1, f + 0.08)), 1.15)
    # iki orduyu birlikte göster, sonra Mohaç'a dal
    kamera(9.2, 2.2, ((xy(*SEHIR["Mohaç"])[0] + xy(*SEHIR["Petervaradin"])[0]) / 2, xy(*SEHIR["Mohaç"])[1] - 40), 0.95)
    kamera(12.2, 1.6, xy(*SEHIR["Mohaç"]), 2.3, "power3.in")
    tl.append(f'tl.to("#egim", {{rotationX:50, duration:1.6, ease:"power2.in"}}, 12.2);')

    # rota çizgileri (çizilerek ilerler) + ordular
    for ad, yol, (a, b) in (("osm", osm, YURU), ("mac", mac, MAC)):
        uz = sum(math.dist(yol[i], yol[i + 1]) for i in range(len(yol) - 1))
        tl.append(f'tl.fromTo("#rota-{ad}", {{strokeDashoffset:{uz:.0f}}}, {{strokeDashoffset:0, duration:{b - a}, ease:"none"}}, {a});')
        tl.append(f'tl.fromTo("#parlak-{ad}", {{strokeDashoffset:{uz:.0f}}}, {{strokeDashoffset:0, duration:{b - a}, ease:"none"}}, {a});')
        tl.append(f'tl.fromTo("#ordu-{ad}", {{autoAlpha:0, scale:0.3}}, {{autoAlpha:1, scale:1, duration:0.5, ease:"back.out(2)"}}, {a - 0.3});')
        tl.append(f'tl.to("#ordu-{ad}", {{motionPath:{{path:{json.dumps([{"x": round(x, 1), "y": round(y, 1)} for x, y in yol[::2]] + [{"x": round(yol[-1][0], 1), "y": round(yol[-1][1], 1)}])}, curviness:0.6}}, duration:{b - a}, ease:"none"}}, {a});')
        # toz bulutları
        for i in range(int((b - a) * 5)):
            f = i / ((b - a) * 5)
            x, y = uzunluk_noktasi(yol, f)
            t = a + (b - a) * f
            tl.append(f'tl.fromTo("#toz-{ad}-{i}", {{autoAlpha:0.75, scale:0.4, x:{x:.0f}, y:{y:.0f}}}, '
                      f'{{autoAlpha:0, scale:2.4, y:{y - 26:.0f}, duration:1.4, ease:"power1.out"}}, {t:.2f});')
    # yürüyüş sallanması ve sancak dalgası (sonlu tekrar)
    tl.append(f'tl.fromTo(".adim", {{y:0}}, {{y:-5, duration:0.18, yoyo:true, repeat:{int(SURE / 0.18)}, ease:"sine.inOut"}}, 0);')
    tl.append(f'tl.fromTo(".bayrak", {{skewY:0}}, {{skewY:-10, duration:0.45, yoyo:true, repeat:{int(SURE / 0.45)}, ease:"sine.inOut", transformOrigin:"0% 50%"}}, 0);')

    # şehir iğneleri: ordu geçerken ayağa kalkar
    pin_html = []
    sira = ("İstanbul", "Edirne", "Filibe", "Sofya", "Niş", "Belgrad", "Petervaradin", "Mohaç")
    for i, s in enumerate(list(SEHIR)):
        x, y = xy(*SEHIR[s])
        pid = f"pin{i}"
        pin_html.append(f'<div class="pin-pos" style="left:{x:.0f}px;top:{y:.0f}px"><div class="pin" id="{pid}">'
                        f'<div class="pin-ad">{s.upper().replace("I", "I")}</div><div class="pin-sap"></div><div class="pin-nokta"></div></div></div>')
        if s in sira:
            t = YURU[0] + (YURU[1] - YURU[0]) * sira.index(s) / (len(sira) - 1) - 0.3
        else:
            t = MAC[0] - 0.4
        tl.append(f'tl.fromTo("#{pid}", {{autoAlpha:0, rotationX:-90}}, {{autoAlpha:1, rotationX:-40, duration:0.6, ease:"back.out(2.5)"}}, {max(0.2, t):.2f});')

    # ay sayacı ve alt bilgi kartları
    aylar = ["23 NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS"]
    for i, ay in enumerate(aylar):
        t = YURU[0] + (YURU[1] - YURU[0]) * i / len(aylar)
        tl.append(f'tl.set("#ay", {{textContent:"{ay}"}}, {t:.2f});')
        tl.append(f'tl.fromTo("#ay", {{y:30, autoAlpha:0}}, {{y:0, autoAlpha:1, duration:0.35, ease:"power2.out"}}, {t:.2f});')
    tl.append('tl.fromTo("#takvim", {autoAlpha:0, x:-60}, {autoAlpha:1, x:0, duration:0.6, ease:"power3.out"}, 1.6);')
    notlar = [(2.2, "Kanuni İstanbul'dan yola çıkıyor"), (6.6, "Belgrad'dan Tuna boyunca kuzeye"),
              (9.4, "Macar ordusu Budin'den iniyor"), (12.6, "Mohaç ovası")]
    for i, (t, m) in enumerate(notlar):
        tl.append(f'tl.fromTo("#not{i}", {{autoAlpha:0, y:40}}, {{autoAlpha:1, y:0, duration:0.45, ease:"power3.out"}}, {t});')
        son = notlar[i + 1][0] - 0.2 if i + 1 < len(notlar) else CARP - 0.1
        tl.append(f'tl.to("#not{i}", {{autoAlpha:0, y:-30, duration:0.3}}, {son});')

    # çarpışma: ışık, sarsıntı, duman, kılıçlar, damga
    mx, my = xy(*SEHIR["Mohaç"])
    tl.append(f'tl.fromTo("#flas", {{opacity:0}}, {{opacity:0.9, duration:0.08, yoyo:true, repeat:1}}, {CARP});')
    tl.append(f'tl.fromTo("#sars", {{x:0}}, {{x:14, duration:0.05, yoyo:true, repeat:11, ease:"none"}}, {CARP});')
    for i in range(14):
        aci = i / 14 * 2 * math.pi
        r = 70 + (i % 3) * 30
        tl.append(f'tl.fromTo("#duman{i}", {{autoAlpha:0.85, scale:0.3, x:{mx + 6:.0f}, y:{my - 6:.0f}}}, '
                  f'{{autoAlpha:0, scale:2.6, x:{mx + math.cos(aci) * r:.0f}, y:{my + math.sin(aci) * r * 0.6 - 20:.0f}, duration:2.4, ease:"power2.out"}}, {CARP + i * 0.04:.2f});')
    tl.append(f'tl.fromTo("#kilic", {{autoAlpha:0, scale:3, rotation:-30}}, {{autoAlpha:1, scale:1, rotation:0, duration:0.45, ease:"back.out(2.4)"}}, {CARP + 0.05});')
    tl.append(f'tl.to("#ordu-mac", {{autoAlpha:0, x:"-=60", y:"-=90", duration:1.6, ease:"power2.in"}}, {CARP + 1.8});')
    tl.append(f'tl.to("#kilic", {{autoAlpha:0, duration:0.5}}, {CARP + 2.6});')
    tl.append(f'tl.fromTo("#damga", {{autoAlpha:0, scale:2.6, rotation:-18}}, {{autoAlpha:1, scale:1, rotation:-8, duration:0.35, ease:"power4.in"}}, {CARP + 3.0});')
    tl.append(f'tl.fromTo("#damga-golge", {{autoAlpha:0}}, {{autoAlpha:1, duration:0.2}}, {CARP + 3.3});')
    kamera(CARP + 2.8, 3.5, (mx, my - 30), 1.7)
    tl.append(f'tl.to("#egim", {{rotationX:30, duration:3.5, ease:"power2.out"}}, {CARP + 2.8});')
    # başlık, bulutlar, ışık süpürmesi
    tl.append('tl.from("#baslik .h", {y:-140, autoAlpha:0, rotation:-10, duration:0.55, stagger:0.045, ease:"back.out(2.2)"}, 0.3);')
    tl.append('tl.from("#altbaslik", {autoAlpha:0, letterSpacing:"30px", duration:1.0, ease:"power3.out"}, 0.9);')
    for i in range(4):
        tl.append(f'tl.fromTo("#bulut{i}", {{x:{-500 + i * 420}}}, {{x:{-500 + i * 420 + 520}, duration:{SURE}, ease:"none"}}, 0);')
    tl.append(f'tl.fromTo("#isik", {{x:-900}}, {{x:1500, duration:3.0, ease:"power1.inOut"}}, 0.4);')

    toz = "".join(f'<div class="toz" id="toz-{ad}-{i}"></div>' for ad, (a, b) in (("osm", YURU), ("mac", MAC)) for i in range(int((b - a) * 5)))
    duman = "".join(f'<div class="duman" id="duman{i}"></div>' for i in range(14))
    bulutlar = "".join(f'<div class="bulut" id="bulut{i}" style="top:{180 + i * 430}px;left:{(i % 2) * 300}px"></div>' for i in range(4))
    baslik = " ".join('<span class="kel">' + "".join(f'<span class="h">{c}</span>' for c in k) + "</span>" for k in "MOHAÇ 1526".split())
    hilal = '<circle cx="104" cy="14" r="4" fill="#fff"/><circle cx="105.6" cy="14" r="3.3" fill="#b3241f"/>'
    hac = '<rect x="102" y="9.5" width="2.4" height="9" fill="#fff"/><rect x="99" y="12.8" width="8.4" height="2.4" fill="#fff"/>'
    osm_svg = ordu_svg("#b3241f", "#4a0d0b", hilal)
    mac_svg = ordu_svg("#2b4f9e", "#0e1d44", hac)
    uz_osm = sum(math.dist(osm[i], osm[i + 1]) for i in range(len(osm) - 1))
    uz_mac = sum(math.dist(mac[i], mac[i + 1]) for i in range(len(mac) - 1))
    izgara = "".join(f'<line x1="{xy(l, 50)[0]:.0f}" y1="0" x2="{xy(l, 50)[0]:.0f}" y2="{MH}"/>' for l in range(15, 33, 2)) + \
             "".join(f'<line x1="0" y1="{xy(20, l)[1]:.0f}" x2="{MW}" y2="{xy(20, l)[1]:.0f}"/>' for l in range(39, 50, 2))

    sayfa = f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8">
<link rel="stylesheet" href="assets/playfair/700.css"><link rel="stylesheet" href="assets/inter/800.css">
<script src="assets/gsap.min.js"></script><script src="assets/MotionPathPlugin.min.js"></script>
<style>
html,body{{margin:0;background:#000}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:#0b1a22;font-family:'Inter',sans-serif}}
.clip{{position:absolute;inset:0;overflow:hidden}}
#sars{{position:absolute;inset:0}}
#sahne{{position:absolute;inset:0;perspective:1500px;perspective-origin:50% 30%}}
#egim{{position:absolute;inset:0;transform-style:preserve-3d;transform-origin:50% 62%}}
#kamera{{position:absolute;left:0;top:0;width:{MW}px;height:{MH}px;transform-origin:0 0;transform-style:preserve-3d}}
#harita{{position:absolute;left:0;top:0}}
.pin-pos{{position:absolute;width:0;height:0;transform-style:preserve-3d}}
.pin{{position:absolute;left:0;top:0;transform-origin:0 0;transform-style:preserve-3d;visibility:hidden}}
.pin-nokta{{position:absolute;left:-9px;top:-9px;width:18px;height:18px;border-radius:50%;background:#e8be69;border:4px solid #3a2410;box-shadow:0 0 18px rgba(255,200,110,.9)}}
.pin-sap{{position:absolute;left:-2px;top:-62px;width:4px;height:62px;background:linear-gradient(#3a2410,#7a5328)}}
.pin-ad{{position:absolute;left:0;top:-112px;transform:translateX(-50%);white-space:nowrap;padding:8px 18px;background:#f6ead0;border:3px solid #3a2410;border-radius:10px;font-family:'Playfair Display',serif;font-weight:700;font-size:34px;color:#2a1608;box-shadow:0 8px 18px rgba(0,0,0,.45)}}
.ordu-pos{{position:absolute;left:0;top:0;width:0;height:0;transform-style:preserve-3d;visibility:hidden}}
.ordu-gor{{position:absolute;left:-55px;top:-82px;transform-origin:50% 100%;transform:rotateX(-40deg) scale(1.35)}}
.toz{{position:absolute;left:-26px;top:-26px;width:52px;height:52px;border-radius:50%;background:radial-gradient(rgba(214,188,140,.9),rgba(214,188,140,0) 70%);visibility:hidden}}
.duman{{position:absolute;left:-60px;top:-60px;width:120px;height:120px;border-radius:50%;background:radial-gradient(rgba(70,62,56,.95),rgba(70,62,56,0) 70%);visibility:hidden}}
#kilic{{position:absolute;left:{mx - 70:.0f}px;top:{my - 190:.0f}px;width:140px;height:140px;visibility:hidden;transform:rotateX(-40deg)}}
#damga{{position:absolute;left:{mx + 40:.0f}px;top:{my - 230:.0f}px;padding:16px 26px;border:6px double #b3241f;color:#b3241f;font-family:'Playfair Display',serif;font-weight:700;font-size:44px;line-height:1.1;text-align:center;background:rgba(246,234,208,.85);transform-origin:50% 50%;visibility:hidden}}
#damga-golge{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 55%,transparent 30%,rgba(0,0,0,.5));visibility:hidden}}
.bulut{{position:absolute;width:760px;height:300px;border-radius:50%;background:radial-gradient(rgba(255,252,244,.42),rgba(255,252,244,0) 70%);filter:blur(10px)}}
#isik{{position:absolute;top:-200px;width:420px;height:2400px;background:linear-gradient(90deg,transparent,rgba(255,235,190,.16),transparent);transform:rotate(18deg)}}
#vinyet{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 52%,transparent 50%,rgba(0,0,0,.7)),linear-gradient(to bottom,rgba(5,10,14,.85),transparent 26%,transparent 70%,rgba(5,10,14,.9))}}
#flas{{position:absolute;inset:0;background:radial-gradient(circle at 50% 55%,#fff6dc,rgba(255,190,90,.5) 40%,transparent 75%);opacity:0}}
#ust{{position:absolute;top:150px;width:100%;text-align:center;color:#e8be69;font-weight:800;font-size:34px;letter-spacing:6px;text-shadow:0 3px 10px #000}}
#baslik{{position:absolute;top:205px;width:100%;text-align:center;font-family:'Playfair Display',serif;font-weight:700;font-size:120px;color:#ffe9a8;text-shadow:0 0 34px rgba(255,190,90,.6),0 6px 0 #2a1608,0 12px 30px #000}}
.h,.kel{{display:inline-block}} .kel{{white-space:nowrap}}
#altbaslik{{position:absolute;top:350px;width:100%;text-align:center;color:#f3dca6;font-weight:800;font-size:36px;letter-spacing:10px;text-shadow:0 3px 10px #000}}
#takvim{{position:absolute;left:60px;top:450px;padding:14px 26px;background:rgba(20,12,8,.82);border:3px solid #e8be69;border-radius:16px;color:#e8be69;font-weight:800;font-size:26px;letter-spacing:4px;visibility:hidden}}
#ay{{display:block;color:#fff3cf;font-family:'Playfair Display',serif;font-size:56px;letter-spacing:1px}}
.not{{position:absolute;left:60px;right:60px;top:1500px;text-align:center;visibility:hidden}}
.not span{{display:inline-block;padding:18px 34px;background:rgba(18,10,6,.86);border:3px solid #e8be69;border-radius:18px;color:#fff;font-weight:800;font-size:56px;line-height:1.15}}
</style></head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{SURE}" data-width="{W}" data-height="{H}">
<section id="katman" class="clip" data-start="0" data-duration="{SURE}" data-track-index="1">
<div id="sars"><div id="sahne"><div id="egim"><div id="kamera">
<svg id="harita" width="{MW}" height="{MH}" viewBox="0 0 {MW} {MH}">
<defs>
<filter id="kagit" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="4" seed="7"/>
<feColorMatrix values="0 0 0 0 0.45  0 0 0 0 0.33  0 0 0 0 0.18  0 0 0 0.55 0"/><feComposite in2="SourceGraphic" operator="in"/></filter>
<filter id="kiyi" x="-5%" y="-5%" width="110%" height="110%"><feMorphology in="SourceAlpha" operator="dilate" radius="10"/><feGaussianBlur stdDeviation="9"/>
<feColorMatrix values="0 0 0 0 0.55  0 0 0 0 0.8  0 0 0 0 0.85  0 0 0 0.55 0"/></filter>
<linearGradient id="deniz" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d4a5a"/><stop offset="1" stop-color="#0d2632"/></linearGradient>
<linearGradient id="kara" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ead7a8"/><stop offset=".6" stop-color="#d9bd85"/><stop offset="1" stop-color="#c4a36a"/></linearGradient>
<pattern id="dalga" width="90" height="40" patternUnits="userSpaceOnUse"><path d="M0,20 q11,-9 22,0 t22,0" fill="none" stroke="rgba(170,215,225,.18)" stroke-width="2"/></pattern>
</defs>
<rect width="{MW}" height="{MH}" fill="url(#deniz)"/><rect width="{MW}" height="{MH}" fill="url(#dalga)"/>
<g stroke="rgba(255,240,200,.08)" stroke-width="2">{izgara}</g>
<path d="{kara_yolu()}" filter="url(#kiyi)"/>
<path d="{kara_yolu()}" fill="url(#kara)" stroke="#5a3d1e" stroke-width="3.5" stroke-linejoin="round"/>
<path d="{kara_yolu()}" fill="#000" filter="url(#kagit)" opacity=".9"/>
<path d="{d_yolu(tuna)}" fill="none" stroke="#3f7f95" stroke-width="13" stroke-linecap="round" stroke-linejoin="round" opacity=".9"/>
<path d="{d_yolu(tuna)}" fill="none" stroke="#9fd0dc" stroke-width="4" stroke-linecap="round" opacity=".8"/>
<text x="{xy(24.6, 43.95)[0]:.0f}" y="{xy(24.6, 43.95)[1]:.0f}" font-family="Playfair Display,serif" font-size="40" font-style="italic" fill="#2f6a80" opacity=".85">Tuna</text>
<path id="rota-osm" d="{d_yolu(osm)}" fill="none" stroke="#7a1512" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="{uz_osm:.0f}" opacity=".9"/>
<path id="parlak-osm" d="{d_yolu(osm)}" fill="none" stroke="#ff8a5c" stroke-width="5" stroke-linecap="round" stroke-dasharray="{uz_osm:.0f}"/>
<path id="rota-mac" d="{d_yolu(mac)}" fill="none" stroke="#14275a" stroke-width="16" stroke-linecap="round" stroke-dasharray="{uz_mac:.0f}" opacity=".9"/>
<path id="parlak-mac" d="{d_yolu(mac)}" fill="none" stroke="#7aa6ff" stroke-width="5" stroke-linecap="round" stroke-dasharray="{uz_mac:.0f}"/>
</svg>
{toz}
{"".join(pin_html)}
<div class="ordu-pos" id="ordu-osm"><div class="ordu-gor"><div class="adim">{osm_svg}</div></div></div>
<div class="ordu-pos" id="ordu-mac"><div class="ordu-gor"><div class="adim">{mac_svg}</div></div></div>
{duman}
<svg id="kilic" viewBox="0 0 140 140"><g stroke="#2a1a0e" stroke-width="5" stroke-linecap="round"><line x1="20" y1="120" x2="118" y2="22" stroke="#e9eef2" stroke-width="10"/><line x1="120" y1="120" x2="22" y2="22" stroke="#e9eef2" stroke-width="10"/>
<line x1="30" y1="96" x2="44" y2="110"/><line x1="96" y1="110" x2="110" y2="96"/></g></svg>
<div id="damga">ZAFER<br><small style="font-size:26px">29 AĞUSTOS 1526</small></div>
</div></div></div>
{bulutlar}<div id="isik"></div><div id="vinyet"></div><div id="damga-golge"></div><div id="flas"></div>
</div>
<div id="ust">SAVAŞLAR VE İSYANLAR</div>
<div id="baslik">{baslik}</div><div id="altbaslik">KANUNİ'NİN MACARİSTAN SEFERİ</div>
<div id="takvim">1526<span id="ay">23 NİSAN</span></div>
{"".join(f'<div class="not" id="not{i}"><span>{m}</span></div>' for i, (_, m) in enumerate(notlar))}
</section>
</div>
<script>
gsap.registerPlugin(MotionPathPlugin);
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(tl)}
window.__timelines = window.__timelines || {{}};
window.__timelines.main = tl;
</script>
</body></html>
"""
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(sayfa)
    print(f"Harita denemesi hazır: {OUT} · {SURE} sn · harita {MW}x{MH}px · {len(tl)} animasyon adımı")


if __name__ == "__main__":
    main()
