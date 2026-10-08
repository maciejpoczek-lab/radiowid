# RadioWid — where does the signal come from?

**Live: <https://radio-wid.pl>** · licence: [AGPL-3.0](LICENSE) · code comments and UI in Polish

RadioWid is a map of radio coverage for all of Poland. It covers FM, DAB+, digital TV (DVB-T) and 4G/5G cell sites. The calculation runs live in the browser, on terrain plus the actual buildings and trees.
Tap a spot and RadioWid shows which transmitters reach it, along which path, and where to point an antenna.
Every result is a **SIMULATION**, not a measurement.

The page is static: no backend, no tracking, and the user's position never leaves the phone.
All heavy lifting happens in two places:
- in an offline pipeline that turns open geodata into compact binary "packs";
- in a dependency-free JavaScript engine that runs in Web Workers.

## How it works

| Part | What it does |
|---|---|
| `silnik/` | Propagation engine (plain ES modules, browser and Node). Knife-edge diffraction over a terrain + surface profile, foliage loss (Weissberger), optional wall scattering (ITU-R P.1411 §4.2.1), broadcast field strength from ITU-R P.1546 curves. |
| `telefon/poziomy.html` | The page served at radio-wid.pl. Zoom levels by grid size: 4 m (buildings and trees), 16 m, 100 m (terrain only), 1 km (country). |
| `przygotuj/` | Data pipeline (Python + numpy, no GDAL). Open data → 20 × 20 km packs on a national grid (EPSG:2180) → `.pak` files. |
| `przygotuj/kolejka_paczek.py` | Night queue on a compute host: download sheets → buildings → pack → delete raw tiles. One pack takes about 18 min, mostly downloading. |
| `przygotuj/paczki-na-strone.sh`, `paczki-rano.sh` | Pull finished packs, build zoom levels and building outlines, publish data (never the page) every morning. Hosts are set in `przygotuj/ustawienia.sh`. |
| `telefon/zloz.sh` | Assembles the static site into `_telefon/`. |
| `weryfikacja/` | Bit-exact checks of the JS engine against the Python reference models. Those models are not in this repo, so these checks only run on the author's machine. |
| `docs/` | Design notes (Polish): pack layout, sizes, zoom levels, privacy. |

## Data (not in the repo — regenerate with `przygotuj/`)

| Data | Source | Licence |
|---|---|---|
| Terrain (DTM) 1 m and 100 m, surface model (DSM) 1 m | GUGiK, opendata.geoportal.gov.pl | Polish open data, free reuse |
| Buildings LoD1 (3D models, 2024) | GUGiK | **CC BY 4.0** — attribution required |
| Roads, rivers, places (BDOT10k), borders and addresses (PRG) | GUGiK | Polish open data |
| Terrain outside Poland | Copernicus DEM GLO-30 | Copernicus licence (attribution text shown on the page) |
| Transmitters (FM, DAB+, DVB-T) and cell sites | UKE (Polish telecom regulator) public registries | public registry |
| Broadcast curves | ITU-R P.1546-6, tables from the ITU-R SG3 reference implementation | see ITU terms |

## Adapting it to another country

The engine (`silnik/`) and the page do not depend on Poland. Only the inputs do. To port it you need:
1. **Grid and projection.** Everything uses EPSG:2180 metres (`przygotuj/puwg92.py`, `przygotuj/uklad.py`). Pick your national metric CRS and pack size.
2. **Elevation.** A terrain model and, ideally, a surface model with buildings and tree canopy, at about 1 m (`arkusze.py`, `paczka.py`). Without a surface model you can use LoD1 building heights alone. Trees are then missing.
3. **Buildings.** Footprints with heights (`budynki_paczki.py` reads CityGML LoD1).
4. **Transmitters.** For each one: position, antenna height, ERP and frequency. Your regulator's register replaces the UKE readers (`uke.py`, `rtv_kraj.py`, `stacje_kraj.py`).
5. **Base map.** Roads, water, places and borders (`mapa_kraj.py` reads BDOT10k/PRG). Any vector source works. Note that OSM is ODbL.

Scripts still contain the author's paths (`~/dev/showreel-2/dane`, environment variables in some of them). Treat them as a worked example, not a turnkey tool. Issues and pull requests that make the pipeline country-agnostic are welcome.

## Running locally

```bash
telefon/zloz.sh                       # needs the data in dane/ (see przygotuj/)
python3 -m http.server 8794 --directory _telefon
```

## Privacy

The site has no analytics, no cookies and no server-side logging of map requests. A position from the GPS or the address search is used only inside the browser.

## Licence

Copyright © 2026 Maciej Poczek. Licensed under the GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
If you run a modified version as a public service, you must publish your changes under the same licence.
Data keep their own licences (table above).

---

**PL:** Mapa zasięgu radia, telewizji i sieci komórkowych dla całej Polski, liczona w przeglądarce na terenie, budynkach i drzewach. Kod na licencji AGPL-3.0. Dane (GUGiK, UKE, Copernicus) nie są w repozytorium. Skrypty z `przygotuj/` pobierają je i przetwarzają.
