#!/usr/bin/env python3
# Podklad Polski (docs/projekt-paczek-20km.md §8.1-8.3): plik krajowy dla wszystkich + podklad i adresy kazdej paczki 20 km.
# Zrodla (GUGiK, dane otwarte, bezplatnie, pobrane 2026-10-07 na komputer testowy, katalog GUGIK):
#   granice.zip          - PRG jednostki administracyjne (A00 panstwo, A01 wojewodztwa, A02 powiaty; wspolrzedne ETRS89 w stopniach)
#   bdot/{TERYT}_GML.zip - BDOT10k per powiat: jezdnie, tory, rzeki, wody, miejscowosci
#   prg-adresy/{TERYT}_PRG.zip - PRG ulice i punkty adresowe per powiat (EPSG:2180)
# Dwa etapy, bo powiat lezy w kilku paczkach, a paczka w kilku powiatach:
#   powiaty - kazdy powiat osobno (rownolegle): linie pociete na granicach paczek, uproszczone, wspolrzedne od rogu paczki
#             -> GUGIK/posrednie/paczki/E...N.../{TERYT}.json.gz oraz GUGIK/posrednie/kraj/{TERYT}.json.gz (wklad do pliku krajowego)
#   zloz    - paczka po paczce: E...N...-mapa.json.gz, E...N...-adresy.json.gz (katalog PACZKI); potem kraj/podklad.json.gz
# Uproszczenie Douglasa-Peuckera: paczka 2 m (pelna) i 30 m (ogolna, widok > ok. 20 km), kraj 150 m (granice 200 m).
# Paczki sie stykaja, nie zachodza: linia przecinajaca granice jest cieta na granicy, wody (wielokaty) przycinane do kwadratu.
# Podklad sluzy tylko do orientacji na mapie zasiegu (SYMULACJA), nie jest mapa urzedowa.
# Uzycie: nice ionice -c3 python3 mapa_kraj.py powiaty [TERYT ...]   (bez listy: wszystkie z bdot/, ktorych jeszcze nie ma)
#         nice ionice -c3 python3 mapa_kraj.py zloz
import collections, glob, gzip, json, os, sys, zipfile
from multiprocessing import Pool
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gugik import gml, dbf, shp, dp, tnij, dlugosc, pole
from puwg92 import na_2180

GUGIK = os.environ.get("GUGIK") or os.path.expanduser("~/paczki/dane/gugik")
KRAJ = os.environ.get("KRAJ_WYJSCIE") or os.path.expanduser("~/paczki/kraj")
PACZKI = os.environ.get("PACZKI_WYJSCIE") or os.path.expanduser("~/paczki/mapa-paczek")
POSR = os.path.join(GUGIK, "posrednie")
BOK, TOL, TOL_OGOL, TOL_KRAJ, TOL_GRANIC = 20000, 2.0, 30.0, 150.0, 200.0
KLASA = {"autostrada": 4, "droga ekspresowa": 4, "droga główna ruchu przyśpieszonego": 4, "droga główna": 4,
         "droga zbiorcza": 3, "droga lokalna": 2, "droga dojazdowa": 1}          # reszta (wewnetrzne, inne) = 0, jak krok 1 (+ autostrada)
KAT_KRAJ = {"krajowa": 2, "wojewódzka": 1}                                         # kraj: 3 = autostrada/ekspresowa, 2 krajowa, 1 wojewodzka
ZRODLO = ["Drogi, tory, rzeki, wody, miejscowości: BDOT10k, GUGiK (dane otwarte), przetworzone",
          "Ulice i punkty adresowe: PRG, GUGiK (dane otwarte), przetworzone"]
nazwa_paczki = lambda pe, pn: f"E{pe * BOK // 1000:03d}N{pn * BOK // 1000:03d}"

def wzgl(pk, x0, y0): return np.round(pk - (x0, y0)).astype(int).ravel().tolist()
def bezwzgl(pk): return np.round(pk).astype(int).ravel().tolist()

def zapisz_gz(sciezka, d, poziom=9):
    b = gzip.compress(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode(), poziom, mtime=0)
    with open(sciezka + ".tmp", "wb") as f: f.write(b)
    os.replace(sciezka + ".tmp", sciezka); return len(b)
def czytaj_gz(sciezka):
    with gzip.open(sciezka, "rt", encoding="utf-8") as f: return json.load(f)

