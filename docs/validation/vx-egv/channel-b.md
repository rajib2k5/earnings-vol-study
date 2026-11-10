# Channel B (runtime auditor): VX* cross-check claims C1-C10

Empirical only. No documentation, no web, no network. Env: `.venv/bin/python -I` (Python 3.12, numpy/pandas per env-pin). No repo file was modified: mutants live in the scratchpad `.../scratchpad/vxb/` (copies are also in `probes/mutants/`) and are loaded with importlib. Checksums of `src/earnings_vol/stats/vx_crosscheck.py` and `tools/vx_crosscheck.py` were taken before and re-verified after all mutant runs (`sha256sum -c`: OK, OK).
Scripts: `probes/probe_data.py` (+`common.py`), `probe_c4.py`, `probe_c9.py`, `probe_c10.py`, `run_all.sh`; verbatim outputs: `probes/run_all.out`, `c4.out`, `c9.out`, `c10.out`. `probes/ibm_roll_detail.out` was removed because it held per-day Cboe values (log changes); `probes/ibm_roll_detail.py` now prints aggregates only.

## Verdicts

| ID | Verdict | One line |
|---|---|---|
| C1 | CONFIRMED (empirical consistency only) | The five series behave as 30-day single-stock vols: sit above our blind 30d ATM IV on 91-99% of days, d-log corr 0.67-0.86 with cm30_blind vs 0.52-0.77 with front_atm_iv; IBM's VX jumps +16-21% on the Monday after Jun/Sep quarterly expiry, i.e. when its 30d window first spans the next earnings date. |
| C2 | UNVERIFIABLE | Option strip / VIX method cannot be seen in a daily CLOSE. Data are consistent with it (VX > ATM IV on 91-99% of days; no roll jump beyond 1.42x median |dln|), which does not prove the method. |
| C3 | UNVERIFIABLE | No GOOG or GOOGL option data in the allowed evidence; only VXGOG vs our GOOGL series is observable (d-log r 0.78, lowest-but-one), which cannot distinguish share classes. |
| C4 | CONFIRMED (from the recorded fetch, not re-fetched) | Five files, columns DATE,OPEN,HIGH,LOW,CLOSE, 3978 daily rows each (2011-01-07..2026-11-06), sha256 matches fetch_log. Caveat: fetch_log records the final URL `https://cdn-api.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv` after a 307 redirect (hops [307,200]); the claim's host `cdn.cboe.com` was redirected to `cdn-api.cboe.com`, and the original request URL is not logged. |
| C5 | CONFIRMED | Median (CLOSE/100)/cm30_blind_iv = 1.08-1.12 per name; median CLOSE/100 0.28-0.36 (decimal vols). Without /100 the ratio is ~108-112. |
| C6 | CONFIRMED | d-log correlation vs cm30_blind_iv at lag 0 = 0.67-0.86 per name (pooled 0.790); at -1 and +1 it is -0.09..0.10 (pooled 0.035, -0.038). Lag 0 is highest for every name. Shifting Cboe dates one session moves the peak to lag +1. |
| C7 | CONFIRMED | Over the 1713 sessions 2020-01-02..2026-10-26 every file has a value on 1712 (99.94%); the single gap is 2020-10-16 in all five files. |
| C8 | UNVERIFIABLE | "Documents no maturity" is a statement about documentation; no runtime probe can settle it. |
| C9 | CONFIRMED | `block_counts` draws starts on [0, n-l] inclusive, ceil(n/l) fixed-length contiguous blocks per replicate, overlapping, with replacement (repeated starts give count >1), joined and cut to n, no wrap; real-rng coverage matches the non-circular moving-block expectation to <0.005. |
| C10 | CONFIRMED | `bar_i_ii` pooled r and slope CIs equal an independent reference that applies ONE count row to all names' observations per replicate; independent-draw reference differs (probe has power). |

## Probe records

Format per the field manual. sandbox: none (no network is used by any probe; read-only on data and repo; `python -I`, no `env -i`/unshare wrapper, so the wrapper self-test does not apply). Toolchain: Python 3.12 venv of the repo, numpy 2.5.4, pandas 3.1.0.

