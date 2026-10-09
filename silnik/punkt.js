// Widok z punktu: dla JEDNEGO punktu oglądającego jeden profil do każdej stacji (silnik łączony, ta sama krawędź
// dominująca co na mapie). Wynik: kierunek anteny (azymut od punktu), odległość, nadwyżka strat ponad wolną przestrzeń
// per pasmo i ocena czysta / częściowo / zasłonięta. „Najbliższa” ≠ „widoczna” - sortujemy po stratach, nie po odległości.
// Położenie punktu nie opuszcza wywołującego (liczone lokalnie). Każdy wynik to SYMULACJA, nie pomiar.
import { geometriaLaczona, stratyLaczone } from "./laczony.js";
import { J, C_MHZ } from "./silnik.js";
import { poleKrzywe, wysokoscH1, heffKierunku, poprawkaOdbiornika } from "./p1546.js";

// Środek pasma w kierunku stacja -> telefon [MHz] (downlink); nazwy jak w plikach UKE
export const PASMA_MHZ = {
  lte420: 425, cdma420: 425, lte450: 465, lte700: 773, "5g700": 773, lte800: 806, "gsm-r": 923,
  gsm900: 942, umts900: 942, lte900: 942, "5g900": 942, gsm1800: 1842, lte1800: 1842, "5g1800": 1842,
  umts2100: 2140, lte2100: 2140, "5g2100": 2140, lte2600: 2655, "5g2600": 2655, "5g3600": 3600,
};
export const PROGI_DB = { czysta: 3, czesciowo: 15 };   // nadwyżka < 3 dB: czysta; < 15 dB: częściowo; reszta: zasłonięta
export const H_STACJI_ZALOZENIE = 35;                   // gdy nie znamy wysokości anteny (rejestr UKE jej nie ma)
// Granica zasięgu [dB całkowitej straty drogi: wolna przestrzeń + przeszkody], od której telefon traci łączność (decyzja Maćka
// 2026-10-09). Wspólne 135 dB dotąd = koniec poświaty dla wszystkich pasm. Częstotliwość jest już w stracie (wolna przestrzeń
// 20 log f, dyfrakcja, korony), więc tu tylko to, czego tor fali nie zawiera - sprzęt po obu stronach, zwykle uplink:
// 700-900 MHz -1 dB (mniejszy zysk anten stacji), 1800-2600 punkt odniesienia, 3600 MHz -3 dB (uplink 5G 3,5 GHz ok. 5 dB
// gorszy niż 4G 2,6 GHz, z czego ok. 2,6 dB to wolna przestrzeń liczona osobno). Przybliżenie z typowych bilansów łącza, nie pomiar.
export const GRANICA_DB = (fMHz) => fMHz < 1000 ? 134 : fMHz < 3000 ? 135 : 132;
export const PROG_MOCNY_DB = 15;                        // zapas co najmniej tyle: mocny; 0..15: słaby; poniżej 0: poza zasięgiem
export const ocenaZasiegu = (zapas) => zapas >= PROG_MOCNY_DB ? "mocny" : zapas >= 0 ? "slaby" : "poza";

export function ocena(nadDb) {
  return nadDb < PROGI_DB.czysta ? "czysta" : nadDb < PROGI_DB.czesciowo ? "czesciowo" : "zaslonieta";
}

