// ITU-R P.1546-6 — natężenie pola nadajnika radia/TV w ograniczeniu do tego, czego potrzebuje mapa:
// droga lądowa, 50% czasu, 50% miejsc, 1 kW e.r.p., odbiór na wysokości odniesienia 10 m (krzywe), plus poprawka
// anteny odbiorczej z §9. Przeniesione z implementacji wzorcowej ITU-R SG3 (P1546FieldStrMixed.m v6.2): kroki 7–9
// (interpolacja po odległości, wysokości nadajnika h1 i częstotliwości), §3 (h1), §9 (Step_14a). Pominięte: drogi
// morskie i mieszane, d < 1 km, rozpraszanie troposferyczne (§13), zmienność miejsc (§12). Poprawka kąta prześwitu
// terenu przy odbiorniku (§11, krok 12) - poprawkaKataPrzeswitu; kąt liczy wywołujący (silnik/punkt.js, katPrzeswitu).
// Sprawdzenie zgodności z przykładami ITU: weryfikacja/p1546.mjs.
import T from "./p1546-tabele.js";

const ODL = T.d, WYS = T.h1, FREQ = [100, 600, 2000];
function sasiednie(x, v) {                          // jak searchclosest: dwa sąsiednie węzły (poza zakresem - dwa skrajne)
  if (v >= x[x.length - 1]) return v === x[x.length - 1] ? [x.length - 1, x.length - 1] : [x.length - 2, x.length - 1];
  if (v <= x[0]) return v === x[0] ? [0, 0] : [0, 1];
  let k = 1; while (x[k] < v) k++;
  return x[k] === v ? [k, k] : [k - 1, k];
}
const logInterp = (v, a, b, Ea, Eb) => (a === b ? Ea : Ea + (Eb - Ea) * Math.log10(v / a) / Math.log10(b / a));
const Jnu = (nu) => (nu > -0.78 ? 6.9 + 20 * Math.log10(Math.sqrt((nu - 0.1) ** 2 + 1) + nu - 0.1) : 0);
const Emax = (d) => 106.9 - 20 * Math.log10(d);    // pole w wolnej przestrzeni dla 1 kW e.r.p. (§2, ląd, 50% czasu)

function poOdleglosci(tab, ih, d) {                 // równ. (13)
  const [a, b] = sasiednie(ODL, d);
  return logInterp(d, ODL[a], ODL[b], tab[a][ih], tab[b][ih]);
}
function naCzestotliwosciNominalnej(fn, h1, d) {
  const tab = T.E[fn];
  if (h1 >= 10) {                                   // krok 8.1, równ. (8)
    const [a, b] = sasiednie(WYS, h1);
    return Math.min(logInterp(h1, WYS[a], WYS[b], poOdleglosci(tab, a, d), poOdleglosci(tab, b, d)), Emax(d));
  }
  // krok 8.2 (ląd): h1 < 10 m - ekstrapolacja z krzywych 10 i 20 m, równ. (9)-(12)
  const E10 = poOdleglosci(tab, 0, d), E20 = poOdleglosci(tab, 1, d), Kv = { 100: 1.35, 600: 3.31, 2000: 6 }[fn];
  const v = (h) => Kv * Math.atan(-h / 9000) * 180 / Math.PI;
  const Ezero = E10 + 0.5 * (E10 - E20 + 6.03 - Jnu(v(-10)));
  return h1 >= 0 ? Ezero + 0.1 * h1 * (E10 - Ezero) : Ezero + 6.03 - Jnu(v(h1));
}

// Pole z krzywych [dBµV/m] dla 1 kW e.r.p. przy odbiorze na 10 m: d [km], h1 [m] (§3), f [MHz]; równ. (14)
export function poleKrzywe(d, h1, f) {
  d = Math.max(d, 1);                               // P.1546-5+: dla d < 1 km krzywe na 1 km (krok 17 pominięty)
  const [a, b] = sasiednie(FREQ, f);
  const Ea = naCzestotliwosciNominalnej(FREQ[a], h1, d);
  return a === b ? Ea : logInterp(f, FREQ[a], FREQ[b], Ea, naCzestotliwosciNominalnej(FREQ[b], h1, d));
}

// §3: wysokość h1 nadajnika - heff (nad średnim terenem 3–15 km od nadajnika w stronę odbiornika) dla d >= 15 km;
// bliżej - przejście od wysokości nad gruntem ha (równ. 4-5, wariant bez profilu terenu)
// heff jako liczba (dane/rtv*.json: w stronę jednego miejsca) albo 36 wartości co 10° w osiach siatki (kraj/nadajniki.json,
// przygotuj/rtv_kraj.py): liniowo między sąsiednimi sektorami; sektor bez terenu (null) -> wysokość anteny ha.
export function heffKierunku(heff, ha, azSiatki) {
  if (!Array.isArray(heff)) return heff ?? ha;
  const s = ((azSiatki % 360) + 360) % 360 / 10, k = Math.floor(s) % 36, f = s - Math.floor(s);
  const a = heff[k] ?? ha, b = heff[(k + 1) % 36] ?? ha;
  return a + (b - a) * f;
}
export function wysokoscH1(d, heff, ha) {
  if (d >= 15) return heff;
  if (d <= 3) return ha;
  return ha + (heff - ha) * (d - 3) / 12;
}

// §9: poprawka anteny odbiorczej h2 [m] względem 10 m. Teren otwarty: K_h2 log(h2/10) (równ. 29). W zabudowie P.1546
// zakłada przeszkodę o wysokości R w 27 m i daje 6,03 - J(nu) (równ. 28a) - u nas zamiast przyjętej przeszkody jest
// prawdziwa krawędź z budynków i koron (zaslonaDb = J z geometrii miasta), więc bierzemy gorszą z dwóch gałęzi.
export function poprawkaOdbiornika(h2, f, zaslonaDb = 0) {
  const otwarty = (3.2 + 6.2 * Math.log10(f)) * Math.log10(h2 / 10);
  return zaslonaDb > 0 ? Math.min(otwarty, 6.03 - zaslonaDb) : otwarty;
}

// §11 (krok 12, Step_12a wzorca): poprawka [dB] na kąt prześwitu terenu tca [°] - kąt wzniesienia linii od anteny odbiorczej,
// która mija cały teren w stronę nadajnika do 16 km (bez krzywizny Ziemi). tca ograniczony do 0,55..40°, więc poprawka jest
// zawsze ≤ 0 (przy 0,55° ok. 0 dB): odbiornik w dolinie traci, na szczycie nie zyskuje ponad krzywe.
export function poprawkaKataPrzeswitu(f, tca) {
  const t = Math.min(Math.max(tca, 0.55), 40);
  return Jnu(0.036 * Math.sqrt(f)) - Jnu(0.065 * t * Math.sqrt(f));
}

// Gotowe pole w punkcie [dBµV/m]: e.r.p. [kW], d [km], h1 [m], f [MHz], h2 [m], zasłona miejska [dB], tłumienie anteny nadawczej [dB]
export function pole1546(erpKw, d, h1, f, h2, zaslonaDb, tlumAnteny = 0) {
  const E = poleKrzywe(d, h1, f) + poprawkaOdbiornika(h2, f, zaslonaDb);
  return Math.min(E, Emax(Math.max(d, 1e-3))) + 10 * Math.log10(erpKw) - tlumAnteny;
}
