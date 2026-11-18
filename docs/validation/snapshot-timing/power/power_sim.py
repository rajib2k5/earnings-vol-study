"""Power and calibration of the snapshot-timing check (preregistration.md §7-§10, §12), on synthetic data.

    uv run python -I docs/validation/snapshot-timing/power/power_sim.py <config> [reps] [boot_reps]

Prints one JSON line. It runs the check's own estimator code (earnings_vol.stats.snapshot_timing) on synthetic ln
levels laid on the REAL calendar, the REAL H1 events and H4 subset and the REAL session classes (timing_map.json).
It reads no IV, price or measure value: event eligibility comes from whether a measure is present, never from its
value. The generator follows the adversarial review's (ledger §1.2): a market factor seen in ln VIX with noise,
company loadings, a persistent company component, measurement noise, and per event a run-up, a crush and a
post-event drift; on off sessions a level error with a common daily part. The sigma_d series is 1.55 times as noisy
(the ratio of the phase-0 robust sds, 0.068 / 0.044). It is one series per company here, not per event; the per-event
key changes no algebra (tests/test_snapshot_timing.py checks it).

Rates per measure (H1 on the ln CM30 world, H4 on the ln sigma_d world):
  P_SMALL, P_LARGE   the §10 verdict after the §8 gate
  rej_up, rej_dn     the restricted-bootstrap one-sided tests at the realised true shift, rejecting at 5% (each
                     should be near 5%: the calibration of the verdict's tests)
  cov90, cov95       coverage of the descriptive unrestricted bootstrap-t intervals
and the identity check's rejection rate (restricted bootstrap and analytic F), per series.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from earnings_vol import params as params_mod
from earnings_vol.stats import snapshot_timing as stm

REPO = Path(__file__).resolve().parents[4]
LINE = {"H1": 0.0112, "H4": 0.0112}
SIGMA_SCALE = 1.55

# name: (generator parameters, seed). at_line = the planted shift in lines (negative: a smaller measured crush).
CONFIGS = {
    "null_gauss": ({}, 101),
    "null_t3": ({"tdf": 3}, 102),
    "null_common": ({"sF": 0.05}, 103),
    "null_offvol": ({"off_vol": 1.4}, 104),
    "at_line": ({"at_line": -1.0}, 105),
    "at_line_t3": ({"at_line": -1.0, "tdf": 3}, 106),
    "half_line": ({"at_line": -0.5}, 107),
    "viol_drift_1line": ({"drift_off": 0.0583}, 108),
}


def skeleton() -> dict:
    tmap = json.loads((REPO / "docs/validation/snapshot-timing/timing_map.json").read_text())
    cls = {date.fromisoformat(d): c for c in ("off", "late", "unknown") for d in tmap[f"{c}_dates"]}
    p = params_mod.load()
    first, last = p.day("snapshot_eras", "daily_from"), date.fromisoformat(tmap["last_session"])
    ses = sorted(d for d in pd.to_datetime(pd.read_parquet(REPO / "data/derived/session.parquet")["session_date"])
                 .dt.date if first <= d <= last)
    ev = pd.read_parquet(REPO / "data/derived/events.parquet")
    em = pd.read_parquet(REPO / "data/derived/event_measures.parquet")
    have = em[["event_id", "eligible_crush"]].assign(h1=em["crush_mean_adj"].notna(), h4=em["dsigma_d_mean_adj"].notna())
    e = ev.merge(have, on="event_id")
    e = e[(e["sample"] == "daily") & e["day0_session"].notna()]
    h1 = e[e["eligible_crush"].astype(bool) & e["h1"]]
    h4 = set(e.loc[e["eligible_crush"].astype(bool) & e["h4"], "event_id"])
    return {"sessions": ses, "cls": [cls.get(d, "close") for d in ses],
            "ev": [(r.security_id, pd.Timestamp(r.day0_session).date(), str(r.season), r.event_id in h4)
                   for r in h1.itertuples()],
            "all_d0": [(r.security_id, pd.Timestamp(r.day0_session).date()) for r in e.itertuples()]}


class Sim:
    def __init__(self, sk: dict):
        # 15 synthetic weekdays (class close) after the last session host day +1 to +10 of the last events, so every
        # H1 event of the real sample is in the simulation
        pad, d = [], sk["sessions"][-1]
        while len(pad) < 15:
            d = d + timedelta(days=1)
            if d.weekday() < 5:
                pad.append(d)
        self.S = S = sk["sessions"] + pad
        self.T = len(S)
        ix = {d: i for i, d in enumerate(S)}
        cls_arr = np.array(sk["cls"] + ["close"] * len(pad))
        cls_of = dict(zip(S, cls_arr))
        self.cls = lambda s: cls_of.get(s, "close")
        self.off = cls_arr == "off"
        self.firms = sorted({e[0] for e in sk["ev"]})
        self.fx = {f: i for i, f in enumerate(self.firms)}
        keep = [(s, d, sea, h4) for s, d, sea, h4 in sk["ev"] if d in ix and ix[d] >= 10]
        ev = pd.DataFrame({"event_id": [f"e{i}" for i in range(len(keep))], "firm": [e[0] for e in keep],
                           "season": [e[2] for e in keep], "h4": [e[3] for e in keep], "p0": [ix[e[1]] for e in keep]})
        for col, rel in (("s_m2", -2), ("s_m1", -1), ("s_0", 0), ("s_p1", 1), ("s_p10", 10)):
            ev[col] = [S[p + rel] for p in ev["p0"]]
        self.ev = ev
        self.ev4 = ev[ev["h4"]].reset_index(drop=True)
        self.near = set()
        for s, d in sk["all_d0"]:
            if s in self.fx and d in ix:
                i = ix[d]
                self.near.update((s, S[j]) for j in range(max(0, i - 2), min(self.T, i + 3)))

    def world(self, p: dict, rng, scale: float, extra0: float):
        """Levels (company x session) of one series, plus the planted level errors B. extra0 is added to the error
        of every off day 0 of the series' events (the planted shift)."""
        T, F, off = self.T, len(self.firms), self.off

        def noise(size, sd):
            if p.get("tdf") is None:
                return rng.normal(0, sd, size)
            z = rng.standard_t(p["tdf"], size)
            return z * sd / 1.4826 / np.median(np.abs(z))
        fsd = np.full(T, p.get("sF", 0.025))
        fsd[off] *= p.get("off_vol", 1.0)
        fc = np.cumsum(noise(T, 1) * fsd)
        lam = rng.uniform(0.7, 1.3, F)
        eps = noise((F, T), p.get("sI", 0.025) * scale)
        Y = np.zeros((F, T))
        for t in range(1, T):
            Y[:, t] = 0.98 * Y[:, t - 1] + eps[:, t]
        X = lam[:, None] * fc[None, :] + Y + noise((F, T), p.get("sE", 0.02) * scale)
        for r in self.ev.itertuples():
            c, i = self.fx[r.firm], r.p0
            a = rng.normal(0.23, 0.08)
            X[c, i - 10:i] += a * (np.arange(-10, 0) + 11) / 10
            drift = p.get("drift", -0.003) + (p.get("drift_off", 0.0) if off[i] else 0.0)
            X[c, i:i + 11] += a + rng.normal(-0.20, 0.20) + drift * np.arange(11)
            for k in (-2, -1, 1, 2):
                X[c, i + k] += rng.normal(0, p.get("evn", 0.025) * scale)
        B = np.zeros((F, T))
        nu = rng.normal(0, p.get("snu", 0.015) * scale, T)
        B[:, off] = p.get("mu", 0.0) + nu[off][None, :] + rng.normal(0, 0.01 * scale, (F, int(off.sum())))
        for r in self.ev.itertuples():
            if off[r.p0]:
                B[self.fx[r.firm], r.p0] += extra0
        m = fc + rng.normal(0, p.get("vix_noise", 0.02), T)  # ln VIX: the factor, seen with noise
        lv = {(self.firms[c], self.S[t]): float(X[c, t] + B[c, t]) for c in range(F) for t in range(T)}
        return lv, dict(zip(self.S, m)), B

    def k(self, e: pd.DataFrame) -> dict:
        return {"k0": int(sum(self.cls(x) == "off" for x in e["s_0"])),
                "km1": int(sum(self.cls(x) == "off" for x in e["s_m1"]))}

    def one(self, p: dict, rng, boot_reps: int, seed: int) -> dict:
        ev, ev4 = self.ev, self.ev4
        n1, n4 = len(ev), len(ev4)
        k1, k4 = self.k(ev), self.k(ev4)
        x1 = p.get("at_line", 0.0) * LINE["H1"] * n1 / k1["k0"]
        x4 = p.get("at_line", 0.0) * LINE["H4"] * n4 / k4["k0"]
        lv1, m, b1 = self.world(p, rng, 1.0, x1)
        lv4, _, b4 = self.world(p, rng, SIGMA_SCALE, x4)
        blocks = {"cm30.O": (stm.block_ordinary(lv1, m, self.firms, self.S, self.cls, self.near, self.S[1]), "O")}
        for kind in ("P", "A", "C"):
            blocks[f"cm30.{kind}"] = (stm.block_event(ev, lv1, m, self.cls, kind), kind)
            blocks[f"sigma.{kind}"] = (stm.block_event(ev4, lv4, m, self.cls, kind), kind)
        fit = stm.stacked_fit(blocks)
        combos, tests, true = {}, {}, {}
        for h, e, B, s, k in (("H1", ev, b1, "cm30", k1), ("H4", ev4, b4, "sigma", k4)):
            w = stm.vector(fit, stm.shift_weights(s, "crush", k, len(e)))
            cc = np.array([self.fx[f] for f in e["firm"]])
            p0 = e["p0"].to_numpy()
            true[h] = float(np.mean(B[cc, p0] - B[cc, p0 - 1]))  # the realised shift of the measured crush
            combos[h] = w
            tests |= {f"{h} {side}": wc for side, wc in stm.line_tests(w, LINE[h]).items()}
            tests[f"{h} true"] = (w, true[h])
        walds = {s: stm.identity_rows(fit, s) for s in ("cm30", "sigma")}
        boot = stm.wild_bootstrap(fit, combos, boot_reps, seed)
        wcr = stm.wcr_bootstrap(fit, tests, walds, boot_reps, seed)
        rej = {s: wcr["walds"][s]["p_boot"] < 0.05 for s in walds}
        raw = {h: stm.tost_verdict(wcr["tests"][f"{h} lo"], wcr["tests"][f"{h} hi"]) for h in combos}
        verdict = stm.gated(raw, {"H1": "cm30", "H4": "sigma"}, rej)
        out = {"rej": rej, "rejF": {s: wcr["walds"][s]["p_F"] < 0.05 for s in walds}}
        for h in combos:
            b, t = boot["combos"][h], wcr["tests"][f"{h} true"]
            out[h] = {"true": true[h], "est": b["estimate"], "se": b["se"], "verdict": verdict[h],
                      "cov90": b["ci90"][0] <= true[h] <= b["ci90"][1],
                      "cov95": b["ci95"][0] <= true[h] <= b["ci95"][1],
                      "rej_up": t["p_up"] < 0.05, "rej_dn": t["p_dn"] < 0.05}
        return out


