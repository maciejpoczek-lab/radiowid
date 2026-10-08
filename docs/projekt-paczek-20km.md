# Paczki 20 km — podział Polski (projekt, 2026-10-07)

Decyzja Maćka 2026-10-07 00:23: cała Polska w równej siatce paczek ok. 20 × 20 km, w środku kafle 1 km,
telefon pobiera 1–4 paczki wokół punktu. Serwer wie tylko, że ktoś ogląda miasto z okolicą.
Ten plik to PROJEKT — nic z tego jeszcze nie jest zbudowane. Wyniki mapy to SYMULACJA.

## 1. Układ siatki

- **Układ współrzędnych: EPSG:2180 (PUWG 1992)**, nie lokalny kwadrat wokół rynku. Jedna strefa na całą Polskę,
  metry, w nim są wszystkie dane GUGiK (NMT/NMPT, LoD1, PRG, BDOT10k). Znika obrót ~2° lokalnego kwadratu
  (powód pół boku 2880 zamiast 3000) i wielomian w `przygotuj/uklad.py`.
- **Paczka = kwadrat 20 000 m wyrównany do wielokrotności 20 km** w EPSG:2180.
  Polska mieści się w x ≈ 170–870 km, y ≈ 130–790 km → siatka 35 × 33; paczek przecinających ląd
  ok. 800–900 (szacunek z powierzchni 312,7 tys. km² / 400 km²; policzyć z granicy PRG).
- **Kafel = 1 km × 1 km** wyrównany do pełnych kilometrów, 250 × 250 komórek po 4 m. 400 kafli w paczce.
- Okno mapy wokół punktu: kwadrat osiowy w EPSG:2180, krawędzie na pełnych 4 m → okna z kilku paczek
  skleja się kopiowaniem wierszy, bez przeliczania.

## 2. Nazewnictwo

- Paczka: `E{wschód km}N{północ km}` lewego dolnego rogu, 3 cyfry, np. `E620N480` (= x 620–640 km, y 480–500 km).
- Kafel w paczce: `{wschód km}_{północ km}`, np. `633_487`.
- Plik: `paczki/v{wersja}/E620N480.pak` — wersja danych w ścieżce, żeby stara kopia w pamięci telefonu
  nie mieszała się z nową.

## 3. Co jest w paczce

| Warstwa | Rozdzielczość | Zasięg | Zmierzona waga |
|---|---|---|---|
| G (grunt), O − G (pokrycie), ZW, BUD, NMPT_PROC | 4 m, per kafel 1 km | paczka | 80 kB/km² wieś/małe miasto, 108–148 kB/km² Warszawa (mediana 133) |
| T (teren NMT) | 30 m | paczka + 10 km marginesu (profile do stacji 3 km za krawędzią okna) | ok. 1,7 MB (z T Warszawy 0,58 MB / 23,6 km bok) |
| stacje komórkowe UKE | lista | paczka + 10 km marginesu, z wysokością anteny z NMPT | 0,1–2 MB |
| wektory (ulice, numery domów, obrysy) | per kafel | paczka | 11 kB/km² Garwolin, ok. 45 kB/km² Warszawa |

Poza paczkami, **jeden plik krajowy**: nadajniki FM / DAB+ / DVB-T z wysokością efektywną h1 per sektor 10°
(P.1546 liczy h1 w kierunku odbiornika; ok. 220 nadajników × 36 sektorów — dziesiątki kB). **Poprawka 2026-10-07 (pomiar, §8.4):**
nie 220, tylko ok. 990 położeń i ok. 2200 pozwoleń — plik ok. 0,25 MB po kompresji. Każdy pobiera
ten sam plik, więc nic nie zdradza.

**Copernicus (M) wypada z telefonu.** Stacje leżą najdalej 3 km za krawędzią okna, więc profile mieszczą się
w T; M na stronie Garwolina to 8,6 z 11 MB. PRAWDOPODOBNE — potwierdzić licznikiem odwołań do M w
`silnik/teren-dolek.js` przed usunięciem.

Format pliku `.pak`: nagłówek JSON (wersja, róg, spis bloków: warstwa × kafel → przesunięcie, długość) +
sklejone bloki gzip w obecnym kodowaniu (`kompresuj.py`: int16 cm, różnice, O nad G). Jedno zapytanie na
paczkę; telefon rozpakowuje tylko kafle z okna (36–49 z 400), reszta leży w pamięci podręcznej
przeglądarki (Cache API) na następny raz.

## 4. Waga (z pomiaru 2026-10-07, 1 km kafle Garwolina i Warszawy)

| | Garwolin-podobne | Warszawa |
|---|---|---|
| raster 4 m | 32 MB | 53 MB |
| + T, stacje, wektory | ok. 38 MB | ok. 75 MB |

Ile paczek potrzeba (okno 5,76 km, punkt losowy): 1 paczka 51%, 2 — 41%, 4 — 8%; średnio 1,7.
Pierwsze wejście: ok. 60 MB na wsi, do ok. 300 MB w rogu czterech paczek warszawskich. Kolejne — z pamięci.
Cała Polska na serwerze: ok. 850 × 40 MB ≈ 30–35 GB (szacunek).

**Grunt G to 55–60 kB/km², 2/3 wagi.** Szum NMT na poziomie centymetrów (mediana reszty 5–7 cm): lepszy
predyktor (gradient) daje −5%, xz −15%, krok 5 cm −40%, 10 cm −60%. Wcześniejszy pomiar (2026-10-06 12:08):
krok 10 cm na wszystkich warstwach przesuwał wynik stacji do 3,4 dB — nie wiadomo, ile z tego to G.

**Pomiar 2026-10-07 (4G, 10 m, mapa całości, `G_KROK` w `weryfikacja/czas-komorkowe.mjs`; O i ZW przesunięte razem z G):**
grunt co 5 cm — strata > 1 dB w 0,31% (Garwolin) / 0,38% (Warszawa) komórek, > 3 dB 0,00%, jasność > 10% 0,000%;
co 10 cm — 0,67% / 0,85%, > 3 dB 0,00%, jasność 0,000%. Wniosek: **grunt co 5 cm** (zapas wobec 10 cm). Raster paczki ok. 24 MB
na wsi i ok. 43 MB w Warszawie zamiast 32 / 53 MB (szacunek z kompresji jednego kafla, do potwierdzenia na całej paczce).

**Próba 2026-10-07 (`przygotuj/paczka.py`, 25 kafli wokół Garwolina, dwie paczki E660N440 i E680N440):** 58–61 kB na kafel
(G 32–33, O−G 7, ZW 16–21, BUD 1,4 kB) → **raster pełnej paczki ok. 23–24 MB** — szacunek potwierdzony na prawdziwych kaflach.
Czytnik `silnik/paczka.js` skleja okno 5,76 km przez granicę dwóch paczek bit w bit względem niezależnego dekodera w numpy
(`weryfikacja/test-paczki.{py,mjs}`); rozpakowanie okna w Node ok. 110 ms dla wszystkich warstw. Na telefonie niezmierzone.

**Pierwsza pełna paczka E660N440 (2026-10-07, komputer testowy, z arkuszy):** 400 kafli, **33 MB** (83 kB/kafel: G 30, O−G 2, **ZW 50**,
BUD 0,4 kB). Okolica leśna, więc korony zajmują więcej niż grunt. ZW co 1 cm to przesada (wysokość drzewa ±1 cm nic nie zmienia):
krok 10–25 cm to pierwsza oszczędność do zmierzenia. Pobranie arkuszy: 7,2 GB w 8 min (194 arkusze). Liczenie paczki: 129 s, 160 MB RAM, jeden rdzeń.
Na wspólnych kaflach Garwolina zgodna z paczką z WCS (G: mediana 0, 99% < 0,15 m; ZW różni się w 4% komórek — nowsze arkusze NMPT 2025, hipoteza).
Cała Polska z tego tempa: ok. 850 paczek × 10 min ≈ 6 dni ciągłej pracy, ok. 6 TB pobrań (szacunek).

