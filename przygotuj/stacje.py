#!/usr/bin/env python3
# Stacje bazowe z rejestru UKE (stan 2026-09-25) w promieniu R km od RYNKU (punkt publiczny) -> mapa/dane/stacje.json.
# Jedna stacja = jedno polozenie (lat/lon zaokraglone do 1e-4), wszystkie pasma i operatorzy razem.
# Do kazdej stacji: odleglosc i azymut OD RYNKU, pokrycie danymi terenu (NMT 40 m region, NMT/NMPT 1 m rynek)
# oraz to, co NMPT mowi o wysokosci w punkcie stacji (tylko w kwadracie 1 m) - rejestr UKE wysokosci anten NIE ma.
# Uzycie: python3 stacje.py [R_km=10]
import glob, json, math, os, re, sys
import numpy as np
DANE = os.path.expanduser("~/dev/showreel-2/dane")
sys.path.insert(0, os.path.join(DANE, "nmpt")); sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/proby/budynki"))
from puwg92 import na_2180
from uke import wiersze
from miejsce import SR, przyrostek
HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0
R = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0

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
        x, y = (lon - SR[1]) * KX, (lat - SR[0]) * KY
        if math.hypot(x, y) > R * 1000: continue
        s = st.setdefault((round(lat, 4), round(lon, 4)), {"lat": round(lat, 5), "lon": round(lon, 5), "x": round(x), "y": round(y),
                          "operatorzy": set(), "pasma": set(), "adres": f'{w.get("G", "")}, {w.get("H", "")}'.strip(", ")})
        s["operatorzy"].add(w.get("A", "").strip()); s["pasma"].add(pasmo)

# --- dane terenu ---
REGK = os.path.join(DANE, "nmpt", przyrostek("region"))
reg = json.load(open(os.path.join(REGK, "nmt.json"))); REG = np.load(os.path.join(REGK, "nmt.npy"))
RYN = os.path.join(DANE, "nmpt", przyrostek("rynek"))     # kwadrat 1 m z pierwszego etapu - jest tylko dla Garwolina
if os.path.exists(os.path.join(RYN, "zakres.json")):
    zk = json.load(open(os.path.join(RYN, "zakres.json")))
    NMT = np.load(os.path.join(RYN, "nmt.npy"), mmap_mode="r"); NMPT = np.load(os.path.join(RYN, "nmpt.npy"), mmap_mode="r")
else: zk = NMT = NMPT = None

