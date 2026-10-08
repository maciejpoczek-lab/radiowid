#!/usr/bin/env python3
# Kolejka paczek 20 km (docs/projekt-paczek-20km.md §6) na komputerze testowym: dla kazdej paczki arkusze.py -> budynki_paczki.py ->
# paczka.py km, potem kasowanie kafli 1 m. Miasta najpierw (Warszawa E620N480, reszta Warszawy, Krakow, Lodz, Wroclaw, Poznan, Trojmiasto),
# dalej pozostale miasta wedlug liczby mieszkancow, na koncu reszta paczek wedlug wagi -adresy (gestosc zabudowy).
# Wznawialna: stan w ~/paczki/kolejka/stan.json, arkusze.py sam wznawia pobieranie w srodku paczki.
# Grzecznosc i wspolna maszyna:
#   - tylko noca (NOC_OD..NOC_DO czasu warszawskiego, domyslnie 23-7); poza oknem nowa paczka nie rusza, proces czeka,
#   - blokada srodowiska testowego (~/.srodowisko-testowe/blokada, ten sam format i zamek flock co bin/srodowisko-testowe.sh
#     w zirael-cp): bierze ja na czas paczki (30 min, odnawiana co 5 min), oddaje miedzy paczkami; cudza zywa -> czeka,
#   - nice 19 + ionice idle, pobieranie po jednym pliku z pauza (w arkusze.py),
#   - wolne miejsce < MIN_GB -> czeka; plik ~/paczki/kolejka/STOP -> konczy po biezacej paczce; 3 bledy z rzedu -> stop.
# Uzycie (na komputerze testowym, z ~/paczki):
#   venv/bin/python kod/kolejka_paczek.py lista            -> kolejka/lista.json (bez liczenia)
#   venv/bin/python kod/kolejka_paczek.py stan             -> ile zrobione, czasy, wagi
#   venv/bin/python kod/kolejka_paczek.py licz [--ile N]   -> liczy (N paczek i koniec; bez --ile do konca listy)
# Usluga: ~/.config/systemd/user/paczki-kolejka.service (start z systemem, linger), log kolejka/licz.log
import datetime, fcntl, gzip, json, os, shutil, subprocess, sys, threading, time
from zoneinfo import ZoneInfo

DOM = os.path.expanduser("~/paczki"); KOD = os.path.join(DOM, "kod"); PY = os.path.join(DOM, "venv", "bin", "python")
KAT = os.path.join(DOM, "kolejka"); PRACA = os.path.join(DOM, "praca"); WYJ = os.path.join(DOM, "gotowe")
POSR = os.path.join(DOM, "dane", "gugik", "posrednie", "paczki")       # {paczka}/{TERYT}.json.gz z mapa_kraj.py = powiaty paczki
LISTA, STAN, STOP = (os.path.join(KAT, f) for f in ("lista.json", "stan.json", "STOP"))
NOC_OD, NOC_DO = int(os.environ.get("NOC_OD", 23)), int(os.environ.get("NOC_DO", 7))
MIN_GB = float(os.environ.get("MIN_GB", 15))
BLOK_KAT = os.path.expanduser("~/.srodowisko-testowe"); BLOK = os.path.join(BLOK_KAT, "blokada")
KTO = "paczki-20km@zirael-test:kolejka_paczek.py"; REPO = "/opt/zirael-cp"
MIASTA = [["Warszawa"], ["Kraków"], ["Łódź"], ["Wrocław"], ["Poznań"], ["Gdańsk", "Gdynia", "Sopot"]]
os.makedirs(KAT, exist_ok=True)

def teraz(): return datetime.datetime.now(ZoneInfo("Europe/Warsaw"))
def log(*a): print(teraz().strftime("%m-%d %H:%M:%S"), *a, flush=True)
def noc(): h = teraz().hour; return h >= NOC_OD or h < NOC_DO if NOC_OD > NOC_DO else NOC_OD <= h < NOC_DO
def wczytaj(p, dom): return json.load(open(p)) if os.path.exists(p) else dom
def zapisz(p, d): json.dump(d, open(p + ".nowy", "w"), indent=1, ensure_ascii=False); os.replace(p + ".nowy", p)

