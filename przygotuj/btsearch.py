# Stacje oznaczone w BTSearch (btsearch.pl, baza tworzona przez uzytkownikow) jako nieczynne - dla stacje_kraj.py
# (decyzja Macka 2026-10-17). Publiczne API v2 bez klucza, tylko status `inactive` (kilka zapytan), grzecznie wobec
# limitu 20 zapytan / ~5 min. Kopia w dane/kraj/btsearch-nieczynne.json (poza gitem): gdy API nie odpowiada, bierzemy
# kopie nie starsza niz WAZNOSC dni, inaczej pusta lista - przeliczenie ma przejsc i bez BTSearch.
import json, os, sys, time, urllib.parse, urllib.request
API = "https://btsearch.pl/api/v2"; WAZNOSC = 30
# operatorId BTSearch -> poczatki nazw operatorow w rejestrze UKE (8 = NetWorkS!, maszty wspolne Orange i T-Mobile)
OPERATORZY = {1: ("Polkomtel",), 2: ("P4",), 5: ("T-Mobile",), 6: ("Orange",), 8: ("Orange", "T-Mobile")}

def _pobierz(sciezka, maks=40):
    wynik, kursor, ile = [], None, 0
    while True:
        q = {"statuses": "inactive", "limit": 200, **({"cursor": kursor} if kursor else {})}
        r = urllib.request.urlopen(urllib.request.Request(f"{API}{sciezka}?{urllib.parse.urlencode(q)}",
                                   headers={"User-Agent": "radio-wid.pl (stacje nieczynne)"}), timeout=60)
        d = json.load(r); wynik += d["data"]; ile += 1; kursor = d["paging"]["nextCursor"]
        if not kursor: return wynik
        if ile >= maks: raise RuntimeError(f"{sciezka}: ponad {maks} stron")
        if int(r.headers.get("X-RateLimit-Remaining", 5)) <= 1:
            time.sleep(max(5, int(r.headers.get("X-RateLimit-Reset", 0)) - time.time() + 3))

def nieczynne(kopia):
    """[{operatorzy, lat, lon, adres, od, notatka}] dla stacji nieczynnych w BTSearch."""
    try:
        st, lo = _pobierz("/stations"), _pobierz("/locations")
        d = {"pobrane": time.strftime("%Y-%m-%d"), "stacje": st, "lokalizacje": lo}
        json.dump(d, open(kopia, "w"), ensure_ascii=False)
    except Exception as e:
        if os.path.exists(kopia) and time.time() - os.path.getmtime(kopia) < WAZNOSC * 86400:
            d = json.load(open(kopia)); print(f"BTSearch nie odpowiada ({e}) - kopia z {d['pobrane']}", file=sys.stderr)
        else:
            print(f"BTSearch nie odpowiada ({e}) i brak swiezej kopii - bez zdejmowania nieczynnych", file=sys.stderr); return [], None
    lok = {l["id"]: l for l in d["lokalizacje"]}
    return [{"operatorzy": OPERATORZY[s["operatorId"]], "lat": lok[s["locationId"]]["latitude"], "lon": lok[s["locationId"]]["longitude"],
             "adres": f'{lok[s["locationId"]]["city"]}, {lok[s["locationId"]]["address"]}', "od": (s.get("statusChangedAt") or "")[:10],
             "notatka": s.get("notes")}
            for s in d["stacje"] if s["operatorId"] in OPERATORZY and s["locationId"] in lok], d["pobrane"]
