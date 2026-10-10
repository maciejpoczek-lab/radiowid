// Silnik "swiatla radiowego": straty drogi od nadajnika do kazdego punktu siatki.
// Dziala bez zaleznosci w przegladarce (Web Worker) i w Node (weryfikacja wzgledem Pythona).
// Port 1:1 z proby/miasto/fala.py (miasto: budynki + korony) i proby/teren/dolek.py (zaslona terenu, ziemia 4/3).
// Kazdy wynik to SYMULACJA, nie pomiar: jedna krawedz dominujaca (ITU-R P.526), bez odbic, moc nadajnika zalozona.

export const C_MHZ = 299.792458;               // lambda [m] = C_MHZ / f [MHz]

// ITU-R P.526, pojedyncza krawedz: strata [dB] dla parametru v
export function J(v) {
  if (!(v > -0.78)) return 0;
  const a = v - 0.1;
  return 6.9 + 20 * Math.log10(Math.sqrt(a * a + 1) + a);
}

// Weissberger, korony w lisciach; model wazny 230 MHz - 95 GHz, nizej drzew nie liczymy
export function weissberger(fMHz, d) {
  if (fMHz < 230) return 0;
  const g = (fMHz / 1000) ** 0.284;
  return d <= 14 ? 0.45 * g * d : 1.33 * g * Math.min(d, 400) ** 0.588;
}
// Korony wg ITU-R P.833-10 §2.1 (terminal w zadrzewieniu): A = Am (1 - exp(-d gamma / Am)) - strata rośnie z drogą przez
// drzewa, ale dochodzi do pułapu Am, bo fala obchodzi drzewa górą (fala powierzchniowa nad koronami) i rozprasza się w nich
// do przodu. Weissberger tego pułapu nie ma (do 400 m drogi daje przy 1,8 GHz 54 dB) - kalibracja telefonem 2026-10-10
// (Play, Bródno/Targówek, 121 punktów) pokazała, że zmierzony sygnał koron Weissbergera prawie nie widzi; P.833 zmniejsza ten dryf tylko częściowo
// (lte1800: K powyżej 1 km o 14,7 zamiast 17,5 dB wyżej niż bliżej) - korony liczone wzdłuż promienia nadal są za duże.
// gamma [dB/m]: tabela 1 zalecenia (las mieszany, St. Petersburg, 105,9-2117,5 MHz), interpolacja log-log; powyżej
// 2117,5 MHz ekstrapolacja ostatnim odcinkiem (3,6 GHz: ok. 0,56 dB/m) - poza zakresem pomiaru.
// Am [dB] = A1 f^alfa, wz. 2, A1 = 1,15, alfa = 0,43 (las koło Miluzy, 900-2200 MHz, odbiornik w samochodzie 1,6 m,
// nadajnik 25 m - geometria najbliższa naszej); 1,8 GHz: 29 dB, 3,6 GHz: 39 dB (zalecenie: 46 dB przy 3605 MHz, Anglia),
// 800 MHz: 20 dB. Poza 900-2200 MHz ekstrapolacja. Odchylenie pomiarów w Miluzie 8,7 dB - to rząd wielkości, nie dokładność.
// Poniżej 230 MHz zero jak w weissberger (radio FM bez koron, bez zmian).
const P833_GAMMA = [[105.9, 0.04], [466.475, 0.12], [949, 0.17], [1852.2, 0.30], [2117.5, 0.34]];
export function gammaP833(fMHz) {
  const T = P833_GAMMA, j = T.findIndex(([f]) => f > fMHz);       // odcinek tabeli; poza nią skrajny odcinek
  const i = j < 0 ? T.length - 2 : Math.max(0, j - 1), [[f0, g0], [f1, g1]] = [T[i], T[i + 1]];
  return g0 * Math.exp(Math.log(g1 / g0) * Math.log(fMHz / f0) / Math.log(f1 / f0));
}
export const amP833 = (fMHz) => 1.15 * fMHz ** 0.43;
export function koronyP833(fMHz, d) {
  if (fMHz < 230 || !(d > 0)) return 0;
  const Am = amP833(fMHz);
  return Am * (1 - Math.exp(-d * gammaP833(fMHz) / Am));
}

