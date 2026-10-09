// Pomiar fizyki silnika przed/po poprawce: prawdziwy wątek mapy (telefon/poziomy-praca.js) w Node, te same pliki danych
// co strona (dane/ lokalnie). Dla kilku punktów: stacje komórkowe do 10 km (jak karta punktu) i radio/TV. SYMULACJA.
// Uzycie: node weryfikacja/pomiar-fizyki.mjs [plik.json]   - zapisuje pełny wynik do pliku (porównanie przed/po: jq/diff)
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url)), TELEFON = join(HERE, "../telefon");
globalThis.fetch = async (u) => {                      // względem telefon/ (jak w wątku), bez parametrów zapytania
  const p = join(TELEFON, String(u).split("?")[0]);
  return existsSync(p) ? new Response(readFileSync(p)) : new Response(null, { status: 404 });
};
const wyniki = new Map();
globalThis.postMessage = (m) => { wyniki.get(m.id)?.(m); };
globalThis.onmessage = null;                           // wątek przypisuje onmessage bez deklaracji (Worker ma je w zasięgu)
await import("../telefon/poziomy-praca.js");
let nr = 0;
const zlec = (z) => new Promise((ok) => { const id = ++nr; wyniki.set(id, ok); globalThis.onmessage({ data: { ...z, id } }); });

// WGS84 -> EPSG:2180 (PL-1992: TM, południk 19°, k0 0,9993, GRS80)
function pl1992(lat, lon) {
  const a = 6378137, f = 1 / 298.257222101, e2 = f * (2 - f), k0 = 0.9993, ep2 = e2 / (1 - e2), r = Math.PI / 180;
  const fi = lat * r, l = (lon - 19) * r, N = a / Math.sqrt(1 - e2 * Math.sin(fi) ** 2), T = Math.tan(fi) ** 2, C = ep2 * Math.cos(fi) ** 2, A = l * Math.cos(fi);
  const M = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * fi - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * Math.sin(2 * fi)
    + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * Math.sin(4 * fi) - (35 * e2 ** 3 / 3072) * Math.sin(6 * fi));
  const E = 500000 + k0 * N * (A + (1 - T + C) * A ** 3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A ** 5 / 120);
  const Nn = -5300000 + k0 * (M + N * Math.tan(fi) * (A * A / 2 + (5 - T + 9 * C + 4 * C * C) * A ** 4 / 24 + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A ** 6 / 720));
  return [E, Nn];
}
const E0 = 679860, N0 = 451200;                         // rynek Garwolina (układ wątku)
const PUNKTY = [
  ["Warszawa, pl. Defilad", 52.2318, 21.0060],
  ["Garwolin, rynek", null, null],
  ["Nowy Sącz, dolina Dunajca", 49.6245, 20.6930],
  ["Zakopane, Krupówki (granica)", 49.2960, 19.9510],
];
const kr = JSON.parse(new TextDecoder().decode(await new Response(new Response(readFileSync(join(HERE, "../dane/kraj/stacje.json.gz"))).body
  .pipeThrough(new DecompressionStream("gzip"))).arrayBuffer()));
const stacje = kr.stacje.map(([x, y, h, op, pa, adres]) => ({ x, y, ...(h == null ? {} : { h_ant: h }), operatorzy: op.map((k) => kr.operatorzy[k]), pasma: pa.map((k) => kr.pasma[k]), adres }));

const wynik = {};
for (const [nazwa, lat, lon] of PUNKTY) {
  const P = lat == null ? { x: 0, y: 0 } : (([E, N]) => ({ x: E - E0, y: N - N0 }))(pl1992(lat, lon));
  const blisko = stacje.filter((s) => Math.hypot(s.x - P.x, s.y - P.y) <= 10000);
  const t0 = performance.now(), w = await zlec({ typ: "punkt", P, hRx: 1.5, stacje: blisko }), ms = performance.now() - t0;
  if (w.blad) throw new Error(`${nazwa}: ${w.blad}`);
  const st = w.stacje.map((s) => ({ adres: s.adres, km: +s.km.toFixed(2), ocena: s.ocena, krawedz_m: s.przeszkoda_m,
    pasma: Object.fromEntries(Object.entries(s.pasma_wynik).map(([p, r]) => [p, { nad: r.nadwyzka_db, zapas: r.zapas_db }])) }));
  const zasieg = { mocny: 0, slaby: 0, poza: 0 };
  for (const s of st) for (const r of Object.values(s.pasma)) zasieg[r.zapas >= 15 ? "mocny" : r.zapas >= 0 ? "slaby" : "poza"]++;
  const rtv = w.fm.map((p) => ({ typ: p.typ, program: p.program, stacja: p.stacja, km: +p.km.toFixed(1), E: p.E_dBuVm, ocena: p.ocena }));
  const ile = (t, o) => rtv.filter((p) => p.typ === t && p.ocena === o).length;
  wynik[nazwa] = { P: { x: Math.round(P.x), y: Math.round(P.y) }, scena: w.scena, ms: Math.round(ms), stacje: st, rtv };
  console.log(`\n${nazwa}  (${Math.round(P.x)}, ${Math.round(P.y)})  scena ${w.scena}, ${Math.round(ms)} ms, ${st.length} stacji`);
  console.log(`  komórki, pary stacja×pasmo: mocny ${zasieg.mocny} · słaby ${zasieg.slaby} · poza ${zasieg.poza}`);
  for (const s of st.slice(0, 5)) console.log(`  ${s.ocena.padEnd(10)} ${String(s.km).padStart(5)} km  krawędź ${String(s.krawedz_m ?? "-").padStart(5)} m  ` +
    Object.entries(s.pasma).slice(0, 4).map(([p, r]) => `${p} nad ${r.nad} zapas ${r.zapas}`).join(" | "));
  for (const t of ["fm", "dab", "dvbt"]) console.log(`  ${t.padEnd(4)}: słychać ${ile(t, "slychac")} · granica ${ile(t, "granica")} · nie ${ile(t, "nie") + w.reszta[t]}`);
  for (const p of rtv.filter((p) => p.typ === "fm").slice(0, 3)) console.log(`    fm ${p.E.toFixed(1)} dBµV/m ${p.ocena} ${p.program} (${p.stacja}, ${p.km} km)`);
}
if (process.argv[2]) writeFileSync(process.argv[2], JSON.stringify(wynik, null, 1));
