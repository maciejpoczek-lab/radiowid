#!/usr/bin/env python3
# Obrysy budynkow LoD1 jednej paczki 20 km do strony: budynki.json z budynki_paczki.py -> E...N...-budynki.json.gz na stdout
#   {"rog": [e, n], "skala": 0.1, "zrodlo", "budynki": [[x0, y0, x1, y1, ...] w decymetrach od rogu paczki (EPSG:2180), ...]}
# Budynek nalezy do paczki, w ktorej lezy srodek jego obrysu (na brzegu - tylko w jednej). Uruchamiany na komputerze testowym,
# gdzie leza budynki.json (setki MB), wynik idzie na Maca strumieniem:
#   ssh "$KOLEJKA" "python3 - ~/paczki/praca/E620N480/budynki.json" < przygotuj/obrysy_paczki.py > dane/paczki/v1/E620N480-budynki.json.gz
import gzip, json, sys
src = json.load(open(sys.argv[1]))
x1, x2, y1, y2 = src["kwadrat"]
bud = []
for b in src["budynki"]:
    o = b["obrys"]
    if len(o) > 1 and o[0] == o[-1]: o = o[:-1]
    if len(o) < 3: continue
    sx = sum(q[0] for q in o) / len(o); sy = sum(q[1] for q in o) / len(o)
    if not (x1 <= sx < x2 and y1 <= sy < y2): continue
    bud.append([round((v - r) * 10) for q in o for v, r in zip(q, (x1, y1))])
out = {"rog": [x1, y1], "skala": 0.1, "zrodlo": src.get("zrodlo", "GUGiK, modele 3D budynkow LoD1 2024, CC BY 4.0"), "budynki": bud}
sys.stdout.buffer.write(gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 9, mtime=0))
print(f"{len(bud)} budynkow z {len(src['budynki'])}", file=sys.stderr)
