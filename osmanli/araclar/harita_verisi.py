"""Natural Earth (kamu malı) kara verisinden Akdeniz–Karadeniz bölgesini kesip sadeleştirir:
osmanli/assets/harita_kara.json  →  [[[lon, lat], ...], ...]  (dış halkalar)"""
import json, os, sys, urllib.request
from shapely.geometry import box, shape, mapping
from shapely.ops import unary_union

KAYNAK = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson"
BOLGE = box(-12, 24, 60, 56)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

veri = json.load(urllib.request.urlopen(KAYNAK))
kara = unary_union([shape(f["geometry"]) for f in veri["features"]]).intersection(BOLGE)
kara = kara.simplify(0.012, preserve_topology=True)
halkalar = []
for g in getattr(kara, "geoms", [kara]):
    if g.geom_type != "Polygon" or g.area < 0.004:
        continue
    halkalar.append([[round(x, 3), round(y, 3)] for x, y in g.exterior.coords])
yol = os.path.join(ROOT, "osmanli", "assets", "harita_kara.json")
os.makedirs(os.path.dirname(yol), exist_ok=True)
with open(yol, "w") as f:
    json.dump(halkalar, f, separators=(",", ":"))
print(len(halkalar), "halka", os.path.getsize(yol) // 1024, "KB")