**Krok ZW (2026-10-07, E660N440 przeliczona na komputerze testowym, `ZW_KROK` w `paczka.py` i `weryfikacja/czas-komorkowe.mjs`):**
ZW co 1 cm 33,2 MB → **co 10 cm 29,1 MB (ZW 40 kB/kafel)** → co 25 cm 26,6 MB (ZW 34 kB). Wpływ na mapę 4G (10 m, cała mapa):
10 cm — > 1 dB w 0,27% (Garwolin) / 0,40% (Warszawa) komórek, > 3 dB 0,00%, jasność > 10% 0,000%; 25 cm — 0,69% / 0,92%, > 3 dB 0,01%.
Wszystkie pasma Garwolin (20 stacji): 10 cm 0,32%, 25 cm 0,80%. Wniosek: **ZW co 10 cm** (ten sam poziom co grunt co 5 cm);
25 cm podwaja błąd za 2,5 MB. Reszta wagi ZW to kształt koron (brzegi lasu), nie dokładność zapisu.

**Druga pełna paczka E680N440 (2026-10-07, ta sama procedura §6, ZW co 10 cm):** 400 kafli, **23,9 MB** (60 kB/kafel: G 28, O−G 2, ZW 29,
BUD 0,5 kB). 97 arkuszy NMT/NMPT, 8,0 GB pobrań w 7 min; KRON86 → EVRF2007 poprawka −0,01 m z 36 439 komórek (IQR 0,05 m — pewniejsza niż w E660N440).
Budynki: powiaty 1403 i 0611, 25 220 brył. Liczenie 2:13, 227 MB RAM. Okno Garwolina z dwóch pełnych paczek: 100% mapy, bit w bit zgodne.
Dwie zmierzone paczki wiejskie: **24–29 MB** (las podnosi ZW).

## 5. Jak strona łączy 1–4 paczki

1. Punkt (dotknięcie / adres / GPS — GPS nie wychodzi z telefonu) → okno 5,76 km w EPSG:2180.
2. Paczki przecinające okno → 1, 2 albo 4 nazwy → pobranie całych plików (nigdy zapytanie o kafel ani zakres
   bajtów: to zdradziłoby punkt z dokładnością do 1 km).
3. Z każdej paczki kafle w oknie → jedna tablica okna (sklejanie wierszy). T i stacje: suma z paczek, stacje
   bez duplikatów po identyfikatorze UKE.
4. Silnik dostaje okno jak dziś `obszar-2880` — zmiana w silniku tylko w układzie (2180 zamiast lokalnego).

## 6. Decyzje i miejsce na dane

- 2026-10-07: **paczka 20 km** (Maciek: „zobaczymy, jak będzie wyglądać”).
- **Miejsce: dysk Zirael** (zmierzone 2026-10-07: 781 GB wolne z 929 GB, RAID1 na dwóch NVMe 1 TB; 16 rdzeni, 61 GB RAM).
  Paczki całej Polski ok. 30–35 GB = ok. 4% wolnego miejsca, bez dodatkowych kosztów. Darmowe chmury za małe:
  Cloudflare R2 i Backblaze B2 mają 10 GB za darmo.
- **Dane 1 m nie muszą leżeć na dysku w całości:** arkusz po arkuszu — pobierz, przelicz do 4 m (kafle 1 km), skasuj surowy.
  Na dysku tylko wynik i bieżący arkusz.
- **2026-10-07, decyzja Maćka: przeliczanie na komputerze testowym (`zirael-test`, Garwolin), nie na Zirael** — Zirael
  od betatestów będzie obciążony, priorytet ma pirxstream. Zirael tylko przechowuje i wydaje gotowe paczki (pliki statyczne,
  z limitem prędkości wysyłania). Zmierzone 2026-10-07: 8 wątków, 15 GB RAM, dysk systemowy 70 GB wolne (z 110 GB);
  drugi dysk Samsung 466 GB jest NTFS (Windows), nie zamontowany w Ubuntu. Maszyna jest wspólna (środowisko testowe ZIR-160,
  dual-boot z grami) — praca tylko z blokadą `bin/srodowisko-testowe.sh wez/zwolnij` i nocą.
- Do ustalenia z Hubem (deploy na Zirael to jego teren): katalog danych, usługa serwująca paczki **bez dziennika zapytań**
  (inaczej serwer i tak zapisuje, kto oglądał którą okolicę), godziny przeliczania (nocą — nie zabierać procesora produkcji).
- **Źródło danych 1 m (ustalone 2026-10-07, bez WCS):** całe arkusze `.asc` z `opendata.geoportal.gov.pl` (zwykłe HTTP, bez logowania);
  listę adresów daje skorowidz ArcGIS REST `https://mapy.geoportal.gov.pl/gprest/services/SkorowidzeFOTOMF/MapServer/4/query`
  (zapytanie prostokątem w EPSG:2180 → JSON z `url_do_pobrania`, `akt_rok`, `char_przestrz`, `uklad_h`; limit 1000 rekordów → pytać kafelkami 20 km).
  Adres znaleziony w pakiecie R `rgugik`. Arkusz NMT 1 m ≈ 37 MB tekstu, nieregularny, sąsiednie zachodzą.
  - NMT: 1 m EVRF2007 prawie w całym kraju (roczniki 2018–2026) — dla każdego godła najnowszy rok.
  - **NMPT 1 m EVRF2007 NIE jest krajowy** (ok. 52 tys. arkuszy wobec 152 tys. NMT). Koło Garwolina (sprawdzone) jest tylko
    NMPT 0,5 m EVRF2007 (2023, 2025) i 1 m w starym układzie wysokości KRON86 (2014). Kolejność: 1 m EVRF2007 → 0,5 m EVRF2007
    (uśrednić do 1 m) → KRON86 tylko gdy nic innego, z poprawką wysokości (do zmierzenia na styku).
  - Wolumen surowy: rząd 3–6 TB (szacunek) → wyłącznie arkusz po arkuszu z kasowaniem. Przy łączu 100 Mbit/s to kilka dni ciągłego
    pobierania; pobieranie grzecznie: jeden wątek, pauzy, wznawianie.
- **Procedura jednej paczki (komputer testowy, `~/paczki`, venv z numpy i Pillow):**
  1. `kod/arkusze.py E N praca/E…N…` — skorowidz → wybór arkuszy (EVRF2007 przed KRON86, najnowszy rok, .asc przed .xyz) → pobranie po jednym → kafle 1 km po 1 m.
     Arkusze 1 m mają środki komórek na pełnych metrach: przesunięcie pół komórki na zachód i północ daje 0,000 m różnicy wobec WCS.
     KRON86 → EVRF2007: jedna poprawka z zakładek gruntu (E660N440: +0,03 m z 11 764 komórek, IQR 0,12 m — słaba, do sprawdzenia).
  2. `kod/budynki_paczki.py E N praca/E…N… TERYT…` — bryły LoD1 z `opendata.geoportal.gov.pl/InneDane/Budynki3D/LOD1/2024/{woj}/{powiat}.zip`;
     powiaty z ULDK `GetCountyByXY` po siatce punktów paczki co 2,5 km (E660N440: 1403, 1417, 1407).
  3. `kod/paczka.py km praca/E…N…` → `.pak`. Kafle 1 m (3 GB na paczkę) można skasować po zbudowaniu.
- Publikacja paczek — osobna zgoda Maćka na konkretną wersję.

### Strona w układzie 2180 (Garwolin, 2026-10-07)

Decyzja Maćka: strona przechodzi na 2180, zaczynając od Garwolina. Układ mapy = EPSG:2180 minus rynek zaokrąglony do 4 m
(E0 679860, N0 451200), więc komórki miasta to komórki paczek 1:1. `?paczki` włącza zestaw `obszar-2880-2180-z`
(T i Copernicus przepróbkowany do siatki 2180, `przygotuj/na2180.py`) i pliki z przyrostkiem `-2180` (stacje, rtv, wektory);
warstwy miasta przychodzą tylko z paczek. Silnik liczy azymut w osiach siatki; strona pokazuje azymut geograficzny
(siatka + zbieżność południków, w rynku +2,058°), rysunek na mapie zostaje w osiach siatki. Charakterystyka anteny nadajnika
radia/TV dostaje azymut geograficzny ze zbieżnością w miejscu nadajnika (`rtv-2180.json`, pole `zbieznosc`, 0,79–3,27°).
GPS: `na2180(lat, lon)` minus E0/N0, tylko w telefonie.

