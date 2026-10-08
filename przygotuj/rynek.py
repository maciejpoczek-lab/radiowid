#!/usr/bin/env python3
# Dane do mapy swiatla radiowego dla Garwolina - WYLACZNIE kwadrat wokol RYNKU (punkt publiczny). Wariant C: pliki statyczne.
# Uklad: metry od rynku, x = wschod, y = polnoc (jak dolek.py: KX = 111320 cos(lat_rynku), KY = 110570).
# Miasto (siatka KOM m, pol boku POLE m): z NMT i NMPT GUGiK 1 m (dane/nmpt/rynek/) i obrysow LoD1 (dane/budynki3d/rynek.json):
#   G  = grunt (srednia NMT w komorce),
#   O  = wysokosc nieprzezroczysta: komorka w >= polowie pod obrysem budynku -> mediana NMPT pod obrysem, inaczej grunt,
#   ZW = wysokosc korony nad gruntem: komorka w >= polowie zielona (NMPT - NMT > 2,5 m poza obrysami powiekszonymi o 1 m).
#   Agregacja jak w fala.py (tam 1,2 m -> 4,8 m, budynki z ortofotomapy; tu 1 m -> 4 m, budynki z LoD1).
# Teren dalej: ten sam co w dolek.py MODEL=nmt (NMT 30 m do 11,8 km, dalej Copernicus GLO-30) - kopia z eksportu weryfikacji.
# Nadajniki: maszty FM z dolek.py + stacja UKE przy Kosciuszki 6 (maszt 35 m nad gruntem - ZALOZENIE jak w fala.py).
# Wyjscie: mapa/dane/rynek/manifest.json + *.bin (format eksport.py). Kazdy wynik z tych danych to SYMULACJA.
# Uzycie: python3 rynek.py                    -> kwadrat +-900 m z dane/nmpt/rynek (jak dotad), mapa/dane/rynek
#         python3 rynek.py 3000 kafle         -> kwadrat +-3000 m z kafli 1 km (dane/nmpt/kafle), mapa/dane/obszar-3000
#   Z kafli: NMPT poza miastem bywa pusty (usluga oddaje 0) -> budynek bez NMPT dostaje grunt + wysokosc LoD1,
#   koron tam nie znamy (ZW = 0) - tablica NMPT_PROC mowi, jaka czesc komorki miala NMPT.
import json, math, os, shutil, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/dane/nmpt"))
from puwg92 import na_2180
from miejsce import SR, NAZWA, przyrostek

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
DANE = os.path.expanduser("~/dev/showreel-2/dane")
OUT = os.path.join(MAPA, "dane", "rynek"); os.makedirs(OUT, exist_ok=True)
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0
POLE = float(sys.argv[1]) if len(sys.argv) > 1 else 900.0
ZRODLO = sys.argv[2] if len(sys.argv) > 2 else "rynek"
if ZRODLO != "rynek": OUT = os.path.join(MAPA, "dane", przyrostek(f"obszar-{POLE:.0f}")); os.makedirs(OUT, exist_ok=True)
KOM, SUB = 4.0, 4                     # pol boku [m], komorka [m], probki 1 m na bok komorki
PROG_BUD, PROG_ZIEL, H_RX, PODSTAWA_KORONY, H_BTS = 0.5, 0.5, 1.5, 0.3, 35.0

# --- rastry 1 m w EPSG:2180 ---
KAFLE = os.path.join(DANE, "nmpt", przyrostek(ZRODLO))
zk = json.load(open(os.path.join(KAFLE, "zakres.json")))
if ZRODLO == "rynek":
    NMT = np.load(os.path.join(DANE, "nmpt/rynek/nmt.npy")); NMPT = np.load(os.path.join(DANE, "nmpt/rynek/nmpt.npy"))
