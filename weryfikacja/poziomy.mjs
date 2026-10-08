// Poziomy przyblizenia (docs §7.5): mapa okna Garwolina (5,76 km, punkty co 16 m jak "cala mapa" na stronie) liczona na warstwach
// miasta 4 m (paczki), 16 m (E...-16.pak) i 100 m (E...-100.pak, sam teren). Te same punkty, ten sam teren dalej (T/Copernicus) -
// roznica to wylacznie warstwa miasta. Komorkowe: min strata L w 4 grupach pasm (stacje jak na stronie); radio/TV: natezenie E.
// Uzycie: [HRX=1.5] [RODZAJ=lte] [BAZA16=katalog z -16.pak] [BAZA100=katalog z -100.pak, np. z NMT 100 m kraju] node poziomy.mjs
import { readFileSync } from "node:fs";
import { wczytajZestaw } from "../silnik/dane.js";
import { POZIOMY, warstwyPoziomu } from "../silnik/paczka.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { widokZPunktu, fmZPunktu, poleNaSiatce } from "../silnik/punkt.js";
const M = new URL("../", import.meta.url).pathname, TEL = M + "telefon/", PAK = M + "dane/paczki/v1/";
const BAZA16 = process.env.BAZA16, BAZA100 = process.env.BAZA100;
globalThis.fetch = async (u) => { try { const p = BAZA16 && u.endsWith("-16.pak") ? BAZA16 + "/" + u.split("/").pop()
    : BAZA100 && u.endsWith("-100.pak") ? BAZA100 + "/" + u.split("/").pop() : TEL + u;
  const b = readFileSync(p); return { ok: true, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length) }; } catch { return { ok: false }; } };
const czytaj = async (p) => new Uint8Array(readFileSync(TEL + p)), json = (p) => JSON.parse(readFileSync(M + "dane/" + p, "utf8"));
const HRX = +(process.env.HRX ?? 1.5), RODZAJ = process.env.RODZAJ ?? "lte";
const { meta, t } = await wczytajZestaw("../dane/obszar-2880-2180-z", czytaj);
const m = meta.miasto, U = meta.uklad, teren = { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU };
const sc = (mi) => ({ miasto: mi, teren, R_E: meta.R_E, podstawaKorony: meta.PODSTAWA_KORONY });

// sceny: okno miasta w ukladzie mapy (metry od E0/N0), komorka poziomu; 100 m - okno wyrownane do 100 m obejmujace 5,76 km
const pamiec = new Map(), sceny = {};
for (const p of POZIOMY) {
  const x0 = Math.floor((U.E0 + m.X0) / p.m) * p.m, y1 = Math.ceil((U.N0 + m.Y1) / p.m) * p.m;
  const n = Math.ceil((U.E0 + m.X0 + m.nx * m.DX - x0) / p.m), t0 = performance.now();
  const w = await warstwyPoziomu("../dane/paczki/v1", p, x0, y1, n, n, pamiec);
  sceny[p.nazwa] = { ...w, mi: { nx: n, ny: n, X0: x0 - U.E0, Y1: y1 - U.N0, DX: p.m, DY: p.m, O: w.O, G: w.G, ZW: w.ZW } };
  console.log(`${p.nazwa}: ${n} x ${n} po ${p.m} m, pliki ${w.paczki}/${w.z} ${(w.bajty / 1e6).toFixed(2)} MB, ${(100 * w.komorek / (n * n)).toFixed(1)}% z danymi, ${Math.round(performance.now() - t0)} ms`);
}
// kontrola pliku 16 m: G 16 m = srednia 4 x 4 z paczki 4 m (niezaleznie od paczka.py), do kwantyzacji 5 cm
{ const a = sceny.ulica, b = sceny.okolica; let zle = 0, mx = 0;
  for (let i = 0; i < b.mi.ny; i++) for (let j = 0; j < b.mi.nx; j++) {
    const i4 = (a.mi.Y1 - b.mi.Y1 + i * 16) / 4, j4 = (b.mi.X0 - a.mi.X0 + j * 16) / 4; if (i4 < 0 || j4 < 0 || i4 + 4 > a.mi.ny || j4 + 4 > a.mi.nx) continue;
    let s = 0; for (let di = 0; di < 4; di++) for (let dj = 0; dj < 4; dj++) s += a.G[(i4 + di) * a.mi.nx + j4 + dj];
    const d = Math.abs(s / 16 - b.G[i * b.mi.nx + j]); mx = Math.max(mx, d); if (d > 0.0251 + 0.0251) zle++; }
  console.log(`kontrola G 16 m wobec sredniej z 4 m: max roznica ${mx.toFixed(3)} m, poza kwantyzacja ${zle}`); }