def zakres(pk):
    (a, b), (c, d) = pk.min(0), pk.max(0)
    return int(a // BOK), int(b // BOK), int(c // BOK), int(d // BOK)

def po_paczkach(pk):                                       # linia (E, N) -> [(pe, pn, czesc)] pocieta na granicach paczek
    pe0, pn0, pe1, pn1 = zakres(pk)
    if pe0 == pe1 and pn0 == pn1: return [(pe0, pn0, pk)]
    return [(pe, pn, cz) for pe in range(pe0, pe1 + 1) for pn in range(pn0, pn1 + 1)
            for cz in tnij(pk, pe * BOK, pn * BOK, (pe + 1) * BOK, (pn + 1) * BOK)]

def przytnij_wielokat(pk, x0, y0, x1, y1):                 # Sutherland-Hodgman: pierscien -> pierscien wewnatrz prostokata (albo None)
    pts = [tuple(p) for p in pk]
    for o, gr, wew in ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1)):
        if not pts: break
        nowe, prev = [], pts[-1]
        for cur in pts:
            pin, cin = (prev[o] - gr) * wew >= 0, (cur[o] - gr) * wew >= 0
            if cin != pin:
                t = (gr - prev[o]) / (cur[o] - prev[o]); nowe.append((prev[0] + t * (cur[0] - prev[0]), prev[1] + t * (cur[1] - prev[1])))
            if cin: nowe.append(cur)
            prev = cur
        pts = nowe
    return np.array(pts) if len(pts) >= 3 else None

def wielokat_po_paczkach(pk):
    pe0, pn0, pe1, pn1 = zakres(pk)
    if pe0 == pe1 and pn0 == pn1: return [(pe0, pn0, pk)]
    out = []
    for pe in range(pe0, pe1 + 1):
        for pn in range(pn0, pn1 + 1):
            w = przytnij_wielokat(pk, pe * BOK, pn * BOK, (pe + 1) * BOK, (pn + 1) * BOK)
            if w is not None: out.append((pe, pn, w))
    return out

