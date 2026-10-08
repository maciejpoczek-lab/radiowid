# Czytniki danych GUGiK bez GDAL (komputer testowy ma tylko numpy): BDOT10k GML w zipie, SHP/DBF (PRG), upraszczanie linii.
# Te same czytniki co w mapa_pasa.py (krok 1), wyniesione do wspolnego modulu dla mapa_kraj.py (docs/projekt-paczek-20km.md §8).
import struct
import xml.etree.ElementTree as ET
import numpy as np

def gml(z, cecha):                                         # (atrybuty, [posList jako (E, N)]) z warstwy BDOT10k w zipie
    nazwy = [n for n in z.namelist() if n.endswith(f"__{cecha}.xml")]
    if not nazwy: return
    with z.open(nazwy[0]) as f:
        for _, el in ET.iterparse(f):
            if el.tag.endswith("}" + cecha):
                atr = {c.tag.split("}")[1]: (c.text or "").strip() for c in el if len(c) == 0}
                geo = [np.array(p.text.split(), float).reshape(-1, 2) for p in el.iter() if p.tag.endswith("}posList") or p.tag.endswith("}pos")]
                yield atr, geo; el.clear()

def dbf(b, kod="utf-8"):                                   # rekordy DBF (pola jako tekst) z bajtow
    n, hl, rl = struct.unpack("<IHH", b[4:12]); pola = [(b[32 + 32 * i:43 + 32 * i].split(b"\0")[0].decode(), b[48 + 32 * i]) for i in range((hl - 33) // 32)]
    for r in range(n):
        o, w = hl + r * rl + 1, {}
        for nazwa, dl in pola: w[nazwa] = b[o:o + dl].decode(kod, "replace").strip(); o += dl
        yield w

def shp(b):                                                # geometrie SHP: punkt -> [(E, N)], linia/wielokat -> lista czesci (pierscieni)
    o = 100
    while o < len(b):
        _, dl = struct.unpack(">II", b[o:o + 8]); typ = struct.unpack("<i", b[o + 8:o + 12])[0]; s = o + 8
        if typ in (1, 11, 21): yield [np.array([struct.unpack("<dd", b[s + 4:s + 20])])]
        elif typ in (3, 5, 13, 15, 23, 25):
            nc, npk = struct.unpack("<ii", b[s + 36:s + 44]); cz = list(struct.unpack(f"<{nc}i", b[s + 44:s + 44 + 4 * nc])) + [npk]
            pk = np.frombuffer(b, "<f8", 2 * npk, s + 44 + 4 * nc).reshape(-1, 2); yield [pk[cz[i]:cz[i + 1]] for i in range(nc)]
        else: yield []
        o += 8 + 2 * dl

def dp(pk, tol):                                           # Douglas-Peucker (iteracyjnie) -> punkty linii odchylone o >= tol zostaja
    n = len(pk)
    if n < 3 or tol <= 0: return pk
    zost = np.zeros(n, bool); zost[0] = zost[-1] = True; stos = [(0, n - 1)]
    while stos:
        a, b = stos.pop()
        if b <= a + 1: continue
        p, q = pk[a], pk[b]; d = q - p; L = np.hypot(*d); s = pk[a + 1:b] - p
        odl = np.abs(d[0] * s[:, 1] - d[1] * s[:, 0]) / L if L > 0 else np.hypot(s[:, 0], s[:, 1])
        k = int(np.argmax(odl))
        if odl[k] >= tol: m = a + 1 + k; zost[m] = True; stos += [(a, m), (m, b)]
    return pk[zost]

def tnij(pk, x0, y0, x1, y1):                              # linia -> czesci wewnatrz prostokata [x0, x1] x [y0, y1] (Liang-Barsky po odcinkach)
    czesci, biez = [], []
    for k in range(len(pk) - 1):
        (ax, ay), (bx, by) = pk[k], pk[k + 1]; dx, dy = bx - ax, by - ay; t0, t1 = 0.0, 1.0; ok = True
        for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
            if p == 0:
                if q < 0: ok = False; break
            else:
                t = q / p
                if p < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        if not ok or t0 > t1:
            if len(biez) >= 2: czesci.append(np.array(biez))
            biez = []; continue
        A, B = (ax + t0 * dx, ay + t0 * dy), (ax + t1 * dx, ay + t1 * dy)
        if not biez: biez = [A]
        biez.append(B)
        if t1 < 1:
            if len(biez) >= 2: czesci.append(np.array(biez))
            biez = []
    if len(biez) >= 2: czesci.append(np.array(biez))
    return czesci

def dlugosc(pk): return float(np.hypot(*np.diff(pk, axis=0).T).sum()) if len(pk) > 1 else 0.0
def pole(pk): return abs(float(np.dot(pk[:-1, 0], pk[1:, 1]) - np.dot(pk[1:, 0], pk[:-1, 1]))) / 2