# --- lista ---
def lista():
    sp = json.load(gzip.open(os.path.join(DOM, "kraj", "miejscowosci.json.gz")))
    wszystkie = sorted(os.listdir(POSR)); kol = []
    def dodaj(ps):
        for p in ps:
            if p not in kol and p in wszystkie: kol.append(p)
    mi = sp["miejscowosci"]; miasta = [m for m in mi if m[1] == "miasto"]
    dodaj(["E620N480"])                                              # pierwsza: pomiar czasu i wagi paczki miejskiej
    for grupa in MIASTA:
        for nazwa in grupa:
            m = max((m for m in miasta if m[0] == nazwa), key=lambda m: m[2]); dodaj(m[7])
    for m in sorted(miasta, key=lambda m: -m[2]): dodaj(m[7])
    n_miast = len(kol)
    adr = lambda p: os.path.getsize(f) if os.path.exists(f := os.path.join(DOM, "mapa-paczek", p + "-adresy.json.gz")) else 0
    dodaj(sorted(wszystkie, key=lambda p: -adr(p)))
    zapisz(LISTA, kol); log(f"lista: {len(kol)} paczek (z miast {n_miast}), poczatek {kol[:8]}")
    return kol

# --- blokada srodowiska testowego (zgodna z bin/srodowisko-testowe.sh: pola kto/opis/commit/od/wygasa/stan, zamek .zamek) ---
def _zamek(f):
    os.makedirs(BLOK_KAT, exist_ok=True); z = open(os.path.join(BLOK_KAT, ".zamek"), "w"); fcntl.flock(z, fcntl.LOCK_EX)
    try: return f()
    finally: z.close()
def _czytaj():
    if not os.path.exists(BLOK): return {}
    return dict(l.rstrip("\n").split("=", 1) for l in open(BLOK) if "=" in l)
def _pisz(d):
    open(BLOK + ".nowy", "w").write("".join(f"{k}={d[k]}\n" for k in ("kto", "opis", "commit", "od", "wygasa", "stan"))); os.replace(BLOK + ".nowy", BLOK)
def wez(opis, minuty=30):                        # True = nasza; False = cudza zywa
    def f():
        b, t = _czytaj(), int(time.time())
        if b and b.get("kto") != KTO and int(b.get("wygasa", 0)) > t: return False
        glowa = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        od = b.get("od") if b.get("kto") == KTO else str(t)
        _pisz({"kto": KTO, "opis": opis, "commit": glowa, "od": od, "wygasa": t + minuty * 60, "stan": "liczenie"}); return True
    return _zamek(f)
def zwolnij():
    def f():
        if _czytaj().get("kto") == KTO: os.remove(BLOK)
    _zamek(f)

# --- jedna paczka ---
def uruchom(argv, plik_logu, env=None):
    with open(plik_logu, "a") as lg:
        lg.write(f"\n=== {teraz():%Y-%m-%d %H:%M:%S} {' '.join(argv)}\n"); lg.flush()
        pr = subprocess.Popen(["nice", "-n", "19", "ionice", "-c3"] + argv, stdout=lg, stderr=subprocess.STDOUT, cwd=DOM,
                              env=env, stdin=subprocess.DEVNULL)
        try: return pr.wait()
        except BaseException: pr.terminate(); pr.wait(); raise       # kill kolejki = koniec dziecka (arkusze.py wznowi sie przy nastepnym starcie)

def paczka(p):
    e, n = int(p[1:4]), int(p[5:8]); kat = os.path.join(PRACA, p); lg = kat + ".log"; os.makedirs(kat, exist_ok=True)
    w = {"start": teraz().isoformat(timespec="seconds")}; t0 = time.time()
    if uruchom([PY, os.path.join(KOD, "arkusze.py"), str(e), str(n), kat], lg): return w | {"wynik": "blad", "etap": "arkusze"}
    w["arkusze_s"] = round(time.time() - t0); w["pobrane_gb"] = round(wczytaj(os.path.join(kat, "stan.json"), {}).get("bajty", 0) / 1e9, 2)
    if not os.path.isdir(os.path.join(kat, "kafle", "nmt")) or not os.listdir(os.path.join(kat, "kafle", "nmt")):
        return w | {"wynik": "pusta"}                                # brak arkuszy NMT (morze, za granica)
    powiaty = sorted(f[:-8] for f in os.listdir(os.path.join(POSR, p)) if f.endswith(".json.gz"))
    t1 = time.time()
    if uruchom([PY, os.path.join(KOD, "budynki_paczki.py"), str(e), str(n), kat] + powiaty, lg): return w | {"wynik": "blad", "etap": "budynki"}
    w["budynki_s"], w["powiaty"] = round(time.time() - t1), powiaty
    t2 = time.time(); env = dict(os.environ, PACZKI_WYJSCIE=WYJ)
    if uruchom([PY, os.path.join(KOD, "paczka.py"), "km", kat], lg, env): return w | {"wynik": "blad", "etap": "paczka"}
    pak = os.path.join(WYJ, "v1", p + ".pak")
    if not os.path.exists(pak) or os.path.getmtime(pak) < t2: return w | {"wynik": "blad", "etap": "paczka (brak pliku)"}
    w |= {"paczka_s": round(time.time() - t2), "mb": round(os.path.getsize(pak) / 1e6, 2), "wynik": "gotowa"}
    for d in ("kafle", "kron86"): shutil.rmtree(os.path.join(kat, d), ignore_errors=True)   # kafle 1 m (ok. 3 GB) nie sa juz potrzebne
    return w

