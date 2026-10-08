// Nadajniki radia/TV dla mapy: grupy (miejsce + wysokość anteny) z programami i wysokością efektywną masztu (ITU-R P.1546 §3).
// Pole liczy strona wg P.1546 (silnik/p1546.js); do 2026-10-06 liczyło się tu umax odcinka dalekiego profilu (daleko.bin) -
// krzywe P.1546 uśredniają teren po drodze, więc odpadło.
// Teren: NMT GUGiK 30 m do 11,8 km od rynku, dalej Copernicus GLO-30 na mozaice 51-53 N, 20-23 E.
// Wejście: ../../dane/uke-fm/fm-100km.json (UKE, stan 2018-10-01), ../dane/rynek (T + meta.teren), ../../dane/dem/*.npy
// Wyjście: ../dane/<wyjście>.json. Każdy wynik to SYMULACJA.
// Uzycie: node fm.mjs [pol_boku_m=3000] [komorka_m=60] [R_km=100]
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";

const HERE = dirname(fileURLToPath(import.meta.url)), DANE = join(HERE, "../../dane");
const R_KM = +(process.argv[4] ?? 100);           // argumenty 2-3 (bok kwadratu, komórka) zostały po odcinku dalekim - nieużywane
// 5. argument: plik nadajników (domyślnie FM 2018), 6.: katalog wyjścia w mapa/dane (domyślnie fm). Radio i TV 2026:
//   node fm.mjs 3000 60 120 uke-2026/rtv.json rtv
const WEJSCIE = process.argv[5] ?? "uke-fm/fm-100km.json", WYJSCIE = process.argv[6] ?? "fm";


function npy(p) {                                                    // float32, C-order, little endian
  const b = readFileSync(p), hl = b.readUInt16LE(8), h = b.toString("latin1", 10, 10 + hl);
  if (!h.includes("'<f4'") || h.includes("True")) throw new Error(`nieobslugiwany npy: ${p} ${h}`);
  const shape = h.match(/\((\d+), (\d+)\)/).slice(1).map(Number);
  const a = new Float32Array(b.buffer.slice(b.byteOffset + 10 + hl, b.byteOffset + b.length)); a.ksztalt = shape; return a;
}
// Miejsce: zmienna MIEJSCE jak w dane/nmpt/miejsce.py (garwolin - domyslne katalogi, inne - przyrostek "-<nazwa>").
const MIEJSCE = process.env.MIEJSCE ?? "garwolin", przyrostek = (n) => (MIEJSCE === "garwolin" ? n : `${n}-${MIEJSCE}`);
// mozaika kafli 1 stopien (wiersz 0 = polnoc). Garwolin: N52 E020..E022 nad N51 E020..E022 (jak dotad);
// Warszawa (52,23 N, 21,01 E; nadajniki do 120 km): N53..N51 x E019..E022
const KAF = MIEJSCE === "garwolin" ? [["N52E020", "N52E021", "N52E022"], ["N51E020", "N51E021", "N51E022"]]
  : [53, 52, 51].map((la) => [19, 20, 21, 22].map((lo) => `N${la}E0${lo}`));
const LAT_TOP = MIEJSCE === "garwolin" ? 53 : 54, LON_L = MIEJSCE === "garwolin" ? 20 : 19;
const k0 = npy(join(DANE, "dem/N52E021.npy")), [kh, kw] = k0.ksztalt;
const nw = KAF.length, nk = KAF[0].length;
const M = new Float32Array(nw * kh * nk * kw); M.ksztalt = [nw * kh, nk * kw];
KAF.forEach((wiersz, a) => wiersz.forEach((n, b) => {
  const k = npy(join(DANE, `dem/${n}.npy`));
  for (let i = 0; i < kh; i++) M.set(k.subarray(i * kw, (i + 1) * kw), (a * kh + i) * nk * kw + b * kw);
}));
// T + meta terenu: przygotuj/teren.py (dla Garwolina T bit w bit jak w dane/rynek)
const { meta, t } = await wczytajZestaw(join(HERE, "../dane", przyrostek("teren")), async (p) => new Uint8Array(readFileSync(p)));
const mt = { ...(meta.teren ?? meta), LAT_TOP, LON_L, M_wiersz0: 0, M_kolumna0: 0, M_ksztalt_calej: M.ksztalt };
const wysokosc = probnikDolek(mt, { T: t.T, M });
const { SR, KX, KY } = mt;

