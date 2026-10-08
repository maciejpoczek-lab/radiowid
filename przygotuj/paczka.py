#!/usr/bin/env python3
# PROBA paczek 20 km (docs/projekt-paczek-20km.md): z kafli 1 m NMT/NMPT (dane/nmpt/kafle) i LoD1 -> pliki .pak w siatce EPSG:2180.
# Paczka = kwadrat 20 km wyrownany do wielokrotnosci 20 km, kafel = 1 km wyrownany do pelnych km, 250 x 250 komorek po 4 m, wiersz 0 = polnoc.
# Warstwy jak w rynek.py (G srednia NMT, O mediana NMPT pod budynkiem albo grunt + LoD1, ZW korona, BUD, NMPT_PROC), ale w osiach 2180
# - bez obrotu lokalnego kwadratu. Do paczki trafiaja tylko kafle w calosci wewnatrz pobranej mozaiki (proba: 6 x 6 km wokol rynku).
# Kodowanie bloku: G int16 co 5 cm, O jako O - G co 1 cm, ZW co 10 cm; roznice wzdluz wiersza modulo 2^16; gzip. BUD, NMPT_PROC: uint8 + gzip.
# Plik: "PAK1" + uint32 LE dlugosc naglowka + naglowek JSON (UTF-8) + bloki. Odczyt: silnik/paczka.js. Kazdy wynik to SYMULACJA.
# Uzycie: python3 paczka.py [kafle]        -> mapa/dane/paczki/v1/E{km}N{km}.pak (mozaika wokol rynku)
#         python3 paczka.py km KATALOG    -> z kafli 1 km arkusze.py i budynki_paczki.py (cala paczka)
import gzip, json, os, sys
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__)); MAPA = os.path.dirname(HERE)
DANE = os.environ.get("PACZKI_DANE") or os.path.expanduser("~/dev/showreel-2/dane")
ZRODLO = sys.argv[1] if len(sys.argv) > 1 else "kafle"
WERSJA, PACZKA, KAFEL, KOM = 1, 20000, 1000, 4
SUB, NK = KOM, KAFEL // KOM                          # probki 1 m na bok komorki, komorek na bok kafla
PROG_BUD, PROG_ZIEL = 0.5, 0.5
SKALA = {"G": 0.05, "O": 0.01, "ZW": float(os.environ.get("ZW_KROK", 0.10))}   # ZW co 10 cm (pomiar 2026-10-07, docs §4)
OUT = os.path.join(os.environ.get("PACZKI_WYJSCIE") or os.path.join(MAPA, "dane", "paczki"), f"v{WERSJA}"); os.makedirs(OUT, exist_ok=True)

def int16_roznice(a, skala, brak=False):              # brak: NaN -> -32768 (warstwy poziomow maja dziury tam, gdzie paczka nie ma kafla)
    q = np.round(np.nan_to_num(a, nan=0) / skala); assert np.abs(q).max() < 32767
    if brak: q = np.where(np.isnan(a), -32768, q)
    q = q.astype(np.int16)
    return gzip.compress(np.diff(q, axis=-1, prepend=np.zeros((q.shape[0], 1), np.int16)).astype("<i2").tobytes(), 9, mtime=0), q