def powiat(p):
    pacz = collections.defaultdict(lambda: collections.defaultdict(list))   # (pe, pn) -> warstwa -> lista
    kraj = collections.defaultdict(list); spis = {}
    def linia(pk, war, ogol, pre=()):                      # do paczek: pelna (TOL) i, gdy ogol, ogolna (TOL_OGOL)
        for pe, pn, cz in po_paczkach(pk):
            x0, y0 = pe * BOK, pn * BOK; s = dp(cz, TOL)
            if len(s) < 2: continue
            pacz[pe, pn][war].append([*pre, wzgl(s, x0, y0)] if pre else wzgl(s, x0, y0))
            if ogol:
                o = dp(cz, TOL_OGOL); pacz[pe, pn][war + "_ogol"].append([*pre, wzgl(o, x0, y0)] if pre else wzgl(o, x0, y0))
    z = zipfile.ZipFile(os.path.join(GUGIK, "bdot", f"{p}_GML.zip"))
    for atr, geo in gml(z, "OT_SKJZ_L"):
        kl = KLASA.get(atr.get("klasaDrogi"), 0); kk = KAT_KRAJ.get(atr.get("kategoriaZarzadzania"))
        if atr.get("klasaDrogi") in ("autostrada", "droga ekspresowa"): kk = 3
        for pk in geo:
            if len(pk) < 2: continue
            linia(pk, "jezdnie", kl >= 3, (kl,))
            if kk: kraj["drogi"].append([kk, atr.get("numerDrogi", ""), bezwzgl(pk)])   # pelna: sklejanie w ciagi w zloz, potem uproszczenie
    for atr, geo in gml(z, "OT_SKTR_L"):
        for pk in geo:
            if len(pk) < 2: continue
            linia(pk, "tory", True)
            if atr.get("numerLinii"): kraj["tory"].append([atr["numerLinii"], bezwzgl(pk)])
    for atr, geo in gml(z, "OT_SWRS_L"):
        n = atr.get("nazwa", "")
        for pk in geo:
            if len(pk) < 2: continue
            dl = dlugosc(pk); linia(pk, "rzeki", False, (n,))
            if n and dl > 2000:
                for pe, pn, cz in po_paczkach(pk): pacz[pe, pn]["rzeki_ogol"].append([n, wzgl(dp(cz, TOL_OGOL), pe * BOK, pn * BOK)])
            if n and atr.get("rodzaj") == "rzeka": kraj["rzeki"].append([n, dl, bezwzgl(dp(pk, TOL))])
    for atr, geo in gml(z, "OT_PTWP_A"):
        if not geo or len(geo[0]) < 4: continue
        pk = geo[0]; pl = pole(pk)                         # tylko obwod zewnetrzny
        for pe, pn, w in wielokat_po_paczkach(pk):
            x0, y0 = pe * BOK, pn * BOK; s = dp(w, TOL)
            if len(s) >= 3: pacz[pe, pn]["wody"].append(wzgl(s, x0, y0))
            if pl > 50000:
                o = dp(w, TOL_OGOL)
                if len(o) >= 3: pacz[pe, pn]["wody_ogol"].append(wzgl(o, x0, y0))
        if pl > 1e6:
            o = dp(pk, TOL_KRAJ)
            if len(o) >= 4: kraj["wody"].append(bezwzgl(o))
    for atr, geo in gml(z, "OT_ADMS_P"):
        if not geo or not atr.get("nazwa"): continue
        E, N = geo[0][0]; pe, pn = int(E // BOK), int(N // BOK); lud = int(atr.get("liczbaMieszkancow") or 0)
        pacz[pe, pn]["miejscowosci"].append([atr["nazwa"], atr.get("rodzaj", ""), lud, int(round(E - pe * BOK)), int(round(N - pn * BOK))])
        kraj["msc"].append([atr["nazwa"], atr.get("rodzaj", ""), lud, int(round(E)), int(round(N)), atr.get("identyfikatorSIMC", "")])
    zr = os.path.join(GUGIK, "prg-adresy", f"{p}_PRG.zip")
    if os.path.exists(zr):
        q = zipfile.ZipFile(zr); naz = lambda s: next(n for n in q.namelist() if n.endswith(s))
        for rek, g in zip(dbf(q.read(naz(f"PRG_Ulice_{p}.dbf"))), shp(q.read(naz(f"PRG_Ulice_{p}.shp")))):
            if rek.get("NAZWA_ULC"):
                for cz in g:
                    if len(cz) >= 2: linia(cz, "ulice", False, (rek["NAZWA_ULC"],))
        for rek, g in zip(dbf(q.read(naz(f"PRG_PunktyAdresowe_{p}.dbf"))), shp(q.read(naz(f"PRG_PunktyAdresowe_{p}.shp")))):
            if not g: continue
            E, N = g[0][0]; pe, pn = int(E // BOK), int(N // BOK); msc = rek.get("NAZWA_MSC", "")
            pacz[pe, pn]["adresy"].append([rek.get("NAZWA_ULC") or msc, msc, rek.get("NUMER_PORZ", ""),
                                            int(round(E - pe * BOK)), int(round(N - pn * BOK))])
            s = spis.setdefault(rek.get("ID_SIMC") or msc, {"nazwa": msc, "gmina": rek.get("NAZWA_GMI", ""), "paczki": {}, "E": 0.0, "N": 0.0, "ile": 0})
            k = nazwa_paczki(pe, pn); s["paczki"][k] = s["paczki"].get(k, 0) + 1; s["E"] += E; s["N"] += N; s["ile"] += 1
    else: print(f"{p}: brak PRG adresow", flush=True)
    for (pe, pn), w in pacz.items():
        d = os.path.join(POSR, "paczki", nazwa_paczki(pe, pn)); os.makedirs(d, exist_ok=True)
        zapisz_gz(os.path.join(d, f"{p}.json.gz"), w, 1)
    os.makedirs(os.path.join(POSR, "kraj"), exist_ok=True)
    zapisz_gz(os.path.join(POSR, "kraj", f"{p}.json.gz"), {"kraj": kraj, "spis": spis}, 1)   # zapisany ostatni = znacznik: powiat gotowy
    return p, len(pacz), sum(len(w.get("jezdnie", [])) for w in pacz.values()), sum(len(w.get("adresy", [])) for w in pacz.values())

def zloz_paczke(nazwa):
    w = collections.defaultdict(list)
    for plik in sorted(glob.glob(os.path.join(POSR, "paczki", nazwa, "*.json.gz"))):
        for k, v in czytaj_gz(plik).items(): w[k] += v
    rog = [int(nazwa[1:4]) * 1000, int(nazwa[5:8]) * 1000]
    msc = {(m[0], m[3] // 50, m[4] // 50): m for m in w.pop("miejscowosci", [])}   # ten sam punkt z dwoch powiatow - raz
    adr = w.pop("adresy", []); ulice_nazwy, idx, adresy = [], {}, []
    for u, m, nr, x, y in adr:
        k = idx.setdefault((u, m), len(ulice_nazwy))
        if k == len(ulice_nazwy): ulice_nazwy.append([u, m])
        adresy.append([k, nr, x, y])
    uklad = f"EPSG:2180 minus rog paczki (E {rog[0]}, N {rog[1]}), metry, x = wschod, y = polnoc"
    a = zapisz_gz(os.path.join(PACZKI, f"{nazwa}-mapa.json.gz"), {"zrodlo": ZRODLO, "uklad": uklad, "rog": rog,
        "miejscowosci": sorted(msc.values(), key=lambda m: -m[2]), **{k: w.get(k, []) for k in
        ("jezdnie", "jezdnie_ogol", "tory", "tory_ogol", "rzeki", "rzeki_ogol", "wody", "wody_ogol", "ulice")}})
    b = zapisz_gz(os.path.join(PACZKI, f"{nazwa}-adresy.json.gz"), {"zrodlo": ZRODLO[1:], "uklad": uklad, "rog": rog,
        "ulice_nazwy": ulice_nazwy, "adresy": adresy}) if adresy else 0
    return nazwa, a, b, len(adresy)

def lancuchy(odcinki):                                     # odcinki [x, y, x, y, ...] -> ciagi sklejone po wspolnych koncach (BDOT dzieli linie na skrzyzowaniach)
    kon = collections.defaultdict(list)
    for i, l in enumerate(odcinki): kon[l[0], l[1]].append(i); kon[l[-2], l[-1]].append(i)
    uzyte, wyn = [False] * len(odcinki), []
    def dalej(c):                                          # c: lista punktow (x, y); dokleja na koncu, dopoki cos tam sie zaczyna/konczy
        while True:
            nast = next((i for i in kon[c[-1]] if not uzyte[i]), None)
            if nast is None: return
            uzyte[nast] = True; l = odcinki[nast]; pk = list(zip(l[::2], l[1::2]))
            c += pk[1:] if pk[0] == c[-1] else pk[::-1][1:]
    for i, l in enumerate(odcinki):
        if uzyte[i]: continue
        uzyte[i] = True; c = list(zip(l[::2], l[1::2])); dalej(c); c.reverse(); dalej(c); wyn.append(np.array(c, float))
    return wyn

def sklej(rekordy, klucz):                                 # [(klucz..., linia)] -> [(klucz..., linia sklejona i uproszczona do TOL_KRAJ)]
    grupy = collections.defaultdict(list)
    for r in rekordy: grupy[klucz(r)].append(r[-1])
    return [[*k, bezwzgl(dp(c, TOL_KRAJ))] for k, ods in grupy.items() for c in lancuchy(ods) if dlugosc(c) > 300]

def granice():                                             # PRG: panstwo, wojewodztwa, powiaty -> linie w 2180 (uproszczone) + nazwy powiatow
    z = zipfile.ZipFile(os.path.join(GUGIK, "granice.zip")); wyn, nazwy = {}, {}
    naz = lambda s: next(n for n in z.namelist() if n.endswith(s))
    for klucz, plik in (("panstwo", "A00_Granice_panstwa"), ("wojewodztwa", "A01_Granice_wojewodztw"), ("powiaty", "A02_Granice_powiatow")):
        linie = []
        for rek, g in zip(dbf(z.read(naz(plik + ".dbf"))), shp(z.read(naz(plik + ".shp")))):
            if klucz == "powiaty": nazwy[rek["JPT_KOD_JE"]] = rek["JPT_NAZWA_"].removeprefix("powiat ")
            for cz in g:
                n, e = na_2180(cz[:, 1], cz[:, 0]); s = dp(np.column_stack([e, n]), TOL_GRANIC)
                if len(s) >= 3: linie.append(bezwzgl(s))
        wyn[klucz] = linie
    return wyn, nazwy

def zloz():
    os.makedirs(PACZKI, exist_ok=True); os.makedirs(KRAJ, exist_ok=True)
    nazwy_p = sorted(os.listdir(os.path.join(POSR, "paczki")))
    with Pool(int(os.environ.get("WATKI", "6"))) as pool:
        wyniki = pool.map(zloz_paczke, nazwy_p, chunksize=4)
    mb = sum(a + b for _, a, b, _ in wyniki) / 1e6
    print(f"paczki: {len(wyniki)}, razem {mb:.0f} MB; mapa: mediana {np.median([a for _, a, _, _ in wyniki]) / 1e3:.0f} kB, "
          f"maks. {max(wyniki, key=lambda r: r[1])[:2]}; adresow razem {sum(r[3] for r in wyniki)}", flush=True)
    gr, nazwy_pow = granice(); kr = collections.defaultdict(list); spis = {}
    for plik in sorted(glob.glob(os.path.join(POSR, "kraj", "*.json.gz"))):
        p = os.path.basename(plik)[:4]; d = czytaj_gz(plik)
        for k, v in d["kraj"].items(): kr[k] += v
        for simc, s in d["spis"].items():
            t = spis.setdefault(simc, {"nazwa": s["nazwa"], "gmina": s["gmina"], "paczki": collections.Counter(), "E": 0.0, "N": 0.0, "ile": 0,
                                       "powiat": nazwy_pow.get(p, p)})
            t["paczki"].update(s["paczki"]); t["E"] += s["E"]; t["N"] += s["N"]; t["ile"] += s["ile"]
    dl = collections.Counter()                             # rzeki glowne: laczna dlugosc rzeki o tej nazwie w kraju >= 50 km
    for n, d, _ in kr["rzeki"]: dl[n] += d
    rzeki = sklej([(n, l) for n, d, l in kr["rzeki"] if dl[n] >= 50000], lambda r: (r[0],))
    tory = [l for _, l in sklej(kr["tory"], lambda r: (r[0],))]
    drogi = sklej(kr["drogi"], lambda r: (r[0], r[1]))
    # miejscowosci: punkt z BDOT (OT_ADMS_P), paczki z adresow PRG po SIMC; bez adresow - paczka punktu
    gminy, powiaty, miasta, gi, pi = [], [], [], {}, {}
    def ix(tab, slow, v):
        if v not in slow: slow[v] = len(tab); tab.append(v)
        return slow[v]
    for nazwa, rodzaj, lud, E, N, simc in kr["msc"]:
        s = spis.pop(simc, None)
        pacz = [n for n, _ in s["paczki"].most_common()] if s else [nazwa_paczki(E // BOK, N // BOK)]
        miasta.append([nazwa, rodzaj, lud, E, N, ix(gminy, gi, s["gmina"] if s else ""), ix(powiaty, pi, s["powiat"] if s else ""), pacz])
    for s in spis.values():                                # miejscowosci z adresami, ktorych punktu nie ma w BDOT
        miasta.append([s["nazwa"], "", 0, int(s["E"] / s["ile"]), int(s["N"] / s["ile"]), ix(gminy, gi, s["gmina"]), ix(powiaty, pi, s["powiat"]),
                       [n for n, _ in s["paczki"].most_common()]])
    miasta.sort(key=lambda m: -m[2])
    uklad = "EPSG:2180 bezwzglednie, metry, x = wschod, y = polnoc"
    # podklad: linie + napisy duzych miejscowosci (miasta, >= 1000 mieszkancow); pelny spis osobno - wczytywany dopiero przy wyszukiwaniu
    b = zapisz_gz(os.path.join(KRAJ, "podklad.json.gz"), {"zrodlo": ["Granice: PRG, GUGiK (dane otwarte), przetworzone"] + ZRODLO, "uklad": uklad,
        "paczka_bok_m": BOK, "paczki_z_mapa": [r[0] for r in wyniki], **gr, "drogi": drogi, "tory": tory, "rzeki": rzeki, "wody": kr["wody"],
        "miejscowosci": [m[:5] for m in miasta if m[1] == "miasto" or m[2] >= 1000]})
    c = zapisz_gz(os.path.join(KRAJ, "miejscowosci.json.gz"), {"zrodlo": ZRODLO, "uklad": uklad, "gminy": gminy, "powiaty": powiaty,
        "pola": ["nazwa", "rodzaj", "mieszkancy", "E", "N", "gmina (indeks)", "powiat (indeks)", "paczki z adresami (najwiecej najpierw)"],
        "miejscowosci": miasta})
    print(f"kraj/podklad.json.gz {b / 1e6:.2f} MB: drogi {len(drogi)} ciagow, tory {len(tory)}, rzeki {len(rzeki)}, wody {len(kr['wody'])}, "
          "granice " + ", ".join(f"{k} {len(v)}" for k, v in gr.items()) + f"; kraj/miejscowosci.json.gz {c / 1e6:.2f} MB, {len(miasta)} miejscowosci", flush=True)

if __name__ == "__main__":
    if sys.argv[1] == "powiaty":
        gotowe = {os.path.basename(f)[:4] for f in glob.glob(os.path.join(POSR, "kraj", "*.json.gz"))}
        lista = sys.argv[2:] or [os.path.basename(f)[:4] for f in sorted(glob.glob(os.path.join(GUGIK, "bdot", "*_GML.zip")))
                                 if os.path.basename(f)[:4] not in gotowe        # adresy pobierane po BDOT: bez nich powiat czeka
                                 and os.path.exists(os.path.join(GUGIK, "prg-adresy", os.path.basename(f)[:4] + "_PRG.zip"))]
        with Pool(int(os.environ.get("WATKI", "6"))) as pool:
            for p, np_, nj, na in pool.imap_unordered(powiat, lista):
                print(f"{p}: paczek {np_}, jezdni {nj}, adresow {na}", flush=True)
    elif sys.argv[1] == "zloz": zloz()
