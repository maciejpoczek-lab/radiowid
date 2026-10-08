#!/usr/bin/env python3
# Stacje bazowe UKE (stan 2026-09-25) w pasie paczek + 3 km (stacje do 3 km za krawedzia widoku, jak ZASIEG_MAPY na stronie)
# -> mapa/dane/stacje-pas.json, uklad strony 2180 (x = E - E0, y = N - N0, rynek Garwolina). Docs §7 (poziomy przyblizenia).
# Wysokosc anteny: ze stacje-2180.json, gdy ta sama stacja (tam z NMPT 1 m); inaczej z paczki 4 m - szczyt O nad mediana G
# w oknie +-32 m N-S / +-20 m E-W (komorka 1" UKE, jak stacje.py), ponizej 8 m albo bez paczki -> brak (silnik bierze zalozenie).
# Uzycie: python3 stacje_pas.py [E_od N_od E_do N_do km]   (domyslnie pas E660N440 + E680N440: 660 440 700 460)
import glob, gzip, json, math, os, re, sys
import numpy as np
DANE = os.path.expanduser("~/dev/showreel-2/dane")
sys.path.insert(0, os.path.join(DANE, "nmpt")); sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/proby/budynki"))
from puwg92 import na_2180
from uke import wiersze
HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE); PAK = os.path.join(MAPA, "dane", "paczki", "v1")
E_OD, N_OD, E_DO, N_DO = (float(v) * 1000 for v in (sys.argv[1:5] if len(sys.argv) > 4 else (660, 440, 700, 460)))
MARGINES, H_MIN = 3000, 8.0
ST0 = json.load(open(os.path.join(MAPA, "dane", "stacje-2180.json"))); E0, N0 = 679860, 451200
assert "E0 679860" in ST0["uklad"] and "N0 451200" in ST0["uklad"], "zmienil sie uklad strony"
ZNANE = {(s["lat"], s["lon"]): s for s in ST0["stacje"]}

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
        n, e = (float(v) for v in na_2180(lat, lon))
        if not (E_OD - MARGINES <= e < E_DO + MARGINES and N_OD - MARGINES <= n < N_DO + MARGINES): continue
        s = st.setdefault((round(lat, 4), round(lon, 4)), {"lat": round(lat, 5), "lon": round(lon, 5), "e": e, "n": n,
                          "operatorzy": set(), "pasma": set(), "adres": f'{w.get("G", "")}, {w.get("H", "")}'.strip(", ")})
        s["operatorzy"].add(w.get("A", "").strip()); s["pasma"].add(pasmo)

# --- paczki 4 m: G i O kafli wokol stacji (dekoder jak weryfikacja/test-paczki.py) ---
paczki = {}
for f in sorted(f for f in os.listdir(PAK) if re.fullmatch(r"E\d{3}N\d{3}\.pak", f)):
    b = open(os.path.join(PAK, f), "rb").read(); dl = int.from_bytes(b[4:8], "little"); paczki[f[:-4]] = (json.loads(b[8:8 + dl]), b, 8 + dl)
pamiec = {}
def kafel(e, n):                                      # kafel 1 km -> (G, O) 250 x 250 albo None
    if (e, n) in pamiec: return pamiec[(e, n)]
    w = None
    for nag, b, st0 in paczki.values():
        wp = nag["kafle"].get(f"{e}_{n}")
        if not wp: continue
        nk, t = nag["ksztalt_kafla"][0], {}
        for x in ("G", "O"):
            off, ln = wp[x]; q = np.cumsum(np.frombuffer(gzip.decompress(b[st0 + off:st0 + off + ln]), "<i2").reshape(nk, nk).astype(np.int64), 1)
            t[x] = ((q + 32768) % 65536 - 32768) * nag["warstwy"][x]["skala"]
        w = (t["G"], t["O"] + t["G"]); break
    pamiec[(e, n)] = w; return w
def okno(e, n, dy=32, dx=20):                         # komorki 4 m w oknie wokol (e, n) -> (G, O) albo None, gdy brak paczki
    G, O = [], []
    for y in np.arange(n - dy + 2, n + dy, 4):
        for x in np.arange(e - dx + 2, e + dx, 4):
            k = kafel(int(x // 1000), int(y // 1000))
            if k is None: return None
            i, j = int((1000 * (y // 1000 + 1) - y) // 4), int((x - 1000 * (x // 1000)) // 4)
            G.append(k[0][i, j]); O.append(k[1][i, j])
    return np.array(G), np.array(O)

out, zr = [], {"stacje-2180 (NMPT 1 m)": 0, "paczka 4 m": 0, "brak": 0}
for s in sorted(st.values(), key=lambda s: (s["n"], s["e"])):
    z = ZNANE.get((s["lat"], s["lon"])); r = {"lat": s["lat"], "lon": s["lon"], "x": round(s["e"] - E0, 1), "y": round(s["n"] - N0, 1),
          "operatorzy": sorted(o for o in s["operatorzy"] if o), "pasma": sorted(s["pasma"]), "adres": s["adres"]}
    if z and z.get("h_ant") is not None: r["h_ant"], r["h_ant_zrodlo"] = z["h_ant"], z["h_ant_zrodlo"]; zr["stacje-2180 (NMPT 1 m)"] += 1
    else:
        w = okno(s["e"], s["n"])
        if w is None: r["h_ant_zrodlo"] = "brak paczki"; zr["brak"] += 1
        else:
            h = float(np.max(w[1]) - np.median(w[0]))
            if h >= H_MIN: r["h_ant"], r["h_ant_zrodlo"] = round(h), "paczka 4 m: szczyt O w komórce 1\""; zr["paczka 4 m"] += 1
            else: r["h_ant_zrodlo"] = f"paczka 4 m: szczyt {h:.0f} m < {H_MIN:g} m"; zr["brak"] += 1
    out.append(r)
json.dump({"zrodlo": "UKE rejestr stacji bazowych, stan 2026-09-25 (bez wysokosci anten, azymutow i mocy)", "uklad": ST0["uklad"],
           "pas_m": [E_OD, N_OD, E_DO, N_DO], "margines_m": MARGINES, "stacje": out},
          open(os.path.join(MAPA, "dane", "stacje-pas.json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(f"stacji w pasie + {MARGINES / 1000:g} km: {len(out)}; wysokosc anteny: {zr}")
