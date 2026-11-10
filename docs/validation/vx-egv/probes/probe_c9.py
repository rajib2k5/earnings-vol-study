"""C9 probe: block_counts is a moving-block bootstrap (overlapping, fixed length, with replacement, no wrap, cut to n).
usage: probe_c9.py <path-to-vx_crosscheck.py>   exit 0 = claim survived. Expected values come from the claim, not the code."""
import sys, importlib.util, numpy as np
path = sys.argv[1]
spec = importlib.util.spec_from_file_location('vxmod_under_test', path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
fails = []
def check(name, ok, info=''):
    print(('ok   ' if ok else 'FAIL ') + name, info)
    if not ok: fails.append(name)

class FakeRng:
    """records the integers() call and returns scripted block starts"""
    def __init__(self, starts): self.starts = np.asarray(starts); self.calls = []
    def integers(self, low, high=None, size=None, **kw):
        self.calls.append((low, high, size)); return self.starts

def ref(starts, n, l):  # reference built from the claim: join fixed-length contiguous blocks, no wrap, cut to n
    out = np.zeros((len(starts), n), dtype=int)
    for r, row in enumerate(starts):
        seq = np.concatenate([np.arange(s, s + l) for s in row])[:n]
        assert seq.max() < n  # no wrap needed when starts <= n-l
        for j in seq: out[r, j] += 1
    return out

# 1. support of the start draw: low 0, high (exclusive) n-l+1, shape (reps, ceil(n/l))
for n, l, reps in [(10, 4, 3), (12, 3, 2), (7, 7, 2), (9, 1, 2)]:
    nb = -(-n // l); f = FakeRng(np.zeros((reps, nb), dtype=int)); m.block_counts(n, l, reps, f)
    low, high, size = f.calls[0]
    check(f'start support n={n} l={l}: draws on [0, n-l] inclusive', low == 0 and high == n - l + 1, f'integers({low},{high},size={size})')
    check(f'  number of blocks = ceil(n/l)', tuple(size) == (reps, nb), f'size={size}')
# 2. exact contiguity / truncation / overlap / replacement with scripted starts
cases = [(10, 4, [[0, 6, 3], [2, 2, 2]]),      # n=10 l=4 nb=3 -> 12 cut to 10; second row: same start thrice (with replacement)
         (12, 3, [[0, 1, 2, 9], [9, 9, 0, 0]]),  # overlapping starts 0,1,2 ; last allowed start 9
         (7, 7, [[0], [0]]),
         (9, 1, [[8, 8, 0, 0, 3, 3, 3, 1, 8]])]
for n, l, st in cases:
    st = np.array(st); got = m.block_counts(n, l, len(st), FakeRng(st)); want = ref(st, n, l)
    check(f'counts == contiguous fixed-length blocks, cut to n (n={n}, l={l}, starts={st.tolist()})', np.array_equal(got, want), f'got={got.tolist()} want={want.tolist()}')
    check('  every row sums to n', bool((got.sum(axis=1) == n).all()))
# 3. no wrap-around: with the last start n-l, sessions 0.. must NOT be hit by the tail
st = np.array([[9, 9, 9, 9]]); got = m.block_counts(12, 3, 1, FakeRng(st))[0]
check('no wrap: starts at n-l never feed session 0..', got[:9].sum() == 0 and got[9:].sum() == 12 and got[9] == 4, str(got.tolist()))
# 4. real rng: seeded, expected per-session coverage under a non-circular moving block
n, l, reps = 12, 3, 100_000
c = m.block_counts(n, l, reps, np.random.default_rng(1)); nb = n // l
k = np.array([min(j, n - l) - max(0, j - l + 1) + 1 for j in range(n)])
exp = nb * k / (n - l + 1)
check('real rng: row sums == n', bool((c.sum(axis=1) == n).all()))
check('real rng: mean count per session matches moving-block (non-circular) expectation', np.allclose(c.mean(axis=0), exp, atol=0.02), f'mean={np.round(c.mean(axis=0),3).tolist()} exp={np.round(exp,3).tolist()}')
# with replacement: some replicate has a session drawn >= 2 times in non-overlapping... use l=1: pure iid draws
c1 = m.block_counts(9, 1, 5000, np.random.default_rng(2))
check('l=1 reduces to iid draws with replacement (some session drawn twice)', int(c1.max()) >= 2)
# determinism with seed
a = m.block_counts(30, 5, 50, np.random.default_rng(7)); b = m.block_counts(30, 5, 50, np.random.default_rng(7))
check('same seed same counts', np.array_equal(a, b))
print('FAIL' if fails else 'PASS', fails); sys.exit(1 if fails else 0)