export function wolnaPrzestrzen(dM, fMHz) {
  return 20 * Math.log10(dM / 1000) + 20 * Math.log10(fMHz) + 32.44;
}

const f32 = Math.fround;

// --- Miasto (fala.py: geometria) ---
// scena: {nx, ny, X0, Y1, DX, DY, O, G, ZW}  (O = wysokosc nieprzezroczysta, G = grunt, ZW = wysokosc korony; Float32Array/Float64Array, wiersz 0 = polnoc)
// T: [tx, ty, tz] w metrach ukladu sceny; hRx: odbiornik nad gruntem; podstawaKorony: liscie od tego ulamka wysokosci drzewa
// Zwraca {D, umax, kor}: odleglosc pozioma, geometria krawedzi dominujacej u (v = u / sqrt(lambda)), metry drogi w koronach.
// jakNumpy: odtwarza zaokraglenia float32 z NumPy 2 (NEP 50: skalar Pythona nie podnosi float32 do float64) - tylko do weryfikacji.
// wiersze: [i0, i1) - fragment siatki dla jednego watku; Dmax: globalne maksimum D (wymagane przy podziale na watki)
export function dmaxMiasto(scena, T) {
  const { nx, ny, X0, Y1, DX, DY } = scena; let m = 0;
  for (const i of [0, ny - 1]) for (const j of [0, nx - 1])          // maksimum odleglosci od punktu lezy w rogu prostokata srodkow
    m = Math.max(m, Math.hypot(T[0] - (X0 + (j + 0.5) * DX), T[1] - (Y1 - (i + 0.5) * DY)));
  return m;
}
export function geometriaMiasto(scena, T, { hRx = 1.5, podstawaKorony = 0.3, smaxGeom, jakNumpy = false, wiersze, Dmax } = {}) {
  const { nx, ny, X0, Y1, DX, DY, O, G, ZW } = scena;
  const [tx, ty, tz] = T;
  const [i0, i1] = wiersze ?? [0, ny];
  const n = nx * (i1 - i0);
  const D = new Float64Array(n), umax = new Float64Array(n), kor = new Float32Array(n);
  Dmax ??= dmaxMiasto(scena, T);
  const step = DX;
  const smax = Math.min(Dmax, smaxGeom ?? Infinity);
  for (let i = i0; i < i1; i++) {
    const py = Y1 - (i + 0.5) * DY;
    for (let j = 0; j < nx; j++) {
      const px = X0 + (j + 0.5) * DX, k = (i - i0) * nx + j;
      const d = D[k] = Math.hypot(tx - px, ty - py), ux = (tx - px) / d, uy = (ty - py) / d;
      const pz = f32(G[i * nx + j] + hRx), dz = jakNumpy ? f32(f32(tz) - pz) : tz - pz;
      let um = -Infinity, kr = 0;
      for (let s = step; s < smax; s += step) {          // ta sama kumulacja s co w Pythonie -> te same indeksy komorek
        if (!(s < d - step)) break;                       // do komorki nadajnika (bez niej)
        const jj = Math.floor((px + ux * s - X0) / DX), ii = Math.floor((Y1 - (py + uy * s)) / DY);
        if (ii < 0 || ii >= ny || jj < 0 || jj >= nx) break;   // promien opuscil siatke (prostokat jest wypukly - nie wroci)
        const kk = ii * nx + jj;
        const zl = pz + (jakNumpy ? f32(dz * f32(s)) : dz * s) / d;   // wysokosc linii odbiornik-nadajnik
        const u = (O[kk] - zl) * Math.sqrt(2 * d / (s * (d - s)));
        if (u > um) um = u;
        const g = G[kk], zw = ZW[kk];
        if (zl > g + podstawaKorony * zw && zl < g + zw) kr = f32(kr + step);
      }
      umax[k] = um; kor[k] = kr;
    }
  }
  return { D, umax, kor, k0: i0 * nx };
}