Pomiar (`weryfikacja/porownaj-2180.mjs`, 9 punktów co 1,5 km, 1,5 i 10 m; sam wpływ układu = stary układ z paczkami
przepróbkowanymi): azymut geograficzny zgodny do 1,06° (zaokrąglenie), odległości stacji +21…61 m (stary układ zaniżał
skalę: −0,63% N–S, −0,21% W–E), komórkowe — nadwyżka strat mediana 0,38 dB, 95% 3,6 dB, inna ocena w 6,3% par; radio/TV
mediana 0,1 dB, inna ocena 0,4%. Przykład w rynku przy 10 m: Dęblin zyskuje 0,5–0,8 dB i ma 3 multipleksy z pewnym odbiorem,
tyle samo co Raszyn — remis rozstrzyga liczba multipleksów, więc pierwszy kierunek zmienia się z Raszyna (291°) na Dęblin (141°).
Ranking kierunków jest czuły na próg przy remisie — do osobnego przeglądu.

## 7. Poziomy przybliżenia (projekt 2026-10-07, krok 1 na E660N440 + E680N440)

Decyzja Maćka 2026-10-07 15:23: mapa wielopoziomowa — duża mapa Polski z nadajnikami, nakładka z cieniami od pewnego
przybliżenia, kilka poziomów dobieranych do przybliżenia. Podkład Polski własny (cudze kafelki mapy zdradzałyby, gdzie ktoś patrzy).
Kolejność: **krok 1** — poziomy na dwóch paczkach (pas 40 × 20 km, x 660–700 km, y 440–460 km) → Polska z własnym podkładem →
paczki kolejnych obszarów. Wyniki to nadal SYMULACJA.

### 7.1 Poziomy i progi

Zasada: **na ekranie zawsze ok. 360 × 360 punktów liczenia**, niezależnie od przybliżenia. Bok widoku W [m] → potrzebny krok
punktów W / 360. Poziom = najgrubsza siatka danych, której komórka jest nie większa niż ten krok; krok punktów = wielokrotność komórki
poziomu (k = ⌊W / 360 / komórka⌋, co najmniej 1), więc punkt liczenia zawsze trafia w środek bloku komórek, jak dziś.

| Poziom | Komórka danych | Bok widoku przy k = 1 | Zakres boku widoku | Co liczy | Podpis pod mapą |
|---|---|---|---|---|---|
| ulica | 4 m (paczka jak dziś) | 1,44 km | do 5,76 km (k 1–3) | grunt, budynki, drzewa | jak dziś |
| okolica | 16 m (warstwa 16 m) | 5,76 km | 5,76–36 km (k 1–6) | grunt, budynki i drzewa uśrednione do 16 m | „budynki i drzewa uproszczone do kratki 16 m” |
| powiat | 100 m (warstwa 100 m) | 36 km | 36–72 km (k 1–2) | **sam teren** — bez budynków i drzew | „tylko ukształtowanie terenu — bez budynków i drzew; w mieście będzie gorzej” |
| kraj | — | > 72 km | — | bez nakładki: podkład + punkty nadajników | „przybliż, żeby zobaczyć zasięg” |

Progi liczą się od boku widoku, nie od numeru przybliżenia; przejście ulica → okolica przy 5,76 km to dokładnie dzisiejsza
„cała mapa co 16 m”. W pasie 40 × 20 km widok poziomu powiat (36 km) wystaje poza dane: komórki bez danych zostają bez nakładki
(szare), a linia stanu mówi, ile procent widoku pokrywają paczki.

Wybór poziomu i okno liczy telefon. Serwer dostaje tylko nazwy paczek poziomu (patrz 7.3) — tak jak dziś: jakie paczki, nie jaki punkt.

### 7.2 Skąd dane na każdym poziomie

- **ulica** — bez zmian: warstwy 4 m z `E…N….pak`, teren poza oknem z T (30 m) / Copernicus.
- **okolica** — warstwy 16 m wyliczone **z paczki 4 m** (nie z arkuszy 1 m): blok 4 × 4 komórek →
  G = średnia, O i ZW = do zmierzenia (średnia albo maksimum bloku; wybiera pomiar w 7.5), BUD = udział budynków (0–100 %).
  Ten sam plik jest terenem w pasie (lepszy niż T 30 m); poza pasem — Copernicus jak dziś.
- **powiat** — warstwa 100 m z paczki 4 m: tylko G (średnia z 25 × 25 komórek). Budynków i drzew na tym poziomie świadomie nie ma:
  na 100 m dach uśredniony z ulicą to fałsz, a nie przybliżenie — stąd inny podpis.
- **nadajniki radia/TV** — punkty z krajowego pliku (`rtv-2180.json`, 119 grup wokół Garwolina; docelowo ok. 220 w Polsce) na każdym
  poziomie, także „kraj”. Trójkąt = miejsce nadajnika; podpis po dotknięciu: stacja, programy, wysokość anteny. Plik jest jeden dla
  wszystkich, więc nic nie zdradza.
- **stacje komórkowe** — na poziomach ulica i okolica jak dziś (z promieniem przycięcia); na poziomie powiat liczone na siatce 100 m,
  każda w swoim promieniu (do sprawdzenia czasu: w 36 km mieści się ok. 150 stacji).

### 7.3 Pliki i waga

Warstwy uproszczone to **osobne pliki obok paczki**, w tym samym formacie PAK1: `E660N440-16.pak`, `E660N440-100.pak`
(jeden blok na warstwę dla całej paczki: 1250 × 1250 komórek po 16 m, 200 × 200 po 100 m; nagłówek jak w §3, `komorka_m` 16 / 100,
`kafel_m` 20 000). Dlaczego osobno, a nie w środku `.pak`: widok poziomu powiat obejmuje do 3 × 3 paczek — z warstwą w środku paczki
telefon pobrałby 9 × 25–30 MB po to, żeby użyć 0,2% tych bajtów. Zakres bajtów (początek pliku) odpada z §5. Prywatność bez zmian:
zapytanie mówi „paczka E660N440, poziom 16 m”, tak samo dla każdego, kto ogląda którąkolwiek okolicę w tych 20 km.

Waga (szacunek, do potwierdzenia przy budowie): 16 m ≈ 1/16 rastra 4 m z gorszą kompresją → **ok. 2–3 MB na paczkę**;
100 m ≈ **50–100 kB na paczkę**, cała Polska ok. 50–80 MB — przy kroku „Polska” warstwę 100 m może być rozsądniej zebrać w większe
pliki (np. 100 × 100 km). Pierwsze wejście na poziomie okolica: 1–4 pliki 16 m = do ok. 12 MB zamiast 50–120 MB paczek 4 m.

Liczenie: `przygotuj/paczka.py poziomy PLIK.pak` (z gotowej paczki 4 m, bez arkuszy) — na komputerze testowym, `nice`/`ionice`,
jak reszta paczek.

### 7.4 Strona

- Widok = kwadrat w EPSG:2180 (środek + bok W). Przesuwanie palcem, przybliżanie dwoma palcami / kółkiem; po puszczeniu → poziom i okno
  → pobranie brakujących plików poziomu → liczenie 360 × 360. Podczas liczenia skalowany obraz poprzedniego wyniku (bez pustego ekranu).
- Punkt (dotknięcie) jak dziś: kierunki i tabele liczą się zawsze na danych najdokładniejszego poziomu, który jest w pamięci
  (paczka 4 m pobierana dopiero przy dotknięciu albo przy poziomie ulica).
- Warstwy miasta dla silnika: okno poziomu = widok + margines 3 km (stacje do 3 km za krawędzią, jak `ZASIEG_MAPY`), sklejone z plików
  poziomu przez `okno()` z `silnik/paczka.js` — kod jest już ogólny (komórka i kafel z nagłówka).
- Podkład w kroku 1: cieniowanie terenu z warstwy 100/16 m + wektory, które już są (`mapa-wektor-2180`). Własny podkład Polski — krok 2.

