#!/usr/bin/env python3
# Podklad do orientacji na stronie "widok z punktu": ulice z nazwami, adresy (wyszukiwarka w telefonie), jezdnie, tory, wody.
# Zrodla (GUGiK, dane otwarte, bezplatnie; pobrane dla calego powiatu garwolinskiego 1403 - decyzja Macka 2026-10-06):
#   PRG punkty adresowe + ulice (dane/gugik-wektor/PRG_*_1403.shp), BDOT10k 1403 (OT_SKJZ_L jezdnie, OT_SKTR_L tory,
#   OT_SWRS_L rzeki, OT_PTWP_A wody powierzchniowe). Na strone idzie tylko kwadrat +-POL m wokol RYNKU.
# Wyszukiwanie adresu dziala na tych danych w telefonie - wpisany adres nigdzie nie wychodzi.
# Wyjscie: mapa/dane/mapa-wektor.json.gz; wspolrzedne lokalne w decymetrach (x = wschod, y = polnoc, od rynku).
# Uzycie: python3 mapa_wektor.py [pol_boku_m=3500]
import gzip, json, os, struct, sys
import xml.etree.ElementTree as ET
import numpy as np
import uklad
from uklad import lokalny, SR
from miejsce import POWIAT, przyrostek
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.expanduser("~/dev/showreel-2/dane/" + przyrostek("gugik-wektor"))
BD = os.path.join(D, f"PL.PZGiK.330.{POWIAT}/BDOT10k/PL.PZGiK.330.{POWIAT}__")
POL = float(sys.argv[1]) if len(sys.argv) > 1 else 3500.0

