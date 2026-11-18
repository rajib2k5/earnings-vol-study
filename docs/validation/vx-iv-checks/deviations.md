# vx-iv-checks: deviations ledger

The pre-registration was frozen at 2026-11-18T02:15:34Z (`preregistration.md`
SHA-256 `b640a72508cee85cd629b3b2d68e53586da13579a092f530c8ad57ca4366af75`, `probes/SHA256SUMS`
`9c39e3cd0aae10728bb69c0c2d784f7bd07abcc66a8c7a46500a95826065fe35`). §14 applies from then on. This file
lists every change after the freeze, in time order: the time, what changed, why, and whether a real-data
result was already seen.

## Allowed changes (not deviations)

| Time (UTC) | Change | `loader_sha256` | Why | Real-data result seen before? |
|---|---|---|---|---|
| 2026-11-18T02:21Z | `loader.py` written (stub replaced). | `d985d717085fb904796be5229017b1246ab3cbd5a090af98eaa8931068f530ed` | §3: the loader is written at the start of phase 2. | No. |

How the loader was checked before the first phase-2 run: a scratch harness
(`scratchpad/d1/p2dev/g4dev.py`, outside the repo) imported the frozen `phase2.py` and ran only its `gate_g4` on
the five names. No rule and no statistic ran. The harness switched the Yahoo read off, so `raw/yfinance` was
first read by `phase2.py` itself.

*Added 2026-11-17 after the adversarial review; the first version left this out.* While the loader was written, two
more scratch scripts in the same folder read real stage data (stage `74bed6f4b1281810`):

- `explore.py`, 02:17:43Z: the columns and types of the stage tables (security, ticker alias, session snapshot,
  events, session, chain expiry, IV daily), the five names' security rows, the snapshot status counts and the
  date range per name, and the event counts per name.
- `time1.py`, 02:18:41Z: the time to parse one option-chain file for GOOGL.

Neither computed a statistic of any rule, and neither read Yahoo.

G4 passed on the first version for all five names (GOOGL 3,826 chain rows and
1,210 sessions, GS 3,837 and 1,214, IBM 3,837 and 1,214, AAPL 3,851 and 1,219, AMZN 3,840 and 1,215). So no
loader fix was forced by G4.

Choices the loader makes that the pre-registration does not spell out:

- **Yahoo close as quoted on its own day** (`prices.asof_close`: the split-adjusted close times the later split
  ratios). The option chain, and so the parity forward, is quoted as traded on each day, and the package's own
  snapshot-close check reads Yahoo the same way. With the split-adjusted close, a 20-for-1 split would put a jump
  of ln 20 into one forward-vs-close change.
- **A missing or non-positive Yahoo close is left out**, so the forward-vs-close check skips that change.
- **Ex-dividend sessions** are the dates with a Yahoo dividend > 0.
- **The panel's sessions** are the name's `session_snapshot` rows from 2020-01-02 to 2026-10-26 (1,713 for each
  name), with their status. `security_id` is the ticker for these five names (`security.parquet`).

## Phase-2 runs

| Time (UTC) | Command | `loader_sha256` | Result |
|---|---|---|---|
| 2026-11-18T02:21:45Z to 02:28:08Z | `probes/phase2.py --out <scratch> --reference` | `d985d717085fb904796be5229017b1246ab3cbd5a090af98eaa8931068f530ed` | Gates G1 to G4 pass on all five names; outcome UNCLEAR (strike); exit 0, 382 s. See `results.md`. |

## Deviations

None.