# Poziomy przyblizenia (docs §7): python3 paczka.py poziomy PLIK.pak [...] -> E...N...-16.pak (G, O, ZW, BUD %) i -100.pak (sam G)
# obok paczek 4 m. Jeden blok na warstwe dla calej paczki; O i ZW w bloku 4 x 4: POZIOMY_O=srednia (domyslnie) albo max.
if ZRODLO == "poziomy":
    AGG = os.environ.get("POZIOMY_O", "srednia"); assert AGG in ("srednia", "max")
    def czytaj(plik):                                 # .pak 4 m -> mozaika paczki {warstwa: 5000 x 5000}, NaN / 0 tam, gdzie brak kafla
        b = open(plik, "rb").read(); dl = int.from_bytes(b[4:8], "little"); nag = json.loads(b[8:8 + dl]); st = 8 + dl
        nk, kom, kaf = nag["ksztalt_kafla"][0], nag["komorka_m"], nag["kafel_m"]; e0, n0 = nag["rog_zachod_poludnie_m"]
        N = nag["bok_m"] // kom; m = {w: np.full((N, N), np.nan, np.float32) for w in ("G", "O", "ZW")}; m["BUD"] = np.zeros((N, N), np.float32)
        for k, wp in nag["kafle"].items():
            e, n = map(int, k.split("_")); i0, j0 = (n0 + nag["bok_m"] - (n + 1) * kaf) // kom, (e * kaf - e0) // kom; t = {}
            for w in ("G", "O", "ZW", "BUD"):
                off, ln = wp[w]; r = gzip.decompress(b[st + off:st + off + ln]); o = nag["warstwy"][w]
                if o["dtype"] == "uint8": t[w] = np.frombuffer(r, np.uint8).reshape(nk, nk).astype(np.float32); continue
                q = np.cumsum(np.frombuffer(r, "<i2").reshape(nk, nk).astype(np.int64), 1)
                t[w] = (((q + 32768) % 65536 - 32768) * o["skala"]).astype(np.float32)
            t["O"] = t["O"] + t["G"]
            for w in t: m[w][i0:i0 + nk, j0:j0 + nk] = t[w]
        return nag, m
    def blok(a, s, f):                                # srednia / maksimum w blokach s x s; blok z dziura -> NaN
        n = a.shape[0] // s; b = a[:n * s, :n * s].reshape(n, s, n, s)
        return (b.mean((1, 3)) if f == "srednia" else b.max((1, 3))).astype(np.float32)
    for plik in sys.argv[2:]:
        nag, m = czytaj(plik)
        for kom, warstwy_p in ((16, ("G", "O", "ZW", "BUD")), (100, ("G",))):
            s = kom // nag["komorka_m"]; G = blok(m["G"], s, "srednia"); W = {"G": G}
            if "O" in warstwy_p:
                W["O"] = np.maximum(blok(m["O"], s, AGG), G); W["ZW"] = np.nan_to_num(blok(m["ZW"], s, AGG))
                W["BUD"] = np.nan_to_num(blok(m["BUD"], s, "srednia") * 100).round().astype(np.uint8)
            bloki, wpis, poz = [], {}, 0
            for w in warstwy_p:
                if w == "BUD": bb = gzip.compress(W[w].tobytes(), 9, mtime=0)
                else: bb, _ = int16_roznice(np.nan_to_num(W[w] - G) if w == "O" else W[w], SKALA[w], brak=(w == "G"))
                wpis[w] = [poz, len(bb)]; bloki.append(bb); poz += len(bb)
            e0, n0 = nag["rog_zachod_poludnie_m"]; ka = f"{e0 // nag['bok_m']}_{n0 // nag['bok_m']}"
            opis = {"G": {"dtype": "int16", "skala": SKALA["G"], "roznice": True, "brak": -32768},
                    "O": {"dtype": "int16", "skala": SKALA["O"], "roznice": True, "baza": "G", "blok": AGG},
                    "ZW": {"dtype": "int16", "skala": SKALA["ZW"], "roznice": True, "blok": AGG}, "BUD": {"dtype": "uint8", "jednostka": "%"}}
            n2 = {**{k: v for k, v in nag.items() if k not in ("kafle", "warstwy")}, "poziom_m": kom, "kafel_m": nag["bok_m"], "komorka_m": kom,
                  "ksztalt_kafla": list(G.shape), "warstwy": {w: opis[w] for w in warstwy_p}, "kafle": {ka: wpis},
                  "uwaga": "SYMULACJA, nie pomiar; poziom uproszczony" + (" - sam teren, bez budynkow i drzew" if kom == 100 else "")}
            h = json.dumps(n2, ensure_ascii=False, separators=(",", ":")).encode(); wy = os.path.join(OUT, f"{nag['paczka']}-{kom}.pak")
            with open(wy, "wb") as f:
                f.write(b"PAK1"); f.write(len(h).to_bytes(4, "little")); f.write(h)
                for bb in bloki: f.write(bb)
            print(f"{wy}: {G.shape[0]} x {G.shape[1]} po {kom} m, {os.path.getsize(wy) / 1e3:.0f} kB "
                  f"({', '.join(f'{w} {v[1] / 1e3:.0f}' for w, v in wpis.items())} kB), O/ZW: {AGG}, brak {np.isnan(G).mean() * 100:.1f}%")
    sys.exit(0)

def zalataj(a):                                       # dziury NMT (styki arkuszy) -> srednia sasiadow, az do skutku
    while np.isnan(a).any():
        p = np.pad(a, 1, constant_values=np.nan)
        sasiedzi = np.stack([p[1 + di:p.shape[0] - 1 + di, 1 + dj:p.shape[1] - 1 + dj] for di in (-1, 0, 1) for dj in (-1, 0, 1) if di or dj])
        with np.errstate(all="ignore"):
            import warnings; warnings.simplefilter("ignore", RuntimeWarning); sr = np.nanmean(sasiedzi, 0)
        a = np.where(np.isnan(a), sr, a)
    return a

