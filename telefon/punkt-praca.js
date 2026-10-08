// Wątek roboczy strony „widok z punktu”: dane zestawu (miasto + teren), stacje UKE i FM.
//   hRx (opcjonalnie) - wysokość anteny odbiorczej nad gruntem [m] (suwak); bez niej meta.H_RX = 1,5 m
//   {typ: "punkt", P}              -> lista stacji z kierunkiem i oceną + lista FM (silnik/punkt.js)
//   {typ: "swiatlo", okno, S, f[]} -> straty całkowite L [dB] w próbkach okna dla każdej częstotliwości;
//   {typ: "wysokosci", P, hs[], rodzaj} -> radio/TV danego rodzaju w punkcie dla każdej wysokości anteny z hs
//   {typ: "pole", okno, gi, rodzaj, program?} -> natężenie pola [dBµV/m] grupy nadajników radia/TV gi (rodzaj: fm|dab|dvbt),
//                                     z program - tylko ten program/multipleks;
//                                     S = {x, y, h} stacji, wysokość anteny nad gruntem (grunt liczy wątek)
// Położenie punktu nie opuszcza telefonu: wątek nie wysyła żadnych zapytań poza wczytaniem plików zestawu.
import { geometriaLaczona, stratyLaczone } from "../silnik/laczony.js";
import { probnikDolek } from "../silnik/teren-dolek.js";
import { wczytajZestaw } from "../silnik/dane.js";
import { nalozPaczki } from "../silnik/paczka.js";
import { widokZPunktu, fmZPunktu, poleNaSiatce } from "../silnik/punkt.js";

let stan;
// okno {i0, j0, n, k}: n × n próbek co k komórek (k = 1 - każda komórka 4 m; k = 4 - cała mapa co 16 m), próbka w środku bloku
function siatka(s, m, { i0, j0, n, k = 1 }, hRx) {
  const c = (a) => a * k + (k >> 1);
  const xs = Float64Array.from({ length: n }, (_, j) => m.X0 + (j0 + c(j) + 0.5) * m.DX);
  const ys = Float64Array.from({ length: n }, (_, i) => m.Y1 - (i0 + c(i) + 0.5) * m.DY);
  const Z = new Float32Array(n * n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) Z[i * n + j] = s.t.G[(i0 + c(i)) * m.nx + j0 + c(j)] + (hRx ?? s.meta.H_RX);
  return { xs, ys, Z };
}
async function przygotuj(zestaw, prz = "", paczki = false) {   // prz: przyrostek miejsca ("" Garwolin, "-warszawa")
  const [{ meta, t }, fm, st] = await Promise.all([wczytajZestaw(`../dane/${zestaw}`), fetch(`../dane/rtv${prz}.json`).then((r) => r.json()),
    fetch(`../dane/stacje${prz}.json`).then((r) => r.json())]);
  if (paczki) await nalozPaczki(meta, t, "../dane/paczki/v1");     // te same warstwy co strona (pliki z pamieci przegladarki)
  const m = meta.miasto;
  return { meta, t, fm, stacje: st.stacje, miasto: { ...m, O: t.O, G: t.G, ZW: t.ZW },
           teren: { wysokosc: probnikDolek(meta.teren, t), krok: meta.KROK_TERENU } };
}

onmessage = async ({ data: z }) => {
  stan ??= przygotuj(z.zestaw, z.prz, z.paczki);
  const s = await stan, m = s.meta.miasto, scena = { miasto: s.miasto, teren: s.teren, R_E: s.meta.R_E, podstawaKorony: s.meta.PODSTAWA_KORONY };
  if (z.typ === "punkt") {
    const j = Math.floor((z.P.x - m.X0) / m.DX), i = Math.floor((m.Y1 - z.P.y) / m.DY), g = s.t.G[i * m.nx + j];
    const op = { hRx: z.hRx ?? s.meta.H_RX, gruntPunktu: g };
    postMessage({ id: z.id, stacje: widokZPunktu(z.P, s.stacje, scena, op), fm: fmZPunktu(z.P, s.fm, scena, op) });
  } else if (z.typ === "wysokosci") {                  // radio/TV w punkcie na kilku wysokościach anteny: od ilu metrów jest odbiór
    const j = Math.floor((z.P.x - m.X0) / m.DX), i = Math.floor((m.Y1 - z.P.y) / m.DY), g = s.t.G[i * m.nx + j];
    const fm = { ...s.fm, meta: { ...s.fm.meta, grupy: s.fm.meta.grupy.map((gr) => ({ ...gr, programy: gr.programy.filter((p) => (p.typ ?? "fm") === z.rodzaj) })) } };
    postMessage({ id: z.id, wys: z.hs.map((h) => ({ h, fm: fmZPunktu(z.P, fm, scena, { hRx: h, gruntPunktu: g })
      .map(({ gi, program, kanal, E_dBuVm, ocena }) => ({ gi, program, kanal, E: E_dBuVm, ocena })) })) });
  } else if (z.typ === "swiatlo") {
    const odb = siatka(s, m, z.okno, z.hRx);
    const T = [z.S.x, z.S.y, s.teren.wysokosc(z.S.x, z.S.y) + z.S.h];
    const geo = geometriaLaczona(odb, T, scena);
    const L = z.f.map((f) => stratyLaczone(odb, T, geo, f, { rozpraszanie: true }).L);
    postMessage({ id: z.id, L }, L.map((a) => a.buffer));
  } else if (z.typ === "pole") {                       // radio/TV: natężenie [dBµV/m] grupy nadajników gi w próbkach okna
    const E = poleNaSiatce(siatka(s, m, z.okno, z.hRx), s.fm, z.gi, z.rodzaj, scena, z.hRx ?? s.meta.H_RX, z.program);
    postMessage({ id: z.id, E }, [E.buffer]);
  }
};
