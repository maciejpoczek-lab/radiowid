// Zgodność silnik/p1546.js z implementacją wzorcową ITU-R SG3 (P1546FieldStrMixed.m v6.2): z dzienników walidacji
// (dane/itu-p1546/p1/*/validation_results/*_log.csv) bierze przypadki lądowe z 50% czasu i porównuje
// pole z krzywych (krok 11) oraz poprawkę anteny odbiorczej dla terenu otwartego (krok 14, Rural). Osobno: poprawka kąta
// prześwitu terenu (§11, krok 12) ze wszystkich dzienników p1 i p2, w których jest - kąt tca z dziennika, bez profilu.
// Uzycie: node weryfikacja/p1546.mjs
import { readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { poleKrzywe, poprawkaOdbiornika, poprawkaKataPrzeswitu, poleKroki } from "../silnik/p1546.js";
const D = `${homedir()}/dev/showreel-2/dane/itu-p1546/p1/`, K = D + readdirSync(D).find((n) => n.startsWith("Matlab")) + "/validation_results/";
let n = 0, nh = 0, maks = 0, maksH = 0, pominiete = 0;
for (const plik of readdirSync(K).filter((p) => p.endsWith("_log.csv"))) {
  const w = {}; for (const l of readFileSync(K + plik, "utf8").split("\n")) { const c = l.split(","); if (c.length >= 4) w[c[0].trim()] ??= c[3].trim(); }
  const f = +w["Frequency f (MHz)"], d = +w["Horizontal path length d (km)"], t = +w["Percentage time t (%)"], sea = +w["Sea path (km)"], h1 = +w["Tx antenna height h1 (m)"];
  const E = +w["Field strength (dBuV/m)"];
  if (t !== 50 || sea > 0 || d < 1 || !Number.isFinite(E)) { pominiete++; continue; }
  const r = poleKrzywe(d, h1, f) - E; maks = Math.max(maks, Math.abs(r)); n++;
  if (Math.abs(r) > 0.01) console.log("ROZNICA", plik, { f, d, h1, ITU: E, my: +(E + r).toFixed(4) });
  if (w["Rx clutter type"] === "Rural") {
    const c = +w["Rx antenna height correction (dB)"], rh = poprawkaOdbiornika(+w["Rx antenna height a. g. h2 (m)"], f) - c;
    maksH = Math.max(maksH, Math.abs(rh)); nh++;
    if (Math.abs(rh) > 0.01) console.log("ROZNICA h2", plik, { f, h2: w["Rx antenna height a. g. h2 (m)"], ITU: c });
  }
}
console.log(`krzywe: ${n} przypadków, największa różnica ${maks.toFixed(4)} dB; poprawka h2 (teren otwarty): ${nh} przypadków, ${maksH.toFixed(4)} dB; pominięte (morze, t != 50%, d < 1 km): ${pominiete}`);

let nt = 0, maksT = 0;
for (const cz of ["p1", "p2"]) {
  const R = `${homedir()}/dev/showreel-2/dane/itu-p1546/${cz}/`, KK = R + readdirSync(R).find((n) => /P\.1546/.test(n)) + "/validation_results/";
  for (const plik of readdirSync(KK).filter((p) => p.endsWith("_log.csv"))) {
    const w = {}; for (const l of readFileSync(KK + plik, "utf8").split("\n")) { const c = l.split(","); if (c.length >= 4) w[c[0].trim()] ??= c[3].trim(); }
    const tca = +w["Terrain clearance angle tca (deg)"], c = +w["TCA correction (dB)"];
    if (!Number.isFinite(tca) || !Number.isFinite(c) || w["TCA correction (dB)"] === "") continue;
    const r = poprawkaKataPrzeswitu(+w["Frequency f (MHz)"], tca) - c; maksT = Math.max(maksT, Math.abs(r)); nt++;
    if (Math.abs(r) > 0.01) console.log("ROZNICA tca", cz, plik, { f: w["Frequency f (MHz)"], tca, ITU: c, my: c + r });
  }
}
console.log(`kąt prześwitu (§11): ${nt} przypadków, największa różnica ${maksT.toFixed(4)} dB`);

// §14-15 (kroki 16-17): drogi lądowe 50% czasu krótsze niż 1 km - pole z krzywych na 1 km + poprawki z dziennika (h2, tca,
// zasłona nadajnika), różnica wysokości anten odtworzona z zapisanej poprawki skośnej na 1 km (20 log(1/d_skośna)).
let nk = 0, maksK = 0;
for (const cz of ["p1", "p2"]) {
  const R = `${homedir()}/dev/showreel-2/dane/itu-p1546/${cz}/`, KK = R + readdirSync(R).find((n) => /P\.1546/.test(n)) + "/validation_results/";
  for (const plik of readdirSync(KK).filter((p) => p.endsWith("_log.csv"))) {
    const w = {}; for (const l of readFileSync(KK + plik, "utf8").split("\n")) { const c = l.split(","); if (c.length >= 4) w[c[0].trim()] ??= c[3].trim(); }
    const d = +w["Horizontal path length d (km)"], f = +w["Frequency f (MHz)"], h1 = +w["Tx antenna height h1 (m)"], E = +w["Field strength for d < 1 km (dB)"];
    if (!(d < 1) || +w["Percentage time t (%)"] !== 50 || +w["Sea path (km)"] > 0 || !Number.isFinite(E)) continue;
    const kor = (k) => +w[k] || 0, ds1 = 10 ** (-kor("Rx slope-path correction (dB)") / 20), dz = Math.sqrt((ds1 * ds1 - 1) / 1e-6);
    const popr = kor("TCA correction (dB)") + kor("Rx antenna height correction (dB)") + kor("Tx clutter correction (dB)");
    const r = poleKroki(d, h1, f, popr, dz) - E; maksK = Math.max(maksK, Math.abs(r)); nk++;
    if (Math.abs(r) > 0.01) console.log("ROZNICA d<1km", cz, plik, { d, f, ITU: E, my: +(E + r).toFixed(4) });
  }
}
console.log(`d < 1 km (§15): ${nk} przypadków, największa różnica ${maksK.toFixed(4)} dB`);