// Straty calkowite i nadwyzka ponad wolna przestrzen dla jednej czestotliwosci (fala.py: straty)
export function stratyMiasto(scena, T, geo, fMHz, { hRx = 1.5, jakNumpy = false } = {}) {
  const { D, umax, kor, k0 = 0 } = geo, n = D.length, G = scena.G;
  const L = new Float32Array(n), nad = new Float32Array(n), sl = Math.sqrt(C_MHZ / fMHz);
  for (let k = 0; k < n; k++) {
    const pz = f32(G[k0 + k] + hRx), dz = jakNumpy ? f32(f32(T[2]) - pz) : T[2] - pz, dz2 = jakNumpy ? f32(dz * dz) : dz * dz;
    const a = J(umax[k] / sl) + weissberger(fMHz, kor[k]);
    nad[k] = a; L[k] = wolnaPrzestrzen(Math.sqrt(D[k] * D[k] + dz2), fMHz) + a;
  }
  return { L, nad };
}

// --- Teren (dolek.py) ---
// siatka: {xs: Float64Array}  kwadrat X = xs, Y = -xs (wiersz 0 = polnoc), metry od srodka
// wysokosc(x, y): teren [m n.p.m.] w punkcie ukladu lokalnego; Z: wysokosc odbiornika (teren + hRx) dla kazdego punktu siatki
// T: [tx, ty, tz]; krok: metry; R_E: promien Ziemi zastepczej (4/3)
// Zwraca {umax, gdzie}: u krawedzi dominujacej i jej odleglosc od odbiornika.
// wiersze: [i0, i1) - fragment dla jednego watku; liczba probek n zalezy od globalnego maksimum D (rogi kwadratu)
export function geometriaTeren(xs, Z, T, wysokosc, { krok = 30, R_E = 8.5e6, jakNumpy = false, wiersze } = {}) {
  const N = xs.length, [tx, ty, tz] = T, [i0, i1] = wiersze ?? [0, N];
  let Dmax = 0;
  for (const i of [0, N - 1]) for (const j of [0, N - 1]) Dmax = Math.max(Dmax, Math.hypot(tx - xs[j], ty + xs[i]));
  const n = Math.trunc(Dmax / krok);                      // ta sama liczba probek na kazdym profilu (jak w dolek.py)
  const umax = new Float64Array(N * (i1 - i0)), gdzie = new Float64Array(N * (i1 - i0));
  for (let i = i0; i < i1; i++) {
    const Y = -xs[i];
    for (let j = 0; j < N; j++) {
      const X = xs[j], k = (i - i0) * N + j, d = Math.hypot(tx - X, ty + xs[i]), z = Z[i * N + j];
      let um = -Infinity, gd = 0;
      for (let q = 1; q < n; q++) {
        const f = q / n, s = f * d;
        const zt = wysokosc(X + (tx - X) * f, Y + (ty - Y) * f);
        const zp = jakNumpy ? f32(z + f32(f32(f32(tz) - z) * f32(f))) : z + (tz - z) * f;
        const zl = zp - s * (d - s) / (2 * R_E);           // linia wzroku nad zakrzywiona ziemia
        const u = (zt - zl) * Math.sqrt(2 * d / (s * (d - s)));
        if (u > um) { um = u; gd = s; }
      }
      umax[k] = um; gdzie[k] = gd;
    }
  }
  return { umax, gdzie };
}

// np.rint: zaokraglenie polowek do parzystej
export function rint(x) {
  const r = Math.round(x);
  return (r - x === 0.5 && r % 2 !== 0) ? r - 1 : r;
}
