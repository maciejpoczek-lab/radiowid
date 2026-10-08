// Wczytanie zestawu manifest.json + *.bin (eksport.py) - w przegladarce przez fetch, w Node przez fs.
// Tablice z polem "kodowanie" (przygotuj/kompresuj.py) leza w *.bin.gz: gzip, opcjonalnie int16 w decymetrach z roznicami
// wzdluz wiersza i wysokoscia liczona od innej tablicy ("baza", np. O nad G). Dekodowanie bit w bit wzgledem kodera.
const TYP = { float32: Float32Array, float64: Float64Array, uint8: Uint8Array, int16: Int16Array };

const rozpakuj = async (b) =>
  new Uint8Array(await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());

function zInt16(d, o) {                                  // roznice int16 modulo 2^16 -> float32 (NaN dla braku)
  const k = o.kodowanie, w = o.ksztalt[o.ksztalt.length - 1], a = new Float32Array(d.length);
  for (let p = 0; p < d.length; p += w) {
    let v = 0;
    for (let j = 0; j < w; j++) {
      v = k.roznice ? (v + d[p + j]) << 16 >> 16 : d[p + j];
      a[p + j] = v === k.brak ? NaN : v * k.skala;
    }
  }
  return a;
}

export async function wczytajZestaw(baza, czytaj) {
  czytaj ??= async (p) => new Uint8Array(await (await fetch(p)).arrayBuffer());
  const man = JSON.parse(new TextDecoder().decode(await czytaj(`${baza}/manifest.json`)));
  const t = {};
  await Promise.all(Object.entries(man.tablice).map(async ([n, o]) => {
    if (!o.kodowanie) {
      const b = await czytaj(`${baza}/${n}.bin`);
      t[n] = new TYP[o.dtype](b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength));
    } else {
      const b = await rozpakuj(await czytaj(`${baza}/${n}.bin.gz`));
      t[n] = o.kodowanie.int16 ? zInt16(new Int16Array(b.buffer), o) : new TYP[o.dtype](b.buffer);
    }
    t[n].ksztalt = o.ksztalt;
  }));
  for (const [n, o] of Object.entries(man.tablice)) {     // wysokosci liczone od innej tablicy (O = G + wysokosc nad G)
    const z = o.kodowanie?.baza; if (!z) continue;
    const a = t[n], g = t[z]; for (let k = 0; k < a.length; k++) a[k] = Math.fround(a[k] + g[k]);
  }
  return { meta: man.meta, t };
}
