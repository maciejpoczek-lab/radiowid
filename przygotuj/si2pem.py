# Stacje bazowe z SI2PEM (si2pem.gov.pl, system rzadowy o instalacjach PEM) - dla stacje_kraj.py.
# Warstwa WFS public:extend_base_stations ma pole is_active; false = "(zlikwidowana)" w opisie stacji (probka 12/12).
# Aktywne niosa pasma: `permit` (pozwolenia - to samo co wykaz UKE) i `no_permit` (stacje tylko ZAREJESTROWANE, wpis
# REJ/..., ktorych wykaz pozwolen UKE nie zawiera - glownie Plus i Play; 2026-10-18). Dwa zapytania, kopia
# w dane/kraj/si2pem-stacje.json (poza gitem): gdy serwer nie odpowiada, kopia nie starsza niz WAZNOSC dni, inaczej
# puste listy - przeliczenie ma przejsc i bez SI2PEM.
import json, os, sys, time, urllib.request
WFS = ("https://si2pem.gov.pl/geoserver/public/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=public:extend_base_stations"
       "&outputFormat=application/json&cql_filter=is_active=")
POLA = {False: "geom,identity_name,address,operator_name", True: "geom,identity_name,address,operator_name,permit,no_permit"}
WAZNOSC = 30; WERSJA = 2
# operator SI2PEM -> nazwa w rejestrze UKE
OPERATORZY = {"Orange": "Orange Polska S.A.", "T-Mobile": "T-Mobile Polska S.A.", "P4": "P4 sp. z o.o.", "Polkomtel": "Polkomtel sp. z o.o."}
# kod technologii SI2PEM -> pasmo jak w plikach UKE (liczebnosci kodow zgodne z wykazem UKE); i9 (IoT 900) pomijamy
PASMA = {"g9": "gsm900", "g18": "gsm1800", "u9": "umts900", "u21": "umts2100", "l4": "lte420", "l7": "lte700", "l8": "lte800",
         "l9": "lte900", "l18": "lte1800", "l21": "lte2100", "l26": "lte2600", "g57": "5g700", "g518": "5g1800", "g521": "5g2100",
         "g526": "5g2600", "g536": "5g3600", "c42": "cdma420"}

def _pasma(p, dzis):
    # pozwolenia wszystkie; rejestracje tylko z planowana data uruchomienia, ktora juz minela
    wpisy = json.loads(p.get("permit") or "[]") + [e for e in json.loads(p.get("no_permit") or "[]") if (e.get("planned_date") or "") <= dzis]
    return sorted({PASMA[e["technology"]] for e in wpisy if e.get("technology") in PASMA})

def _pobierz(aktywne):
    r = urllib.request.urlopen(urllib.request.Request(WFS + ("true" if aktywne else "false") + "&propertyName=" + POLA[aktywne],
                                                      headers={"User-Agent": "radio-wid.pl (stacje bazowe)"}), timeout=600)
    dzis = time.strftime("%Y-%m-%d")
    return [[*f["geometry"]["coordinates"], f["properties"]["operator_name"], f["properties"]["identity_name"], f["properties"]["address"]]
            + ([_pasma(f["properties"], dzis)] if aktywne else []) for f in json.load(r)["features"] if f.get("geometry")]

def stacje(kopia):
    """(zlikwidowane, aktywne, stan); stacja = [lon, lat, operator UKE, identyfikator, adres] (+ [pasma] dla aktywnych)."""
    try:
        d = {"wersja": WERSJA, "pobrane": time.strftime("%Y-%m-%d"), "nieaktywne": _pobierz(False), "aktywne": _pobierz(True)}
        json.dump(d, open(kopia, "w"), ensure_ascii=False)
    except Exception as e:
        d = json.load(open(kopia)) if os.path.exists(kopia) and time.time() - os.path.getmtime(kopia) < WAZNOSC * 86400 else {}
        if d.get("wersja") == WERSJA: print(f"SI2PEM nie odpowiada ({e}) - kopia z {d['pobrane']}", file=sys.stderr)
        else: print(f"SI2PEM nie odpowiada ({e}) i brak swiezej kopii - bez SI2PEM", file=sys.stderr); return [], [], None
    op = lambda s: next((v for k, v in OPERATORZY.items() if s.startswith(k)), None)
    zamien = lambda l: [[s[0], s[1], op(s[2]), *s[3:]] for s in l if op(s[2])]
    return zamien(d["nieaktywne"]), zamien(d["aktywne"]), d["pobrane"]
