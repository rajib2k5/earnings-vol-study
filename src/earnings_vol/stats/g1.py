# =============================================================================
# g1.py — Gate G1: the size of the primary statistics at the REAL event
# design (ADR 0005 §5 item 4). It rebuilds research/prototypes/h2h3_size_sim.py
# with the three changes the ADR asks for:
#   1. the events are the real primary events after milestones 1-3: their
#      day-0 dates, firms, sectors and merged seasons, and their baselines
#      with the real holes (other events' zones) and missing sessions (a
#      simulated value is dropped wherever the real cm30_iv is missing);
#   2. every input is estimated in every replication by the package's own
#      functions: beta per firm, the baseline means, ALIV, the abnormal
#      changes, s_i, R-hat, SA_i (panel/abnormal.py), and every statistic
#      (stats/suite.py, the code that makes the reported rows);
#   3. the data-generating processes are the stress designs of ADR 0005 §2g
#      and §5 and a CALIBRATED design whose parameters are estimated from the
#      real pooled clean baselines (calibrate()).
# H1-H3 are simulated on one cm30 series per firm. H4 (DSIGMA_D, a change of
# ln sigma_d) is simulated on a SECOND series per firm (replicate()'s
# `second`), with the sigma_d usable mask and, in the calibrated design, a
# calibration of its own from the real sigma_d baseline changes and DSIGMA_D
# values (added after the milestone-3 review, which found H4 gated on the
# crush process only). As in production (panel/window.py measures(), where
# DSIGMA_D = dln sigma_d - beta dln VIX with the cm30 beta), the second series
# shares the first's ln VIX path and is adjusted with the beta estimated on the
# FIRST (cm30) series, not re-estimated on sigma_d (second_series(); second
# fix round, delta review defect 7).
# A robustness statistic near the bar is re-measured on REMEASURE_REPS
# replications before its p-value is withheld or kept (size_verdicts(); ADR
# 0005 §4, dated note of the second fix round).
#
# THE DATA-GENERATING PROCESS (per firm f and session t; sigma_f = sig0 e^{N(0, sig_disp)},
# sig0 = 0.03 in the stress designs (the prototype's scale) and calibrated in the calibrated ones)
#   eta_ft = sigma_f (sqrt(rho_m) c_t + sqrt(rho_s) g_{sector(f), t}
#            + sqrt(1 - rho_m - rho_s) u_ft) + jump_k sigma_f N(0,1) on each day 0
#   c_t    = the common residual factor: iid N(0,1); or an AR(common_ar)
#            process with unit variance (persistent common changes); plus
#            psi * c_{t-1} on every firm (stale quotes: a cross-firm lag-1
#            correlation of rho_m psi / (1 + rho_m psi^2))
#   L_ft   = phi L_{f,t-1} + eta_ft (a random walk when phi = 1)
#   x_ft   = L_ft + noise sigma_f (sqrt(1 - kappa) eps_ft + sqrt(kappa) nu_t)
#            + drift_f t + (firm effect mu_f from each day 0 to +10)
#            + (shift or the D5 step) + beta_f m_t
#            (kappa = noise_common, the share of the quote noise common to all
#            firms on a date: it gives a NEGATIVE cross-firm lag-1 correlation of
#            changes, kappa * rho_1, which stale quotes cannot)
#   m_t    = ln VIX, a random walk with the real sd of its daily change;
#            beta_f = the firm's real beta (the package re-estimates it).
#   Quote noise makes the changes an MA(1): lag-1 acf -noise^2 / (1 + 2 noise^2).
#
# THE GATE (ADR 0005 §5)
#   The calibrated design is binding: each primary statistic's rejection rate
#   at 5% must be at most the upper exact binomial 99% quantile for the
#   replications used (6.30% at 2,000: the 99.5% quantile of Bin(2000, 0.05) is
#   126). The stress designs are reported, not pass/fail. A primary that fails
#   leaves the confirmatory family; its hypothesis is reported as exploratory.
# =============================================================================

from dataclasses import dataclass, field

import numpy as np
from scipy import stats

from earnings_vol.panel import abnormal
from earnings_vol.stats import clustering, eventtests, suite

