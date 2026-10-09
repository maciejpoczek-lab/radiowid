// Silnik laczony: miasto (blisko, budynki + korony z NMPT - NMT) i teren (daleko, ziemia 4/3) w JEDNYM przebiegu.
// Jeden profil od odbiornika do nadajnika, krawedz dominujaca na calym profilu (ITU-R P.526) + wtorne (nizej):
//   - strefa miasta: probki co krok siatki miasta (jak fala.py), przeszkoda = O (dach albo grunt), korony liczone osobno;
//   - strefa terenu: od miejsca, w ktorym promien opuszcza siatke miasta - probki jak w dolek.py (f = q/n, n wspolne
//     dla calej siatki), przeszkoda = teren z probnika wysokosc(x, y);
//   - linia wzroku nad ziemia zastepcza 4/3 na CALYM profilu (R_E = Infinity -> plaska, jak fala.py).
// Przypadki graniczne (sprawdzane w weryfikacja/laczony.mjs): bez terenu i R_E = Infinity -> geometriaMiasto;
// bez miasta -> geometriaTeren. Kazdy wynik to SYMULACJA, nie pomiar.
// Krawedzie wtorne (ITU-R P.526-13 §4.3, rys. 12, wz. 41-43): po wyborze krawedzi glownej M szukana jest najwyzsza krawedz
// wzgledem podtrasy M-odbiornik i osobno M-nadajnik; kazda dodaje L2 - Tc (nie mniej niz 0). Zalecenie opisuje jedna
// krawedz wtorna; zastosowanie po obu stronach M to rozszerzenie w duchu metody Deygouta (bez dalszej rekurencji).
// Parametry geometryczne (u = nu * sqrt(lambda)) per strona: u2 - krawedz wtorna wzgledem podtrasy, uq - ta sama krawedz
// wzgledem trasy bezposredniej (q z wz. 42b), al - kat alfa (42c). Brak krawedzi wtornej: u2 = -Infinity.
// wtorne: false - bez krawedzi wtornych (wt = null; np. radio/TV, ktore bierze z geometrii tylko umax).
// bud[k] = 1, gdy krawedz dominujaca to budynek (komorka miasta z dachem co najmniej BUDYNEK_M nad gruntem) - tylko wtedy
// stratyLaczone dodaje rozpraszanie miejskie P.1411; za wzgorzem, za drzewami i na wsi go nie ma.
import { J, weissberger, wolnaPrzestrzen, C_MHZ } from "./silnik.js";

export const BUDYNEK_M = 2;                           // dach nizej niz tyle nad gruntem (szopa, murek, szum NMPT) - nie budynek

// odbiorniki: {xs, ys, Z}  srodki kolumn (zachod -> wschod) i wierszy (wiersz 0 = polnoc) w metrach ukladu sceny,
//             Z = wysokosc odbiornika (grunt + hRx) dla kazdego punktu, wiersz po wierszu
// miasto: {nx, ny, X0, Y1, DX, DY, O, G, ZW} albo null  (jak w geometriaMiasto)
// teren:  {wysokosc(x, y), krok} albo null
// T: [tx, ty, tz]; wiersze: [i0, i1) dla jednego watku; Dmax: globalne maksimum odleglosci (przy podziale na watki)
export function dmaxOdbiorniki(odb, T) {
  const { xs, ys } = odb; let m = 0;
  for (const y of [ys[0], ys[ys.length - 1]]) for (const x of [xs[0], xs[xs.length - 1]]) m = Math.max(m, Math.hypot(T[0] - x, T[1] - y));
  return m;
}