// punkty: siatka strony "cala mapa" (k = 4 na 4 m: srodek bloku 4 x 4), wysokosc odbiornika = grunt poziomu + HRX
const K = 4, nm = Math.floor(m.nx / K), xs = Float64Array.from({ length: nm }, (_, j) => m.X0 + (j * K + (K >> 1) + 0.5) * m.DX);
const ys = Float64Array.from({ length: nm }, (_, i) => m.Y1 - (i * K + (K >> 1) + 0.5) * m.DY);
const odb = (s) => { const Z = new Float32Array(nm * nm), mi = s.mi;
  for (let i = 0; i < nm; i++) for (let j = 0; j < nm; j++) Z[i * nm + j] = mi.G[Math.floor((mi.Y1 - ys[i]) / mi.DY) * mi.nx + Math.floor((xs[j] - mi.X0) / mi.DX)] + HRX;
  return { xs, ys, Z }; };

const st = json("stacje-2180.json").stacje, MHZ = (b) => +(b.match(/(\d+)$/)?.[1] ?? 0);
const RE = { lte: (b) => /^lte(?!4[25]0)/.test(b), "5g": (b) => b.startsWith("5g"), wszystko: () => true }[RODZAJ];
const GR = [[806, (f) => f < 1000], [1842, (f) => f >= 1000 && f < 2000], [2140, (f) => f >= 2000 && f < 3000], [3600, (f) => f >= 3000]];
const A = sceny.ulica, g0 = A.G[(A.mi.ny >> 1) * A.mi.nx + (A.mi.nx >> 1)];
const ls = widokZPunktu({ x: 0, y: 0 }, st, sc(A.mi), { hRx: HRX, gruntPunktu: g0 }).map((s) => ({ ...s, pasma: s.pasma.filter(RE) })).filter((s) => s.pasma.length);
const zaKr = (s) => Math.max(m.X0 - s.x, s.x - (m.X0 + m.nx * m.DX), (m.Y1 - m.ny * m.DY) - s.y, s.y - m.Y1, 0);
const grube = ls.filter((s) => zaKr(s) <= 3000);
function mapaKom(s) {
  const o = odb(s), MAPA = GR.map(() => new Float32Array(nm * nm).fill(Infinity)), t0 = performance.now();
  for (const q of grube) {
    const T = [q.x, q.y, teren.wysokosc(q.x, q.y) + q.h_ant_uzyta], geo = geometriaLaczona(o, T, sc(s.mi));
    GR.forEach(([f, g], gi) => { if (!q.pasma.some((b) => g(MHZ(b)))) return;
      const L = stratyLaczone(o, T, geo, f, { rozpraszanie: true }).L; for (let k = 0; k < L.length; k++) if (L[k] < MAPA[gi][k]) MAPA[gi][k] = L[k]; });
  }
  return { MAPA, ms: performance.now() - t0 };
}
const fm = json("rtv-2180.json");
const top = (typ) => [...new Set(fmZPunktu({ x: 0, y: 0 }, { ...fm, meta: { ...fm.meta, grupy: fm.meta.grupy.map((g) => ({ ...g, programy: g.programy.filter((p) => (p.typ ?? "fm") === typ) })) } },
  sc(A.mi), { hRx: HRX, gruntPunktu: g0 }).map((p) => p.gi))].slice(0, 3);
