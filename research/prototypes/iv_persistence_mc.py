"""Illustrative Monte Carlo (pure Python): Patell-style time-series variance applied to persistent IV.
No event effect is simulated, so every rejection is a false positive (nominal 5%)."""
import random, math, statistics as st
rng = random.Random(7)
reps, L1, L2 = 5000, 120, 11
phi, sd_x, sd_e = 0.98, 0.01, 0.005
burn = 300
T = burn + L1 + L2
rejA = rejB = 0
ac_num = ac_den = 0.0
for _ in range(reps):
    x = [rng.gauss(0, sd_x/math.sqrt(1-phi**2))]
    for t in range(1, T): x.append(phi*x[-1] + rng.gauss(0, sd_x))
    iv = [0.40 + xi + rng.gauss(0, sd_e) for xi in x]
    est, evt = iv[burn:burn+L1], iv[burn+L1:]
    m = st.fmean(est)
    zA = sum(v - m for v in evt) / math.sqrt(L2 * st.variance(est))
    d = [iv[i] - iv[i-1] for i in range(burn, T)]
    d_est, d_evt = d[:L1], d[L1:]
    md = st.fmean(d_est)
    zB = sum(v - md for v in d_evt) / math.sqrt(L2 * st.variance(d_est))
    rejA += abs(zA) > 1.96; rejB += abs(zB) > 1.96
    dm = st.fmean(d_est)
    ac_num += sum((d_est[i]-dm)*(d_est[i-1]-dm) for i in range(1, L1)); ac_den += sum((v-dm)**2 for v in d_est)
print(f"pooled lag-1 autocorrelation of daily IV changes: {ac_num/ac_den:.3f}")
print(f"false-positive rate, abnormal IV LEVELS summed over 11 days: {rejA/reps:.3f}")
print(f"false-positive rate, abnormal IV CHANGES summed over 11 days: {rejB/reps:.3f}")