export function geometriaLaczona(odb, T, { miasto = null, teren = null, R_E = 8.5e6, podstawaKorony = 0.3, smaxGeom, wiersze, Dmax, wtorne = true } = {}) {
  const { xs, ys, Z } = odb, nx = xs.length, ny = ys.length;
  const [tx, ty, tz] = T, [i0, i1] = wiersze ?? [0, ny];
  const n = nx * (i1 - i0);
  const D = new Float64Array(n), umax = new Float64Array(n), kor = new Float32Array(n), gdzie = new Float64Array(n), bud = new Uint8Array(n);
  const wt = !wtorne ? null : { u2: [new Float32Array(n), new Float32Array(n)], uq: [new Float32Array(n), new Float32Array(n)], al: [new Float32Array(n), new Float32Array(n)] };
  Dmax ??= dmaxOdbiorniki(odb, T);
  const R2 = 2 * R_E;                                                     // Infinity -> linia prosta
  const nT = teren ? Math.trunc(Dmax / teren.krok) : 0;                   // liczba probek terenu (dolek.py)
  let mX0, mY1, mDX, mDY, mnx, mny, O, G, ZW, step, smax;
  if (miasto) {
    ({ X0: mX0, Y1: mY1, DX: mDX, DY: mDY, nx: mnx, ny: mny, O, G, ZW } = miasto);
    step = mDX; smax = Math.min(Dmax, smaxGeom ?? Infinity);
  }
  const nb = (miasto ? Math.ceil(smax / step) : 0) + nT + 2, bs = new Float64Array(nb), bh = new Float64Array(nb);  // profil: s, wysokosc nad LOS
  for (let i = i0; i < i1; i++) {
    const py = ys[i];
    for (let j = 0; j < nx; j++) {
      const px = xs[j], k = (i - i0) * nx + j, pz = Z[i * nx + j];
      const d = D[k] = Math.hypot(tx - px, ty - py), dz = tz - pz;
      let um = -Infinity, gd = 0, kr = 0, sWyjscie = 0, bd = 0, np = 0, hm = 0, qm = -1;
      if (miasto) {
        const ux = (tx - px) / d, uy = (ty - py) / d;
        sWyjscie = Infinity;
        for (let s = step; s < smax; s += step) {
          if (!(s < d - step)) break;
          const jj = Math.floor((px + ux * s - mX0) / mDX), ii = Math.floor((mY1 - (py + uy * s)) / mDY);
          if (ii < 0 || ii >= mny || jj < 0 || jj >= mnx) { sWyjscie = s; break; }
          const kk = ii * mnx + jj;
          const zl = pz + dz * s / d - s * (d - s) / R2;
          const u = (O[kk] - zl) * Math.sqrt(2 * d / (s * (d - s)));
          bs[np] = s; bh[np++] = O[kk] - zl;
          if (u > um) { um = u; gd = s; qm = np - 1; hm = O[kk] - zl; bd = O[kk] - G[kk] >= BUDYNEK_M ? 1 : 0; }
          const g = G[kk], zw = ZW[kk];
          if (zl > g + podstawaKorony * zw && zl < g + zw) kr = Math.fround(kr + step);
        }
      }
      if (teren && sWyjscie < Infinity) {
        const { wysokosc } = teren;
        for (let q = 1; q < nT; q++) {
          const f = q / nT, s = f * d;
          if (s < sWyjscie) continue;
          const zt = wysokosc(px + (tx - px) * f, py + (ty - py) * f);
          const zl = pz + dz * f - s * (d - s) / R2;
          const u = (zt - zl) * Math.sqrt(2 * d / (s * (d - s)));
          bs[np] = s; bh[np++] = zt - zl;
          if (u > um) { um = u; gd = s; qm = np - 1; hm = zt - zl; bd = 0; }
        }
      }
      umax[k] = um; kor[k] = kr; gdzie[k] = gd; bud[k] = bd;
      // strona 0: miedzy odbiornikiem (s = 0) a M; strona 1: miedzy M a nadajnikiem (s = d)
      if (wt) for (let st = 0; st < 2; st++) {
        let u2 = -Infinity, uq = 0, al = 0;
        if (um > 0 && qm >= 0) {
          // od M na zewnatrz; probki, zanim profil choc raz zejdzie pod podtrase, to ta sama przeszkoda (dach, zbocze) co M
          let osobna = false;
          for (let q = st === 0 ? qm - 1 : qm + 1; st === 0 ? q >= 0 : q < np; q += st === 0 ? -1 : 1) {
            const s = bs[q];
            const x = st === 0 ? s : d - s, L = st === 0 ? gd : d - gd;    // odleglosc od konca podtrasy, dlugosc podtrasy
            const h2 = bh[q] - hm * x / L;
            if (!osobna) { osobna = h2 <= 0; continue; }
            const u = h2 * Math.sqrt(2 * L / (x * (L - x)));
            if (u > u2) { u2 = u; uq = bh[q] * Math.sqrt(2 * d / ((d - x) * x)); al = Math.atan(Math.sqrt((L - x) * d / ((d - L) * x))); }
          }
        }
        wt.u2[st][k] = u2; wt.uq[st][k] = uq; wt.al[st][k] = al;
      }
    }
  }
  return { D, umax, kor, gdzie, bud, wt, k0: i0 * nx };
}