def rastry(nmt, nmpt, budynki, W0, N0):              # 1 m: maska budynkow, wysokosc LoD1, korony (obrysy powiekszone o 1 m)
    ny1, nx1 = nmt.shape
    im = Image.new("L", (nx1, ny1), 0); dr = ImageDraw.Draw(im); imw = Image.new("F", (nx1, ny1), 0.0); drw = ImageDraw.Draw(imw)
    for b in budynki:
        p = [(x - W0, N0 - y) for x, y in b["obrys"]]; dr.polygon(p, fill=255); drw.polygon(p, fill=float(b.get("wys") or 0))
    BM = np.asarray(im) > 0; WYS = np.asarray(imw)
    pad = np.pad(BM, 1); BM1 = pad[1:-1, 1:-1] | pad[:-2, 1:-1] | pad[2:, 1:-1] | pad[1:-1, :-2] | pad[1:-1, 2:]
    with np.errstate(invalid="ignore"): ZIEL = (nmpt - nmt > 2.5) & ~BM1
    return BM, WYS, ZIEL

KM = ZRODLO == "km"                                  # tryb kafli 1 km z arkuszy (arkusze.py + budynki_paczki.py)
if KM:                                               # python3 paczka.py km KATALOG   (kafle/{nmt,nmpt}/{e}_{n}.npy, budynki.json)
    KAT = os.path.expanduser(sys.argv[2]); bud = json.load(open(os.path.join(KAT, "budynki.json")))["budynki"]
    zk = {"zrodlo": "GUGiK NMT/NMPT (arkusze opendata.geoportal.gov.pl, EVRF2007; KRON86 z poprawka), wybor: arkusze.py"}
    INDEKS = {}
    for b in bud:                                    # budynki per kafel km (obwiednia + 1 m)
        xs = [q[0] for q in b["obrys"]]; ys = [q[1] for q in b["obrys"]]
        for e in range(int((min(xs) - 1) // KAFEL), int((max(xs) + 1) // KAFEL) + 1):
            for n in range(int((min(ys) - 1) // KAFEL), int((max(ys) + 1) // KAFEL) + 1): INDEKS.setdefault((e, n), []).append(b)
    KAFLE_KM = sorted({tuple(map(int, f[:-4].split("_"))) for f in os.listdir(os.path.join(KAT, "kafle", "nmt"))})
    def zrodlo_kafla(e, n):
        nmt = np.load(os.path.join(KAT, "kafle", "nmt", f"{e}_{n}.npy"))
        pn = os.path.join(KAT, "kafle", "nmpt", f"{e}_{n}.npy"); nmpt = np.load(pn) if os.path.exists(pn) else np.full_like(nmt, np.nan)
        if np.isnan(nmt).mean() > 0.5: return None   # kafel prawie bez gruntu (granica danych) - pomijamy
        nmt = zalataj(nmt); BM, WYS, ZIEL = rastry(nmt, nmpt, INDEKS.get((e, n), []), e * KAFEL, (n + 1) * KAFEL)
        return nmt, nmpt, BM, ZIEL, WYS
else:                                                # --- mozaika 1 m wokol rynku (jak rynek.py) ---
    KAFLE = os.path.join(DANE, "nmpt", ZRODLO); zk = json.load(open(os.path.join(KAFLE, "zakres.json")))
    nk, K = zk["kafli_na_bok"], zk["kafel"]
    def mozaika(m):
        a = np.empty((nk * K, nk * K), np.float32)
        for i in range(nk):
            for j in range(nk): a[i * K:(i + 1) * K, j * K:(j + 1) * K] = np.load(os.path.join(KAFLE, f"{m}/{i}_{j}.npy"))
        a[a == 0] = np.nan; return a
    NMT, NMPT = mozaika("nmt"), mozaika("nmpt"); NMT = zalataj(NMT)
    W0, N0 = zk["x_zachod"], zk["y_polnoc"]; ny1, nx1 = NMT.shape
    bud = json.load(open(os.path.join(DANE, "budynki3d" + ZRODLO[len("kafle"):], "rynek-3000.json")))["budynki"]
    BM, WYS, ZIEL = rastry(NMT, NMPT, bud, W0, N0)
    e_od, e_do = int(np.ceil(W0 / KAFEL)), int((W0 + nx1) // KAFEL)       # kafle [e_od, e_do) km w calosci w mozaice
    n_od, n_do = int(np.ceil((N0 - ny1) / KAFEL)), int(N0 // KAFEL)
    KAFLE_KM = [(e, n) for e in range(e_od, e_do) for n in range(n_od, n_do)]
    def zrodlo_kafla(e, n):
        i0, j0 = int(round(N0 - (n + 1) * KAFEL)), int(round(e * KAFEL - W0)); s = np.s_[i0:i0 + KAFEL, j0:j0 + KAFEL]
        return NMT[s], NMPT[s], BM[s], ZIEL[s], WYS[s]

def warstwy(g1, s1, b1, z1, w1):                     # kafel 1 km po 1 m -> warstwy 250 x 250
    blk = lambda a: a.reshape(NK, SUB, NK, SUB)
    kom = lambda a: blk(a).transpose(0, 2, 1, 3).reshape(NK, NK, -1)
    G = blk(g1).mean((1, 3))
    fb, fz = blk(b1).mean((1, 3)), blk(z1).mean((1, 3)); BUD = fb >= PROG_BUD
    with np.errstate(all="ignore"):
        import warnings; warnings.simplefilter("ignore", RuntimeWarning)
        Htop = np.nanmedian(kom(np.where(b1, s1, np.nan)), -1)
        Hlod = np.nanmedian(kom(np.where(b1, w1, np.nan)), -1)
    Htop = np.where(BUD & np.isnan(Htop) & ~np.isnan(Hlod), G + Hlod, Htop)
    O = np.maximum(np.where(BUD, np.nan_to_num(Htop, nan=0), G), G)
    ZW = np.where((fz >= PROG_ZIEL) & ~BUD, blk(np.where(z1, s1 - g1, 0)).sum((1, 3)) / np.maximum(blk(z1).sum((1, 3)), 1), 0)
    NP = np.rint(blk(~np.isnan(s1)).mean((1, 3)) * 100).astype(np.uint8)
    return G, O, ZW, BUD.astype(np.uint8), NP

# --- kafle km -> paczki ---
paczki = {}
for e, n in KAFLE_KM:
        paczki.setdefault((e * KAFEL // PACZKA * PACZKA // 1000, n * KAFEL // PACZKA * PACZKA // 1000), []).append((e, n))
for (pe, pn), kafle in sorted(paczki.items()):
    bloki, spis, poz = [], {}, 0
    for e, n in sorted(kafle, key=lambda t: (-t[1], t[0])):
        zr = zrodlo_kafla(e, n)
        if zr is None: print(f"kafel {e}_{n} pominiety (brak gruntu)"); continue
        G, O, ZW, BUD, NP = warstwy(*zr)
        bG, qG = int16_roznice(G, SKALA["G"])
        bO, _ = int16_roznice(O - G, SKALA["O"])          # O - G z wartosci przed kwantyzacja G: odbiornik liczy O = G' + (O - G)
        bZ, _ = int16_roznice(ZW, SKALA["ZW"])
        wpis = {}
        for nazwa, bb in (("G", bG), ("O", bO), ("ZW", bZ), ("BUD", gzip.compress(BUD.tobytes(), 9, mtime=0)),
                          ("NMPT_PROC", gzip.compress(NP.tobytes(), 9, mtime=0))):
            wpis[nazwa] = [poz, len(bb)]; bloki.append(bb); poz += len(bb)
        spis[f"{e}_{n}"] = wpis
    nag = {"format": "pak", "wersja_formatu": 1, "wersja_danych": WERSJA, "uklad": "EPSG:2180",
           "paczka": f"E{pe:03d}N{pn:03d}", "rog_zachod_poludnie_m": [pe * 1000, pn * 1000], "bok_m": PACZKA,
           "kafel_m": KAFEL, "komorka_m": KOM, "ksztalt_kafla": [NK, NK], "wiersz0": "polnoc",
           "warstwy": {"G": {"dtype": "int16", "skala": SKALA["G"], "roznice": True},
                       "O": {"dtype": "int16", "skala": SKALA["O"], "roznice": True, "baza": "G"},
                       "ZW": {"dtype": "int16", "skala": SKALA["ZW"], "roznice": True},
                       "BUD": {"dtype": "uint8"}, "NMPT_PROC": {"dtype": "uint8"}},
           "kafle": spis, "zrodla": [zk["zrodlo"], "Modele 3D budynków LoD1 2024: GUGiK, CC BY 4.0"], "uwaga": "SYMULACJA, nie pomiar; PROBA"}
    h = json.dumps(nag, ensure_ascii=False, separators=(",", ":")).encode()
    plik = os.path.join(OUT, nag["paczka"] + ".pak")
    with open(plik, "wb") as f:
        f.write(b"PAK1"); f.write(len(h).to_bytes(4, "little")); f.write(h)
        for bb in bloki: f.write(bb)
    rozm = os.path.getsize(plik); warstwa = {k: sum(v[k][1] for v in spis.values()) for k in nag["warstwy"]}
    print(f"{plik}: {len(spis)} kafli, {rozm / 1e6:.2f} MB, {rozm / len(spis) / 1e3:.0f} kB/kafel "
          f"({', '.join(f'{k} {v / len(spis) / 1e3:.1f}' for k, v in warstwa.items())} kB) -> 400 kafli ~ {rozm / len(spis) * 400 / 1e6:.0f} MB")
