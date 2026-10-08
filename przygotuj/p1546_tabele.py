#!/usr/bin/env python3
# Tablice krzywych ITU-R P.1546-6 dla mapy: figury 1, 9, 17 (ląd, 50% czasu; 100 / 600 / 2000 MHz; h2 = 10 m; 1 kW e.r.p.)
# z implementacji wzorcowej ITU-R SG3 (P1546FieldStrMixed.m v6.2, zmienna exceltables) -> mapa/silnik/p1546-tabele.js
# Wejście: dane/itu-p1546/p1/ (paczka R19-WP3K-C-0264!N05-P1, itu.int, pobrana 2026-10-06 za zgodą Maćka).
# Uzycie: python3 p1546_tabele.py
import glob, json, os, re
src = glob.glob(os.path.expanduser("~/dev/showreel-2/dane/itu-p1546/p1/*/P1546FieldStrMixed.m"))[0]
t = open(src).read(); a = t.index("exceltables = ..."); b = t.index("}", a)
tabs = [[[float(x) for x in r.split(",")] for r in m.strip().split(";") if r.strip()] for m in re.findall(r"\[([^\]]*)\]", t[a:b])]
assert len(tabs) == 24 and all(len(x) == 79 for x in tabs)
sel = {100: tabs[0], 600: tabs[8], 2000: tabs[16]}
out = {"zrodlo": "ITU-R P.1546-6, tabele krzywych (figury 1, 9, 17: ląd, 50% czasu, 50% miejsc, h2 = 10 m, 1 kW e.r.p.), z implementacji wzorcowej ITU-R SG3 P1546FieldStrMixed.m v6.2",
       "h1": sel[100][0][1:9], "d": [r[0] for r in sel[100][1:]], "E": {str(f): [r[1:9] for r in v[1:]] for f, v in sel.items()}}
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../silnik/p1546-tabele.js")
open(p, "w").write("// " + out["zrodlo"] + "\n// E[f][i_d][i_h1] w dBµV/m; d [km], h1 [m]. Wygenerowane przez przygotuj/p1546_tabele.py\nexport default "
                   + json.dumps(out, separators=(",", ":")) + ";\n")
print(p, os.path.getsize(p), "B")
