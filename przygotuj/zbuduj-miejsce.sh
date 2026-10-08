#!/bin/bash
# Caly zestaw danych mapy dla jednego miejsca (dane/nmpt/miejsce.py), w kolejnosci zaleznosci.
# Wymaga pobranych wczesniej (za zgoda Macka): kafli 1 km (dane/nmpt/kafle.py 3), terenu 40 m (dane/nmpt/region.py),
# LoD1 powiatu (dane/budynki3d[-miejsce]/), PRG + BDOT10k powiatu (dane/gugik-wektor[-miejsce]/), kafli Copernicus wokol.
# Uzycie: MIEJSCE=warszawa przygotuj/zbuduj-miejsce.sh   -> mapa/dane/*-<miejsce>*, potem telefon/zloz.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${MIEJSCE:?ustaw MIEJSCE (np. warszawa)}"; export MIEJSCE
P=$([ "$MIEJSCE" = garwolin ] && echo "" || echo "-$MIEJSCE")
python3 teren.py
python3 rtv.py | tail -1
node fm.mjs 3000 60 120 "uke-2026/rtv$P.json" rtv | tail -1
python3 budynki_lod1.py 3000
python3 budynki_wektor.py | tail -1
python3 mapa_wektor.py | tail -1
python3 stacje.py | sed -n 1p
python3 rynek.py 2880 kafle | tail -1
python3 kompresuj.py "../dane/obszar-2880$P"