**Stan kroku 1 (2026-10-07, sprawdzone w przeglądarce na Macu, nie na telefonie):** osobna strona `telefon/poziomy.html`
+ wątek `telefon/poziomy-praca.js`; `punkt.html` bez zmian. Różnice wobec planu wyżej:
- punkty co `max(m, bok/360)` m (zaokrąglone do metra), nie `m·k` — zawsze ok. 360 × 360, przy k z dzielenia całkowitego bywało do 720;
- okno sceny = widok + max(1 km, ¼ boku), nie + 3 km; powyżej 1600 komórek na bok kratka uśredniana f × f;
- nakładka tylko w pasie paczek (poza nim teren nieznany — próbnik daje najbliższą komórkę pasa, smugi przycięte);
- ~~dotknięcie: tylko informacja o nadajniku radia/TV (kierunki i tabele zostają w `punkt.html`)~~ — **nieaktualne**, od wieczora
  2026-10-07 dotknięcie ustawia punkt z kierunkami (§9); podkład = samo cieniowanie (100 m dla pasa, warstwa poziomu dla widoku), bez wektorów;
- radio/TV: 3 grupy najmocniejsze w środku widoku; komórkowe: ~~wszystkie stacje rodzaju w widoku + 3 km, `dane/stacje-pas.json`
  (73 stacje)~~ — **nieaktualne**: stacje całej Polski i domyślnie 3 najbliższe punktu (§9).
Zmierzone w przeglądarce (Mac, 4G, 1,5 m): ulica 14 stacji 1,9 s (pliki 4 m 53 MB), okolica 18 stacji 1,2 s (4,7 MB),
powiat 58 stacji 2,9 s (0,1 MB); powyżej 72 km bez nakładki, same nadajniki.

**Podkład orientacyjny (2026-10-07, prośba Maćka: „cały czas nakładki tego, na co patrzę”):** zawsze nad nakładką zasięgu,
na każdym poziomie — drogi (5 klas BDOT10k, drobniejsze pojawiają się z przybliżeniem), tory, rzeki, wody, nazwy miejscowości
(ranga: miasto → >1000 mieszk. → >200 → wieś → część wsi), nazwy ulic od ok. 2,5 m/piksel, numery domów od ok. 0,9 m/piksel;
wyszukiwarka miejscowości i adresów oraz przycisk „gdzie jestem” (GPS tylko przez HTTPS) — wszystko liczone w telefonie.
Pliki z `przygotuj/mapa_pasa.py` (BDOT10k + PRG 9 powiatów, pas + 3 km): `dane/mapa-pas.json.gz` **2,3 MB** (linie pełne co ≥ 2 m
i ogólne co ≥ 30 m powyżej 25 m/piksel), `dane/adresy-pas.json.gz` **0,22 MB** (25 811 adresów, wczytywane przy pierwszym
wyszukiwaniu). Linie pocięte na kwadraty 2 km, rysowane tylko w widoku. Dla Polski (krok 2) ten sam podział trzeba będzie zrobić
per paczka 20 km, a nie jednym plikiem.

### 7.5 Pomiary przed uznaniem poziomu

1. **okolica vs ulica**: mapa 4G i radio/TV w oknie Garwolina (5,76 km, punkty co 16 m) liczona na warstwie 16 m i na 4 m —
   ile komórek różni się o > 1 / > 3 dB i ile zmienia jasność o > 10%; osobno O/ZW jako średnia i maksimum bloku. Próg jak przy
   kroku gruntu (§4): > 3 dB w ≈ 0% komórek.
2. **powiat vs okolica**: te same miary dla 100 m (sam teren) wobec 16 m — tu różnica będzie duża w mieście i to jest treść podpisu,
   nie błąd; liczba trafia do podpisu („w mieście będzie gorzej o …”) dopiero po pomiarze.
3. Czas liczenia 360 × 360 na każdym poziomie (Node; telefon niezmierzony, dopóki strona nie jest osiągalna z telefonu).
4. Waga plików 16 / 100 m z dwóch paczek.

### 7.6 Wyniki pomiaru (2026-10-07, `weryfikacja/poziomy.mjs`, okno Garwolina 5,76 km, 360 × 360 punktów co 16 m, 4G: 18 stacji)

Pliki (z gotowych paczek 4 m, komputer testowy, 8–10 s na dwie paczki): **16 m — 2,6 MB (E660N440, las) i 2,1 MB (E680N440)**;
**100 m — 42 i 44 kB**. Kontrola: G 16 m = średnia 4 × 4 z paczki 4 m, różnica ≤ 0,025 m (kwantyzacja). O/ZW jako maksimum bloku: 4,0 / 3,4 MB.

Różnica wobec liczenia na warstwie 4 m (te same punkty, ten sam teren dalej; „> 3 dB” = odsetek punktów, „jasność” = zmiana jasności o > 10%):

| | antena 1,5 m: 4G > 3 dB | jasność | antena 10 m: 4G > 3 dB | jasność | DVB-T > 3 dB (1,5 / 10 m) | FM > 3 dB (1,5 / 10 m) |
|---|---|---|---|---|---|---|
| okolica 16 m, O/ZW średnia | 38–40% (mediana −0,9 dB, 5%: −13…−16 dB) | 24–29% | 12% (5%: −5…−6,5 dB) | 5–7% | 2,6 / 5,2% | 1,4 / 2,2% |
| okolica 16 m, O/ZW maksimum | 50% (mediana +2,5 dB) | 38–42% | — | — | 2,4% / — | 1,3% / — |
| powiat 100 m, sam teren | 54–55% (mediana −4 dB) | 42–45% | 17% | 9–10% | 2,8 / 12% | 1,4 / 6% |

Wnioski:
- **O/ZW w 16 m = średnia bloku** (maksimum jest gorsze: zawyża straty o 2,5 dB w połowie punktów). Ustawione jako domyślne w `paczka.py poziomy`.
- **Próg z 7.5 (> 3 dB w ≈ 0% punktów) NIE jest spełniony.** Na 16 m znikają przeszkody tuż przy odbiorniku: antena 1,5 m przy ścianie
  „widzi” uśredniony dach — mapa jest optymistyczna (do 13–16 dB w 5% punktów). Przy antenie 10 m zgodność jest dużo lepsza.
  Poziom okolica to więc **przegląd**, nie wynik dla konkretnego domu; podpis musi to mówić, a kierunki i tabele w punkcie liczą się
  zawsze na 4 m (7.4).
- Radio/TV są mało czułe na warstwę miasta przy 1,5 m (P.1546 liczy pole z wysokości efektywnej nadajnika; warstwa miasta wchodzi tylko
  przez zasłonę przy odbiorniku); przy 10 m widać różnicę (DVB-T 5% / 12% punktów > 3 dB dla 16 / 100 m).
- Czas w Node (jeden wątek, 4G): 4 m 14 s, 16 m 5 s, 100 m 2,4 s dla tych samych 130 tys. punktów — tu zysk poziomu to dane
  (2–4,5 MB zamiast 53 MB), nie czas: czas zależy od liczby punktów i stacji.

## 8. Krok 2 — Polska z własnym podkładem i wszystkimi nadajnikami (projekt 2026-10-07, przed kodem)

Cel: strona `poziomy.html` otwiera się na całej Polsce; widać podkład (granice, drogi, rzeki, miejscowości) i **wszystkie**
nadajniki radia/TV; nakładka zasięgu pojawia się od poziomu „powiat” (bok widoku ≤ 72 km, §7.1) — tam, gdzie są dane.
Nic z tego nie jest jeszcze zbudowane. Wyniki to SYMULACJA. Bez publikacji (osobna zgoda na konkretną wersję).

### 8.1 Zasada podziału — dwa rodzaje plików

| Plik | Dla kogo | Zawartość | Kiedy pobierany |
|---|---|---|---|
| `kraj/podklad.json.gz` | wszyscy ten sam | granice, drogi główne, duże rzeki i wody, miasta — uproszczone do widoku > 36 km | przy otwarciu strony |
| `kraj/nadajniki.json.gz` | wszyscy ten sam | wszystkie nadajniki FM / DAB+ / DVB-T z UKE, heff w 36 sektorach | przy otwarciu strony |
| `kraj/teren-100.pak` (lub 100 × 100 km, §8.5) | wszyscy ten sam albo po nazwie | cieniowanie i teren 100 m | przy otwarciu / przy przesunięciu |
| `paczki/v…/E…N…-mapa.json.gz` | po nazwie paczki | podkład szczegółowy paczki 20 km: wszystkie jezdnie, tory, rzeki, wody, nazwy ulic i miejscowości | od boku widoku ≤ 36 km |
| `paczki/v…/E…N…-adresy.json.gz` | po nazwie paczki | adresy do wyszukiwarki i numerów domów | przy wyszukiwaniu / przy numerach domów |