def licz(ile):
    kol = wczytaj(LISTA, None) or lista(); stan = wczytaj(STAN, {}); zrobione, bledy, czeka = 0, 0, False
    for p in kol:
        if stan.get(p, {}).get("wynik") in ("gotowa", "pusta"): continue
        if ile is not None and zrobione >= ile: break
        while True:
            if os.path.exists(STOP): log("STOP - plik", STOP); return
            wolne = shutil.disk_usage(DOM).free / 1e9
            if wolne < MIN_GB:                                       # czekamy, nie konczymy: 2026-10-08 07:41 ktos zajal chwilowo ~34 GB
                if not czeka: log(f"wolne {wolne:.0f} GB < {MIN_GB:.0f} GB - czekam")
                czeka = True; time.sleep(600); continue
            if not noc():
                if not czeka: log(f"dzien - czekam do {NOC_OD}:00")
                czeka = True; time.sleep(600); continue
            czeka = False
            if not wez(f"liczenie paczki {p} (kolejka paczek 20 km, nice/ionice)"):
                log("srodowisko testowe zajete:", _czytaj().get("opis")); time.sleep(120); continue
            break
        koniec = threading.Event()
        def odnawiaj():
            while not koniec.wait(300): wez(f"liczenie paczki {p} (kolejka paczek 20 km, nice/ionice)")
        th = threading.Thread(target=odnawiaj, daemon=True); th.start()
        log("start", p)
        try: w = paczka(p)
        except Exception as ex: w = {"wynik": "blad", "etap": repr(ex)[:300]}
        finally: koniec.set(); th.join(); zwolnij()
        w["koniec"] = teraz().isoformat(timespec="seconds"); stan[p] = w; zapisz(STAN, stan); log(p, json.dumps(w, ensure_ascii=False))
        zrobione += 1; bledy = bledy + 1 if w["wynik"] == "blad" else 0
        if bledy >= 3: log("STOP - 3 bledy z rzedu"); return
        time.sleep(60)                                               # okno dla innych sesji na wziecie blokady
    log("koniec kolejki" if ile is None else f"koniec: {zrobione} paczek")

def pokaz():
    kol, stan = wczytaj(LISTA, []), wczytaj(STAN, {})
    g = [v for v in stan.values() if v.get("wynik") == "gotowa"]
    print(f"lista {len(kol)} · gotowe {len(g)} · puste {sum(v.get('wynik') == 'pusta' for v in stan.values())} · "
          f"bledy {sum(v.get('wynik') == 'blad' for v in stan.values())} · {sum(v['mb'] for v in g) / 1e3:.1f} GB wyniku · "
          f"{sum(v.get('pobrane_gb', 0) for v in stan.values()):.0f} GB pobran")
    for p, v in list(stan.items())[-10:]: print(p, json.dumps(v, ensure_ascii=False))

if __name__ == "__main__":
    import signal; signal.signal(signal.SIGTERM, lambda *a: sys.exit(143))   # kill -> finally: blokada oddana, dziecko zakonczone
    op = sys.argv[1] if len(sys.argv) > 1 else "stan"
    if op == "lista": lista()
    elif op == "stan": pokaz()
    elif op == "licz":
        jedna = open(os.path.join(KAT, ".licz"), "w")              # jedna kolejka naraz (usluga systemd + reczne uruchomienie)
        try: fcntl.flock(jedna, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: log("kolejka juz liczy - koniec"); sys.exit(0)
        licz(int(sys.argv[sys.argv.index("--ile") + 1]) if "--ile" in sys.argv else None)
    else: raise SystemExit(__doc__ or "uzycie: lista | stan | licz [--ile N]")