else:                                                # mozaika kafli 1 km; 0 = brak danych (usluga nie daje NaN)
    nk, K = zk["kafli_na_bok"], zk["kafel"]
    def mozaika(m):
        a = np.empty((nk * K, nk * K), np.float32)
        for i in range(nk):
            for j in range(nk): a[i * K:(i + 1) * K, j * K:(j + 1) * K] = np.load(os.path.join(KAFLE, f"{m}/{i}_{j}.npy"))
        a[a == 0] = np.nan; return a
    NMT, NMPT = mozaika("nmt"), mozaika("nmpt")
    # NMT ma pojedyncze dziury na stykach arkuszy GUGiK (412 komorek 1 m w 4 kaflach, 2026-10-06) -> srednia sasiadow, az do skutku
    while np.isnan(NMT).any():
        p = np.pad(NMT, 1, constant_values=np.nan)
        sasiedzi = np.stack([p[1 + di:p.shape[0] - 1 + di, 1 + dj:p.shape[1] - 1 + dj] for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj])
        with np.errstate(all="ignore"): sr = np.nanmean(sasiedzi, 0)
        NMT = np.where(np.isnan(NMT), sr, NMT)
assert NMT.shape == NMPT.shape
W0, N0 = zk["x_zachod"], zk["y_polnoc"]; ny1, nx1 = NMT.shape
bud = json.load(open(os.path.join(DANE, przyrostek("budynki3d"), "rynek.json" if ZRODLO == "rynek" else "rynek-3000.json")))
im = Image.new("L", (nx1, ny1), 0); dr = ImageDraw.Draw(im)
imw = Image.new("F", (nx1, ny1), 0.0); drw = ImageDraw.Draw(imw)       # wysokosc LoD1 (zapas, gdy brak NMPT)
for b in bud["budynki"]:
    p = [(x - W0, N0 - y) for x, y in b["obrys"]]; dr.polygon(p, fill=255); drw.polygon(p, fill=float(b.get("wys") or 0))
BM = np.asarray(im) > 0; WYS = np.asarray(imw)
pad = np.pad(BM, 1); BM1 = pad[1:-1, 1:-1] | pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]   # obrys + 1 m
nDSM = NMPT - NMT
ZIEL = (nDSM > 2.5) & ~BM1

# --- probki 1 m siatki miasta (uklad lokalny) -> komorki 1 m w EPSG:2180 (najblizszy) ---
n = int(round(2 * POLE / KOM)); m = n * SUB
o = -POLE + (np.arange(m) + 0.5) * (KOM / SUB)
PX, PY = np.meshgrid(o, -o)                        # wiersz 0 = polnoc
pl, ws = na_2180(SR[0] + PY / KY, SR[1] + PX / KX)
ii = np.floor(N0 - pl).astype(int); jj = np.floor(ws - W0).astype(int)
assert ii.min() >= 0 and jj.min() >= 0 and ii.max() < ny1 and jj.max() < nx1, "siatka miasta wychodzi poza pobrany kwadrat"
g1, s1, b1, z1, w1 = NMT[ii, jj], NMPT[ii, jj], BM[ii, jj], ZIEL[ii, jj], WYS[ii, jj]
assert not np.isnan(g1).any(), "braki w NMT"
assert ZRODLO != "rynek" or not np.isnan(s1).any(), "braki w NMPT"
blk = lambda a: a.reshape(n, SUB, n, SUB)
G = blk(g1).mean((1, 3)).astype(np.float32)
fb = blk(b1).mean((1, 3)); fz = blk(z1).mean((1, 3))
Htop = np.where(b1, s1, np.nan); Htop = np.nanmedian(blk(Htop).transpose(0, 2, 1, 3).reshape(n, n, -1), -1) if b1.any() else np.full((n, n), np.nan)
BUD = fb >= PROG_BUD
NMPT_PROC = np.rint(blk(~np.isnan(s1)).mean((1, 3)) * 100).astype(np.uint8)
if np.isnan(s1).any():                               # budynek bez NMPT: grunt + mediana wysokosci LoD1 pod obrysem
    Hlod = np.where(b1, w1, np.nan); Hlod = np.nanmedian(blk(Hlod).transpose(0, 2, 1, 3).reshape(n, n, -1), -1)
    zast = BUD & np.isnan(Htop) & ~np.isnan(Hlod)
    Htop = np.where(zast, G + Hlod, Htop)
    print(f"NMPT pokrywa {np.mean(NMPT_PROC >= 50) * 100:.1f}% komorek; budynkow z wysokoscia z LoD1: {zast.sum()} komorek")