Ta sama reguła prywatności co w §5: pliki krajowe są jednakowe dla wszystkich (nic nie mówią), pliki paczek mówią tylko „ktoś
ogląda te 20 km”. Wyszukiwarka adresów działa w telefonie — **wpisany adres nie wychodzi**. Problem: szukanie adresu w innej części
Polski wymaga wiedzy, w której paczce on leży, zanim się pobierze jej adresy. Rozwiązanie: krajowy **spis miejscowości**
(nazwa, gmina, środek, paczki, w których leży jej obszar) w `kraj/podklad.json.gz` — wyszukiwarka najpierw znajduje miejscowość
lokalnie, potem pobiera adresy jej paczki (1–4), jak przy oglądaniu. Serwer dowiaduje się tylko tego, co przy przesunięciu mapy.

Pliki paczek 20 km, a nie jeden plik pasa (jak `mapa-pas.json.gz`): ten sam podział co rastry, ta sama nazwa, ta sama wersja
w ścieżce; linia przecinająca granicę paczki jest cięta na granicy (krawędzie paczek się stykają, nie zachodzą), wewnątrz paczki
zostaje podział na kwadraty 2 km z kroku 1 (rysowanie tylko widocznych).

### 8.2 Co na którym poziomie (podkład)

| Bok widoku | Podkład | Skąd |
|---|---|---|
| > 72 km (kraj) | granica państwa i województw, autostrady, ekspresowe, drogi krajowe, tory główne, rzeki główne, jeziora > 1 km², miasta (od największych, gęstość jak w kroku 1) | `kraj/podklad` |
| 36–72 km (powiat) | + granice powiatów, drogi wojewódzkie, miejscowości > 1000 mieszk. | `kraj/podklad` |
| ≤ 36 km (okolica, ulica) | podkład paczki jak w kroku 1 (5 klas dróg, ulice, numery domów od 0,9 m/piksel) | `E…N…-mapa`, `-adresy` |

Granica 36 km jest po to, żeby przy widoku powiatu (do 3 × 3 paczek) nie pobierać 9 plików szczegółowych — tak samo jak dla
rastrów w §7.3.

### 8.3 Źródła (GUGiK, dane otwarte, bezpłatnie — te same co w kroku 1)

- **BDOT10k** per powiat (`opendata.geoportal.gov.pl/bdot10k/schemat2021/{woj}/{TERYT}_GML.zip`) — jezdnie z klasą drogi, tory, rzeki,
  wody, miejscowości (nazwa, rodzaj, liczba mieszkańców). Polska ma 380 powiatów (314 ziemskich + 66 miast na prawach powiatu).
  Waga zmierzona na 9 powiatach pasa: 25–68 MB na zip, średnio 38 MB → **cała Polska ok. 14 GB pobrań** (szacunek), arkusz po arkuszu
  z kasowaniem jak NMT.
- **PRG** — granice: `prg/granice/00_jednostki_administracyjne.zip` (jeden plik krajowy, **377 MB**, nagłówek sprawdzony 2026-10-07);
  punkty adresowe i ulice: per powiat (`prg/adresy/PunktyAdresowe/{woj}/{TERYT}.zip`, w pasie 1,5–5,7 MB) albo jednym plikiem
  `prg/adresy/PunktyAdresowe/POLSKA.zip` (**564 MB**).
- Wybór dróg na poziomach kraj / powiat — **sprawdzone 2026-10-07 na `1403_GML.zip`:** jezdnia `OT_SKJZ_L` ma `kategoriaZarzadzania`
  (krajowa / wojewódzka / powiatowa / gminna / wewnętrzna, wypełnione w 100% obiektów) i `numerDrogi` (np. `S17`, w 32% — drogi publiczne).
  Poziom kraj: krajowe (w tym ekspresowe i autostrady po `klasaDrogi`); powiat: + wojewódzkie. Numer drogi jako podpis przy linii.
- Bez OSM i bez cudzych kafelków mapy (OSM jest w `dane/osm`, ale ODbL wymaga udostępniania pochodnych na tej samej licencji —
  niepotrzebna komplikacja, skoro BDOT10k jest pełniejszy).

### 8.4 Nadajniki radia/TV dla całego kraju

**Źródło jest już krajowe.** Pliki UKE w `dane/uke-2026` (stan 2026-09-18) to wykaz całego kraju; `rtv.py` tylko przycina je do 100/120 km
od rynku. Zmierzone 2026-10-07: FM 1488 wierszy, DAB+ 103, DVB-T 663; tymczasowe 42 / 13 / 8; **991 różnych położeń**. Po odrzuceniu
tymczasowych, wygasłych i bez ERP / wysokości anteny zostanie ok. 2100–2200 programów w ok. 900–990 grupach (szacunek, `rtv.py` policzy).

Co trzeba zmienić:
1. `rtv.py` bez promienia (cała Polska), współrzędne od razu w EPSG:2180 (bez rynku), grupy = to samo położenie + ta sama wysokość anteny
   (jak w `fm.mjs`).
2. **heff w 36 sektorach co 10°**, nie jedna liczba w stronę rynku: dziś `fm.mjs` liczy heff tylko w kierunku Garwolina (średni teren
   3–15 km od masztu w stronę odbiornika, P.1546 §3). Dla całego kraju odbiornik może być w każdym kierunku → 36 wartości na grupę,
   strona bierze sektor kierunku do odbiornika (interpolacja liniowa między sąsiednimi). Teren do heff: koło o promieniu 15 km wokół
   każdego masztu. Źródło: Copernicus GLO-30 (już używany; to model **pokrycia**, z lasem i budynkami — tak liczy dziś `fm.mjs` poza 11,8 km,
   więc bez zmiany metody), docelowo NMT 30/100 m z paczek, gdy będą. Mozaika Copernicus dla Polski + pas 15 km za granicą:
   ok. 6 × 10 kafli po 1° (dziś leży 10). Liczenie: 990 grup × 36 profili × 120 punktów — sekundy.
3. Waga (z pomiaru: 119 grup / 198 programów = 70 kB, 13 kB po kompresji): ok. 11 × więcej programów + 36 liczb heff na grupę →
   **ok. 0,2–0,3 MB po kompresji** (szacunek). Jeden plik dla wszystkich.
4. **Nadajniki zagraniczne (Niemcy, Czechy, Słowacja, Ukraina, Białoruś, Litwa, Rosja) nie są w wykazie UKE.** Przy granicy mapa pokaże
   tylko polskie stacje, a cudze potrafią tam zagłuszać albo być lepsze. Tego krok 2 nie rozwiązuje — podpis w pasie 30 km od granicy:
   „tylko polskie nadajniki”. (Rejestr międzynarodowy ITU — osobny temat, nie teraz.)
5. Na stronie: trójkąty wszystkich grup na każdym poziomie; przy 990 punktach na widoku kraju — od najsilniejszego ERP, z odstępem
   w pikselach (jak nazwy miejscowości w kroku 1), reszta pojawia się z przybliżeniem. Nakładka radia/TV liczy jak w kroku 1:
   3 grupy najmocniejsze w środku widoku, ale wybór spośród nadajników do 150 km od środka (nie z pliku 119 grup).
   **W kodzie inaczej:** wątek liczy pole wszystkich grup rodzaju w punkcie (`fmZPunktu`, bez promienia) i bierze 3 najmocniejsze —
   w punkcie, gdy jest ustawiony, inaczej w środku widoku (§9).

Stacje komórkowe: rejestr UKE (`dane/uke/*.xlsx`, stan 2026-09-25) też jest krajowy; trafiają do paczki z marginesem 10 km (§3),
bez zmian projektu. Na poziomie kraj nie są rysowane (dziesiątki tysięcy punktów, nic nie mówią w tej skali).