const RT = { fm: top("fm"), dvbt: top("dvbt") };
function mapaRtv(s) { const o = odb(s), w = {}; for (const [typ, gis] of Object.entries(RT)) w[typ] = gis.map((gi) => poleNaSiatce(o, fm, gi, typ, sc(s.mi), HRX)); return w; }

const jasL = (L) => Math.min(Math.max((135 - L) / 50, 0), 1);
const q = (a, p) => a[Math.floor(p * (a.length - 1))];
function porownaj(nazwa, a, b) {
  for (let gi = 0; gi < GR.length; gi++) {
    const d = [], A_ = a.MAPA[gi], B_ = b.MAPA[gi]; let j10 = 0;
    for (let k = 0; k < A_.length; k++) if (isFinite(A_[k]) && isFinite(B_[k])) { d.push(B_[k] - A_[k]); if (Math.abs(jasL(B_[k]) - jasL(A_[k])) > 0.1) j10++; }
    if (!d.length) continue; const ab = d.map(Math.abs).sort((x, y) => x - y), sd = [...d].sort((x, y) => x - y);
    console.log(`  ${nazwa} ${GR[gi][0]} MHz: |dL| > 1 dB ${(100 * ab.filter((x) => x > 1).length / ab.length).toFixed(2)}%, > 3 dB ${(100 * ab.filter((x) => x > 3).length / ab.length).toFixed(2)}%, ` +
      `> 10 dB ${(100 * ab.filter((x) => x > 10).length / ab.length).toFixed(2)}%; dL mediana ${q(sd, .5).toFixed(2)}, 5% ${q(sd, .05).toFixed(1)}, 95% ${q(sd, .95).toFixed(1)} dB; jasnosc > 10% ${(100 * j10 / ab.length).toFixed(2)}%`);
  }
}
function porownajRtv(nazwa, a, b) {
  for (const typ of Object.keys(RT)) { const d = [];
    a[typ].forEach((E, n) => { for (let k = 0; k < E.length; k++) if (isFinite(E[k]) && isFinite(b[typ][n][k])) d.push(b[typ][n][k] - E[k]); });
    const ab = d.map(Math.abs).sort((x, y) => x - y), sd = [...d].sort((x, y) => x - y);
    console.log(`  ${nazwa} ${typ} (${RT[typ].length} grupy): |dE| > 1 dB ${(100 * ab.filter((x) => x > 1).length / ab.length).toFixed(2)}%, > 3 dB ${(100 * ab.filter((x) => x > 3).length / ab.length).toFixed(2)}%; dE mediana ${q(sd, .5).toFixed(2)}, 5% ${q(sd, .05).toFixed(1)}, 95% ${q(sd, .95).toFixed(1)} dB`);
  }
}
console.log(`HRX ${HRX} m, ${RODZAJ}: stacji w liczeniu ${grube.length}, punktow ${nm} x ${nm}${BAZA16 ? `, 16 m z ${BAZA16}` : ""}`);
const R = {}; for (const n of ["ulica", "okolica", "powiat"]) { R[n] = mapaKom(sceny[n]); R[n].rtv = mapaRtv(sceny[n]); console.log(`${n}: komorkowe ${(R[n].ms / 1000).toFixed(1)} s`); }
porownaj("okolica (16 m) wobec ulicy (4 m)", R.ulica, R.okolica); porownajRtv("okolica wobec ulicy", R.ulica.rtv, R.okolica.rtv);
porownaj("powiat (100 m, sam teren) wobec ulicy", R.ulica, R.powiat); porownajRtv("powiat wobec ulicy", R.ulica.rtv, R.powiat.rtv);
