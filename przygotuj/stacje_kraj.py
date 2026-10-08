#!/usr/bin/env python3
# Stacje bazowe UKE (stan 2026-09-25) z calej Polski -> mapa/dane/kraj/stacje.json.gz dla poziomy.html (4G/5G poza pasem paczek).
# Uklad jak stacje-pas.json (x = E - E0, y = N - N0, rynek Garwolina). Wysokosc anteny tylko ze stacje-pas.json (pas paczek:
# NMPT 1 m albo paczka 4 m); poza pasem brak - silnik bierze zalozenie 35 m (rejestr UKE wysokosci nie ma).
# Zapis kolumnowy (slowniki operatorow i pasm), zeby plik byl maly: stacje = [x, y, h_ant|null, [operatorzy], [pasma], adres].
# Uzycie: python3 stacje_kraj.py
import glob, gzip, json, os, re, sys
DANE = os.path.expanduser("~/dev/showreel-2/dane")
sys.path.insert(0, os.path.join(DANE, "nmpt")); sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/proby/budynki"))
from puwg92 import na_2180
from uke import wiersze
HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
PAS = json.load(open(os.path.join(MAPA, "dane", "stacje-pas.json"))); E0, N0 = 679860, 451200
assert "E0 679860" in PAS["uklad"] and "N0 451200" in PAS["uklad"], "zmienil sie uklad strony"
ZNANE = {(s["lat"], s["lon"]): s["h_ant"] for s in PAS["stacje"] if s.get("h_ant") is not None}

def dms(s):
    m = re.match(r"(\d+)[NSEW](\d+)'(\d+)\"", (s or "").strip())
    return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600 if m else None

st = {}
for p in sorted(glob.glob(os.path.join(DANE, "uke/*.xlsx"))):
    pasmo = os.path.basename(p).split("_-_")[0]
    for i, w in enumerate(wiersze(p)):
        if i == 0: continue
        lon, lat = dms(w.get("E")), dms(w.get("F"))
        if lon is None: continue
        s = st.setdefault((round(lat, 4), round(lon, 4)), {"lat": round(lat, 5), "lon": round(lon, 5), "operatorzy": set(), "pasma": set(),
                          "adres": f'{w.get("G", "")}, {w.get("H", "")}'.strip(", ")})
        s["operatorzy"].add(w.get("A", "").strip()); s["pasma"].add(pasmo)

OP = sorted({o for s in st.values() for o in s["operatorzy"] if o}); PA = sorted({p for s in st.values() for p in s["pasma"]})
iop, ipa = {o: k for k, o in enumerate(OP)}, {p: k for k, p in enumerate(PA)}
# rejestr podaje wspolrzedne w pelnych sekundach, a ten sam maszt roznych operatorow bywa zgloszony z roznica 1-2" (20-60 m):
# punkty blizej niz SKLEJ m to jedna stacja (inaczej "3 najblizsze stacje" bywaja jednym masztem)
SKLEJ = 60
siatka, wsp = {}, []
for s in st.values():
    n, e = (float(v) for v in na_2180(s["lat"], s["lon"])); x, y = e - E0, n - N0
    kx, ky = int(x // SKLEJ), int(y // SKLEJ)
    cel = next((c for i in (-1, 0, 1) for j in (-1, 0, 1) for c in siatka.get((kx + i, ky + j), ()) if (c["x"] - x) ** 2 + (c["y"] - y) ** 2 < SKLEJ ** 2), None)
    if cel is None:
        cel = {"x": x, "y": y, "h": None, "operatorzy": set(), "pasma": set(), "adres": s["adres"], "n": 0}; siatka.setdefault((kx, ky), []).append(cel); wsp.append(cel)
    cel["operatorzy"] |= s["operatorzy"]; cel["pasma"] |= s["pasma"]; cel["n"] += 1
    h = ZNANE.get((s["lat"], s["lon"]))
    if h is not None: cel["h"] = h if cel["h"] is None else max(cel["h"], h)
out = [[round(c["x"]), round(c["y"]), c["h"], sorted(iop[o] for o in c["operatorzy"] if o), sorted(ipa[p] for p in c["pasma"]), c["adres"]] for c in wsp]
zh = sum(c["h"] is not None for c in wsp)
out.sort(key=lambda r: (r[1], r[0]))
os.makedirs(os.path.join(MAPA, "dane", "kraj"), exist_ok=True)
cel = os.path.join(MAPA, "dane", "kraj", "stacje.json.gz")
with gzip.open(cel, "wt", encoding="utf-8", compresslevel=9) as f:
    json.dump({"zrodlo": "UKE rejestr stacji bazowych, stan 2026-09-25 (bez wysokosci anten, azymutow i mocy)", "uklad": "EPSG:2180 minus E0 679860, N0 451200 (rynek Garwolina); azymut geograficzny = siatki + zbieznosc poludnikow w punkcie (liczy strona)",
               "kolumny": ["x", "y", "h_ant", "operatorzy", "pasma", "adres"], "operatorzy": OP, "pasma": PA, "stacje": out},
              f, ensure_ascii=False, separators=(",", ":"))
print(f"punktow rejestru: {len(st)}; stacji po sklejeniu < {SKLEJ} m: {len(out)}; z wysokoscia anteny (pas): {zh}; plik {os.path.getsize(cel) / 1e6:.2f} MB")