**Stan 2026-10-07 (wieczór, zrobione).** `przygotuj/rtv_kraj.py` (zirael-test) → `kraj/nadajniki.json.gz` **188 kB**
(1041 kB bez kompresji): wszystkie grupy z wykazu UKE 2026-09-18, heff w 36 sektorach co 10° w osiach siatki 2180, grunt pod
masztem z NMT 100 m (poza NMT — `hter` z UKE). 195 grup ma sektor z mniej niż połową punktów terenu (granica, morze), 838 sektorów
bez terenu → silnik bierze wtedy wysokość anteny. Kontrola wobec dotychczasowego `rtv-2180.json` (118 grup ≥ 15 km od rynku,
sektor w stronę rynku): różnica mediana +0,3 m, |d| 50% 2,6 m, 90% 12 m, maks. 48,6 m (Mielnik) — największe różnice to lepszy
grunt, zgodny z `hter` UKE (Mielnik: stare 118, nowe 158, UKE 164). Silnik: `heffKierunku` w `silnik/p1546.js` (interpolacja
między sektorami; liczba zamiast tablicy działa jak dotąd), azymut anteny = azymut siatki + zbieżność; wynik pasa
(`weryfikacja/poziomy.mjs`) identyczny jak przed zmianą.

**Strona `telefon/poziomy.html` na danych krajowych (2026-10-07, sprawdzone w przeglądarce na Macu, na telefonie nie):**
- poziom powiat w całej Polsce z `kraj/teren-100/` (kwadraty 100 km, `warstwyPoziomu` z `poziom.bok`); ulica i okolica tylko
  w pasie paczek — poza pasem strona przechodzi na powiat z podpisem, że tu budynków i drzew jeszcze nie ma w danych (bez odsyłania do Garwolina, §9);
- cieniowanie kraju z `kraj/teren-1000.pak`; nadajniki z `kraj/nadajniki.json.gz`, rysowane od najsilniejszego (ERP),
  słabszy bliżej niż 16 px od narysowanego pomijany (dotknąć da się tylko narysowane);
- podpis „tylko polskie nadajniki” w legendzie, gdy w widoku + 30 km jest komórka poza NMT (zagranica albo morze);
- teren wątku: T wokół rynku → NMT 100 m kraju (wczytane kwadraty, okno + 20 km) → 0; warstwa -100 paczek nieużywana;
- `#E,N,km` w adresie ustawia widok startowy (część po `#` nie wychodzi z przeglądarki) — do sprawdzania innych miejsc;
- zmierzone: Kraków 60 km TV 7,4 s przy pierwszym pobraniu kwadratów (3,0 MB), Słubice 50 km FM 0,7 s, pas 40 km 4G 58 stacji 2,4 s.
Brakowało wtedy: podkład wektorowy i wyszukiwarka poza pasem — zrobione (§8.6, stan wieczorny); stacje komórkowe poza pasem — zrobione (§9).

### 8.5 Teren i cieniowanie kraju, nakładka poza paczkami

Dziś są dwie paczki (pas 40 × 20 km). Paczki całej Polski to ok. 6 dni liczenia na komputerze testowym (§4) — długo przed tym
strona ma wyglądać jak mapa Polski. Dlatego:

- **Cieniowanie poza paczkami** z krajowego terenu 100 m. Kandydaci: (a) Copernicus GLO-30 uśredniony do 100 m — jest, ale to model
  pokrycia (lasy wyglądają jak wzgórza o 20–30 m); (b) **NMT 100 m GUGiK** — **istnieje, sprawdzone 2026-10-07:** 16 plików wojewódzkich
  `opendata.geoportal.gov.pl/NumDaneWys/NMT_100/ASCII_XYZ/{województwo}_grid100.zip` (mazowieckie 15,8 MB; adres z pakietu R `rgugik`,
  `pointDTM100_download`), punkty XYZ co 100 m — model **terenu**, bez lasu i budynków; (c) uśrednianie arkuszy NMT 1 m przy liczeniu paczek — dopiero razem z paczkami.
  Wybór: **(b)**; (a) odpada. Rozmiar: 7000 × 6600 komórek 100 m, int16 cm z kompresją jak w paczkach →
  ok. 20–40 MB dla kraju (szacunek z 42–44 kB na paczkę × 850) — **za dużo na jedno pobranie przy otwarciu**. Więc dwa pliki:
  `kraj/teren-1000.pak` (1 km, ok. 0,3–0,5 MB, cieniowanie widoku kraju) i `teren-100` w plikach 100 × 100 km (25 paczek, ok. 1–1,5 MB,
  pobierane od poziomu powiat). Plik 100 × 100 km zdradza mniej niż paczka 20 km.
- **Nakładka zasięgu na poziomie powiat poza paczkami** — do decyzji (8.7, pytanie 1). Teren 100 m wystarcza silnikowi na tym poziomie
  (sam teren, §7.1), więc zasięg „sam teren” dałoby się pokazać od razu w całej Polsce. NMT_100 to ten sam rodzaj danych co warstwa 100 m z paczek
  (sam teren), różnić się może sposób uśrednienia (punkt co 100 m vs średnia 25 × 25 komórek) — zmierzyć na E660N440 + E680N440 przed włączeniem.
  Poziomy okolica i ulica — tylko tam, gdzie są paczki; poza nimi szara kratka i linia stanu „brak szczegółowych danych dla tego obszaru”.
- Mapa pokrycia paczek (które są gotowe) w `kraj/podklad.json.gz` — strona wie z góry, gdzie przybliżenie da szczegóły,
  i nie pyta serwera o paczki, których nie ma (takie zapytanie też byłoby śladem).

**Stan 2026-10-07 (komputer testowy, `przygotuj/teren_kraj.py`, 32 s, 3,5 GB RAM):** 16 plików NMT_100 = 31 230 165 punktów
(= 312 tys. km², cała Polska; wysokości −103 m — odkrywka Bełchatów — do 2355 m), bez zakładek między województwami.
Wynik: **`teren-100/` 47 plików 100 × 100 km, razem 28,9 MB, średnio 615 kB** (G co 10 cm — co 5 cm nie mieści Tatr w int16);
**`teren-1000.pak` 435 kB** (800 × 800 km od E 100 / N 100 km); `teren100.npy` (256 MB, tylko na komputerze testowym, do heff).
Siatka: komórka 100 m = średnia 4 punktów w rogach, czyli te same komórki co `-100.pak` paczek.
Pomiar zgodności z warstwą 100 m paczek (`teren_kraj.py porownaj`): E660N440 mediana +0,22 m, 95% |d| < 0,85 m, > 1 m w 3,5% komórek;
E680N440 +0,18 m, 95% < 0,82 m, > 1 m w 2,8% (stałe +0,2 m — hipoteza: inny układ wysokości albo rocznik NMT_100, niesprawdzone).
Wpływ na mapę (`weryfikacja/poziomy.mjs`, `BAZA100` = pliki 20 km wycięte z kraju, `teren_kraj.py wytnij`): poziom powiat wobec 4 m
przy 1,5 m — 4G > 3 dB 54,1–55,7% (paczki 54,1–55,4%), radio/TV bez zmian; przy 10 m — 4G identycznie (16,6–17,2%), FM/DVB-T
+0,06–0,2 pkt. **Wniosek: NMT_100 zastępuje warstwę 100 m paczek bez straty — nakładka „powiat” w całej Polsce z danych krajowych**
(decyzja Maćka). Pliki `-100.pak` paczek stają się zbędne — strona i wątek już czytają poziom 100 m wyłącznie z `teren-100/` (`KRAJ100`).

### 8.6 Waga i liczenie