O = np.maximum(np.where(BUD, np.nan_to_num(Htop, nan=0), G), G).astype(np.float32)
zw1 = np.where(z1, s1 - g1, 0)
ZW = np.where((fz >= PROG_ZIEL) & ~BUD, blk(zw1).sum((1, 3)) / np.maximum(blk(z1).sum((1, 3)), 1), 0).astype(np.float32)
print(f"miasto {n}x{n} po {KOM} m: budynki {BUD.mean() * 100:.1f}% komorek, korony {(ZW > 0).mean() * 100:.1f}%, "
      f"grunt {G.min():.1f}-{G.max():.1f} m n.p.m., dachy do {np.nanmax(O - G):.1f} m nad gruntem")

# --- teren dalej: kopia z eksportu weryfikacji dolek.py (wysrodkowany na rynku) ---
# Garwolin: eksport weryfikacji (jak dotad, wycinek M obejmuje tez dalekie maszty FM); inne miejsca: przygotuj/teren.py
DOL = os.path.join(MAPA, "weryfikacja/dane/dolek") if NAZWA == "garwolin" else os.path.join(MAPA, "dane", przyrostek("teren"))
md = json.load(open(os.path.join(DOL, "manifest.json")))
assert md["meta"]["SR"] == list(SR) and abs(md["meta"]["KX"] - KX) < 1e-9
tab = {"O": O, "G": G, "ZW": ZW, "BUD": BUD.astype(np.uint8)}
if ZRODLO != "rynek": tab["NMPT_PROC"] = NMPT_PROC
man = {"tablice": {}}
for k in ("T", "M"):
    shutil.copy(os.path.join(DOL, k + ".bin"), os.path.join(OUT, k + ".bin")); man["tablice"][k] = md["tablice"][k]

# --- nadajniki ---
def lokal(lat, lon): return (lon - SR[1]) * KX, (lat - SR[0]) * KY
nad = [{"nazwa": t["nazwa"].replace("_", " "), "T": t["T"], "f": [100.0], "rodzaj": "FM"} for t in md["meta"]["nadajniki"]]
if NAZWA == "garwolin":                              # stacja z pierwszego etapu (strona index.html)
    bx, by = lokal(51.89611, 21.61639)              # UKE: Orange, Garwolin, Kosciuszki 6 (polozenie z wykazu UKE)
    jb, ib = int((bx + POLE) // KOM), int((POLE - by) // KOM)
    nad.append({"nazwa": "Kościuszki 6", "T": [bx, by, float(G[ib, jb]) + H_BTS], "f": [806.0, 3600.0], "rodzaj": "stacja"})

for k, a in tab.items():
    a = np.ascontiguousarray(a); a.astype(a.dtype.newbyteorder("<")).tofile(os.path.join(OUT, k + ".bin"))
    man["tablice"][k] = {"dtype": a.dtype.name, "ksztalt": list(a.shape)}
md_t = md["meta"]
man["meta"] = {
    "miasto": {"nx": n, "ny": n, "X0": -POLE, "Y1": POLE, "DX": KOM, "DY": KOM},
    "teren": {k: md_t[k] for k in ("SR", "KX", "KY", "RL", "CL", "LAT_TOP", "LON_L", "DLAT", "DLON", "M_wiersz0", "M_kolumna0", "M_ksztalt_calej")},
    "KROK_TERENU": md_t["KROK"], "R_E": md_t["R_E"], "H_RX": H_RX, "PODSTAWA_KORONY": PODSTAWA_KORONY, "nadajniki": nad,
    "zrodla": ["NMT i NMPT: GUGiK (geoportal.gov.pl), stan 2026-10-06",
               "Modele 3D budynków LoD1 2024: GUGiK, CC BY 4.0",
               "Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved",
               "Stacje i nadajniki: UKE (BIP), przetworzone"],
    "uwaga": "SYMULACJA, nie pomiar"}
json.dump(man, open(os.path.join(OUT, "manifest.json"), "w"), indent=1, ensure_ascii=False)
print("->", OUT, {k: v["ksztalt"] for k, v in man["tablice"].items()},
      f"{sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) / 1e6:.1f} MB")