### C5, C6, C7, C1/C2 (`probe_data.py <claim> <mode>`)
```
probe_cmd:     .venv/bin/python -I docs/validation/vx-egv/probes/probe_data.py C5 normal      -> rc 0
falsifier_cmd: ... probe_data.py C5 nodiv   (mutated reading: CLOSE not divided by 100)       -> falsifier_rc 1
probe_cmd:     ... probe_data.py C6 normal                                                    -> rc 0
falsifier_cmd: ... probe_data.py C6 shift   (Cboe dates moved one session later)              -> falsifier_rc 1
probe_cmd:     ... probe_data.py C7 normal                                                    -> rc 0
falsifier_cmd: ... probe_data.py C7 dmy     (dates read as DD/MM/YYYY)                        -> falsifier_rc 1
probe_cmd:     ... probe_data.py C1C2 normal                                                  -> rc 0
falsifier_cmd: ... probe_data.py C1C2 shift                                                   -> falsifier_rc 1
```
Verbatim stdout: `probes/run_all.out` (regenerate with `probes/run_all.sh`). Key lines:
```
### C5 normal  AAPL median ratio 1.1196 | AMZN 1.0861 | GOOGL 1.0844 | GS 1.0873 | IBM 1.0797   PASS rc=0
### C5 nodiv   AAPL median ratio 111.9558 ... IBM 107.9704   FAIL (all five) rc=1
### C6 normal  pooled {-1: 0.0354, 0: 0.7899, 1: -0.0382}  PASS rc=0
### C6 shift   pooled {-1: 0.0592, 0: 0.0354, 1: 0.7899}   FAIL rc=1
### C7 normal  each file: sessions 1713, cboe cov of span 0.9994, missing ['2020-10-16']   PASS rc=0
### C7 dmy     cboe cov of span 0.2732 (1245 missing)   FAIL rc=1
### C1C2 normal  share vx>blind AAPL .991 AMZN .974 GOOGL .960 GS .979 IBM .914
               d-log corr vs blind / vs front: .858/.768, .837/.713, .778/.674, .847/.747, .668/.515
               roll-day median|dlnVX| ratio vs other Mondays: 1.23 1.11 0.89 1.26 1.42   PASS rc=0
### C1C2 shift   FAIL ['GS:track'] rc=1
```
Honest notes on C1/C2 probe: it was tuned in four passes after seeing the first output, because the first "roll day" definitions were confounded: (a) front_expiry changes nearly daily (weeklies), so rolls were redefined as the first session after each third Friday; (b) that day is a Monday, so the control became other Mondays; (c) IBM reports right after the third Friday and VX legitimately jumps when earnings enter its 30-day window (six such roll days showed jumps of that kind; the per-day detail was removed with `probes/ibm_roll_detail.out`, see the header), so days within 3 sessions of an event, and days 18-25 sessions before one, are dropped from the roll set; (d) mean was replaced by median (one very large VXIBM move dominated the mean). Threshold 1.5 was fixed after these passes, so the "no roll jump" leg is weakly pre-registered. The C1C2 shift mutant is killed only by GS (rc=1), a weak falsifier; the C5/C6/C7 falsifiers fail on all names.
Also observed: cm30_blind_iv is NaN on 494-512 of the 1713 sessions per name (not a Cboe issue).

### C4 (`probe_c4.py`)
```
probe_cmd:     .venv/bin/python -I docs/validation/vx-egv/probes/probe_c4.py   -> rc 0 (PASS), output in probes/c4.out
falsifier_cmd: same script with 'CLOSE' in c.columns replaced by 'SETTLE' in c.columns (probes/mutants/c4_mut.py) -> falsifier_rc 1
```
Not re-fetched (no network); evidence is the builder's `fetch_log.json` plus the files and their sha256, so this is a record check, not a live URL check.

### C9 (`probe_c9.py <module>`)
```
probe_cmd:     .venv/bin/python -I docs/validation/vx-egv/probes/probe_c9.py src/earnings_vol/stats/vx_crosscheck.py  -> rc 0, 16 checks ok (probes/c9.out)
```
The probe passes a scripted fake RNG to record `integers(low, high, size)` and to supply known starts, then compares counts with a reference built from the claim (concatenate [s, s+l) blocks, cut to n); it also checks real-RNG per-session mean counts against the non-circular moving-block expectation nb*k_j/(n-l+1) with 100,000 replicates, and l=1 iid behaviour.
Mutants (copies, ORIGINAL checksum unchanged afterwards):
```
m1_highbound   integers(0, n - block)           -> falsifier_rc 1 (5 assertions FAIL)
m2_circular    starts on [0,n) with modulo wrap  -> falsifier_rc 1 (4 assertions FAIL)
m3_floor       nb = n // block                   -> falsifier_rc 1 (killed by ValueError reshape, not by an assertion)
m4_extra_block nb = ceil(n/block) + 1            -> falsifier_rc 1 (killed by ValueError reshape, not by an assertion)
m5_nonoverlap  fixed starts k*block, rng ignored -> falsifier_rc 1 (killed by IndexError: fake rng never called)
```
m3-m5 die by exception rather than a logic assertion, so they show the probe is not vacuous but are weaker kills than m1/m2.

### C10 (`probe_c10.py <tools module>`)
```
probe_cmd:     .venv/bin/python -I docs/validation/vx-egv/probes/probe_c10.py tools/vx_crosscheck.py  -> rc 0 (probes/c10.out)
  pooled r CI   got (0.5223, 0.701)  want (0.5223, 0.701)
  pooled slope CI got (1.4869, 2.3669) want (1.4869, 2.3669)
  independent-draw reference r CI (0.5263, 0.7213)  differs -> power ok
falsifier c10_m1_shifteddates (each name's dates shifted by a different offset when stacked)  -> falsifier_rc 1  (r CI 0.5223, 0.6928)
falsifier c10_m2_rolledcounts (pooled uses np.roll(counts) )                                 -> falsifier_rc 1  (r CI 0.5135, 0.7066)
```
Scope: this tests `bar_i_ii` pooled (also used for lags, secondary changes, maturity via the same function). `level_block` pooled reuses the same count matrix and stacked positions (read in `tools/vx_crosscheck.py`) but is not separately probed.

## Not claimed
Values of agreement statistics (not EGV claims per the ledger). C2 and C3 stay UNVERIFIABLE by channel B and are left to channel A.
