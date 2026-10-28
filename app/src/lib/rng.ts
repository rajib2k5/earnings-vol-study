/**
 * Seeded random numbers. This is the ONLY source of randomness allowed in the app (and its
 * tests): `Math.random()` is never used, so every illustrative shape is reproducible.
 */

/**
 * mulberry32: a tiny 32-bit PRNG. Returns a function that yields uniform numbers in [0, 1);
 * the same seed always gives the same sequence.
 */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** One approximately standard-normal draw (Box-Muller) from a uniform generator. */
export function gaussian(rand: () => number): number {
  // 1 - rand() lies in (0, 1], so log() never sees zero.
  const u = 1 - rand()
  const v = rand()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}