TESTS = {"H1": "crush", "H2": "runup", "H3": "persist_10", "H4": "dsigma_d"}
ONE_SESSION = ("crush", "dsigma_d")
SIG0 = 0.03
# ADR 0005 §4, dated note of the second fix round: a robustness row whose calibrated rate is within
# REMEASURE_MARGIN of the bar of the main run (6.30% at 2,000) is re-measured on REMEASURE_REPS fresh
# replications (seeds from block REMEASURE_BLOCK of the run's seed stride) and decided against the bar
# for that count (5.57% at 10,000). Fixed here, beside the band, rather than in params.yaml: they are
# part of the gate's machinery, like the band's 99.5% quantile.
REMEASURE_REPS = 10_000
REMEASURE_MARGIN = 0.01
REMEASURE_BLOCK = 1000


@dataclass
class Design:
    """The fixed event structure of the gate (built once from the real tables)."""

    firms: list                   # security ids
    firm_sector: np.ndarray       # sector code per firm
    T: int                        # sessions simulated (global index - t0)
    t0: int
    firm: np.ndarray              # per event: firm index
    sess: np.ndarray              # N x W session index - t0
    usable: np.ndarray            # N x W
    in_baseline: np.ndarray       # N x W
    day0: np.ndarray              # per event: session index - t0
    day0_ord: np.ndarray          # per event: day-0 ordinal (for merging seasons)
    season: np.ndarray            # per event: raw season
    sector: np.ndarray            # per event: sector code
    sets: dict                    # test -> event indices (the real eligible set)
    target: dict                  # measure -> N column (ramps) or the crush's (pre, post) columns
    q: dict = field(default_factory=dict)   # measure -> N x (L+1) lag products of the grid weights
    beta_true: np.ndarray = None  # per firm
    dm_sd: float = 0.07           # sd of the daily change of ln VIX
    max_lag: int = 10


def build_design(firms, firm_sector, sess, usable, in_baseline, firm, day0, day0_ord, season, sector, sets,
                 beta_true, dm_sd, max_lag: int = 10) -> Design:
    """The Design, with the targets and the span-change weights of each measure (fixed by
    the structure: they depend on which sessions are usable, not on the values)."""
    t0 = int(sess.min())
    sess = sess - t0
    n = sess.shape[0]
    target = {"runup": np.full(n, abnormal.col(-1)), "persist_10": np.full(n, abnormal.col(10)),
              "crush": np.full(n, abnormal.col(0)), "dsigma_d": np.full(n, abnormal.col(0))}
    q = {}
    for m, tgt in target.items():
        a = np.zeros(sess.shape)
        for i in range(n):
            t = int(tgt[i])
            if m in ONE_SESSION:
                a[i, t] = 1.0
            elif usable[i, t] and in_baseline[i].any():
                a[i] = abnormal.grid_weights(abnormal.span_changes(in_baseline[i], usable[i], t), sess.shape[1])
        q[m] = abnormal.lag_products(a, max_lag)
    return Design(list(firms), np.asarray(firm_sector), int(sess.max()) + 1, t0, np.asarray(firm), sess,
                  np.asarray(usable, bool), np.asarray(in_baseline, bool), np.asarray(day0) - t0,
                  np.asarray(day0_ord), np.asarray(season, dtype=object), np.asarray(sector), sets, target, q,
                  np.asarray(beta_true, float), float(dm_sd), max_lag)


def stale_psi(rho_m: float, c1: float) -> float:
    """psi with rho_m psi / (1 + rho_m psi^2) = c1 (the smaller root), capped at the largest
    attainable c1, sqrt(rho_m)/2 (psi = 1/sqrt(rho_m)); 0 when c1 <= 0 or rho_m = 0."""
    if c1 <= 0 or rho_m <= 0:
        return 0.0
    disc = rho_m ** 2 - 4 * rho_m * c1 ** 2
    if disc < 0:
        return 1.0 / np.sqrt(rho_m)
    return (rho_m - np.sqrt(disc)) / (2 * rho_m * c1)


