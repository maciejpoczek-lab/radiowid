# EPSG:2180 (wschod, polnoc) -> uklad lokalny mapy (metry od rynku, x = wschod, y = polnoc; KX = 111320 cos(lat), KY = 110570).
# puwg92 ma tylko kierunek "na 2180", wiec odwrotnosc to wielomian 2. stopnia dopasowany na siatce punktow +-4,5 km;
# blad dopasowania sprawdzany przy imporcie (assert < 5 cm; zmierzone 0,26 cm).
import math, os, sys
import numpy as np
sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/dane/nmpt"))
from puwg92 import na_2180
from miejsce import SR
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0

_lx, _ly = (a.ravel() for a in np.meshgrid(np.arange(-4500, 4501, 250.0), np.arange(-4500, 4501, 250.0)))
_pl, _ws = (np.array(v, float) for v in zip(*(na_2180(SR[0] + y / KY, SR[1] + x / KX) for x, y in zip(_lx, _ly))))
_ws0, _pl0 = _ws.mean(), _pl.mean()
def _cechy(w, p): u, v = (np.asarray(w, float) - _ws0) / 1000, (np.asarray(p, float) - _pl0) / 1000; return np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], -1)
_A = _cechy(_ws, _pl); _cx = np.linalg.lstsq(_A, _lx, rcond=None)[0]; _cy = np.linalg.lstsq(_A, _ly, rcond=None)[0]
BLAD_M = float(max(np.abs(_A @ _cx - _lx).max(), np.abs(_A @ _cy - _ly).max()))
assert BLAD_M < 0.05, BLAD_M

def lokalny(wschod, polnoc):
    F = _cechy(wschod, polnoc); return F @ _cx, F @ _cy

# --- UKLAD=2180: metry EPSG:2180 przesuniete do rynku (x = E - E0, y = N - N0), osie siatki krajowej, bez obrotu ---
# E0, N0 = rynek zaokraglony do 4 m, zeby komorki miasta (4 m) lezaly dokladnie na komorkach paczek 20 km (przygotuj/paczka.py).
# Polnoc siatki 2180 odchyla sie od polnocy geograficznej (zbieznosc poludnikow, Garwolin ok. 2 st.): azymut geograficzny
# = azymut w siatce + ZBIEZNOSC. Pliki wyjsciowe dostaja przyrostek "-2180" (wyjscie()).
UKLAD = os.environ.get("UKLAD", "lokalny"); assert UKLAD in ("lokalny", "2180"), UKLAD
N0, E0 = (round(float(v) / 4) * 4 for v in na_2180(*SR))
_dn, _de = (float(b - a) for a, b in zip(na_2180(*SR), na_2180(SR[0] + 0.01, SR[1])))
ZBIEZNOSC = -math.degrees(math.atan2(_de, _dn))         # azymut geograficzny - azymut w siatce 2180 [st.]
if UKLAD == "2180":
    def lokalny(wschod, polnoc): return np.asarray(wschod, float) - E0, np.asarray(polnoc, float) - N0
    BLAD_M = 0.0
OPIS = (f"EPSG:2180 minus rynek (E0 {E0}, N0 {N0}), x = wschod, y = polnoc siatki 2180; azymut geograficzny = siatki + {ZBIEZNOSC:.3f} st."
        if UKLAD == "2180" else f"metry od rynku {SR[0]} N {SR[1]} E, x = wschod, y = polnoc")
def wyjscie(nazwa): return nazwa + ("-2180" if UKLAD == "2180" else "")
def z_ll(lat, lon):                                    # stopnie -> uklad mapy
    if UKLAD == "2180": pl, ws = na_2180(lat, lon); return np.asarray(ws, float) - E0, np.asarray(pl, float) - N0
    return (np.asarray(lon, float) - SR[1]) * KX, (np.asarray(lat, float) - SR[0]) * KY
def do_ll(x, y, iter=6):                               # uklad 2180 mapy -> stopnie (Newton na na_2180; blad < 1 mm)
    x, y = np.asarray(x, float), np.asarray(y, float); la = SR[0] + y / KY; lo = SR[1] + x / KX; h = 1e-6
    for _ in range(iter):
        pl, ws = na_2180(la, lo); fn, fe = pl - N0 - y, ws - E0 - x
        pa, wa = na_2180(la + h, lo); po, wo = na_2180(la, lo + h)
        a, b, c, d = (pa - pl) / h, (po - pl) / h, (wa - ws) / h, (wo - ws) / h; det = a * d - b * c
        la, lo = la - (d * fn - b * fe) / det, lo - (a * fe - c * fn) / det
    return la, lo