def run(name: str, reps: int, boot_reps: int) -> dict:
    cfg, seed = CONFIGS[name]
    sim = Sim(skeleton())
    rng = np.random.default_rng(seed)
    rs = [sim.one(cfg, rng, boot_reps, seed * 100_000 + i) for i in range(reps)]
    res = {"config": name, "params": cfg, "seed": seed, "reps": reps, "boot_reps": boot_reps,
           "events": {"H1": len(sim.ev), "H4": len(sim.ev4)}}
    for h in ("H1", "H4"):
        g = lambda key: [r[h][key] for r in rs]  # noqa: E731
        res[h] = {"mean_true": float(np.mean(g("true"))), "mean_est": float(np.mean(g("est"))),
                  "sd_est": float(np.std(g("est"))), "mean_se": float(np.mean(g("se"))),
                  "P_SMALL": float(np.mean([v == "SMALL" for v in g("verdict")])),
                  "P_LARGE": float(np.mean([v == "LARGE" for v in g("verdict")])),
                  "rej_up": float(np.mean(g("rej_up"))), "rej_dn": float(np.mean(g("rej_dn"))),
                  "cov90": float(np.mean(g("cov90"))), "cov95": float(np.mean(g("cov95")))}
    res["identity_rej_boot"] = {s: float(np.mean([r["rej"][s] for r in rs])) for s in ("cm30", "sigma")}
    res["identity_rej_F"] = {s: float(np.mean([r["rejF"][s] for r in rs])) for s in ("cm30", "sigma")}
    return res