def w_regionie(pl, ws):
    i, j = int((reg["y_polnoc"] - pl) // reg["komorka"]), int((ws - reg["x_zachod"]) // reg["komorka"])
    if not (0 <= i < REG.shape[0] and 0 <= j < REG.shape[1]): return None
    v = float(REG[i, j]); return None if math.isnan(v) or v < -100 else round(v, 1)

def nmpt_w_punkcie(pl, ws, r=6):
    if zk is None: return None
    i, j = int(zk["y_polnoc"] - pl), int(ws - zk["x_zachod"])
    if not (r <= i < NMT.shape[0] - r and r <= j < NMT.shape[1] - r): return None
    g = float(np.nanmedian(NMT[i - r:i + r + 1, j - r:j + r + 1]))
    s = np.asarray(NMPT[i - r:i + r + 1, j - r:j + r + 1]) - g
    return {"grunt": round(g, 1), "nad_gruntem_w_punkcie": round(float(NMPT[i, j]) - g, 1), "max_w_promieniu_6m": round(float(np.nanmax(s)), 1)}

# --- wysokosc anteny z NMPT: szczyt (NMPT - grunt) w komorce 1" wokol wspolrzednych UKE ---
# UKE podaje polozenie z dokladnoscia 1" (nie wiemy, czy zaokragla, czy obcina) -> okno +-1" (ok. +-31 m N-S, +-19 m E-W);
# przy +-0,5" Koscuszki 69 dawalo 2 m, czyli maszt lezal poza oknem. Bierzemy NAJWYZSZY
# punkt pokrycia w tej komorce: maszt/antena na dachu wystaje ponad wszystko obok. To GORNA granica (antena wisi zwykle
# nizej niz szczyt masztu). Ponizej H_MIN albo bez danych NMPT (usluga oddaje 0) -> brak pomiaru, zostaje zalozenie.
DY_OK, DX_OK, H_MIN = 31, 19, 8.0
KAF = os.path.join(DANE, "nmpt", przyrostek("kafle")); KZ = json.load(open(os.path.join(KAF, "zakres.json"))) if os.path.exists(os.path.join(KAF, "zakres.json")) else None
WYC = os.path.join(DANE, "nmpt", przyrostek("stacje")); WZ = json.load(open(os.path.join(WYC, "zakres.json"))) if os.path.exists(os.path.join(WYC, "zakres.json")) else {}

def z_kafli(model, pl, ws):
    if not KZ: return None
    a = np.full((2 * DY_OK + 1, 2 * DX_OK + 1), np.nan, np.float32)
    for di in range(-DY_OK, DY_OK + 1):
        for dj in range(-DX_OK, DX_OK + 1):
            r, c = int(KZ["y_polnoc"] - pl) + di, int(ws - KZ["x_zachod"]) + dj
            ti, tj = r // KZ["kafel"], c // KZ["kafel"]
            plik = os.path.join(KAF, model, f"{ti}_{tj}.npy")
            if not (0 <= ti < KZ["kafli_na_bok"] and 0 <= tj < KZ["kafli_na_bok"]) or not os.path.exists(plik): return None
            a[di + DY_OK, dj + DX_OK] = np.load(plik, mmap_mode="r")[r % KZ["kafel"], c % KZ["kafel"]]
    return a

def z_wycinka(model, s, pl, ws):
    k = f'{s["lat"]:.5f}_{s["lon"]:.5f}'; plik = os.path.join(WYC, model, k + ".npy")
    if k not in WZ or not os.path.exists(plik): return None
    z = WZ[k]; i, j = int(z["y_polnoc"] - pl), int(ws - z["x_zachod"])
    return np.asarray(np.load(plik)[i - DY_OK:i + DY_OK + 1, j - DX_OK:j + DX_OK + 1], np.float32)

def z_rynku(model, pl, ws):
    if zk is None: return None
    a = NMT if model == "nmt" else NMPT; i, j = int(zk["y_polnoc"] - pl), int(ws - zk["x_zachod"])
    if not (DY_OK <= i < a.shape[0] - DY_OK and DX_OK <= j < a.shape[1] - DX_OK): return None
    return np.asarray(a[i - DY_OK:i + DY_OK + 1, j - DX_OK:j + DX_OK + 1], np.float32)

def h_anteny(s, pl, ws):
    for zr, f in (("kwadrat 1 m przy rynku", lambda m: z_rynku(m, pl, ws)), ("kafle 1 km", lambda m: z_kafli(m, pl, ws)), ("wycinek przy stacji", lambda m: z_wycinka(m, s, pl, ws))):
        g, p = f("nmt"), f("nmpt")
        if g is None or p is None: continue
        p = np.where(p == 0, np.nan, p); g = np.where(g == 0, np.nan, g)
        if np.all(np.isnan(p)) or np.all(np.isnan(g)): return None, f"{zr}: brak NMPT"
        h = float(np.nanmax(p - np.nanmedian(g)))
        return (round(h), f"{zr}: szczyt NMPT w komórce 1\"") if h >= H_MIN else (None, f"{zr}: szczyt {h:.0f} m < {H_MIN:g} m")
    return None, "brak danych 1 m"

out = []
for s in sorted(st.values(), key=lambda s: math.hypot(s["x"], s["y"])):
    pl, ws = (float(v) for v in na_2180(s["lat"], s["lon"]))
    d = math.hypot(s["x"], s["y"])
    s.update(km=round(d / 1000, 2), azymut_od_rynku=round(math.degrees(math.atan2(s["x"], s["y"])) % 360),
             operatorzy=sorted(o for o in s["operatorzy"] if o), pasma=sorted(s["pasma"]),
             nmt40=w_regionie(pl, ws), nmpt1=nmpt_w_punkcie(pl, ws))
    h, opis = h_anteny(s, pl, ws)
    if h is not None: s["h_ant"] = h
    s["h_ant_zrodlo"] = opis
    out.append(s)

os.makedirs(os.path.join(MAPA, "dane"), exist_ok=True)
json.dump({"zrodlo": "UKE rejestr stacji bazowych, stan 2026-09-25 (bez wysokosci anten, azymutow i mocy)", "srodek": "rynek",
           "rynek": SR, "R_km": R, "stacje": out}, open(os.path.join(MAPA, "dane", przyrostek("stacje") + ".json"), "w"), ensure_ascii=False, indent=1)
bez = [s for s in out if s["nmt40"] is None]
print(f"stacji w {R:g} km: {len(out)}; bez terenu 40 m: {len(bez)}; w kwadracie 1 m: {sum(s['nmpt1'] is not None for s in out)}")
for s in out:
    n = s["nmpt1"]
    print(f'{s["km"]:5.2f} km {s["azymut_od_rynku"]:3d}°  {"+".join(o.split()[0] for o in s["operatorzy"]):22s} {len(s["pasma"]):2d} pasm  '
          f'{s["adres"][:40]:40s}  h_ant {s.get("h_ant", "-")!s:>3} ({s["h_ant_zrodlo"]})' + (f'  NMPT: punkt {n["nad_gruntem_w_punkcie"]} m, max(6 m) {n["max_w_promieniu_6m"]} m' if n else ""))
