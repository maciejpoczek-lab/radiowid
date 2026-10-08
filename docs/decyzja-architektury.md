# Mapa światła radiowego — skąd przeglądarka bierze dane (6.10.2026)

**Decyzja Maćka 6.10, 10:24: wariant C; pliki na Zirael (poczek.pl).**

## Rekomendacja

**Wariant C: dane przygotowane z góry jako pliki statyczne na poczek.pl, liczenie na żywo w przeglądarce.**
Skrypt na Macu bierze dane GUGiK (teren 1 m, wysokości budynków i drzew), UKE i OSM, przycina je
i zapisuje w kaflach. Przeglądarka pobiera tylko kawałki potrzebne dla wybranego miasta i liczy
w wątkach roboczych. Silnik JS wystarcza, WebGPU odkładamy (pomiar niżej).

Dlaczego: najlepsze dane w Polsce (GUGiK 1 m) są **dla przeglądarki niedostępne wprost** — serwer
GUGiK nie zezwala na odczyt z innej domeny. Darmowe usługi, które zezwalają (Overpass), są
zawodne i mają limity — przy publicznej stronie każdy odwiedzający to kolejne zapytanie.
Pliki na własnej domenie omijają oba problemy, a adres IP odwiedzającego nie trafia do nikogo
trzeciego.

## Pomiar dostępu z przeglądarki (6.10, ok. 10:00)

Zapytania z nagłówkiem `Origin: https://poczek.pl`, prostokąty wokół rynku w Garwolinie.

| Źródło | Przeglądarka z poczek.pl odczyta? | Uwagi |
|---|---|---|
| GUGiK WCS — NMT i NMPT (model terenu i pokrycia, 1 m) | **nie** — brak `Access-Control-Allow-Origin` | serwer odpowiada 200, tylko przeglądarka zablokuje odczyt |
| GUGiK WMS — ortofotomapa | tak — odbija domenę | tło mapy możliwe wprost |
| GUGiK — modele 3D budynków (LoD1/LoD2) | to nie usługa: pliki CityGML na powiat | tylko przez przygotowanie z góry |
| Copernicus GLO-30 na AWS S3 | **nie** — brak nagłówka, zapytanie wstępne 403 | |
| Kafle terenu AWS „Terrarium” (dla Polski źródło EU-DEM, 25 m) | tak — `*` | z tego korzysta Meshtastic Site Planner |
| Overpass (OpenStreetMap) | tak — `*` | w chwili testu **504** dla jednego kwartału; zapytanie bez nagłówków przeglądarki — 406 |
| Overture Maps (kafle na S3) | tak — `*` | sprawdzone tylko nagłówki zasobnika, nie konkretny plik |
| UKE — wykaz stacji (xlsx w BIP) | nie dotyczy | i tak wymaga przeróbki: xlsx, brak wysokości anten |

## Licencje

| Dane | Warunek | Pewność |
|---|---|---|
| GUGiK NMT | „dostępne bezpłatnie i możliwe do dowolnego wykorzystania” (geoportal.gov.pl) | pewne (cytat ze strony) |
| GUGiK modele 3D budynków LoD1 (2024) | **CC BY 4.0** — podpis źródła obowiązkowy (poprawka 6.10: odpowiedź usługi `ModeleBudynkow3D` podaje licencję przy pliku powiatu) | pewne (odpowiedź usługi) |
| GUGiK NMPT | ta sama zasada | prawdopodobne (strony NMPT nie czytałem słowo w słowo) |
| Copernicus GLO-30 | wolne; po przetworzeniu obowiązkowa formuła: *produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved* | pewne (licencja COPDEM-30) |
| EU-DEM (kafle Terrarium) | wolne z podaniem źródła | prawdopodobne (z pamięci) |
| OpenStreetMap (ODbL) | obraz mapy = „Produced Work”: podpis „© OpenStreetMap contributors”. Jeśli publikujemy **kafle danych** pochodnych z OSM — muszą wyjść na ODbL (dzielenie się na tych samych warunkach) | pewne (warunki ODbL) |
| UKE (BIP) | bez opłat; obowiązek podania **źródła, czasu wytworzenia i pozyskania** oraz informacji o **przetworzeniu**; UKE nie odpowiada za dalsze użycie | pewne (strona „Ponowne wykorzystanie informacji” w BIP UKE) |