WHAT = {
    "null_gauss": "no shift, Gaussian noise",
    "null_t3": "no shift, t(3) noise",
    "null_common": "no shift, market factor twice as large",
    "null_offvol": "no shift, off days 1.4× as volatile",
    "at_line": "shift of −1 line",
    "at_line_t3": "shift of −1 line, t(3) noise",
    "half_line": "shift of −½ line",
    "viol_drift_1line": "no shift; §8 violated: drift on off day 0 worth 1 line",
}


def table(results: Path) -> str:
    """The plan's §12 tables from results/<config>.json."""
    rs = [json.loads((results / f"{k}.json").read_text()) for k in CONFIGS]
    pct = lambda x: f"{100 * x:.1f}"  # noqa: E731
    a = ["| Configuration | true shift H1 / H4 (lines) | H1 SMALL / LARGE % | H4 SMALL / LARGE % | identity rejects cm30 / σ % |",
         "|---|---|---|---|---|"]
    b = ["| Configuration | H1 rejects at the truth, up / down % | H4 up / down % | H1 cover 90 / 95 % | H4 cover 90 / 95 % | identity, analytic F, cm30 / σ % |",
         "|---|---|---|---|---|---|"]
    for r in rs:
        h1, h4, ib, iF = r["H1"], r["H4"], r["identity_rej_boot"], r["identity_rej_F"]
        name = f"{r['config']}: {WHAT[r['config']]}"
        a.append(f"| {name} | {h1['mean_true'] / LINE['H1']:+.2f} / {h4['mean_true'] / LINE['H4']:+.2f} | "
                 f"{pct(h1['P_SMALL'])} / {pct(h1['P_LARGE'])} | {pct(h4['P_SMALL'])} / {pct(h4['P_LARGE'])} | "
                 f"{pct(ib['cm30'])} / {pct(ib['sigma'])} |")
        b.append(f"| {r['config']} | {pct(h1['rej_up'])} / {pct(h1['rej_dn'])} | {pct(h4['rej_up'])} / "
                 f"{pct(h4['rej_dn'])} | {pct(h1['cov90'])} / {pct(h1['cov95'])} | {pct(h4['cov90'])} / "
                 f"{pct(h4['cov95'])} | {pct(iF['cm30'])} / {pct(iF['sigma'])} |")
    reps = {r["reps"] for r in rs}
    boot = {r["boot_reps"] for r in rs}
    return "\n".join(a) + "\n\n" + "\n".join(b) + f"\n\n(reps {sorted(reps)}, bootstrap draws {sorted(boot)})\n"


if __name__ == "__main__":
    if sys.argv[1] == "table":
        print(table(Path(__file__).resolve().parent / "results"), end="")
        sys.exit(0)
    name = sys.argv[1]
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    boot_reps = int(sys.argv[3]) if len(sys.argv) > 3 else 999
    print(json.dumps(run(name, reps, boot_reps)))
