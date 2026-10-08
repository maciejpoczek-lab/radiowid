#!/usr/bin/env python3
# Nadajniki radia i telewizji z wykazu pozwolen radiowych UKE (stan 2026-09-18, pliki *_r: ostatnia decyzja dla kazdej
# stacji nadawczej) w promieniu R km od RYNKU -> dane/uke-2026/rtv.json. Zastepuje fm-100km.json (stan 2018).
#   UKF FM  pozwolenie_ukf_r_2026-09-18.csv   (UTF-8 z BOM)
#   DAB+    pozwolenia_dab_r_2026-09-18.csv   (cp1250)
#   DVB-T   pozwolenia_ntc_r_2026-09-18.csv   (cp1250; naziemna telewizja cyfrowa)
# Pola jak w fm-100km.json (fm.mjs/rtv.mjs je czyta) + typ (fm|dab|dvbt), kanal, system.
# Charakterystyka: 36 wartosci co 10 st = tlumienie anteny [dB] wzgledem kierunku maksymalnego.
# Pobrane 2026-10-06 z bip.uke.gov.pl za zgoda Macka.
# Uzycie: python3 rtv.py
import csv, datetime, json, math, os, re, sys
sys.path.insert(0, os.path.expanduser("~/dev/showreel-2/dane/nmpt"))
from miejsce import SR, przyrostek
DANE = os.path.expanduser("~/dev/showreel-2/dane/uke-2026")
KX, KY = 111320 * math.cos(math.radians(SR[0])), 110570.0
DZIS = datetime.date(2026, 10, 6)
PLIKI = [  # typ, plik, kodowanie, promien km, mapowanie pol
    ("fm", "pozwolenie_ukf_r_2026-09-18.csv", "utf-8-sig", 100,
     dict(mhz="F [MHz]", program="Program", lon="Dł. geogr.", lat="Sz. geogr.", hter="H ter.", hant="H ant.", pol="Pol.", char="Char.", system="Syst.")),
    ("dab", "pozwolenia_dab_r_2026-09-18.csv", "cp1250", 100,
     dict(mhz="Czestotliwość środkowa [MHz]", program="Nazwa multipleksu", kanal="Kanał/blok częstotliwościowy", lon="Dł.geogr. (WGS84)",
          lat="Sz.geogr. (WGS84)", hter="Wysokość lokalizacji [m. npm]", hant="Wysokość anteny [m. npt]", pol="Polaryzacja", char="Charakterystyka", system="System emisji")),
    ("dvbt", "pozwolenia_ntc_r_2026-09-18.csv", "cp1250", 120,
     dict(mhz="Czestotliwość środkowa [MHz]", program="Nazwa multipleksu", kanal="Kanał/blok częstotliwościowy", lon="Dł.geogr. (WGS84)",
          lat="Sz.geogr. (WGS84)", hter="Wysokość lokalizacji [m. npm]", hant="Wysokość anteny [m. npt]", pol="Polaryzacja", char="Charakterystyka", system="System emisji")),
]

def dms(s):                      # 21E00'22" ; w pliku FM bywa litera E takze przy szerokosci (literowka UKE) - litera bez znaczenia
    m = re.match(r"\s*(\d+)[NSEW](\d+)'(\d+)", s or "")
    return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600 if m else None
liczba = lambda s: float(s.replace(",", ".")) if s and s.strip() not in ("", "-") else None
def data(s):
    s = (s or "").strip()
    for f in ("%Y-%m-%d", "%d.%m.%Y"):
        try: return datetime.datetime.strptime(s, f).date()
        except ValueError: pass
    return None

wynik, pominiete = [], {}
for typ, plik, kod, R, p in PLIKI:
    for w in csv.DictReader(open(os.path.join(DANE, plik), encoding=kod), delimiter=";"):
        lat, lon = dms(w[p["lat"]]), dms(w[p["lon"]])
        wazn = data(w["Ważny do"])
        if lat is None or lon is None: pominiete[typ, "bez wspolrzednych"] = pominiete.get((typ, "bez wspolrzednych"), 0) + 1; continue
        x, y = (lon - SR[1]) * KX, (lat - SR[0]) * KY; km = math.hypot(x, y) / 1000
        if km > R: continue
        if re.search(r"eksperym|okazjonal|czasow", w["Status"], re.I):         # emisje tymczasowe - anteny na nie nie ustawia sie na stale
            pominiete[typ, "tymczasowe"] = pominiete.get((typ, "tymczasowe"), 0) + 1; continue
        if wazn and wazn < DZIS: pominiete[typ, "wygasle"] = pominiete.get((typ, "wygasle"), 0) + 1; continue
        erp, hant = liczba(w["ERP[kW]"]), liczba(w[p["hant"]])
        if not erp or not hant: pominiete[typ, "bez ERP/H ant"] = pominiete.get((typ, "bez ERP/H ant"), 0) + 1; continue
        tl = [liczba(w.get(f"{a}°")) or 0.0 for a in range(0, 360, 10)]
        wynik.append({"typ": typ, "mhz": liczba(w[p["mhz"]]), "program": w[p["program"]].strip(), "kanal": (w.get(p.get("kanal", "")) or "").strip(),
                      "stacja": w["Nazwa stacji"].strip(), "lok": w["Lokalizacja stacji"].strip(), "lat": round(lat, 5), "lon": round(lon, 5),
                      "km": round(km, 1), "az": round(math.degrees(math.atan2(x, y)) % 360), "hter": liczba(w[p["hter"]]), "hant": hant,
                      "erp_kw": erp, "pol": w[p["pol"]].strip(), "char": w[p["char"]].strip(), "tlumienie_db": tl,
                      "system": w[p["system"]].strip(), "status": w["Status"].strip(), "waznosc": wazn.isoformat() if wazn else ""})
wynik.sort(key=lambda s: (s["typ"], s["km"]))
json.dump({"zrodlo": "UKE, wykaz pozwolen radiowych: UKF FM, T-DAB, naziemna telewizja cyfrowa; stan 2026-09-18 (pliki *_r), przetworzone",
           "rynek": SR, "stacje": wynik}, open(os.path.join(DANE, przyrostek("rtv") + ".json"), "w"), ensure_ascii=False, indent=0)
for typ in ("fm", "dab", "dvbt"):
    s = [v for v in wynik if v["typ"] == typ]
    print(f"{typ:5s} {len(s):4d} nadajnikow, {len({(v['lat'], v['lon']) for v in s}):3d} miejsc, najblizej:",
          "; ".join(f"{v['program'][:18]} {v['stacja'][:14]} {v['km']} km {v['erp_kw']} kW" for v in s[:3]))
print("pominiete:", pominiete)