## Warianty

**A. Wszystko wprost z cudzych serwerów.** Teren z kafli AWS (EU-DEM 25 m), budynki z Overpass.
Zero infrastruktury. Odpada jako podstawa: bez GUGiK 1 m, Overpass zawodny i z limitami,
IP odwiedzających trafia do osób trzecich. Zostaje jako zapas dla miast spoza Polski (etap 3).

**B. Własny pośrednik na serwerze.** Przeglądarka pyta poczek.pl, serwer pyta GUGiK i zapisuje.
Daje 1 m na żądanie, ale: serwer do utrzymania, obciążanie GUGiK, długie oczekiwanie
(4 × 4 km przeskalowane do 40 m — 25 s, zmierzone 6.10), furtka do nadużyć.

**C. Pliki przygotowane z góry (rekomendacja).** Plusy: ta sama domena (problem zezwoleń znika),
najlepsze dane, brak zależności od cudzej dostępności, prywatność odwiedzających, dane z datą
„stan na” (wymóg UKE). Minusy: skrypt przygotowujący do napisania, miejsce na pliki,
aktualizacja ręczna. Rachunek objętości dla całej Polski: 312,7 tys. km² × teren 25 m ≈ 500 mln
komórek ≈ 1 GB bez kompresji; budynki i drzewa tylko dla miast — do policzenia w etapie 2.

## Silnik — pomiar (prototyp w `silnik/`)

Zgodność z Pythonem w tych samych punktach (`weryfikacja/porownaj.mjs`): największa różnica
**0,000015 dB** — miasto (`fala.py`, 164 tys. punktów, 3 pasma) i teren (`dolek.py`, 71 tys. punktów,
3 maszty FM). Wyniki zapisane wcześniej (`fala.npz`, `dolek.npz`) są identyczne z obecnym kodem.

Czas na M2 Pro (Node = ten sam silnik JavaScript co Chrome, `weryfikacja/czas-watki.mjs`, mediana z 3):

| Przebieg | 1 wątek | 8 wątków |
|---|---|---|
| miasto 2,2 × 1,7 km po 4,8 m, jeden nadajnik i pasmo | 0,19 s | 0,03 s |
| teren 8 × 8 km po 30 m, maszt 9 km (Górzno) | 0,39 s | 0,06 s |
| teren 8 × 8 km po 30 m, maszt 56 km (PKiN) | 1,65 s | 0,25 s |
| teren 8 × 8 km po 30 m, maszt 87 km (Łosice) | 2,38 s | 0,39 s |

Wniosek: liczenie na żywo działa na procesorze, bez WebGPU. Telefony będą wolniejsze —
**niezmierzone**. Ta sama strona działa w Chromium w wątkach (`podglad/`), ale czasy stamtąd
pominięte: panel przeglądarki był ukryty i dławił wątki.

## Czego ta decyzja nie przesądza

- ~~gdzie leżą pliki~~ — rozstrzygnięte: Zirael. Zmierzone 6.10: poczek.pl serwuje Caddy z `/srv/poczek` (blok w `/opt/zirael/Caddyfile`), na dysku 806 GB wolne. Obecna polityka bezpieczeństwa strony (`connect-src 'self'`, `script-src 'self'`, `img-src https:`) przepuszcza wariant C bez zmian: dane i wątki z tej samej domeny, tło z ortofotomapy GUGiK jako obrazki. Wgranie plików na serwer to wdrożenie na Zirael — przez Hub CC albo za zgodą Maćka;
- jednego silnika łączącego teren i miasto w jednym przebiegu — następny krok, niezależny od wariantu.