| Plik | Szacunek | Podstawa |
|---|---|---|
| `kraj/podklad.json.gz` | 1–3 MB | warstwy ogólne pasa (drogi klasy ≥ zbiorczej, tolerancja 30 m): 107 kB / 1196 km² → kraj przy tej samej szczegółowości ok. 28 MB — za dużo; poziom kraj potrzebuje dróg ≥ głównej i tolerancji 100–300 m, czyli ok. 1/10. Do zmierzenia |
| `kraj/nadajniki.json.gz` | 0,2–0,3 MB | §8.4 |
| `kraj/teren-1000.pak` | 0,3–0,5 MB | §8.5 |
| pierwsze otwarcie strony razem | ok. 2–4 MB | |
| `E…N…-mapa.json.gz` | ok. 0,8 MB wieś, 2–4 MB miasto | pas: 2,3 MB / 1196 km² = 1,9 kB/km² (wieś i Garwolin); miasto — hipoteza ×2–5, zmierzyć na Warszawie (`gugik-wektor-warszawa`) |
| `E…N…-adresy.json.gz` | ok. 0,1 MB wieś | pas: 0,22 MB / 25 811 adresów ≈ 8,5 B/adres |
| cała Polska na serwerze (podkład) | ok. 0,7–1 GB | 850 paczek |

Liczenie: wyłącznie komputer testowy (`zirael-test`, `nice`/`ionice`, blokada `bin/srodowisko-testowe.sh`, nocą), nie Mac i nie Zirael.
Kolejność: najpierw pliki krajowe (podkład, nadajniki, teren 1 km — małe, jedno pobranie PRG granic + BDOT per powiat tylko dla dróg
głównych), potem `-mapa`/`-adresy` dla paczek, które już mają rastry. BDOT per powiat potrzebny jest raz do obu: z jednego przebiegu
powiatu powstają wkład do `kraj/podklad` i podkład wszystkich paczek, które powiat przecina (powiat jest w kilku paczkach, paczka
w kilku powiatach — skrypt zbiera wkład per paczka i składa paczkę, gdy przyszły wszystkie jej powiaty; powiaty paczki z ULDK jak w §6).

**Stan 2026-10-07 (wieczór, zrobione) — podkład całej Polski.** Pobrane na komputer testowy: BDOT10k i PRG adresy wszystkich
380 powiatów (`~/paczki/dane/gugik/`, 16 GB + 636 MB, `pobierz.sh`), PRG granice (377 MB). Skrypt `przygotuj/mapa_kraj.py`
(czytniki w `przygotuj/gugik.py`, bez GDAL): etap `powiaty` (ok. 10 s na powiat, 6 procesów, całość ok. 10 min) tnie linie na granicach
paczek i zapisuje wkłady pośrednie (JSON gzip, 364 MB); etap `zloz` (50 s) składa paczki i pliki krajowe. Odcinki BDOT (dzielone na
każdym skrzyżowaniu) są w pliku kraju sklejane w ciągi po numerze drogi / linii / nazwie rzeki, dopiero potem upraszczane do 150 m —
bez tego drogi kraju to 98 tys. dwupunktowych kawałków. Poprawiony błąd kroku 1: klasa „autostrada” (w `mapa_pasa.py` nieobjęta).

| Plik | Szacunek §8.6 | Pomiar |
|---|---|---|
| `kraj/podklad.json.gz` (granice PRG, drogi krajowe i wojewódzkie, tory z numerem linii, rzeki ≥ 50 km, wody > 1 km², miejscowości ≥ 1000 mieszk. i miasta) | 1–3 MB | **1,40 MB** |
| `kraj/miejscowosci.json.gz` (spis do wyszukiwarki: 99 457 miejscowości, gmina, powiat, paczki z adresami) — wczytywany przy pierwszym wyszukiwaniu | — | **1,95 MB** |
| pierwsze otwarcie strony (podkład + nadajniki + teren 1 km) | 2–4 MB | **2,0 MB** |
| `E…N…-mapa.json.gz`, 939 paczek | 0,8 MB wieś, 2–4 MB miasto | mediana **217 kB**, 90% ≤ 430 kB, Warszawa E620N480 **1,06 MB**, Kraków E560N220 0,83 MB |
| `E…N…-adresy.json.gz`, 860 paczek, 8,6 mln adresów | 0,1 MB wieś | mediana **59 kB**, Warszawa 0,77 MB |
| cała Polska (podkład + adresy) | 0,7–1 GB | **291 MB** |

Paczki pasa ważą 0,56 MB wobec 2,3 MB `mapa-pas` z kroku 1; liczba obiektów odpowiada polu (800 vs 1196 km²: jezdnie 20,6 vs 29,0 tys.,
ulice 2,3 vs 2,7 tys.) — przyczyny różnicy wagi na obiekt nie rozłożyłem.

**Strona** (`telefon/poziomy.html`): widok > 36 km — podkład kraju (granice powiatów do 300 km, województwa i państwo zawsze); widok
≤ 36 km — `-mapa` paczek w widoku (wczytywane w tle, przerysowanie po wczytaniu); numery domów z `-adresy` paczek w widoku poniżej
0,9 m/px. Wyszukiwarka: spis kraju lokalnie; adres — paczki (najwyżej 4) miejscowości wymienionej w zapytaniu, bez miejscowości —
paczka środka widoku. `mapa-pas`/`adresy-pas` strona już nie czyta, a `telefon/zloz.sh` ich nie kopiuje (§9). Sprawdzone w przeglądarce na Macu (konsola bez błędów): Warszawa
30 km i 600 m (ulice, numery), cała Polska, „Floriańska 1 Kraków” (znacznik przy Rynku), „Sejny” (podpis przy granicy), pas Garwolina
(okolica 16 m, 6,8 s). Na telefonie niezmierzone. Liczone w dzień (zgoda Maćka na zakres i pobranie 2026-10-07), nie nocą jak w §8.6.

### 8.7 Pomiary przed uznaniem kroku 2

1. Waga `kraj/podklad.json.gz` przy dwóch tolerancjach; czas wczytania i rysowania widoku całej Polski w przeglądarce (Mac).
2. ~~Atrybuty `OT_SKJZ_L`~~ — sprawdzone: są `kategoriaZarzadzania` i `numerDrogi` (8.3).
3. Waga `-mapa` dla paczki miejskiej (Warszawa) — sprawdzenie hipotezy ×2–5.
4. heff 36 sektorów vs dzisiejsze heff w stronę Garwolina dla 119 grup: sektor w kierunku rynku musi dać tę samą liczbę ± zaokrąglenie
   interpolacji (kontrola, że nowa metoda nie zmienia wyników kroku 1).
5. Teren 100 m z NMT_100 vs 100 m z paczek na dwóch paczkach (różnica wysokości; jeśli nakładka powiat poza paczkami — pytanie 1 — także miary jak §7.6).
6. Liczba zapytań do serwera przy przesunięciu przez całą Polskę — tylko nazwy plików z 8.1, nic z punktem.

**Decyzje Maćka 2026-10-07 ~18:30:** pobranie NMT_100 na komputer testowy — tak; nakładka „sam teren” (powiat) w **całej Polsce**
z NMT_100 — tak (po pomiarze 5); podpis „tylko polskie nadajniki” przy granicy — tak.

Pytania do Maćka (rozstrzygnięte, zostawione dla historii):
1. Nakładka „sam teren” na poziomie powiat w całej Polsce (z terenu krajowego), zanim policzą się paczki — czy tylko w paczkach? (blokuje 8.5, punkt 2)
2. Podpis przy granicy „tylko polskie nadajniki” — wystarczy na teraz? (blokuje nic; domyślnie tak)

## 9. Stan strony `poziomy.html` (2026-10-07, noc) — co jest w kodzie

Ta sekcja opisuje kod, nie plan; gdzie wyżej jest inaczej, rozstrzyga ona. Sprawdzone w przeglądarce na Macu (tryb telefonu),
**na prawdziwym telefonie niezmierzone**. Pliki: `telefon/poziomy.html`, `telefon/poziomy-praca.js`, `przygotuj/stacje_kraj.py`, `telefon/zloz.sh`.

### 9.1 Punkt i karta (przeniesione z `punkt.html`)

- Dotknięcie mapy, wynik wyszukiwarki i GPS ustawiają **punkt**. Karta: kompas i azymut geograficzny, ułożenie anteny, siła sygnału
  z radą, kanały / bloki / 6 najmocniejszych stacji FM, „od ilu metrów” (radio/TV, 2–30 m), „jak namierzyć na dachu” (stacja blisko,
  najwyższy budynek na linii, ulica w tę stronę, kompas), tabele stacji komórkowych i programów radia/TV.