def dbf(p):                                            # rekordy jako slowniki (tylko pola C)
    d = open(p, "rb").read(); n, hl, rl = struct.unpack("<IHH", d[4:12])
    pola = [(d[32 + 32 * i:43 + 32 * i].split(b"\0")[0].decode(), d[48 + 32 * i]) for i in range((hl - 33) // 32)]
    kod = open(p[:-4] + ".cpg").read().strip() if os.path.exists(p[:-4] + ".cpg") else "utf-8"
    for r in range(n):
        o, w = hl + r * rl + 1, {}
        for nazwa, dl in pola: w[nazwa] = d[o:o + dl].decode(kod, "replace").strip(); o += dl
        yield w

def shp(p):                                            # geometrie: punkt -> [(x, y)], linia/wielokat -> lista czesci
    d = open(p, "rb").read(); o = 100
    while o < len(d):
        _, dl = struct.unpack(">II", d[o:o + 8]); typ = struct.unpack("<i", d[o + 8:o + 12])[0]; b = o + 8
        if typ in (1, 11, 21): yield [struct.unpack("<dd", d[b + 4:b + 20])]
        elif typ in (3, 5, 13, 15, 23, 25):
            nc, npk = struct.unpack("<ii", d[b + 36:b + 44]); cz = list(struct.unpack(f"<{nc}i", d[b + 44:b + 44 + 4 * nc])) + [npk]
            pk = np.frombuffer(d, "<f8", 2 * npk, b + 44 + 4 * nc).reshape(-1, 2)
            yield [pk[cz[i]:cz[i + 1]] for i in range(nc)]
        else: yield []
        o += 8 + 2 * dl

def do_lokalnego(pk, uprosc=1.0):                     # EPSG:2180 (wschod, polnoc) -> dm lokalne; punkty blizej niz uprosc m odpadaja
    x, y = lokalny(pk[:, 0], pk[:, 1]); out, ost = [], None
    for k, (a, b) in enumerate(zip(x, y)):
        if ost is None or k == len(x) - 1 or (a - ost[0]) ** 2 + (b - ost[1]) ** 2 >= uprosc ** 2: out += [round(a * 10), round(b * 10)]; ost = (a, b)
    return out, x, y

w_kwadracie = lambda x, y: (np.abs(x) <= POL) & (np.abs(y) <= POL)

# --- adresy i ulice (PRG) ---
ulice_nazwy, adresy = [], []
idx = {}
for rek, g in zip(dbf(os.path.join(D, f"PRG_PunktyAdresowe_{POWIAT}.dbf")), shp(os.path.join(D, f"PRG_PunktyAdresowe_{POWIAT}.shp"))):
    if not g: continue
    x, y = lokalny(*g[0])
    if not w_kwadracie(x, y): continue
    u = rek["NAZWA_ULC"] or rek["NAZWA_MSC"]; m = rek["NAZWA_MSC"]
    k = idx.setdefault((u, m), len(ulice_nazwy))
    if k == len(ulice_nazwy): ulice_nazwy.append([u, m])
    adresy.append([k, rek["NUMER_PORZ"], round(float(x) * 10), round(float(y) * 10)])
ulice = []
for rek, g in zip(dbf(os.path.join(D, f"PRG_Ulice_{POWIAT}.dbf")), shp(os.path.join(D, f"PRG_Ulice_{POWIAT}.shp"))):
    for cz in g:
        pk, x, y = do_lokalnego(cz)
        if w_kwadracie(x, y).any(): ulice.append([rek["NAZWA_ULC"], pk])

# --- BDOT10k (GML; posList: wschod polnoc) ---
NS = {"gml": "http://www.opengis.net/gml/3.2"}
def gml(plik, cecha):
    for _, el in ET.iterparse(BD + plik):
        if el.tag.endswith("}" + cecha):
            atr = {c.tag.split("}")[1]: (c.text or "").strip() for c in el if len(c) == 0}
            geo = [np.array(p.text.split(), float).reshape(-1, 2) for p in el.iter("{%s}posList" % NS["gml"])]
            yield atr, geo; el.clear()
KLASA = {"droga ekspresowa": 3, "droga główna ruchu przyśpieszonego": 3, "droga główna": 3, "droga zbiorcza": 2, "droga lokalna": 1}
warstwy = {"jezdnie": [], "tory": [], "rzeki": [], "wody": []}
for plik, cecha, w in (("OT_SKJZ_L.xml", "OT_SKJZ_L", "jezdnie"), ("OT_SKTR_L.xml", "OT_SKTR_L", "tory"),
                       ("OT_SWRS_L.xml", "OT_SWRS_L", "rzeki"), ("OT_PTWP_A.xml", "OT_PTWP_A", "wody")):
    for atr, geo in gml(plik, cecha):
        for pk in geo[:1] if w == "wody" else geo:     # wody: tylko obwod zewnetrzny
            l, x, y = do_lokalnego(pk)
            if not w_kwadracie(x, y).any(): continue
            warstwy[w].append([KLASA.get(atr.get("klasaDrogi"), 0), l] if w == "jezdnie" else [atr.get("nazwa", ""), l] if w == "rzeki" else l)

out = {"zrodlo": ["Punkty adresowe i ulice: PRG, GUGiK (dane otwarte), przetworzone",
                  "Jezdnie, tory, rzeki, wody: BDOT10k, GUGiK (dane otwarte), przetworzone"],
       "skala": 0.1, "uklad": uklad.OPIS, "pol_boku_m": POL,
       "ulice_nazwy": ulice_nazwy, "adresy": adresy, "ulice": ulice, **warstwy}
p = os.path.join(HERE, "../dane", uklad.wyjscie(przyrostek("mapa-wektor")) + ".json.gz")
open(p, "wb").write(gzip.compress(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode(), 9, mtime=0))
print(f"adresy {len(adresy)} ({len(ulice_nazwy)} ulic/miejscowości), linie ulic {len(ulice)}, jezdnie {len(warstwy['jezdnie'])}, "
      f"tory {len(warstwy['tory'])}, rzeki {len(warstwy['rzeki'])}, wody {len(warstwy['wody'])} -> {os.path.getsize(p) / 1e3:.0f} kB")
