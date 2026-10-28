"""ADR 0003 §b: size of the event-variance leak of event-blind 30-day interpolation, over the vendor expiry grid.

Written for the milestone-0 methodology review (ledger N3). Assumptions, all stated in ADR 0003 §b:
- target horizon tau* = 21 sessions; the event lies beyond tau* (so the 30-day horizon should exclude it);
- the bracketing expiries are a CLEAN one at tau_a in 17..21 sessions (the vendor's second expiry) and a SPANNING one at
  tau_b in 27..42 sessions (the vendor's third, monthly expiry); every (tau_a, tau_b) pair is counted once (80 pairs);
- flat diffusive vol sigma_d = 25% (annualised, session clock), two-component model w_j = sigma_d^2 tau_j / 252 + E 1[spans].
Leak fraction f = (tau* - tau_a) / (tau_b - tau_a); leaked IV = sqrt(sigma_d^2 + 252 E f / 21); leak = that minus sigma_d.
Run: uv run --no-sync --frozen python research/prototypes/leak_grid.py > research/prototypes/leak_grid.out.txt
"""
import numpy as np

SIG = 0.25
f = np.array([(21 - ta) / (tb - ta) for ta in range(17, 22) for tb in range(27, 43)])
print(f"pairs {f.size}; leak fraction f: min {f.min():.3f}, median {np.median(f):.3f}, max {f.max():.3f} "
      f"(max at tau_a=17, tau_b=27; f = 0 whenever tau_a = 21)")
for E, label in ((0.0007, 'E = 0.0007'), (0.00088284, 'E = 0.000883 (AAPL worked example, ADR 0003 §c)'),
                 (0.003, 'E = 0.003 (about a 5.5% implied move)')):
    lk = 100 * (np.sqrt(SIG ** 2 + 252 * E * f / 21) - SIG)
    print(f"{label:48s}: leak in vol points min {lk.min():.2f}, median {np.median(lk):.2f}, max {lk.max():.2f}; "
          f"at the ADR's old example (19, 32) {100 * (np.sqrt(SIG**2 + 252 * E * (2 / 13) / 21) - SIG):.2f}")