// punkt: {x, y} w metrach od rynku (x = wschód, y = północ); hRx - wysokość odbiornika nad gruntem
// stacje: [{x, y, pasma, h_ant?, ...}]  (h_ant nad gruntem; brak -> H_STACJI_ZALOZENIE, oznaczone)
// scena: {miasto, teren, R_E, podstawaKorony} jak w geometriaLaczona; teren.wysokosc(x, y) daje grunt
export function widokZPunktu(punkt, stacje, scena, { hRx = 1.5, gruntPunktu } = {}) {
  const { miasto = null, teren = null, R_E = 8.5e6, podstawaKorony = 0.3 } = scena;
  const z0 = (gruntPunktu ?? teren.wysokosc(punkt.x, punkt.y)) + hRx;
  const odb = { xs: Float64Array.of(punkt.x), ys: Float64Array.of(punkt.y), Z: Float32Array.of(z0) };
  const wynik = stacje.map((s) => {
    const zalozona = s.h_ant == null, h = zalozona ? H_STACJI_ZALOZENIE : s.h_ant;
    const T = [s.x, s.y, teren.wysokosc(s.x, s.y) + h];
    const geo = geometriaLaczona(odb, T, { miasto, teren, R_E, podstawaKorony });
    const pasma = {};
    let najgorsza = -Infinity, najlepsza = Infinity;
    for (const p of s.pasma) {
      const f = PASMA_MHZ[p]; if (!f) continue;
      const { nad: [nad], L: [L] } = stratyLaczone(odb, T, geo, f, { rozpraszanie: true });
      pasma[p] = { mhz: f, nadwyzka_db: Math.round(nad * 10) / 10, ocena: ocena(nad), strata_db: Math.round(L * 10) / 10,
                   zapas_db: Math.round((GRANICA_DB(f) - L) * 10) / 10 };
      najgorsza = Math.max(najgorsza, nad); najlepsza = Math.min(najlepsza, nad);
    }
    const dx = s.x - punkt.x, dy = s.y - punkt.y;
    return {
      ...s, azymut: Math.round((Math.atan2(dx, dy) * 180 / Math.PI + 360) % 360), km: Math.hypot(dx, dy) / 1000,
      h_ant_uzyta: h, h_ant_zalozona: zalozona, pasma_wynik: pasma,
      ocena: ocena(najlepsza), nadwyzka_min_db: najlepsza, nadwyzka_max_db: najgorsza,
      przeszkoda_m: geo.umax[0] > -0.78 ? Math.round(geo.gdzie[0]) : null,   // odległość krawędzi dominującej od punktu
      korony_m: Math.round(geo.kor[0]),
    };
  });
  // kolejność: najpierw widoczne (najmniejsza nadwyżka), przy remisie bliższe
  return wynik.sort((a, b) => a.nadwyzka_min_db - b.nadwyzka_min_db || a.km - b.km);
}

// --- radio i TV: „odbiór / granica / nie” ---
// Natężenie pola [dBµV/m] wg ITU-R P.1546-6 (silnik/p1546.js): krzywa dla 1 kW e.r.p. (ląd, 50% czasu i miejsc, odbiór
// na 10 m; h1 z wysokości efektywnej masztu, liczonej w przygotuj/fm.mjs) + 10 log ERP[kW] - tłumienie charakterystyki
// anteny nadawczej + poprawka anteny odbiorczej (§9): na otwartym terenie spadek z obniżeniem anteny poniżej 10 m,
// w zabudowie 6,03 - J krawędzi z prawdziwych budynków i koron między punktem a nadajnikiem (odcinek w mieście).
// Krzywe P.1546 uśredniają teren po drodze, więc odcinek daleki (daleko.bin) nie jest tu już używany.
// Progi (ITU-R BS.412, minimalne natężenie użyteczne): stereo w zabudowie ok. 60, mono 48 dBµV/m.
export const PROGI_FM = { slychac: 60, granica: 48 };
// progi per rodzaj [dBµV/m] (klucz "slychac" = dobry odbiór): DAB+ pasmo III - ok. 50 przenośny, 38 na zewnątrz (EBU, przybliżenie);
// DVB-T pasmo IV/V - 56 antena dachowa (plan GE06, 64-QAM), 48 granica. To przybliżenia do oceny, nie normy odbioru.
export const PROGI_RTV = { fm: PROGI_FM, dab: { slychac: 50, granica: 38 }, dvbt: { slychac: 56, granica: 48 } };
function tlumienieAnteny(tl, az) {                    // tl: 36 wartości co 10° [dB]; interpolacja liniowa
  if (!tl || !tl.length) return 0;
  const a = (az % 360 + 360) % 360 / 10, i = Math.floor(a) % 36, f = a - Math.floor(a);
  return tl[i] * (1 - f) + tl[(i + 1) % 36] * f;
}

