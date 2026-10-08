#!/usr/bin/env python3
# Obrysy budynkow LoD1 (GUGiK, CC BY 4.0) jako wektory do strony - ostre przy kazdym przyblizeniu, zeby oglądający
# rozpoznal, gdzie stoi (siatka 4 m po zblizeniu to kratka). Uklad lokalny: metry od rynku, x = wschod, y = polnoc.
# EPSG:2180 -> lokalny: uklad.py.
# Wejscie: dane/budynki3d/rynek-3000.json. Wyjscie: mapa/dane/budynki-wektor.json.gz
#   {"zrodlo", "skala": 0.1, "budynki": [[x0, y0, x1, y1, ...] w decymetrach, ...], "wys": [m, ...]}
# Uzycie: python3 budynki_wektor.py
import gzip, json, os
import numpy as np
import uklad
from uklad import lokalny, BLAD_M, SR
from miejsce import przyrostek
DANE = os.path.expanduser("~/dev/showreel-2/dane")
HERE = os.path.dirname(os.path.abspath(__file__))
print(f"EPSG:2180 -> lokalny: max blad dopasowania {BLAD_M * 100:.2f} cm")

src = json.load(open(os.path.join(DANE, przyrostek("budynki3d"), "rynek-3000.json")))
bud, wys = [], []
for b in src["budynki"]:
    o = np.array(json.loads(b["obrys"]) if isinstance(b["obrys"], str) else b["obrys"], float)
    x, y = lokalny(o[:, 0], o[:, 1])
    if len(o) > 1 and np.allclose(o[0], o[-1]): x, y = x[:-1], y[:-1]
    bud.append(np.round(np.stack([x, y], 1).ravel() * 10).astype(int).tolist()); wys.append(round(float(b.get("wys") or 0), 1))
out = {"zrodlo": "Modele 3D budynkow LoD1: GUGiK, CC BY 4.0 (przetworzone: obrysy w ukladzie lokalnym)", "skala": 0.1,
       "uklad": uklad.OPIS, "budynki": bud, "wys": wys}
p = os.path.join(HERE, "../dane", uklad.wyjscie(przyrostek("budynki-wektor")) + ".json.gz")
open(p, "wb").write(gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 9, mtime=0))
print(f"{len(bud)} budynkow -> {p} ({os.path.getsize(p) / 1e3:.0f} kB)")