def generate(rng: np.random.Generator, d: Design, p: dict, m: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(x, m): simulated ln cm30 per firm and session (n_firms x T) and ln VIX (T). Given `m`, that
    ln VIX path is used instead of a new one (H4's second series shares the first's: one VIX)."""
    nf, T = len(d.firms), d.T
    ns = int(d.firm_sector.max()) + 1
    sig = p.get("sig0", SIG0) * np.exp(rng.normal(0.0, p.get("sig_disp", 0.0), nf))
    rho_m, rho_s = p.get("rho_m", 0.0), p.get("rho_s", 0.0)
    c = rng.standard_normal(T + 1)
    phc = p.get("common_ar", 0.0)
    if phc:
        cc = np.empty(T + 1)
        cc[0] = c[0]
        for t in range(1, T + 1):
            cc[t] = phc * cc[t - 1] + np.sqrt(1 - phc ** 2) * c[t]
        c = cc
    psi = p.get("psi", 0.0)
    common = c[1:] + psi * c[:-1]
    g = rng.standard_normal((ns, T))
    u = rng.standard_normal((nf, T))
    eta = sig[:, None] * (np.sqrt(rho_m) * common[None] + np.sqrt(rho_s) * g[d.firm_sector]
                          + np.sqrt(max(0.0, 1 - rho_m - rho_s)) * u)
    jk = p.get("jump_k", 0.0)
    if jk:
        for fi in range(nf):
            days = np.unique(d.day0[d.firm == fi])
            eta[fi, days] += jk * sig[fi] * rng.standard_normal(days.size)
    phi = p.get("phi", 1.0)
    if phi >= 1:
        lat = np.cumsum(eta, axis=1)
    else:
        lat = np.empty_like(eta)
        lat[:, 0] = eta[:, 0] / np.sqrt(1 - phi ** 2)
        for t in range(1, T):
            lat[:, t] = phi * lat[:, t - 1] + eta[:, t]
    kap = p.get("noise_common", 0.0)
    eps = np.sqrt(1 - kap) * rng.standard_normal((nf, T)) + np.sqrt(kap) * rng.standard_normal(T)[None]
    x = lat + p.get("noise", 0.0) * sig[:, None] * eps
    if p.get("drift"):
        x = x + rng.normal(0.0, p["drift"], nf)[:, None] * np.arange(T)[None]
    if p.get("firm_fx"):
        mu_f = rng.normal(0.0, p["firm_fx"], nf)
        for i in range(d.firm.size):
            x[d.firm[i], d.day0[i]:d.day0[i] + 11] += mu_f[d.firm[i]]
    step = np.zeros(d.firm.size)
    if p.get("hetero"):
        s_ev = sig[d.firm]
        step = p["hetero"] * (s_ev - s_ev.mean())
    if p.get("mu"):
        step = step + p["mu"]
    lo, hi = (0, 11) if p.get("shift_on") == "crush" else (-21, 11)
    for i in np.flatnonzero(step):
        x[d.firm[i], d.day0[i] + lo:d.day0[i] + hi] += step[i]
    if m is None:
        m = np.cumsum(rng.normal(0.0, d.dm_sd, T))
    x = x + d.beta_true[:, None] * m[None]
    return x, m


def _calendar(rows_win: np.ndarray, sess: np.ndarray, T: int) -> np.ndarray:
    """Scatter N x W window values onto the N x T calendar axis (NaN elsewhere)."""
    out = np.full((rows_win.shape[0], T), np.nan)
    r = np.repeat(np.arange(rows_win.shape[0]), rows_win.shape[1])
    ok = np.isfinite(rows_win.ravel())
    out[r[ok], sess.ravel()[ok]] = rows_win.ravel()[ok]
    return out


def estimate(d: Design, x: np.ndarray, m: np.ndarray, beta: np.ndarray | None = None) -> dict:
    """The inputs every statistic needs, re-estimated from one simulated data set by the
    package's own functions (panel/abnormal.py), as the production run estimates them from the
    real data: beta per firm from the simulated clean baseline changes (never d.beta_true, the
    value the DGP used), ALIV, the abnormal changes e and the scales s_i. N x W matrices.
    `beta` (per event), when given, is used instead of re-estimating it: H4's sigma_d series is
    adjusted with the beta of the cm30 series, as production adjusts DSIGMA_D (second_series)."""
    X = np.where(d.usable, x[d.firm[:, None], d.sess], np.nan)
    M = m[d.sess]
    clean = abnormal.clean_changes(d.in_baseline)
    if beta is None:
        dX, dM = abnormal.one_session_changes(X), abnormal.one_session_changes(M)
        betas = abnormal.beta_by_security(d.firm, d.sess, dX, dM, clean)
        beta = np.array([betas[f][0] for f in d.firm], float)
    al, _ = abnormal.aliv(X, M, d.in_baseline, beta)
    e = abnormal.abnormal_changes(X, M, beta)
    s = abnormal.baseline_sd(e, clean)
    return {"beta": beta, "aliv": al, "e": e, "s": s, "clean": clean}


def evaluate(d: Design, x: np.ndarray, m: np.ndarray, sets: dict, alpha: float, st: dict,
             robust: bool = True, est: dict | None = None) -> dict:
    """{test: {statistic: reject?}} for one simulated data set, through the package's code.
    `est` is estimate()'s output for (d, x, m); computed here when not given."""
    est = estimate(d, x, m) if est is None else est
    al, e, s, clean = est["aliv"], est["e"], est["s"], est["clean"]
    out = {}
    for h, rows in sets.items():
        meas = TESTS[h]
        t = d.target[meas][rows]
        A = (e if meas in ONE_SESSION else al)[rows, t]
        ok = np.isfinite(A)
        rows, A, t = rows[ok], A[ok], t[ok]
        if meas in ONE_SESSION:
            sa = A / s[rows]
            z = _calendar(np.where(clean[rows], e[rows] / s[rows][:, None], np.nan), d.sess[rows], d.T)
            a_cal = np.zeros((rows.size, d.T))
            a_cal[np.arange(rows.size), d.sess[rows, t]] = 1.0
            base = [e[i, clean[i] & np.isfinite(e[i])] for i in rows]
            res = suite.one_session(A, d.day0[rows], d.firm[rows], sa=sa if robust else None, z=z, a_cal=a_cal,
                                    sector=d.sector[rows], n_changes=clean[rows].sum(1),
                                    baseline=base if robust else None, patell=meas == "crush",
                                    min_shared=int(st["kp_min_shared"]), robust=robust)
        else:
            rho, _ = abnormal.rhat(e[rows], s[rows], clean[rows], d.max_lag, int(st["psd_grid"]))
            sa = A / (s[rows] * np.sqrt(abnormal.quad_form(d.q[meas][rows], rho)))
            res = suite.ramp(A, d.season[rows], d.day0_ord[rows], d.firm[rows], sa=sa if robust else None,
                             min_events=int(st["season_min_events"]), ratio=float(st["unbalanced_ratio"]),
                             min_clusters=int(st["min_season_clusters"]), robust=robust)
        dec = {k: bool(v["p_value"] <= alpha) for k, v in res.items()
               if isinstance(v, dict) and "p_value" in v and np.isfinite(v["p_value"])}
        dec["_primary"] = res["primary"]
        # The rejected mutant of ADR 0005 §5: day-0 date clusters for a ramp (it must fail here).
        if meas not in ONE_SESSION:
            dec["date_cluster_t"] = bool(clustering.oneway(A, d.day0[rows])["p_value"] <= alpha)
        out[h] = dec
    return out


def firm_beta(d: Design, beta: np.ndarray, d2: Design) -> np.ndarray:
    """The per-event beta of design d (one value per firm) carried to the events of d2, which
    must have the same firms."""
    if list(d2.firms) != list(d.firms):
        raise ValueError("the second design must have the first design's firms")
    per = np.full(len(d.firms), np.nan)
    per[d.firm] = beta
    return per[d2.firm]


def second_series(seed, d: Design, est: dict, d2: Design, p2: dict, m: np.ndarray) -> tuple:
    """(x2, m, est2): H4's sigma_d series of one replication. Its own generator, seeded from
    (seed, 2), and its own design and DGP parameters; the FIRST series' ln VIX path m (one VIX);
    and its inputs estimated with the beta of the first (cm30) series, est["beta"], because
    production computes DSIGMA_D = dln sigma_d - beta dln VIX with the cm30 beta
    (panel/window.py measures()) and scales it with the same beta (sigma_d_baseline)."""
    x2, m2 = generate(np.random.default_rng([seed, 2]), d2, p2, m=m)
    return x2, m2, estimate(d2, x2, m2, beta=firm_beta(d, est["beta"], d2))


def replicate(args) -> dict:
    """One replication: (design, dgp params, sets, seed, alpha, stats params, robust[, second]).

    `second`, when given and not None, is (design, dgp params, sets) of a second series
    (second_series), evaluated the same way. Gate G1 uses it for H4: DSIGMA_D is a change of
    ln sigma_d, so its rows are simulated on a sigma_d series with the sigma_d usable mask and a
    calibration of its own (stats/run.py), adjusted with the cm30 series' beta."""
    d, p, sets, seed, alpha, st, robust = args[:7]
    rng = np.random.default_rng(seed)
    x, m = generate(rng, d, p)
    est = estimate(d, x, m)
    out = evaluate(d, x, m, sets, alpha, st, robust, est=est)
    second = args[7] if len(args) > 7 else None
    if second is not None:
        d2, p2, sets2 = second
        x2, m2, est2 = second_series(seed, d, est, d2, p2, m)
        out.update(evaluate(d2, x2, m2, sets2, alpha, st, robust, est=est2))
    return out


def binom_band(reps: int, alpha: float = 0.05) -> tuple[float, float]:
    """The exact binomial 99% band of a 5% rejection rate: the 0.5% and 99.5% quantiles of
    Binomial(reps, alpha), divided by reps. 2,000 -> [0.038, 0.063]; 4,000 -> [0.04125, 0.059]."""
    return float(stats.binom.ppf(0.005, reps, alpha) / reps), float(stats.binom.ppf(0.995, reps, alpha) / reps)


def _robustness(rates_h: dict):
    """The robustness statistics of one test's rates: not the primary, not date_cluster_t (G1's
    rejected mutant, never a reported row), not a "_" key."""
    return [k for k in rates_h if not k.startswith("_") and k != rates_h["_primary"] and k != "date_cluster_t"]


def near_bar(cal_rates: dict, reps: int, alpha: float = 0.05) -> dict:
    """{test: [statistic]}: the robustness statistics of the calibrated design (rates()'s output,
    measured on `reps` replications) within REMEASURE_MARGIN of the bar for `reps` (6.30% at 2,000:
    5.30% to 7.30%). The run re-measures them on REMEASURE_REPS replications."""
    _, hi = binom_band(reps, alpha)
    out = {}
    for h, r in cal_rates.items():
        near = [k for k in _robustness(r) if abs(r[k] - hi) <= REMEASURE_MARGIN + 1e-12]
        if near:
            out[h] = near
    return out


def size_verdicts(cal_rates: dict, reps: int, alpha: float = 0.05, remeasured: dict | None = None) -> dict:
    """{(test, statistic): {"rate", "reps", "bar", "oversized"}} for every robustness statistic of
    the calibrated design (ADR 0005 §4, dated notes of both fix rounds). A statistic is oversized
    when its rate is above the upper edge of the exact binomial 99% band FOR THE REPLICATIONS IT WAS
    MEASURED ON (binom_band: 6.30% at 2,000, 5.57% at 10,000). One within REMEASURE_MARGIN of the
    main run's bar (near_bar) is decided on its re-measured rate: `remeasured` is
    {"reps": n, "rates": {test: {statistic: rate}}}; a near-bar statistic missing from it is an
    error, not a silent fallback to the 2,000-replication rate."""
    near = near_bar(cal_rates, reps, alpha)
    out = {}
    for h, r in cal_rates.items():
        for k in _robustness(r):
            rate, n = r[k], reps
            if k in near.get(h, []):
                got = (remeasured or {}).get("rates", {}).get(h, {})
                if k not in got:
                    raise ValueError(f"{h} {k} is within {REMEASURE_MARGIN:.0%} of the bar and was not re-measured")
                rate, n = got[k], int(remeasured["reps"])
            bar = binom_band(n, alpha)[1]
            out[(h, k)] = {"rate": float(rate), "reps": n, "bar": bar, "oversized": bool(rate > bar)}
    return out


def rates(results: list[dict]) -> dict:
    """{test: {statistic: rejection rate}} over replications, and the primary statistic."""
    out = {}
    for h in results[0]:
        keys = [k for k in results[0][h] if not k.startswith("_")]
        out[h] = {k: float(np.mean([r[h][k] for r in results])) for k in keys}
        out[h]["_primary"] = results[0][h]["_primary"]
    return out


def detectable_shift(shifts: list[float], power: list[float], target: float = 0.8) -> float | None:
    """The smallest shift with power >= target, linearly interpolated between the grid
    points; None if no shift on the grid reaches it."""
    for k, (s, pw) in enumerate(zip(shifts, power)):
        if pw >= target:
            if k == 0:
                return float(s)
            s0, p0 = shifts[k - 1], power[k - 1]
            return float(s0 + (target - p0) * (s - s0) / (pw - p0))
    return None


def unbalanced_subset(d: Design, rows: np.ndarray, st: dict, cut: int = 12, n_cut: int = 3,
                      seed: int = 99) -> np.ndarray:
    """The stress design 'unbalanced seasons': in n_cut of the merged seasons (the 2nd, 4th
    and 6th) keep `cut` events, drawn with a fixed seed."""
    merged = clustering.merge_small_seasons(d.season[rows], d.day0_ord[rows], int(st["season_min_events"]))
    keys = sorted(set(merged.tolist()))
    rng = np.random.default_rng(seed)
    keep = np.ones(rows.size, bool)
    for q in [keys[k] for k in (1, 3, 5) if k < len(keys)][:n_cut]:
        idx = np.flatnonzero(merged == q)
        if idx.size > cut:
            keep[rng.choice(idx, idx.size - cut, replace=False)] = False
    return rows[keep]


# --- the calibrated design (ADR 0005 §5: every parameter from the real pooled clean baselines) ---

def _mean_pair_corr(Z: np.ndarray, group: np.ndarray, same: bool, min_shared: int) -> float:
    rho, ok = eventtests.pair_correlations(Z, min_shared)
    sg = group[:, None] == group[None, :]
    sel = ok & (sg if same else ~sg)
    return float(rho[sel].mean()) if sel.any() else 0.0


def lag1_cross_corr(Z: np.ndarray, min_shared: int) -> float:
    """Mean over firm pairs i != j of corr(z_i,t, z_j,t-1) over their shared dates."""
    n, T = Z.shape
    a, b = Z[:, 1:], Z[:, :-1]
    ma, mb = np.isfinite(a).astype(float), np.isfinite(b).astype(float)
    aa, bb = np.nan_to_num(a), np.nan_to_num(b)
    n_sh = ma @ mb.T
    sx, sy = aa @ mb.T, ma @ bb.T
    sxx, syy, sxy = (aa ** 2) @ mb.T, ma @ (bb ** 2).T, aa @ bb.T
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy / n_sh - sx * sy / n_sh ** 2
        rho = cov / np.sqrt((sxx / n_sh - (sx / n_sh) ** 2) * (syy / n_sh - (sy / n_sh) ** 2))
    ok = (n_sh >= min_shared) & np.isfinite(rho) & ~np.eye(n, dtype=bool)
    return float(rho[ok].mean()) if ok.any() else 0.0


def cs_mean_acf(Z: np.ndarray, lags: int = 10, min_firms: int = 10) -> list[float]:
    """Autocorrelations (lags 1..lags, centred) of the cross-sectional mean of z per date,
    over dates with at least min_firms firms."""
    n_t = np.isfinite(Z).sum(0)
    with np.errstate(invalid="ignore"):
        csm = np.where(n_t >= min_firms, np.nanmean(np.where(np.isfinite(Z), Z, np.nan), axis=0), np.nan)
    v = csm - np.nanmean(csm)
    den = np.nansum(v * v)
    out = []
    for k in range(1, lags + 1):
        prod = v[k:] * v[:-k]
        out.append(float(np.nansum(prod) / den))
    return out


def ar_levels(levels: list[np.ndarray], noise_var: np.ndarray | None = None) -> tuple[float, float, float]:
    """(phi_hat, mean length L, corrected phi): pooled AR(1) of baseline levels over pairs of
    consecutive sessions both present, each baseline demeaned over its present values.

    Quote noise of variance noise_var[i] (per baseline) adds to the lag-0 sum but not to the
    lag-1 sum, so it is taken out of the denominator: sum v_{t-1}^2 - n_pairs * noise_var.
    Then Kendall's (1954) correction for a short demeaned series, phi = (L phi + 1)/(L - 3),
    capped at 1. phi_hat is the plain estimate, before both corrections."""
    num = den = den_raw = 0.0
    lens = []
    for i, v in enumerate(levels):
        ok = np.isfinite(v)
        if ok.sum() < 3:
            continue
        v = np.where(ok, v - v[ok].mean(), np.nan)
        pair = ok[1:] & ok[:-1]
        num += float((v[1:][pair] * v[:-1][pair]).sum())
        sq = float((v[:-1][pair] ** 2).sum())
        den_raw += sq
        den += sq - (0.0 if noise_var is None else float(noise_var[i]) * int(pair.sum()))
        lens.append(int(ok.sum()))
    L = float(np.mean(lens))
    ph = num / den
    return num / den_raw, L, min(1.0, (L * ph + 1) / (L - 3))


def calibrate(z_firm: np.ndarray, firm_sector: np.ndarray, rho1: float, levels: list[np.ndarray],
              e_firm: list[np.ndarray], crush_by_firm: list[np.ndarray], sa_crush_by_firm: list[np.ndarray],
              log_s_by_firm: list[np.ndarray], min_shared: int = 20, level_s: np.ndarray | None = None) -> dict:
    """The calibrated DGP parameters and the measured inputs behind each (see the header).

    z_firm   firms x sessions: standardised clean baseline changes (NaN elsewhere)
    rho1     the pooled lag-1 R-hat of the primary events
    levels   per baseline: its market-adjusted abnormal log-IV levels in session order
             (NaN at unobserved sessions); level_s its s_i (for the noise variance -rho1 s_i^2)
    The mapping (each a moment of the DGP above; n^2 = noise^2, infl = 1 + 2 n^2):
      noise^2   = -rho1 / (1 + 2 rho1)                      (lag-1 acf of changes)
      kappa     = c1 / rho1 when both are negative, else 0  (common noise; c1 = lag-1 cross-firm corr)
      psi       = stale_psi(rho_m, c1 infl) when c1 > 0     (stale quotes)
      rho_m     = corr_across infl - 2 kappa n^2             (same-date corr of changes, across sectors)
      rho_s     = (corr_within - corr_across) infl          (the extra within a sector)
      phi       = ar_levels(levels, noise var -rho1 s_i^2)  (AR of levels, noise and Kendall corrected)
      common_ar = max(0, lag-1 acf of the cross-sectional mean of z)
      drift     = sqrt(var of firm mean e - mean sampling var), sampling var s^2 (1 + 2 rho1) / n
      firm_fx   = sqrt(var of firm mean CRUSH - mean of within-firm var / n_f)
      jump_k    = sqrt((day-0 variance ratio - 1) infl), the ratio = var((CRUSH - mean CRUSH) / s_i)
                  around firm means: the tested value is demeaned over the event set first, so that its
                  mean (the effect under test) does not enter through s_i varying within a firm (second
                  fix round, delta review defect 4)
      sig_disp  = sd across firms of mean ln s_i
      sig0      = exp(mean across firms of mean ln s_i) / sqrt(2/(1 + phi) + 2 n^2): a change of the
                  DGP has variance sigma^2 (2/(1 + phi) + 2 n^2), so the parameters in log points
                  (firm_fx, drift, a power shift) sit on the real scale (added after the review)
    e_firm   per firm: its clean baseline abnormal changes
    crush_by_firm, sa_crush_by_firm   per firm: its events' CRUSH and (CRUSH - mean CRUSH) / s_i
    log_s_by_firm                     per firm: its events' ln s_i
    """
    noise2 = -rho1 / (1 + 2 * rho1) if -0.5 < rho1 < 0 else 0.0
    infl = 1 + 2 * noise2                       # observed change variance / latent innovation variance
    rho_w = _mean_pair_corr(z_firm, firm_sector, True, min_shared)
    rho_x = _mean_pair_corr(z_firm, firm_sector, False, min_shared)
    c1 = lag1_cross_corr(z_firm, min_shared)
    kappa = min(1.0, c1 / rho1) if (c1 < 0 and rho1 < 0) else 0.0
    rho_m = max(0.0, rho_x * infl - 2 * kappa * noise2)
    rho_s = max(0.0, (rho_w - rho_x) * infl)
    acf = cs_mean_acf(z_firm)
    nv = None if level_s is None else max(0.0, -rho1) * np.asarray(level_s) ** 2
    ph_hat, L, phi = ar_levels(levels, nv)
    means = np.array([v.mean() for v in e_firm])
    samp = np.array([v.var(ddof=1) * max(0.0, 1 + 2 * rho1) / v.size for v in e_firm])
    drift = float(np.sqrt(max(0.0, means.var(ddof=1) - samp.mean())))
    fm = np.array([v.mean() for v in crush_by_firm if v.size >= 2])
    fv = np.array([v.var(ddof=1) / v.size for v in crush_by_firm if v.size >= 2])
    firm_fx = float(np.sqrt(max(0.0, fm.var(ddof=1) - fv.mean())))
    dev = np.concatenate([v - v.mean() for v in sa_crush_by_firm if v.size >= 2])
    dof = sum(v.size - 1 for v in sa_crush_by_firm if v.size >= 2)
    ratio = float((dev ** 2).sum() / dof)
    jump_k = float(np.sqrt(max(0.0, (ratio - 1) * infl)))
    sig_disp = float(np.std([v.mean() for v in log_s_by_firm], ddof=1))
    sig0 = float(np.exp(np.mean([v.mean() for v in log_s_by_firm])) / np.sqrt(2 / (1 + phi) + 2 * noise2))
    psi = float(stale_psi(rho_m, max(0.0, c1) * infl))
    params = {"phi": phi, "rho_m": rho_m, "rho_s": min(rho_s, 1 - rho_m), "noise": float(np.sqrt(noise2)),
              "noise_common": float(kappa), "sig_disp": sig_disp, "jump_k": jump_k, "drift": drift,
              "firm_fx": firm_fx, "common_ar": max(0.0, acf[0]), "psi": psi, "sig0": sig0}
    measured = {"rho1": rho1, "corr_same_date_within_sector": rho_w, "corr_same_date_across_sectors": rho_x,
                "corr_lag1_cross_firm": c1, "cs_mean_acf": acf, "ar_levels_raw": ph_hat, "ar_levels_mean_len": L,
                "ar_levels": phi, "drift_sd": drift, "firm_crush_sd": firm_fx, "day0_variance_ratio": ratio,
                "sd_log_s": sig_disp}
    return {"params": params, "measured": measured}


def calibrate_from(e: np.ndarray, s: np.ndarray, lv: np.ndarray, in_baseline: np.ndarray, sess: np.ndarray,
                   firm, sector, vals: np.ndarray, max_lag: int = 10, grid: int = 512, min_shared: int = 20) -> dict:
    """calibrate() from the window matrices of one event set, one row per event. The
    production run passes the real ones (stats/run.py calibrate_on); a round-trip test passes
    those of a simulated data set (estimate()).

    e      N x W clean baseline abnormal changes, NaN elsewhere
    s      N scales s_i (the sd of each row of e)
    lv     N x W abnormal log levels; only the baseline [-60, -22] is read, and each baseline
           is demeaned inside ar_levels, so a per-event constant does not matter
    sess   N x W session indices (the calendar axis of z_firm)
    firm, sector   N labels; vals   N tested values A_i (CRUSH or DSIGMA_D); the day-0 ratio reads
                   (A_i - mean A) / s_i
    """
    rho, _ = abnormal.rhat(e, s, np.isfinite(e), max_lag, grid)
    firm, sector = np.asarray(firm, dtype=object), np.asarray(sector, dtype=object)
    cal_firms = sorted(set(firm.tolist()))
    k_of = {c: k for k, c in enumerate(cal_firms)}
    t0 = int(sess.min())
    z_firm = np.full((len(cal_firms), int(sess.max()) - t0 + 1), np.nan)
    for i in range(e.shape[0]):
        k = k_of[firm[i]]
        ok = np.isfinite(e[i]) & ~np.isfinite(z_firm[k, sess[i] - t0])
        z_firm[k, sess[i][ok] - t0] = e[i, ok] / s[i]
    sectors = sorted(set(sector.tolist()))
    first = {c: i for i, c in reversed(list(enumerate(firm.tolist())))}
    cal_sector = np.array([sectors.index(sector[first[c]]) for c in cal_firms])
    lo, hi = abnormal.col(-60), abnormal.col(-22)
    levels = [np.where(in_baseline[k, lo:hi + 1], lv[k, lo:hi + 1], np.nan) for k in range(e.shape[0])]
    by = [np.flatnonzero(firm == c) for c in cal_firms]
    dev = vals - vals.mean()
    cal = calibrate(z_firm, cal_sector, float(rho[0]), levels, [e[ix][np.isfinite(e[ix])] for ix in by],
                    [vals[ix] for ix in by], [dev[ix] / s[ix] for ix in by], [np.log(s[ix]) for ix in by],
                    min_shared, level_s=s)
    cal["measured"]["rhat"] = [float(x) for x in rho]
    return cal


# --- the stress designs (ADR 0005 §2g tables 1-4 and §5) ---------------------------------
D2 = dict(phi=1.0, rho_m=0.10, rho_s=0.0, noise=0.5, sig_disp=0.0, jump_k=0.0)
D4 = dict(phi=0.98, rho_m=0.05, rho_s=0.15, noise=0.5, sig_disp=0.4, jump_k=3.0)
STRESS = {
    "D0": dict(phi=1.0),
    "D1": dict(phi=1.0, rho_m=0.10),
    "D2": D2,
    "D3": dict(D2, noise=0.8),
    "D4": D4,
    "D5": dict(D4, hetero=3.0),
    "D6": dict(phi=0.98, rho_m=0.10),
    "D2+drift0.0005": dict(D2, drift=0.0005),
    "D2+drift0.0015": dict(D2, drift=0.0015),
    "D2 unbalanced": dict(D2, _unbalanced=True),
    "D4+drift0.0005": dict(D4, drift=0.0005),
    "D2+firm_fx0.01": dict(D2, firm_fx=0.01),
    "D2+firm_fx0.03": dict(D2, firm_fx=0.03),
    "D4+firm_fx0.03": dict(D4, firm_fx=0.03),
    "D2+common_ar0.5": dict(D2, common_ar=0.5),
    "D2+common_ar0.9": dict(D2, common_ar=0.9),
    "D2+lag1_0.02": dict(D2, psi=stale_psi(0.10, 0.02)),
    "D2+lag1_0.05": dict(D2, psi=stale_psi(0.10, 0.05)),
}