// fm: {meta: {grupy}} z dane/rtv.json (przygotuj/fm.mjs); miasto: siatka kwadratu
export function fmZPunktu(punkt, fm, scena, { hRx = 1.5, gruntPunktu } = {}) {
  const { miasto = null, teren = null, R_E = 8.5e6 } = scena;
  const z0 = (gruntPunktu ?? teren.wysokosc(punkt.x, punkt.y)) + hRx;
  const odb = { xs: Float64Array.of(punkt.x), ys: Float64Array.of(punkt.y), Z: Float32Array.of(z0) };
  const wynik = [];
  fm.meta.grupy.forEach((g, gi) => {
    if (!g.programy.length) return;
    const T = [g.x, g.y, g.z];
    const umax = miasto ? geometriaLaczona(odb, T, { miasto, teren: null, R_E }).umax[0] : -Infinity;
    const azOdNadajnika = (Math.atan2(punkt.x - g.x, punkt.y - g.y) * 180 / Math.PI + 360) % 360;   // w siatce ukladu mapy
    const dkm = Math.hypot(g.x - punkt.x, g.y - punkt.y) / 1000, h1 = wysokoscH1(dkm, heffKierunku(g.heff, g.hant, azOdNadajnika), g.hant);
    const azGeo = (azOdNadajnika + (g.zbieznosc ?? 0) + 360) % 360;   // charakterystyka anteny UKE: azymut geograficzny (uklad 2180: + zbieznosc w nadajniku)
    for (const p of g.programy) {
      const zaslona = J(umax / Math.sqrt(C_MHZ / p.mhz)), popr = poprawkaOdbiornika(hRx, p.mhz, zaslona);
      const E = Math.min(poleKrzywe(dkm, h1, p.mhz) + popr, 106.9 - 20 * Math.log10(dkm)) + 10 * Math.log10(p.erp_kw) - tlumienieAnteny(p.tlumienie_db, azGeo);
      wynik.push({ ...p, typ: p.typ ?? "fm", gi, km: dkm, azymut: Math.round((azOdNadajnika + 180) % 360), hant: g.hant, h1: Math.round(h1),
        E_dBuVm: Math.round(E * 10) / 10, zaslona_db: Math.round(-popr * 10) / 10, krawedz: zaslona > 0 && 6.03 - zaslona < popr + 1e-9 ? "zabudowa" : "antena nisko",
        ocena: E >= (PROGI_RTV[p.typ ?? "fm"] ?? PROGI_FM).slychac ? "slychac" : E >= (PROGI_RTV[p.typ ?? "fm"] ?? PROGI_FM).granica ? "granica" : "nie" });
    }
  });
  return wynik.sort((a, b) => b.E_dBuVm - a.E_dBuVm);
}

// pole radia/TV na siatce (światło na mapie): odb = {xs, ys, Z} jak w geometriaLaczona; grupa gi z fm.meta.grupy;
// typ - które programy grupy liczyć. Zwraca największe natężenie [dBµV/m] z programów grupy w każdej próbce.
// program (opcjonalnie): tylko ten program/multipleks grupy - bez niego najmocniejszy z programów w każdej próbce
export function poleNaSiatce(odb, fm, gi, typ, scena, hRx, program = null) {
  const { miasto = null, R_E = 8.5e6 } = scena, g = fm.meta.grupy[gi];
  const programy = g.programy.filter((p) => (p.typ ?? "fm") === typ && (!program || p.program === program)), nx = odb.xs.length, ny = odb.ys.length;
  const E = new Float32Array(nx * ny).fill(-Infinity); if (!programy.length) return E;
  const T = [g.x, g.y, g.z];
  const blisko = miasto ? geometriaLaczona(odb, T, { miasto, teren: null, R_E }).umax : null;
  for (let i = 0; i < ny; i++) {
    const y = odb.ys[i];
    for (let j = 0; j < nx; j++) {
      const x = odb.xs[j], q = i * nx + j, umax = blisko ? blisko[q] : -Infinity;
      const azS = Math.atan2(x - g.x, y - g.y) * 180 / Math.PI, az = (azS + 360 + (g.zbieznosc ?? 0)) % 360;   // geograficzny (2180: + zbieznosc)
      const dkm = Math.hypot(g.x - x, g.y - y) / 1000, h1 = wysokoscH1(dkm, heffKierunku(g.heff, g.hant, azS), g.hant), Emx = 106.9 - 20 * Math.log10(dkm);
      let best = -Infinity;
      for (const p of programy) {
        const e = Math.min(poleKrzywe(dkm, h1, p.mhz) + poprawkaOdbiornika(hRx, p.mhz, J(umax / Math.sqrt(C_MHZ / p.mhz))), Emx)
                  + 10 * Math.log10(p.erp_kw) - tlumienieAnteny(p.tlumienie_db, az);
        if (e > best) best = e;
      }
      E[q] = best;
    }
  }
  return E;
}
