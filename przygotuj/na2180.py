#!/usr/bin/env python3
# Zestaw miejsca w ukladzie 2180 (uklad.py, UKLAD=2180: metry EPSG:2180 minus rynek zaokraglony do 4 m) - przejscie strony na 2180.
# Warstwy miasta (G, O, ZW, BUD, NMPT_PROC) NIE leza w zestawie: strona bierze je wprost z paczek 20 km (silnik/paczka.js, nalozPaczki),
# kafle paczek trafiaja w komorki miasta 1:1. Tu zostaje to, czego paczki jeszcze nie maja:
#   T  = NMT GUGiK 40 m (dane/nmpt/region) na siatce 30 m w osiach 2180, pol boku RL (jak teren.py, bez przeliczenia z lat/lon),
#        braki z Copernicus,
#   M  = Copernicus GLO-30 (wycinek z eksportu jak w rynek.py) przepróbkowany RAZ do siatki 30 m w osiach 2180 (najblizszy) -
#        przegladarka nie potrzebuje wtedy przeliczenia 2180 -> stopnie; poza wycinkiem NaN (silnik rzuca blad jak dotad),
#   nadajniki (meta), stacje-2180.json, rtv-2180.json: polozenia ze stopni (uklad lokalny jest odwracalny dokladnie).
# Wektory: UKLAD=2180 python3 budynki_wektor.py / mapa_wektor.py. Kazdy wynik z tych danych to SYMULACJA.
# Uzycie: UKLAD=2180 python3 na2180.py  -> mapa/dane/obszar-2880-2180/ (potem kompresuj.py), stacje-2180.json, rtv-2180.json
import json, math, os, sys
import numpy as np
NM = os.path.expanduser("~/dev/showreel-2/dane/nmpt"); sys.path.insert(0, NM)
import uklad
from uklad import z_ll, do_ll, E0, N0, ZBIEZNOSC
from miejsce import SR, NAZWA, przyrostek
assert uklad.UKLAD == "2180", "uruchom z UKLAD=2180"

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE); D = os.path.join(MAPA, "dane")
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0
z_lok = lambda x, y: z_ll(SR[0] + np.asarray(y, float) / KY, SR[1] + np.asarray(x, float) / KX)   # dotychczasowy lokalny -> 2180

stary = json.load(open(os.path.join(D, przyrostek("obszar-2880") + "-z", "manifest.json")))["meta"]
DOL = os.path.join(MAPA, "weryfikacja/dane/dolek") if NAZWA == "garwolin" else os.path.join(D, przyrostek("teren"))
md = json.load(open(os.path.join(DOL, "manifest.json"))); mt = md["meta"]
czyt = lambda k: np.fromfile(os.path.join(DOL, k + ".bin"), "<f4").reshape(md["tablice"][k]["ksztalt"])
Mw = czyt("M"); r0, c0 = mt["M_wiersz0"], mt["M_kolumna0"]; Mf0, Mf1 = mt["M_ksztalt_calej"]
def h_m(lat, lon):                                   # jak probnikDolek poza RL: komorka calej mozaiki -> wycinek; poza wycinkiem NaN
    i = np.clip(np.rint((mt["LAT_TOP"] - lat) / mt["DLAT"] - 0.5).astype(int), 0, Mf0 - 1) - r0
    j = np.clip(np.rint((lon - mt["LON_L"]) / mt["DLON"] - 0.5).astype(int), 0, Mf1 - 1) - c0
    ok = (i >= 0) & (i < Mw.shape[0]) & (j >= 0) & (j < Mw.shape[1])
    return np.where(ok, Mw[np.clip(i, 0, Mw.shape[0] - 1), np.clip(j, 0, Mw.shape[1] - 1)], np.nan)

RL, CL = mt["RL"], mt["CL"]
zn = json.load(open(os.path.join(NM, przyrostek("region"), "nmt.json"))); NR = np.load(os.path.join(NM, przyrostek("region"), "nmt.npy"))
g = np.arange(-RL, RL + 1, CL); GX, GY = np.meshgrid(g, -g)
ii = np.floor((zn["y_polnoc"] - (N0 + GY)) / zn["komorka"]).astype(int); jj = np.floor((E0 + GX - zn["x_zachod"]) / zn["komorka"]).astype(int)
T = NR[np.clip(ii, 0, NR.shape[0] - 1), np.clip(jj, 0, NR.shape[1] - 1)]
la0, lo0 = math.floor(SR[0] - 0.5), math.floor(SR[1] - 0.5)    # braki NMT: pelna mozaika Copernicus 2 x 2 kafle (jak teren.py)
kaf = lambda a, b: np.load(os.path.expanduser(f"~/dev/showreel-2/dane/dem/N{a:02d}E{b:03d}.npy"))
MC = np.vstack([np.hstack([kaf(la0 + 1, lo0), kaf(la0 + 1, lo0 + 1)]), np.hstack([kaf(la0, lo0), kaf(la0, lo0 + 1)])])
assert (la0 + 2.0, float(lo0)) == (mt["LAT_TOP"], mt["LON_L"]) and list(MC.shape) == [Mf0, Mf1]
def h_dsm(lat, lon):
    return MC[np.clip(np.rint((mt["LAT_TOP"] - lat) / mt["DLAT"] - 0.5).astype(int), 0, Mf0 - 1),
              np.clip(np.rint((lon - mt["LON_L"]) / mt["DLON"] - 0.5).astype(int), 0, Mf1 - 1)]
