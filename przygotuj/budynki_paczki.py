#!/usr/bin/env python3
# Obrysy budynkow LoD1 (GUGiK, modele 3D 2024, CityGML na powiat, CC BY 4.0) dla JEDNEJ paczki 20 km -> <katalog>/budynki.json.
# Obrys = najnizsza sciana bryly (jak budynki_lod1.py). Powiaty podaje sie jawnie (TERYT), np. z uslugi ULDK GetCountyByXY dla siatki
# punktow paczki. Zip powiatu: pobierz -> czytaj GML w pamieci -> skasuj. Jeden plik naraz.
# Uzycie: python3 budynki_paczki.py E_KM N_KM KATALOG TERYT [TERYT ...]     np. 660 440 ~/paczki/praca/E660N440 1403 1417 1407
import io, json, os, re, sys, time, urllib.request, zipfile

E_KM, N_KM, KAT, POW = int(sys.argv[1]), int(sys.argv[2]), os.path.expanduser(sys.argv[3]), sys.argv[4:]
X1, Y1 = E_KM * 1000, N_KM * 1000; X2, Y2 = X1 + 20000, Y1 + 20000
URL = "https://opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD1/2024/{w}/{p}.zip"
UA = {"User-Agent": "showreel-mapa-swiatla/1.0 (pobieranie modeli LoD1 po jednym powiecie)"}
BUD = re.compile(rb"<bldg:Building\b.*?</bldg:Building>", re.S)
POS = re.compile(rb"<gml:posList[^>]*>([^<]*)</gml:posList>")
WYS = re.compile(rb"<bldg:measuredHeight[^>]*>([^<]*)<")
ID = re.compile(rb'gml:id="([^"]*)"')
ENV = re.compile(rb"<gml:lowerCorner>([^<]*)</gml:lowerCorner>\s*<gml:upperCorner>([^<]*)<")
wynik, opis = [], []
for p in POW:
    t0 = time.time(); u = URL.format(w=p[:2], p=p)
    dane = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=600).read()
    z = zipfile.ZipFile(io.BytesIO(dane)); n0, ark = len(wynik), 0
    for nazwa in z.namelist():
        if not nazwa.lower().endswith(".gml"): continue
        s = z.read(nazwa); env = ENV.search(s)
        if env:
            lo, hi = (list(map(float, env.group(k).split())) for k in (1, 2))
            if lo[0] > X2 or hi[0] < X1 or lo[1] > Y2 or hi[1] < Y1: continue
        ark += 1
        for b in BUD.findall(s):
            sciany = []
            for pl in POS.findall(b):
                v = list(map(float, pl.split())); sciany.append([(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)])
            if not sciany: continue
            xs = [q[0] for w in sciany for q in w]; ys = [q[1] for w in sciany for q in w]
            if min(xs) > X2 or max(xs) < X1 or min(ys) > Y2 or max(ys) < Y1: continue
            dol = min(sciany, key=lambda w: (max(q[2] for q in w) - min(q[2] for q in w), sum(q[2] for q in w) / len(w)))
            mh = WYS.search(b)
            wynik.append({"id": ID.search(b).group(1).decode(), "obrys": [[round(q[0], 2), round(q[1], 2)] for q in dol],
                          "wys": float(mh.group(1)) if mh else None})
    del dane, z
    print(f"powiat {p}: arkuszy w paczce {ark}, budynkow {len(wynik) - n0}, {time.time() - t0:.0f} s", flush=True)
    opis.append(p); time.sleep(1)
json.dump({"uklad": "EPSG:2180 (x = wschod, y = polnoc)", "kwadrat": [X1, X2, Y1, Y2], "powiaty": opis,
           "zrodlo": "GUGiK, modele 3D budynkow LoD1 2024, CC BY 4.0", "budynki": wynik}, open(os.path.join(KAT, "budynki.json"), "w"))
print("budynkow razem", len(wynik))
