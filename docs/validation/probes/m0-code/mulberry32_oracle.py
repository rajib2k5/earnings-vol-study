"""C8.2 probe: an independent mulberry32 (written from the published C reference, uint32 masks,
not translated from rng.ts) to check the oracle values pinned in app/src/lib/rng.test.ts.

C reference (Tommy Ettinger, public domain):
    uint32_t mulberry32(uint32_t *s) {
        uint32_t z = (*s += 0x6D2B79F5UL);
        z = (z ^ (z >> 15)) * (z | 1UL);
        z ^= z + (z ^ (z >> 7)) * (z | 61UL);
        return z ^ (z >> 14);
    }
The JS port divides the uint32 by 2**32.
"""
M = 0xFFFFFFFF

def mulberry32(seed):
    s = seed & M
    def nxt():
        nonlocal s
        s = (s + 0x6D2B79F5) & M
        z = s
        z = ((z ^ (z >> 15)) * (z | 1)) & M
        z ^= (z + (((z ^ (z >> 7)) * (z | 61)) & M)) & M
        z &= M
        return (z ^ (z >> 14)) / 2**32
    return nxt

PINNED = {0: [0.26642920868471265, 0.0003297457005828619, 0.2232720274478197],
          42: [0.6011037519201636, 0.44829055899754167, 0.8524657934904099]}
ok = True
for seed, want in PINNED.items():
    r = mulberry32(seed)
    got = [r(), r(), r()]
    same = got == want
    ok &= same
    print(f"seed {seed}: got {got}\n         pinned {want}  equal={same}")
print("ALL EQUAL" if ok else "MISMATCH")
