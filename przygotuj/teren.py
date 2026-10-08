#!/usr/bin/env python3
# Teren daleki dla miejsca (MIEJSCE=garwolin|warszawa, dane/nmpt/miejsce.py) - zamiennik eksportu weryfikacji dolek.py
# (weryfikacja/eksport.py + proby/teren/dolek.py MODEL=nmt), ale wysrodkowany na dowolnym miejscu:
#   T = NMT GUGiK 40 m (dane/nmpt/region[-miejsce]/) przeliczony na siatke lokalna 30 m, pol boku RL = 11,8 km,
#       braki z Copernicus (jak dolek.py, najblizszy sasiad),
#   M = wycinek mozaiki Copernicus GLO-30 2x2 kafle wokol miejsca, pol boku R_M km (stacje komorkowe do 10 km + zapas).
# Format jak weryfikacja/dane/dolek (manifest.json + T.bin, M.bin; meta te same klucze) - czyta go rynek.py.
# Sprawdzenie: dla Garwolina T i wycinek M musza byc bit w bit jak w weryfikacja/dane/dolek.
# Uzycie: [MIEJSCE=warszawa] python3 teren.py [R_M_km=25]  -> mapa/dane/teren[-miejsce]/
import json, math, os, sys
import numpy as np
NM = os.path.expanduser("~/dev/showreel-2/dane/nmpt"); sys.path.insert(0, NM)
from puwg92 import na_2180
from miejsce import SR, przyrostek

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
DEM = os.path.expanduser("~/dev/showreel-2/dane/dem")
OUT = os.path.join(MAPA, "dane", przyrostek("teren")); os.makedirs(OUT, exist_ok=True)
R_M = float(sys.argv[1]) * 1000 if len(sys.argv) > 1 else 25000.0
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0
RL, CL, R_E, KROK = 11800.0, 30.0, 8.5e6, 30.0
def ll(x, y): return SR[0] + y / KY, SR[1] + x / KX

# mozaika 2x2 kafle 1 stopien, tak by miejsce lezalo jak najdalej od jej brzegu (Garwolin: 51-53 N, 21-23 E jak dolek.py)
la0, lo0 = math.floor(SR[0] - 0.5), math.floor(SR[1] - 0.5)
kaf = lambda la, lo: np.load(os.path.join(DEM, f"N{la:02d}E{lo:03d}.npy"))
M = np.vstack([np.hstack([kaf(la0 + 1, lo0), kaf(la0 + 1, lo0 + 1)]), np.hstack([kaf(la0, lo0), kaf(la0, lo0 + 1)])])
LAT_TOP, LON_L, DLAT, DLON = la0 + 2.0, float(lo0), 1 / 3600, 1 / 2400
def h_dsm(lat, lon):
    i = np.clip(np.rint((LAT_TOP - lat) / DLAT - 0.5).astype(int), 0, M.shape[0] - 1)
    j = np.clip(np.rint((lon - LON_L) / DLON - 0.5).astype(int), 0, M.shape[1] - 1)
    return M[i, j]

zn = json.load(open(os.path.join(NM, przyrostek("region"), "nmt.json"))); N = np.load(os.path.join(NM, przyrostek("region"), "nmt.npy"))
g = np.arange(-RL, RL + 1, CL); GX, GY = np.meshgrid(g, -g)
pl, ws = na_2180(*ll(GX, GY))
ii = np.floor((zn["y_polnoc"] - pl) / zn["komorka"]).astype(int); jj = np.floor((ws - zn["x_zachod"]) / zn["komorka"]).astype(int)
T = N[np.clip(ii, 0, N.shape[0] - 1), np.clip(jj, 0, N.shape[1] - 1)]
braki = int(np.isnan(T).sum())
T = np.where(np.isnan(T), h_dsm(*ll(GX, GY)), T).astype(np.float32)

la = [ll(x, y)[0] for x in (-R_M, R_M) for y in (-R_M, R_M)]; lo = [ll(x, y)[1] for x in (-R_M, R_M) for y in (-R_M, R_M)]
r0 = max(int((LAT_TOP - max(la)) / DLAT) - 10, 0); r1 = min(int((LAT_TOP - min(la)) / DLAT) + 10, M.shape[0])
c0 = max(int((min(lo) - LON_L) / DLON) - 10, 0); c1 = min(int((max(lo) - LON_L) / DLON) + 10, M.shape[1])
assert r0 > 0 and c0 > 0 and r1 < M.shape[0] and c1 < M.shape[1], "wycinek dotyka brzegu mozaiki - potrzeba wiecej kafli"
tab = {"T": T, "M": np.ascontiguousarray(M[r0:r1, c0:c1])}
man = {"tablice": {}, "meta": {"SR": list(SR), "KX": KX, "KY": KY, "RL": RL, "CL": CL, "R_E": R_E,
                               "LAT_TOP": LAT_TOP, "LON_L": LON_L, "DLAT": DLAT, "DLON": DLON,
                               "M_wiersz0": r0, "M_kolumna0": c0, "M_ksztalt_calej": list(M.shape), "KROK": KROK, "nadajniki": []}}
for k, a in tab.items():
    a.astype("<f4").tofile(os.path.join(OUT, k + ".bin")); man["tablice"][k] = {"dtype": "float32", "ksztalt": list(a.shape)}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
print("->", OUT, {k: v["ksztalt"] for k, v in man["tablice"].items()}, f"braki NMT w T: {braki}",
      f"teren {T.min():.1f}-{T.max():.1f} m n.p.m.")
