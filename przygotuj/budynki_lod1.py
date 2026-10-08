# Obrysy budynkow z modeli 3D GUGiK LoD1 (CityGML, plik na powiat; 2024, licencja CC BY 4.0 - podpis zrodla obowiazkowy).
# Bierze budynki, ktorych obwiednia przecina kwadrat wokol RYNKU; obrys = najnizsza sciana bryly (podstawa).
# Wejscie: ~/dev/showreel-2/dane/budynki3d/*.gml (rozpakowany 1403.zip); wyjscie: dane/budynki3d/rynek.json (bok 1000 m) albo rynek-<bok>.json
# Uzycie: python3 budynki_lod1.py [pol_boku_m=1000]
import glob, json, os, re, sys
sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/dane/nmpt"))
from puwg92 import na_2180
from miejsce import SR, POWIAT, OPIS, przyrostek
D = os.path.expanduser("~/dev/showreel-2/dane/" + przyrostek("budynki3d"))
H = float(sys.argv[1]) if len(sys.argv) > 1 else 1000.0
pln0, wsch0 = (round(float(v) / 10) * 10 for v in na_2180(*SR))
X1, X2, Y1, Y2 = wsch0 - H, wsch0 + H, pln0 - H, pln0 + H
BUD = re.compile(r"<bldg:Building\b.*?</bldg:Building>", re.S)
POS = re.compile(r"<gml:posList[^>]*>([^<]*)</gml:posList>")
WYS = re.compile(r"<bldg:measuredHeight[^>]*>([^<]*)<")
ID = re.compile(r'gml:id="([^"]*)"')
wynik = []; plikow = 0
for p in sorted(glob.glob(os.path.join(D, "*.gml"))):
    s = open(p, encoding="utf-8").read()
    env = re.search(r"<gml:lowerCorner>([^<]*)</gml:lowerCorner>\s*<gml:upperCorner>([^<]*)<", s)
    lo, hi = (list(map(float, env.group(k).split())) for k in (1, 2))
    if lo[0] > X2 or hi[0] < X1 or lo[1] > Y2 or hi[1] < Y1: continue
    plikow += 1
    for b in BUD.findall(s):
        sciany = []
        for pl in POS.findall(b):
            v = list(map(float, pl.split())); pkt = [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]
            sciany.append(pkt)
        if not sciany: continue
        xs = [q[0] for w in sciany for q in w]; ys = [q[1] for w in sciany for q in w]
        if min(xs) > X2 or max(xs) < X1 or min(ys) > Y2 or max(ys) < Y1: continue
        dol = min(sciany, key=lambda w: (max(q[2] for q in w) - min(q[2] for q in w), sum(q[2] for q in w) / len(w)))
        zmin = min(q[2] for q in dol); zmax = max(q[2] for w in sciany for q in w)
        mh = WYS.search(b)
        wynik.append({"id": ID.search(b).group(1), "obrys": [[round(q[0], 2), round(q[1], 2)] for q in dol],
                      "z_dol": round(zmin, 2), "z_gora": round(zmax, 2), "wys": float(mh.group(1)) if mh else None})
json.dump({"uklad": "EPSG:2180 (x = wschod, y = polnoc)", "kwadrat": [X1, X2, Y1, Y2], "srodek": "rynek",
           "zrodlo": f"GUGiK, modele 3D budynkow LoD1 2024, powiat {POWIAT} ({OPIS}), CC BY 4.0", "budynki": wynik},
          open(os.path.join(D, "rynek.json" if H == 1000 else f"rynek-{H:.0f}.json"), "w"))
print(f"arkuszy {plikow}, budynkow {len(wynik)}; wysokosc (z_gora - z_dol) mediana",
      sorted(b["z_gora"] - b["z_dol"] for b in wynik)[len(wynik) // 2] if wynik else None)