// Straty calkowite [dB] i nadwyzka ponad wolna przestrzen dla jednej czestotliwosci
// Odbicia i rozpraszanie od ścian (opcja rozpraszanie): moc drogi ugiętej (krawędź + korony) dodana do mocy fali
// docierającej po odbiciach - mediana strat NLoS z ITU-R P.1411-13 §4.2.1, tabela 8 (stacja nad dachami, odbiornik
// poniżej): Lb = 43,9 log10(d) - 6,27 + 23,0 log10(f GHz). Tabela podaje NLoS tylko dla zabudowy wysokiej, 2,2-66,5 GHz,
// 260-1200 m: d przycinane do tego przedziału (nadwyżka nad wolną przestrzenią stała poza nim), pasma < 2,2 GHz to
// ekstrapolacja. Wysoka zabudowa tłumi mocniej niż niska, więc granica cienia raczej za głęboka niż za płytka.
// Skutek: cień za budynkiem nie bywa głębszy niż typowy cień ulicy (ok. 19-34 dB nad wolną przestrzenią); w widoczności nic.
// Tylko gdy krawędź dominująca to budynek (geo.bud): wzór opisuje ulicę między domami, nie dolinę za wzgórzem ani las.
export function nadwyzkaRozproszenia(dM, fMHz) {
  const d = Math.min(Math.max(dM, 260), 1200);
  return 43.9 * Math.log10(d) - 6.27 + 23.0 * Math.log10(fMHz / 1000) - wolnaPrzestrzen(d, fMHz);
}
// L2 - Tc dla krawedzi wtornej (P.526-13 wz. 41-43), nie mniej niz 0; p = nu krawedzi glownej, q z wz. 42b
export function krawedzWtorna(p, nu2, q, alfa) {
  if (!(p > 0 && q > 0) || nu2 <= -0.78) return 0;
  const Tc = 12 - 20 * Math.log10(2 / (1 - alfa / Math.PI) * (q / p) ** (2 * p));
  return Math.max(0, J(nu2) - Tc);
}
export function stratyLaczone(odb, T, geo, fMHz, { rozpraszanie = false, wtorne = true } = {}) {
  const { D, umax, kor, bud, wt, k0 = 0 } = geo, n = D.length, Z = odb.Z;
  const L = new Float32Array(n), nad = new Float32Array(n), sl = Math.sqrt(C_MHZ / fMHz);
  for (let k = 0; k < n; k++) {
    const dz = T[2] - Z[k0 + k], r = Math.sqrt(D[k] * D[k] + dz * dz), p = umax[k] / sl;
    let a = J(p) + weissberger(fMHz, kor[k]);
    if (wt && wtorne) for (let st = 0; st < 2; st++) a += krawedzWtorna(p, wt.u2[st][k] / sl, wt.uq[st][k] / sl, wt.al[st][k]);
    if (rozpraszanie && bud?.[k]) a = -10 * Math.log10(10 ** (-a / 10) + 10 ** (-nadwyzkaRozproszenia(r, fMHz) / 10));
    nad[k] = a; L[k] = wolnaPrzestrzen(r, fMHz) + a;
  }
  return { L, nad };
}