- Scena punktu w wątku: **ulica 4 m ± 1,5 km** z budynkami i drzewami, gdy punkt leży w pasie paczek; poza pasem sam teren
  (NMT 100 m kraju). Karta i linia stanu mówią, która to scena; przy granicy (w 30 km komórka poza NMT) karta dopisuje,
  że liczone są tylko polskie stacje i teren.
- Azymut geograficzny = azymut siatki 2180 + **zbieżność południków w punkcie** (wzór Gaussa-Krügera), nie stała Garwolina.
- Suwak wysokości 1,5–40 m, przycisk „antena na dachu” (dach + 2 m, z warstwy BUD/O w pasie). Telewizja przy antenie < 10 m
  podnosi suwak do 10 m i liczy punkt od nowa.
- Nowy punkt od razu czyści kartę i tabele („liczę kierunki…”); wynik starego punktu nie trafia do nowej karty.

### 9.2 Stacje komórkowe całej Polski

- `przygotuj/stacje_kraj.py` → `dane/kraj/stacje.json.gz` (**0,41 MB**, zapis kolumnowy: słowniki operatorów i pasm,
  `[x, y, h_ant|null, [operatorzy], [pasma], adres]` w układzie strony). Źródło: rejestr UKE `dane/uke/*.xlsx` (stan 2026-09-25),
  22 114 położeń → **20 334 stacje** po sklejeniu punktów bliżej niż 60 m (rejestr podaje pełne sekundy; ten sam maszt różnych
  operatorów bywa zgłoszony 1–2″ obok).
- Wysokość anteny znana tylko dla **22 stacji** (z `stacje-pas.json`, pas Garwolina); reszta — założenie 35 m, co mówi legenda i tabela (gwiazdka).
- Na mapie: rodzaje 4G i 5G; **każda grupa pasm ma osobne światło w swoim kolorze** (700–900 / 1800 / 2100–2600 / 3600 MHz,
  kolory jak w `punkt.html`), przełączniki pasm w zakładce Sygnał (widać tylko pasma obecne w liczeniu). Geometria drogi fali
  liczy się raz na stację, kolejne częstotliwości są tanie (3 pasma 1,3–1,4 s wobec 1,2 s dla jednego, pas 16 m, 18 stacji).
- **Wybór stacji do światła:** domyślnie 3 najbliższe punktu (decyzja Maćka 2026-10-07, jak `punkt.html`); do wyboru 6 / 12 / 24 /
  „w widoku”. Punkt liczy się tylko wtedy, gdy leży w widoku (z zapasem 3 km) — inaczej najbliższe środka widoku (punkt kilkaset km
  dalej dawał minuty liczenia i czarną mapę). „W widoku” = stacje w widoku + do 3 km za krawędzią, promień stacji jak w kroku 1
  (3 × odległość do 3. sąsiada, min. 800 m, maks. 3 km), **najwyżej 60 najbliższych środka** (legenda mówi, gdy obcięto).
- Na mapie rysowanych jest najwyżej 30 trójkątów stacji (od najczystszej drogi); reszta w tabeli.

### 9.3 Wątki

- Pula do 6 wątków; zadania `swiatlo` (wiele częstotliwości naraz), `pole`, `grupy`, `punkt`, `wysokosci`, `scena`.
- Wątek przetwarza komunikaty **po kolei** (dwie sceny liczone naraz mogły skończyć w odwrotnej kolejności) i odsyła błąd jako
  `{id, blad}` — strona pisze wtedy, że pliki nie doszły, zamiast czekać bez końca; baza wczytuje się ponownie przy następnym zadaniu.
- Nowy punkt albo zmiana wysokości unieważnia bieżący przebieg widoku; zadania już liczone w wątku dokańczają się (nie da się ich przerwać).

### 9.4 Prywatność — jak jest naprawdę

- Pliki krajowe (podkład, nadajniki, stacje, teren 1 km, spis miejscowości) są jednakowe dla wszystkich.
- Widok ≤ 36 km pobiera `-mapa` paczek w widoku; numery domów i wyszukiwarka — `-adresy`. Punkt pobiera podkład i adresy swojej paczki
  **tylko wtedy, gdy widok i tak ją pobiera** (≤ 36 km, punkt na ekranie); przy oddalonym widoku punkt niczego nie ściąga.
- Kompromis świadomy: przy brzegu pasa paczek 4 m wątek pyta o paczki 4/16 m, których nie ma (404) — to ślad „ktoś ogląda okolicę
  pasa”, nie więcej niż sam widok. Do usunięcia, gdy wątek dostanie listę istniejących paczek 4/16 m (jak `paczki_z_mapa` dla podkładu).
- Nieudane pobranie podkładu/adresów ponawiane najwcześniej po 30 s (wcześniej co klatkę rysowania).

### 9.5 Teksty strony

- Bez odsyłania do Garwolina poza „Jak to liczymy”: gdzie nie ma budynków, strona pisze „tutaj budynków i drzew jeszcze nie ma
  w danych — liczę sam teren w kratce 100 m”; skala pokazuje „powiat”, gdy poza pasem liczy się poziom 100 m.
- SYMULACJA stale w rogu mapy (nagłówek panelu bywa ukryty na telefonie).
- Pola wyszukiwania i wyboru programu 16 px na telefonie (iOS nie powiększa strony przy dotknięciu); dane z plików w karcie escapowane.
- Wyszukiwarka: adresy z największą liczbą słów zapytania pierwsze („Kościuszki 12 Garwolin” → ulica Kościuszki, choć Kościuszki to też wieś).

- Licencje (2026-10-08): w rogu mapy przycisk „© GUGiK · UKE · Copernicus” → zakładka Tabele, sekcja „Dane i licencje” (zawsze widoczna,
  nie w zwiniętym „Jak to liczymy”) z pełną listą źródeł z plików danych, w tym obowiązkowym tekstem Copernicus WorldDEM-30.
  „Postaw kawę”: zwykły odnośnik do Stripe Payment Link (napiwek, kwota wybierana, PLN, BLIK/karta), stała `KAWA` w `poziomy.html`; dziś link **sandbox** — przed publikacją podmienić na live. Ustawienia Stripe zakłada skrypt `~/dev/RadioWid/stripe/ustaw_napiwek.py sandbox|live` (klucz z ograniczonymi uprawnieniami w `~/.config/radiowid/stripe-<env>.key`).

### 9.6 Składanie do serwowania

`telefon/zloz.sh` → `mapa/_telefon/` (439 MB, 2026-10-08; wejście `index.html` → `telefon/poziomy.html`): strony, silnik bez komentarzy całolinijkowych, dane rynku i pasa, paczki v1
(rastry 4/16/100 m pasa + `-mapa`/`-adresy` 939 / 860 paczek), pliki krajowe. Pliki krajowe są **obowiązkowe** — brak któregokolwiek
przerywa składanie (strona bez nich nie wstaje). `mapa-pas`/`adresy-pas` nie są już kopiowane.

### 9.7 Pomiary (Mac, przeglądarka, tryb telefonu)

| Scenariusz | Wynik |
|---|---|
| Garwolin, ulica 4 m, 4G, 3 stacje | 1,1 s; kierunki 0,2 s |
| Garwolin, okolica 16 m, 4G, 18 stacji, 3 pasma | 1,3–1,4 s |
| Kraków 4G / 5G, 3 stacje | 0,4–0,5 s |
| Warszawa, „w widoku”, 60 stacji (powiat) | 1,1 s |
| Punkt w Gdańsku, widok na Garwolinie (dawniej zawieszenie) | 0,7 s, stacje od środka widoku |

### 9.8 Otwarte

- Telefon: czas i pamięć (każdy wątek trzyma własną pamięć paczek 4 m, bez limitu; na poziomie ulica 53 MB plików).
- Wysokości anten stacji komórkowych poza pasem (rejestr UKE ich nie ma).
- Rodzaje 3G/2G i „wszystkie komórkowe” z `punkt.html` — nieprzeniesione.
- Budynki i drzewa poza pasem — dopiero z paczkami 4 m kolejnych obszarów (§4, §6).
- Nadajniki zagraniczne (§8.4 pkt 4).

