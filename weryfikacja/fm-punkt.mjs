// Radio i TV z punktu (silnik/punkt.js, fmZPunktu; pole wg ITU-R P.1546) na obszarze 6 km: lista programów z natężeniem
// pola i oceną. SYMULACJA. Uzycie: node fm-punkt.mjs [x_m y_m [h_odbiornika_m]]
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";
import { fmZPunktu } from "../silnik/punkt.js";
const HERE = dirname(fileURLToPath(import.meta.url)), cz = async (p) => new Uint8Array(readFileSync(p));
const { meta, t } = await wczytajZestaw(join(HERE, "../dane/obszar-2880-z"), cz);
const fm = JSON.parse(readFileSync(join(HERE, "../dane/rtv.json"), "utf8"));
// poza wycinkiem zestawu teren nieznany (kąt prześwitu sięga 16 km): -Infinity = brak przeszkody, jak w wątku mapy 0 m za granicą
const bezpieczny = (h) => (x, y) => { try { return h(x, y); } catch { return -Infinity; } };
const scena = { miasto: { ...meta.miasto, O: t.O, G: t.G, ZW: t.ZW }, teren: { wysokosc: bezpieczny(probnikDolek(meta.teren, t)), krok: 30 }, R_E: meta.R_E };
const P = { x: +(process.argv[2] ?? 0), y: +(process.argv[3] ?? 0) };
const t0 = performance.now(); const w = fmZPunktu(P, fm, scena, { hRx: +(process.argv[4] ?? 1.5) }); const ms = performance.now() - t0;
console.log(`SYMULACJA - radio/TV z punktu (${P.x}, ${P.y}) m od rynku: ${w.length} programów, ${ms.toFixed(0)} ms`);
for (const p of w.filter((p) => p.ocena !== "nie").concat(w.filter((p) => p.ocena === "nie").slice(0, 5)))
  console.log(`${p.typ.padEnd(4)} ${p.ocena.padEnd(8)} ${p.E_dBuVm.toFixed(1).padStart(5)} dBµV/m  ${p.mhz.toFixed(1).padStart(5)} MHz  ${p.program.slice(0, 26).padEnd(26)} ` +
    `${p.stacja.slice(0, 18).padEnd(18)} ${p.km.toFixed(1).padStart(5)} km az ${String(p.azymut).padStart(3)}°  ERP ${p.erp_kw} kW  h1 ${p.h1} m  strata u odbiornika ${p.zaslona_db} dB (${p.krawedz})`);