braki = np.isnan(T); T[braki] = h_dsm(*do_ll(GX[braki], GY[braki])); T = T.astype(np.float32); assert not np.isnan(T).any()

la = [mt["LAT_TOP"] - (r0 + a) * mt["DLAT"] for a in (0, Mw.shape[0])]; lo = [mt["LON_L"] + (c0 + b) * mt["DLON"] for b in (0, Mw.shape[1])]
xs, ys = z_ll(np.array([la[0], la[0], la[1], la[1]]), np.array([lo[0], lo[1], lo[0], lo[1]]))
MX0, MY1 = math.floor(xs.min() / CL) * CL, math.ceil(ys.max() / CL) * CL
mnx, mny = int(math.ceil((xs.max() - MX0) / CL)), int(math.ceil((MY1 - ys.min()) / CL))
M = np.empty((mny, mnx), np.float32)
for a in range(0, mny, 200):                         # srodki komorek siatki 2180 -> stopnie -> komorka Copernicus
    PX, PY = np.meshgrid(MX0 + (np.arange(mnx) + 0.5) * CL, MY1 - (np.arange(a, min(a + 200, mny)) + 0.5) * CL)
    M[a:a + PX.shape[0]] = h_m(*do_ll(PX, PY))

def xy(lat, lon): x, y = z_ll(lat, lon); return round(float(x), 1), round(float(y), 1)
nad = []
for n in stary["nadajniki"]:
    x, y = (float(v) for v in z_lok(*n["T"][:2])); nad.append({**n, "T": [x, y, n["T"][2]]})

OUT = os.path.join(D, uklad.wyjscie(przyrostek("obszar-2880"))); os.makedirs(OUT, exist_ok=True)
man = {"tablice": {}, "meta": {**stary,
    "uklad": {"nazwa": "EPSG:2180", "E0": E0, "N0": N0, "zbieznosc_deg": ZBIEZNOSC, "opis": uklad.OPIS},
    "teren": {"uklad": "EPSG:2180", "RL": RL, "CL": CL, "M_X0": MX0, "M_Y1": MY1, "M_C": CL},
    "nadajniki": nad, "paczki": "dane/paczki/v1 (warstwy miasta G, O, ZW, BUD, NMPT_PROC)"}}
for k, a in (("T", T), ("M", M)):
    a.astype("<f4").tofile(os.path.join(OUT, k + ".bin")); man["tablice"][k] = {"dtype": "float32", "ksztalt": list(a.shape)}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1, ensure_ascii=False)
print(f"-> {OUT}: T {T.shape} (braki NMT {int(braki.sum())}), M {M.shape} od x {MX0} y {MY1}, NaN w M {np.isnan(M).mean() * 100:.1f}%")

st = json.load(open(os.path.join(D, przyrostek("stacje") + ".json")))
for s in st["stacje"]: s["x"], s["y"] = xy(s["lat"], s["lon"])
st["uklad"] = uklad.OPIS
json.dump(st, open(os.path.join(D, uklad.wyjscie(przyrostek("stacje")) + ".json"), "w"), ensure_ascii=False, indent=1)
rtv = json.load(open(os.path.join(D, przyrostek("rtv") + ".json")))
def zbieznosc(lat, lon):                             # azymut geograficzny - azymut w siatce 2180 w danym miejscu [st.]
    (n1, e1), (n2, e2) = uklad.na_2180(lat, lon), uklad.na_2180(lat + 0.01, lon); return -math.degrees(math.atan2(float(e2 - e1), float(n2 - n1)))
for gr in rtv["meta"]["grupy"]:                      # charakterystyka anteny UKE jest geograficzna -> zbieznosc w miejscu nadajnika
    lat, lon = SR[0] + gr["y"] / KY, SR[1] + gr["x"] / KX
    gr["x"], gr["y"] = (float(v) for v in z_lok(gr["x"], gr["y"])); gr["zbieznosc"] = round(zbieznosc(lat, lon), 4)
rtv["meta"]["uklad"] = uklad.OPIS
json.dump(rtv, open(os.path.join(D, uklad.wyjscie(przyrostek("rtv")) + ".json"), "w"), ensure_ascii=False, separators=(",", ":"))
print(f"stacje {len(st['stacje'])}, grupy rtv {len(rtv['meta']['grupy'])}, nadajniki {len(nad)}; zbieznosc {ZBIEZNOSC:.3f} st.")
