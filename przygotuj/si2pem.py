# Stacje bazowe zlikwidowane wg SI2PEM (si2pem.gov.pl, system rzadowy o instalacjach PEM) - dla stacje_kraj.py
# (2026-10-18). Warstwa WFS public:extend_base_stations ma pole is_active; false = "(zlikwidowana)" w opisie stacji
# (sprawdzone na probce 12/12). Dwa zapytania: nieaktywne oraz aktywne (zeby nie zdjac miejsca, gdzie ten sam operator
# ma nowa instalacje). Kopia w dane/kraj/si2pem-stacje.json (poza gitem): gdy serwer nie odpowiada, kopia nie starsza niz
# WAZNOSC dni, inaczej pusta lista - przeliczenie ma przejsc i bez SI2PEM.
import json, os, sys, time, urllib.request
WFS = ("https://si2pem.gov.pl/geoserver/public/wfs?service=WFS&version=2.0.0&request=GetFeature&typeNames=public:extend_base_stations"
       "&outputFormat=application/json&propertyName=geom,identity_name,address,operator_name&cql_filter=is_active=")
WAZNOSC = 30
# operator SI2PEM -> poczatek nazwy w rejestrze UKE
OPERATORZY = {"Orange": "Orange", "T-Mobile": "T-Mobile", "P4": "P4", "Polkomtel": "Polkomtel"}

def _pobierz(aktywne):
    r = urllib.request.urlopen(urllib.request.Request(WFS + ("true" if aktywne else "false"), headers={"User-Agent": "radio-wid.pl (stacje zlikwidowane)"}), timeout=300)
    return [[*f["geometry"]["coordinates"], f["properties"]["operator_name"], f["properties"]["identity_name"], f["properties"]["address"]]
            for f in json.load(r)["features"] if f.get("geometry")]

def stacje(kopia):
    """(zlikwidowane, aktywne, stan); kazda stacja = [lon, lat, operator UKE, identyfikator, adres]."""
    try:
        d = {"pobrane": time.strftime("%Y-%m-%d"), "nieaktywne": _pobierz(False), "aktywne": _pobierz(True)}
        json.dump(d, open(kopia, "w"), ensure_ascii=False)
    except Exception as e:
        if os.path.exists(kopia) and time.time() - os.path.getmtime(kopia) < WAZNOSC * 86400:
            d = json.load(open(kopia)); print(f"SI2PEM nie odpowiada ({e}) - kopia z {d['pobrane']}", file=sys.stderr)
        else:
            print(f"SI2PEM nie odpowiada ({e}) i brak swiezej kopii - bez zdejmowania zlikwidowanych", file=sys.stderr); return [], [], None
    op = lambda s: next((v for k, v in OPERATORZY.items() if s.startswith(k)), None)
    zamien = lambda l: [[s[0], s[1], op(s[2]), s[3], s[4]] for s in l if op(s[2])]
    return zamien(d["nieaktywne"]), zamien(d["aktywne"]), d["pobrane"]
