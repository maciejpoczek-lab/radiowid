#!/usr/bin/env python3
# Eksport wejsc i wynikow wzorcowych z fala.py i dolek.py do porownania z silnikiem JS (porownaj.mjs).
# Wzorzec liczony TERAZ, tym samym kodem: kopia skryptu przycieta przed zapisem wynikow (bez obrazow i plikow
# wyjsciowych) trafia do katalogu tymczasowego i jest uruchamiana przez runpy; HERE wskazuje oryginalny katalog.
# UWAGA PRYWATNOSC: siatka fala.py jest wysrodkowana w prywatnym punkcie -> weryfikacja/dane/ jest w .gitignore, nigdy nie publikowac.
# Uzycie: python3 eksport.py [fala] [dolek]   (domyslnie oba) -> dane/<zestaw>/manifest.json + *.bin
import json, math, os, runpy, sys, tempfile, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PROBY = os.path.expanduser("~/dev/showreel-2/proby")
ZESTAWY = sys.argv[1:] or ["fala", "dolek"]
LINIA_HERE = "HERE = os.path.dirname(os.path.abspath(__file__))"

def uruchom(sciezka, do_znacznika, env=None):
    src = open(sciezka).read()
    assert LINIA_HERE in src and do_znacznika in src, sciezka
    src = src[:src.index(do_znacznika)].replace(LINIA_HERE, f"HERE = {os.path.dirname(sciezka)!r}")
    for k, v in (env or {}).items(): os.environ[k] = v
    with tempfile.TemporaryDirectory() as kat:
        kopia = os.path.join(kat, os.path.basename(sciezka)); open(kopia, "w").write(src)
        t = time.time(); g = runpy.run_path(kopia); return g, time.time() - t

def zapisz(zestaw, tablice, meta):
    kat = os.path.join(HERE, "dane", zestaw); os.makedirs(kat, exist_ok=True)
    man = {"meta": meta, "tablice": {}}
    for nazwa, a in tablice.items():
        a = np.ascontiguousarray(a)
        if a.dtype == bool: a = a.astype(np.uint8)
        a.astype(a.dtype.newbyteorder("<")).tofile(os.path.join(kat, nazwa + ".bin"))
        man["tablice"][nazwa] = {"dtype": a.dtype.name, "ksztalt": list(a.shape)}
    json.dump(man, open(os.path.join(kat, "manifest.json"), "w"), indent=1)
    print(zestaw, "->", kat, {k: v["ksztalt"] for k, v in man["tablice"].items()})

if "fala" in ZESTAWY:
    g, dt = uruchom(os.path.join(PROBY, "miasto/fala.py"), "SUF = ")
    tab = {"O": g["O"], "G": g["G"], "ZW": g["ZW"], "BUD": g["BUD"]}
    for k, (L, nad) in g["mapy"].items(): tab[k + "_L"] = L; tab[k + "_nad"] = nad
    stary = np.load(os.path.join(PROBY, "miasto/out/fala.npz"))   # czy zapisany wynik pochodzi z obecnego kodu
    zgodny = {k: float(np.nanmax(np.abs(stary[k + "_L"] - g["mapy"][k][0]))) for k in g["mapy"]}
    zapisz("fala", tab, {"nx": int(g["nx"]), "ny": int(g["ny"]), "X0": g["X0"], "Y1": g["Y1"], "DX": g["DX"], "DY": g["DY"],
                         "smaxGeom": math.hypot(g["X1"] - g["X0"], g["Y1"] - g["Y0"]),
                         "H_RX": g["H_RX"], "PODSTAWA_KORONY": g["PODSTAWA_KORONY"],
                         "nadajniki": {"fm": {"T": list(g["fT"]), "f": [106.0]}, "stacja": {"T": list(g["sT"]), "f": [806.0, 3600.0]}},
                         "sekundy_python": dt, "roznica_do_zapisanego_npz_dB": zgodny})

if "dolek" in ZESTAWY:
    g, dt = uruchom(os.path.join(PROBY, "teren/dolek.py"), "np.savez_compressed(", {"MODEL": "nmt"})
    M = g["M"]; ll = g["ll"]; SR = g["SR"]
    # wycinek mozaiki Copernicus obejmujacy kwadrat miasta i wszystkie nadajniki (+ margines)
    la = [t["lat"] for t in g["rtv"]]; lo = [t["lon"] for t in g["rtv"]]
    for x in (-g["POLE"], g["POLE"]):
        for y in (-g["POLE"], g["POLE"]):
            a, b = ll(x, y); la.append(a); lo.append(b)
    r0 = max(int((g["LAT_TOP"] - max(la)) / g["DLAT"]) - 10, 0); r1 = min(int((g["LAT_TOP"] - min(la)) / g["DLAT"]) + 10, M.shape[0])
    c0 = max(int((min(lo) - g["LON_L"]) / g["DLON"]) - 10, 0); c1 = min(int((max(lo) - g["LON_L"]) / g["DLON"]) + 10, M.shape[1])
    tab = {"T": g["T"].astype(np.float32), "M": M[r0:r1, c0:c1], "Z": g["Z"], "xs": g["xs"]}
    nad = []
    for t in g["rtv"]:
        k = t["nazwa"].replace(" ", "_"); tab["ref_" + k] = g["wyn"][t["nazwa"]]
        tz = float(g["h"](np.array(t["lat"]), np.array(t["lon"]))) + t["h"]
        nad.append({"nazwa": k, "T": [(t["lon"] - SR[1]) * g["KX"], (t["lat"] - SR[0]) * g["KY"], tz]})
    stary = np.load(os.path.join(PROBY, "teren/out-nmt/dolek.npz"))
    zgodny = {n["nazwa"]: float(np.max(np.abs(stary[n["nazwa"]] - tab["ref_" + n["nazwa"]]))) for n in nad}
    zapisz("dolek", tab, {"SR": list(SR), "KX": g["KX"], "KY": g["KY"], "RL": g["RL"], "CL": g["CL"], "R_E": g["R_E"],
                          "LAT_TOP": g["LAT_TOP"], "LON_L": g["LON_L"], "DLAT": g["DLAT"], "DLON": g["DLON"],
                          "M_wiersz0": r0, "M_kolumna0": c0, "M_ksztalt_calej": list(M.shape),
                          "KROK": g["KROK"], "H_RX": g["H_RX"], "F_MHZ": g["F_MHZ"], "nadajniki": nad,
                          "sekundy_python": dt, "roznica_do_zapisanego_npz_dB": zgodny})
