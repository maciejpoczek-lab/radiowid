// Widok z punktu (silnik/punkt.js) na danych wokół rynku: lista stacji UKE z kierunkiem anteny dla RYNKU (punkt publiczny).
// Kontrola spójności: wynik dla jednego punktu == ten sam punkt wyjęty z siatki miasta (geometriaLaczona na całej siatce).
// Uzycie: [ZESTAW=obszar-2880-z] node punkt.mjs [x_m y_m]   (metry od rynku; domyślnie rynek, zestaw "rynek")
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";
import { widokZPunktu, PASMA_MHZ } from "../silnik/punkt.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const { meta, t } = await wczytajZestaw(join(HERE, "../dane", process.env.ZESTAW || "rynek"), async (p) => new Uint8Array(readFileSync(p)));
const m = meta.miasto;
const miasto = { ...m, O: t.O, G: t.G, ZW: t.ZW };
const teren = { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU };
const scena = { miasto, teren, R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY };
const stacje = JSON.parse(readFileSync(join(HERE, "../dane/stacje.json"), "utf8")).stacje;

// punkt = środek komórki miasta (żeby porównać z siatką); grunt z siatki miasta jak na mapie
const [px, py] = process.argv.length > 3 ? [+process.argv[2], +process.argv[3]] : [0, 0];
const j = Math.floor((px - m.X0) / m.DX), i = Math.floor((m.Y1 - py) / m.DY);
const P = { x: m.X0 + (j + 0.5) * m.DX, y: m.Y1 - (i + 0.5) * m.DY }, g = t.G[i * m.nx + j];
const t0 = performance.now();
const w = widokZPunktu(P, stacje, scena, { hRx: meta.H_RX, gruntPunktu: g });
const ms = performance.now() - t0;

// kontrola: 3 wiersze siatki wokół punktu, cała szerokość - ta sama nadwyżka co w widokZPunktu
const odb = { xs: Float64Array.from({ length: m.nx }, (_, k) => m.X0 + (k + 0.5) * m.DX),
              ys: Float64Array.from({ length: m.ny }, (_, k) => m.Y1 - (k + 0.5) * m.DY),
              Z: Float32Array.from(t.G, (v) => v + meta.H_RX) };
let zle = 0;
for (const s of w.slice(0, 8)) {
  const T = [s.x, s.y, teren.wysokosc(s.x, s.y) + s.h_ant_uzyta];
  const geo = geometriaLaczona(odb, T, { ...scena, wiersze: [i, i + 1] });
  for (const [p, r] of Object.entries(s.pasma_wynik)) {
    const nad = stratyLaczone(odb, T, geo, PASMA_MHZ[p], { rozpraszanie: true }).nad[j];
    if (Math.abs(nad - r.nadwyzka_db) > 0.051) { zle++; console.log("ZLE", s.adres, p, nad, r.nadwyzka_db); }
  }
}

console.log(`SYMULACJA - zestaw ${process.env.ZESTAW || "rynek"}, widok z punktu (${P.x.toFixed(0)}, ${P.y.toFixed(0)}) m od rynku, ${stacje.length} stacji, ${ms.toFixed(0)} ms`);
for (const s of w) {
  const ops = s.operatorzy.map((o) => o.split(" ")[0]).join("+");
  console.log(`${s.ocena.padEnd(10)} az ${String(s.azymut).padStart(3)}°  ${s.km.toFixed(2).padStart(5)} km  ` +
    `nadwyżka ${s.nadwyzka_min_db.toFixed(1).padStart(5)}–${s.nadwyzka_max_db.toFixed(1).padStart(5)} dB  ` +
    `antena ${s.h_ant_uzyta} m${s.h_ant_zalozona ? "*" : " "}  ${ops.padEnd(18)} ${s.adres.slice(0, 34)}` +
    (s.przeszkoda_m != null ? `  krawędź ${s.przeszkoda_m} m od punktu` : ""));
}
console.log("* wysokość anteny ZAŁOŻONA (rejestr UKE jej nie podaje)");
console.log(zle ? `${zle} kontroli ZLE` : "kontrola OK: punkt == ta sama komórka siatki (8 pierwszych stacji, wszystkie pasma)");
process.exitCode = zle ? 1 : 0;