// nadajniki: bez powtórzeń (to samo miejsce, częstotliwość i program -> najpóźniej ważne pozwolenie)
const fm = JSON.parse(readFileSync(join(DANE, WEJSCIE), "utf8"));
const jedn = new Map();
for (const s of fm.stacje) {
  if (s.km > R_KM || !s.erp_kw || !s.hant) continue;
  const k = `${s.typ ?? "fm"},${s.lat.toFixed(3)},${s.lon.toFixed(3)},${s.mhz.toFixed(1)}`;
  const o = jedn.get(k); if (!o || (s.waznosc || "") > (o.waznosc || "")) jedn.set(k, s);
}
// grupy profilu: miejsce (do ~100 m) + wysokość anteny -> jedno umax dla wszystkich programów grupy
const grupy = new Map();
for (const s of jedn.values()) {
  const k = `${s.lat.toFixed(3)},${s.lon.toFixed(3)},${s.hant}`;
  if (!grupy.has(k)) {
    const x = (s.lon - SR[1]) * KX, y = (s.lat - SR[0]) * KY;
    grupy.set(k, { id: grupy.size, x, y, z: wysokosc(x, y) + s.hant, hant: s.hant, hter_uke: s.hter, programy: [] });
  }
  grupy.get(k).programy.push({ typ: s.typ ?? "fm", kanal: s.kanal, system: s.system, mhz: s.mhz, program: s.program, stacja: s.stacja, erp_kw: s.erp_kw, pol: s.pol,
                               tlumienie_db: s.tlumienie_db, waznosc: s.waznosc });
}

const G = [...grupy.values()];
// ITU-R P.1546 §3 / heffCalc: wysokość efektywna = antena + grunt pod masztem - średni teren 3–15 km od nadajnika w stronę
// rynku (dla d < 15 km: od 0,2 d do d); profil co 100 m, średnia trapezami. Strona liczy z niej h1 (silnik/p1546.js).
for (const g of G) {
  const d = Math.hypot(g.x, g.y) / 1000, [a, b] = d >= 15 ? [3, 15] : [0.2 * d, d], kroki = Math.max(2, Math.round((b - a) * 10));
  const h = Array.from({ length: kroki + 1 }, (_, k) => { const s = (a + (b - a) * k / kroki) / d; return wysokosc(g.x * (1 - s), g.y * (1 - s)); });
  const sr = h.reduce((acc, v, k) => acc + (k ? (v + h[k - 1]) / 2 : 0), 0) / kroki;
  g.grunt = Math.round(g.z - g.hant); g.heff = Math.round(g.z - sr);
  console.log(`${String(g.id).padStart(3)} ${g.programy[0].stacja.slice(0, 22).padEnd(22)} ${d.toFixed(1).padStart(5)} km  Hant ${String(g.hant).padStart(3)} m  heff ${String(g.heff).padStart(4)} m  programów ${g.programy.length}`);
}
const OUT = join(HERE, "../dane", `${przyrostek(WYJSCIE)}.json`);
writeFileSync(OUT, JSON.stringify({
  meta: { grupy: G, uwaga: "SYMULACJA, nie pomiar; pole liczy strona wg ITU-R P.1546-6 (silnik/p1546.js)",
    zrodla: [WYJSCIE === "fm" ? "Nadajniki FM: UKE, wykaz pozwoleń radiowych UKF FM, stan 2018-10-01, przetworzone" : "Nadajniki FM, DAB+, DVB-T: UKE, wykaz pozwoleń radiowych, stan 2026-09-18, przetworzone",
             "NMT: GUGiK (geoportal.gov.pl)",
             "Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"] },
}));
console.log(`${G.length} grup -> ${OUT}`);
