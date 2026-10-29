# M2 validation, Channel A: documentation and method audit

- **Channel:** A (primary sources only). No code was executed, no probe written or run, no test run. The only file
  written is this one. No request was made to any SEC host; dolt was not run.
- **Retrieval date for every web source below:** 2026-10-29.
- **Installed versions read** (from `env-pin.txt` and the dist-info folders): scipy 1.18.1, exchange-calendars 4.13.2,
  Python 3.12. Where an official docs page was unreachable, the installed library source of that exact version was read
  instead; that is the primary source matched to the version.
- **Default verdict:** REFUTED until a primary source confirms. "Analytic" means a derivation shown here, not a
  source; it is labelled as such.
- **Quoting:** sources that are public domain (Federal Register), open-licensed (scipy BSD, exchange_calendars
  Apache-2.0) or the repository's own files are quoted briefly. Third-party copyrighted sources (Cboe, FINRA, FRED,
  Yahoo, the Dubinsky-Johannes paper) are paraphrased with an exact locator, with one short quote in all.
- Paths: `<repo>` is the repository root.

## Summary table

| Item | Sub-claim | Verdict |
|---|---|---|
| A1 | `black.py:45-50` is the Black (1976) formula | UNVERIFIABLE (paper unreachable); analytic check passes |
| A2 | Price strictly increasing in w, so root ⇔ P(w_min) < mid < P(w_max) | CONFIRMED (analytic) |
| A3 | brentq `xtol=1e-15, rtol=1e-14, maxiter=200` are legal in scipy 1.18.1 | CONFIRMED |
| A4 | brentq raises when f(a), f(b) have the same sign | CONFIRMED (ValueError) |
| A5 | `scipy.special.ndtr` is the standard normal CDF | CONFIRMED |
| B1 | C − P = DF(F − K); F_K = K + (C − P)/DF | CONFIRMED |
| B2 | CBOE takes the forward from the one strike with the smallest \|C − P\|, ties to the lowest strike | CONFIRMED; the median of 4 is a project choice with no source |
| B3 | American early exercise biases C − P on ITM legs | UNVERIFIABLE (primary sources unreachable) |
| C1 | CBOE interpolates σ²T linearly in time, in minutes | CONFIRMED |
| C2 | `termstructure.py:105` interpolates w linearly in τ | CONFIRMED (code reading); the clock differs from CBOE |
| C3 | The ≤ 10-session extrapolation cap | No source: a project choice. CBOE's fallback is uncapped |
| D1 | E = (w₁τ₂ − w₂τ₁)/(τ₂ − τ₁) is D-J's term-structure estimator | CONFIRMED against the 2004 D-J draft; the 2019 RFS version is UNVERIFIABLE |
| D2 | D-J count trading days | CONFIRMED weakly (2004 example only) |
| D3 | D-J need both expiries to span the event | CONFIRMED; D-J also need both to expire before the *next* announcement, which the code does not check |
| D4 | Negative E | D-J set it to zero. The ADR deliberately keeps it signed: a documented divergence |
| D5 | √(2/π)·√E is E\|jump\| for a normal jump | CONFIRMED (analytic; second-order caveat) |
| E1 | Good-Friday expiry: the last trading day is the Thursday before | CONFIRMED ("generally Thursday") |
| E2 | The exercise value is fixed at the close of the last trading day | REFUTED as stated: the exercise decision cut-off is 5:30 p.m. ET |
| E3a | BMO on expiry day ⇒ that expiry spans | CONFIRMED |
| E3b | AMC on expiry day ⇒ that expiry must not hold the event | REFUTED as an absolute; materiality unmeasured |
| F1 | exchange_calendars 4.13.2 XNYS counts 13:00 early closes as sessions | CONFIRMED |
| F2 | `calendar.py:80-82` counts a half session as 1 | CONFIRMED |
| G1 | DoltHub repos are CC BY-SA 4.0 | CONFIRMED at the pinned commits |
| G2–G5 | DATA.md terms for FRED, Yahoo and Cboe | Accurate in one line, but restrictions are omitted, and several committed files contradict "never committed". **Escalate** (licensing) |
| H | `check_data_files.py` reads the index and "cannot be bypassed" | It reads the index (`git ls-files -s -z`). "Cannot be bypassed" is REFUTED by its own docstring; hypotheses listed below |
| I | ADR 0003 text against the code | 14 divergences listed; 2 not documented anywhere |

---

## A. Black-76 and the inversion (prereg 1a–1c)

**A1. The formula is Black (1976).** UNVERIFIABLE.
- *Source tried:* Black, F. (1976), J. Financial Economics 3(1–2):167–179, doi:10.1016/0304-405X(76)90024-6.
  ScienceDirect returned HTTP 403, and no legitimate free copy was found. Secondary pages (Wikipedia, vendor docs) are
  not accepted.
- *What the code does* (`<repo>/src/earnings_vol/measures/black.py:45-50`):
  `d1 = (np.log(f / k) + 0.5 * w) / s`, `d2 = d1 - s` with `s = sqrt(w)`,
  `c = df * (f * ndtr(d1) - k * ndtr(d2))`, `p = df * (k * ndtr(-d2) - f * ndtr(-d1))`.
  This is the form stated in the task, with σ²T replaced by the total variance w.
- *Analytic check (not a source):* C − P = DF[F(N(d1) + N(−d1)) − K(N(d2) + N(−d2))] = DF(F − K) identically, so the
  pair is parity-consistent.

**A2. Strictly increasing in w; a root exists exactly when P(w_min) < mid < P(w_max).** CONFIRMED (analytic).
- ∂C/∂w = DF·F·φ(d1)/(2√w) > 0 for every w > 0. This uses the identity F·φ(d1) = K·φ(d2). The put has the same
  derivative by parity.
- A continuous, strictly increasing price gives a root on the open interval exactly when the strict inequalities hold
  (intermediate value theorem). `has_root` (`black.py:53-55`) uses strict inequalities, so a price exactly at an
  endpoint is refused. That is harmless.
- **Caveat on the ADR text (`<repo>/docs/adr/0003-iv-measures.md:144-145`).** "The lower end always holds after the
  filter" is not universally true.
  - At K = F, the price at w = 1e-8 is DF·F·(2N(5e-5) − 1) ≈ DF·F·3.99e-5. That reaches 0.05 at F ≈ 1,253.
  - The code tests both ends (`black.py:55`), so there is no consequence for the pipeline.
- **Hypothesis for Channel B.** In floating point, deep-OTM prices at small w underflow to 0. The function is then
  only non-decreasing, which is still safe because mid ≥ 0.05 > 0.

**A3. brentq tolerances are legal.** CONFIRMED.
- *Source:* installed scipy 1.18.1, `scipy/optimize/_zeros_py.py` (BSD-3).
  - Line 11: `_rtol = 4 * np.finfo(float).eps` (≈ 8.88e-16).
  - Lines 853-856: brentq raises only `if xtol <= 0` or `if rtol < _rtol`.
  - Docstring lines 772-774: maxiter "Must be >= 0".
  - So 1e-15 > 0, 1e-14 ≥ 8.88e-16, and 200 ≥ 0 are all legal. (The docs page
    `docs.scipy.org/doc/scipy-1.18.1/...brentq.html` returned 404, so the installed source was used.)
- **Hypothesis for Channel B (bears on prereg 1b's "rel err < 1e-9").** The guaranteed stop is
  |x − x0| ≤ xtol + rtol·|x0| (docstring lines 808-811).
  - At w = 1e-8 that guarantees a relative error of only about 1e-7. The API does not promise 1e-9 near W_MIN; Brent
    often does better.
  - At realistic w (≥ 1e-4) the bound is about 1e-11.

**A4. Same-sign ends raise.** CONFIRMED.
- scipy v1.18.1 `scipy/optimize/Zeros/brentq.c` (GitHub tag v1.18.1): if f is exactly 0 at an endpoint, that endpoint
  is returned as converged. Otherwise, when `signbit(fpre)==signbit(fcur)` it sets `SIGNERR`.
- The installed `_zeros` binary carries the message `f(a) and f(b) must have different signs`.
- The installed test `scipy/optimize/tests/test_zeros.py:905-919` asserts `ValueError` for brentq on same-sign ends.
- A NaN function value raises ValueError (`_zeros_py.py:104-116`).
- The path is not reached in `black.py`, because `has_root` gates the call (`black.py:61-62`).

**A5. `ndtr` is the standard normal CDF.** CONFIRMED.
- The docstring compiled into the installed scipy 1.18.1 `special/_special_ufuncs` binary reads: "Cumulative
  distribution of the standard normal distribution", with the integral from −∞ to x of exp(−t²/2)/√(2π).

## B. Put-call-parity forward (prereg 2a, 2b)

**B1. C − P = DF(F − K) for European options, so F_K = K + (C − P)/DF.** CONFIRMED.
- *Source:* Cboe, *Cboe Volatility Index Mathematics Methodology*, v5.0, last revised 2026-02-26, §3(a)(ii), printed
  p.7 (cdn.cboe.com/api/global/us_indices/governance/Cboe_Volatility_Index_Mathematics_Methodology.pdf).
- It gives F = Strike + e^{RT} × (Call − Put). With DF = e^{−RT} this is the code's formula
  (`<repo>/src/earnings_vol/measures/forward.py:52`).

**B2. CBOE uses the strike with the smallest |C − P|.** CONFIRMED, with a divergence.
- *Source:* the same §3(a)(ii), p.7, paraphrased.
  - Cboe identifies the single strike at which |call mid − put mid| is smallest.
  - If several pairs tie, it takes the lowest such strike.
  - Series with null quotes, or with bid > ask, are not candidates.
  - The *Cboe Volatility Index Methodology* v6.0 (2026-02-26), Appendix 3, pp.10-11, works this through with one ATM
    strike per term (1965 and 1960).
- *Code* (`forward.py:50-53`): the 4 smallest |C − P|. A stable `mergesort` on strikes sorted ascending sends ties to
  the lower strike, which matches Cboe's tie rule. F is the median of those F_K.
- **Divergence:** a median of 4 strikes against Cboe's 1. The project justifies it (ADR 0003 §0 step 2,
  `0003-iv-measures.md:123-131`). No primary source was found that uses a median over the k smallest |C − P|. "A
  recognised practice" is therefore UNVERIFIABLE: the choice is the project's own.
- **Smaller differences:**
  - Cboe then takes K0 = the strike at or just below F and averages the put and call at K0. The code instead splits OTM
    at K ≥ F (`chain.py:145`) and interpolates in k.
  - The code's quote filter is stricter than Cboe's: 0 < bid < ask, mid ≥ 0.05, and relative spread ≤ 0.5.

**B3. American early exercise biases C − P on ITM legs.** UNVERIFIABLE.
- *Tried:* Merton (1973), *Theory of rational option pricing*, Bell J. Econ. 4(1), on JSTOR (paywalled), and its MIT
  Sloan working paper 574-71 (dspace.mit.edu handle 1721.1/49331), which returned HTTP 429.
- The ADR's binomial-tree table (`0003-iv-measures.md:453-470`) is a project measurement, not a source.

## C. Variance-time interpolation (prereg 6)

**C1. CBOE interpolates total variance linearly in time, counted in minutes.** CONFIRMED.
- *Source:* Mathematics Methodology v5.0 §3(b), printed pp.8-9 (paraphrased).
  - VI = 100·√{[T₁σ₁²·(M_T2 − M_CM)/(M_T2 − M_T1) + T₂σ₂²·(M_CM − M_T1)/(M_T2 − M_T1)]·M365/M_CM}.
  - The M are minutes to expiry; M365 = 525,600.
  - That is linear interpolation of Tσ² in minutes, then annualisation.
- *Worked:* VIX Methodology v6.0, Appendix 3, p.14, with a 43,200-minute (30-day) target.

**C2. `interpolate` is linear in τ on w.** CONFIRMED (code reading).
- `<repo>/src/earnings_vol/measures/termstructure.py:105`:
  `w = a.w + (target - a.tau) / (b.tau - a.tau) * (b.w - a.w)`.
- This is the same algebra as Cboe's with M → τ (sessions), M_CM → 21 and M365 → 252 (`termstructure.py:194`).
- **Divergences from Cboe:**
  - the clock: NYSE sessions instead of calendar minutes;
  - the target: 21 sessions instead of 30 calendar days;
  - one expiry is kept per τ (`termstructure.py:87-89`).
- ADR 0003 line 250 says `cm30_blind_iv` is "the same session clock with all expiries interpolated, as CBOE does". Only
  "all expiries" is Cboe-like.

**C3. The ≤ 10-session extrapolation cap.** No primary source; it is a project choice, and the ADR does not claim a
source for it.
- Math Methodology v5.0 §2(a), printed p.4 (paraphrased): the near-term is the expiry with days to expiration ≤ the
  constant-maturity term, or, if there is none, the expiry closest to today. With the §3(b) weights, that is linear
  extrapolation with no cap.
- On the page I read, the §2(a) bullet list contains only the near-term rule; I found no next-term rule there.
- The code also applies the cap and a flat-σ single-expiry rule to `cm30_blind` (`termstructure.py:136-144`). That is a
  further departure from "as CBOE does".

## D. Event variance (prereg 8a, 8b, 9)

**D1. The estimator.** CONFIRMED against the D-J working paper; the RFS version is UNVERIFIABLE.
- *Source:* Dubinsky & Johannes, *Earnings announcements and equity options*, draft of September 2004 (file
  business.columbia.edu/sites/default/files-efs/pubfiles/6051/DJ_2006.pdf), §4.1.1, pp.24-25.
  - Term-structure estimator (paraphrased equation): (σ^Q_term)² = [(σ^BS_T1)² − (σ^BS_T2)²] / (1/T1 − 1/T2).
  - Multiplying by T1T2/(T2 − T1) gives T1T2(σ1² − σ2²)/(T2 − T1).
  - Substituting σj² = wj/Tj gives (w1T2 − w2T1)/(T2 − T1). That is ADR 0003 `0003-iv-measures.md:273` and
    `termstructure.py:147-150`.
- *Analytic note:* E = (w₁τ₂ − w₂τ₁)/(τ₂ − τ₁) is unchanged when τ is rescaled, so the clock enters only through
  τ₂/τ₁, as ADR lines 343-348 say.
- *Unreachable:*
  - Dubinsky, Johannes, Kaeck & Seeger (2019), RFS 32(2):646-687, doi:10.1093/rfs/hhy060: OUP is paywalled, and the
    Sussex figshare copy (sussex.figshare.com/articles/journal_contribution/23454023) returned 403.
  - The authors' 2017 NYU Stern slides (stern.nyu.edu, "NYU conference Johannes final.pdf") show the estimator only as
    images. Their Brexit example (1-month 28.21%, 2-month 21.51%, estimate 7.5%) is reproduced by the formula above
    with T in years (my arithmetic: 7.45%). That is consistent, not a confirmation of the 2019 text.

**D2. D-J count trading days.** CONFIRMED weakly, for the 2004 draft only.
- The draft defines Ti as days to maturity in fractions of years (p.24).
- In its Intel example (p.25), the year fractions 0.0198, 0.0992 and 0.2778 equal 5, 25 and 70 business days divided
  by 252 (4.99, 25.0, 70.0), and the draft labels them business days.
- No explicit "252" rule is stated. ADR line 352-353, "Dubinsky & Johannes count trading days", rests on this example.

**D3. Both expiries span the announcement.** CONFIRMED, with one extra D-J condition.
- 2004 draft, p.24 (paraphrased): the two maturities must both expire after the quarterly announcement **and before
  the following quarter's announcement**. Maturity cycles expiring within five days are dropped.
- *Code:*
  - spanning = `sessions.as_of(exp) >= next_anchor[0]` (`<repo>/src/earnings_vol/measures/tables.py:62`);
  - E comes from `spanning[0], spanning[1]` (`termstructure.py:203-205`);
  - nothing checks that T2 expires before the event *after* the next one.
- **Hypothesis for Channel B:** count `iv_daily` rows whose `ev_exp2` is on or after the following event's day 0. The
  count is expected to be rare: the longest expiry is about 42 sessions, and events are about 63 sessions apart.
- τ ≥ 5 matches D-J's five-day drop. D-J's "days" are not specified as sessions.

**D4. Negative estimates.** A documented divergence from D-J.
- 2004 draft, p.26: about 1 in 9 announcements gave a negative estimate, and D-J write "In these cases, we zeroed out
  the estimator".
- ADR 0003 (`0003-iv-measures.md:408-419` and alternatives row 524) deliberately keeps E signed, and rejects flooring as
  biased upward. The ADR does not attribute its policy to D-J, so this is a choice and not a misquote.
- How the 2019 RFS version treats negative estimates is UNVERIFIABLE.

**D5. √(2/π) for the expected absolute move.** CONFIRMED (analytic).
- For X ~ N(0, s²), E|X| = 2∫₀^∞ x·φ(x/s)/s dx = s·√(2/π).
- *Caveat:* in D-J's model the log jump under Q is N(−s²/2, s²) (2004 draft, p.14, Zj = −½σ² + σε). Then
  E|Z| ≈ s·√(2/π)·(1 + s²/8): about +0.045% (relative) at s = 6%, which is negligible.
- `implied_move = √E` matches D-J's jump volatility σ^Q.

## E. Expiration, exercise and the spans rule (prereg 7)

**E1. When the expiration Friday is a holiday, the last trading day is the Thursday before.** CONFIRMED, as a general
rule.
- *Source:* Cboe BZX notice, Federal Register Vol. 91, No. 16, 26 Jan 2026, p. 3234 (Release 34-104645; SR-CboeBZX-2026-007;
  govinfo.gov/content/pkg/FR-2026-01-26/pdf/2026-01376.pdf).
- Standard series generally expire on a Friday, but if the exchange is closed that Friday, "the standard expiration will
  fall on another day of the week, generally Thursday" (public-domain text).
- The OCC By-Laws Article I definition itself was not reached (theocc.com returned HTTP 403).

**E2. "The exercise or settlement value is fixed at the close of the last trading day."** REFUTED as stated.
- *Sources:*
  - OCC advance notice, FR Vol. 78, No. 100, 23 May 2013, pp. 30945-46 (Release 34-69603; SR-OCC-2013-802;
    govinfo.gov/content/pkg/FR-2013-05-23/pdf/2013-12267.pdf). The expiration time is 11:59 p.m. ET on the expiration
    date, which became the third Friday for contracts after 2015-02-01.
  - FINRA Rule 2360(b)(23)(A)(iii) (finra.org/rules-guidance/rulebooks/finra-rules/2360), paraphrased: holders have
    until 5:30 p.m. ET on the business day of expiration to make the final decision to exercise or not.
  - Rule 2360(A)(v) (paraphrased): where exercise-by-exception is waived, the reference price is per OCC Rule 805,
    normally the last sale in the primary market.
- So US equity options are physically settled. The closing price sets the automatic-exercise default, but the holder's
  decision may use information until 5:30 p.m. ET, 90 minutes after the close.

**E3a. A BMO announcement on expiry day D is in that expiry.** CONFIRMED.
- The series trades on its expiration date, after the pre-open news.
- The code gives `as_of(exp) = D = day 0`, so the expiry spans (`tables.py:62`).

**E3b. An AMC announcement on expiry day D must not be in that expiry.** REFUTED as an absolute.
- Under E2, the holder of an expiring near-the-money option can act on an after-close release through 5:30 p.m. ET, so
  the option's value at the 16:00 close carries part of the event.
- The exchanges treat this as real. The same BZX notice (FR 91:3233-3234) declines to list a qualifying security's extra
  expiry on a day with an after-close earnings announcement, because "post-close price volatility may be impacted due to
  the Earnings Announcement" (public-domain text).
- The code classes such an expiry **clean** (`as_of(exp) = D < day 0 = next(D)`).
- Materiality is unmeasured. It needs an AMC release on a day that is also a listed expiration.
- **Hypothesis for Channel B:** count the `chain_expiry` rows whose `as_of(expiration)` equals the announcement date of
  an AMC event. Those rows are clean at sessions before D, and may carry part of E into clean-class interpolation and
  into the `sigma_d_iv` fallback.

**E3c. Good Friday, and an equivalence the docs miss.**
- `as_of(Friday holiday) = Thursday`, which matches E1.
- *Analytic:* for any day 0 that is a session, `as_of(E) >= day0` holds exactly when `E >= day0`, because no session lies
  in (as_of(E), E]. So the milestone §2 row, "Spans when as_of(expiration) ≥ day 0 … Cost: None measured; Good Friday
  expiries are rare" (`<repo>/docs/milestones/02-iv-measures.md:54`), understates its own case: the two rules give
  identical classes. `as_of` matters only for τ (`chain.py:97`).

## F. NYSE sessions (prereg 4)

**F1. exchange_calendars 4.13.2 XNYS counts early closes as sessions.** CONFIRMED.
- *Source:* the installed package (Apache-2.0; `exchange_calendars-4.13.2.dist-info/METADATA`: `License-Expression:
  Apache-2.0`).
- In `exchange_calendar_xnys.py`:
  - `regular_early_close = time(13)` (line 157);
  - the early closes are `special_closes` (lines 220-259): days before or after Independence Day, Black Friday and
    Christmas Eve, plus the ad hoc days;
  - the docstring lists the regularly observed early closes (lines 110-117);
  - the docstring also lists the 1/9/2025 closure (line 149).
- In `exchange_calendar.py`:
  - lines 325-418: sessions are all days of the calendar's business-day frequency with the holidays removed, and special
    closes only change `closes`;
  - `early_closes` docstring, lines 990-993: "Sessions that close earlier than the prevailing normal close."

**F2. A half session counts as 1.** CONFIRMED (code reading).
- `<repo>/src/earnings_vol/events/calendar.py:80-82` returns `self.index[b] - self.index[a]`, one per session whatever
  its close time.
- The session list comes from xcals (`calendar.py:92-112`). `is_half_day` is stored but never used in a count.
- The 0.5 sensitivity of ADR 0003 §0 step 5 is not built (milestone "Not done").

## G. Licences and terms (prereg 15). Escalate: these are licensing and compliance questions for the owner

**G1. DoltHub `post-no-preference/options` and `/earnings` are CC BY-SA 4.0.** CONFIRMED.
- *Source:* the DoltHub SQL API (read-only GET).
  - Query: `SELECT doc_name, LEFT(doc_text,45), LENGTH(doc_text) FROM dolt_docs AS OF '<pinned commit>'`.
  - The pinned commits are options `msfqpodh24viv7prdqdan8517rkjp861` and earnings `fjrb6h5le9h1qiif2j4pl6cpaas7pnee`.
  - Each returns one row, `LICENSE.md`, beginning `Attribution-ShareAlike 4.0 International`, 20,137 characters long
    (the length of the full legal code).
  - At `master` there is also an `AGENT.md`, which was not read as instructions.
- DATA.md:13 is accurate.
- UNVERIFIABLE: app/DATA.md:117-118 says the repository web pages do not state the licence. The page is rendered by
  JavaScript, and the fetch returned only its title.
- Not verifiable from DoltHub: where the uploader got the option quotes, and so whether they could license them. No
  provenance is stated in `dolt_docs`. **Escalate.**
- *CC BY-SA 4.0 legal code* (creativecommons.org/licenses/by-sa/4.0/legalcode.en):
  - §3(a)(1) asks for the creator identification and notices the licensor supplied, an indication of modifications, and
    the licence's text or URI.
  - §3(b)(3) bars imposing additional or different terms on Adapted Material.

**G1 inconsistencies found in the repository.**
1. `<repo>/data/derived/LICENSE:3-4` says everything in the folder is CC BY-SA 4.0, and `:29-30` says Cboe and Yahoo
   data are not in this folder or anywhere in the repository.
   - But `<repo>/data/derived/README.md:24` says `timing_check.parquet` holds `gap_verdict_yf`, a Yahoo-derived label
     under Yahoo's terms, "not CC BY-SA".
   - The two files contradict each other.
   - If the parquet is Adapted Material of the DoltHub data (it carries the `event_id` keys), carving out a column under
     Yahoo's terms may conflict with SA §3(b)(3).
   - That is a legal judgement. **Escalate.**
2. `<repo>/tools/export_app_data.py:63-83` marks FRED, Cboe and Yahoo `"committed": False`, and its attribution text
   (`:102-103`) says Cboe and Yahoo data is never committed. `<repo>/app/DATA.md:112-114, 124, 129` repeats "never …
   exported".
   - But `<repo>/src/earnings_vol/export/funnel.py:105-120` exports `share_gap_contradicts`, computed from
     `gap_verdict_yf`, into `app/public/data/sample_funnel.json`.
   - `security.in_universe` (committed) comes from a Yahoo market-cap rank.
   - So the "never" statements are stale since the owner's 2026-10-29 decision.
3. ADR 0001 §7 contradicts itself.
   - The owner note (`<repo>/docs/adr/0001-overall-architecture.md:277-285`) allows class-R columns to be committed.
   - The unedited bullet at `:309-315` still says class R is "Never committed".
   - The `data/derived/` allow-list at `:301-305` omits `timing_check`, `session_snapshot`, `event_iv` and
     `earnings_calendar_30_large_caps.json`.
   - `:364-365`, "App JSON inherits CC BY-SA", is false for a Yahoo-derived share.
4. `<repo>/app/DATA.md:137`, "No other page shows study results", is stale: the IV measures page exists.

**G2. FRED DTB3.** DATA.md:16 is accurate in one line, but omits the attribution requirement.
- *Sources:*
  - fred.stlouisfed.org/series/DTB3: source Board of Governors of the Federal Reserve System (US), release H.15, notes
    "Discount Basis". The series tag reads "Public Domain: Citation Requested".
  - **The same page disagrees with itself:** it also shows the generic banner that the graph's data are copyrighted and
    the series notes should be reviewed.
  - fred.stlouisfed.org/legal/ (no date shown), paraphrased: proper attribution is required with any FRED content. For
    public-domain series, cite the source and acknowledge FRED. The user is responsible for complying with usage
    restrictions.
- *Gaps:*
  - DATA.md does not state the citation request.
  - The committed attribution text (`export_app_data.py:97-104`) does not mention FRED, although committed `iv_daily`
    is computed with DTB3. `data/derived/README.md:22` does name "FRED's `DTB3`", which partly meets the request.
  - Inconsistency: ADR 0001 §7 class U lists FRED DTB3 as "Committed" (`:307-308`), and data-model.md:196 says it "may
    be committed". `app/DATA.md:112` and the exporter say FRED is "never" committed.
- *Not checked:* the DTB3 → continuous conversion in `events/market.py:8-13, 32` (a 91-day bill on a 360-day discount
  basis). It is outside the listed scope.

**G3. Yahoo Finance.** DATA.md:15 is accurate, but omits the restrictions. **Escalate.**
- *Sources:*
  - Yahoo Terms of Service (legal.yahoo.com/us/en/yahoo/terms/otos/index.html; no effective date visible; about 100k of
    125k characters read), paraphrased:
    - §2(e): no access or reuse of the Services for any commercial purpose.
    - §2(h): no reproducing, modifying or distributing without explicit written permission.
    - §2(d) item 9: no automated collection (robots, scrapers) without prior permission.
    - §14.2(a)(i): Yahoo Finance is provided by Yahoo Finance LLC.
  - yfinance README (github.com/ranaroussi/yfinance, main branch), paraphrased: not affiliated with Yahoo; for research
    and education; the Yahoo Finance API is for personal use only. The library itself is Apache-2.0.
- **The sources differ:** "personal use" comes from the yfinance README. The ToS text I read says "commercial purpose".
- *Gaps:*
  - DATA.md states none of these restrictions.
  - Whether a committed 3-level label (`gap_verdict_yf`) and its exported share count as "distributing" Yahoo content is
    a legal question.
  - So is whether yfinance's automated access is permitted under §2(d) item 9. **Escalate both.**

**G4. Cboe VX\* and VIX index data.** DATA.md:17 is accurate in one line, but omits restrictions that bear on the
validation plan. **Escalate.**
- *Source:* "Terms and Conditions for Use of Cboe Websites" (cboe.com/terms, last updated 2022-11-16), paraphrased:
  - one copy may be viewed, printed and downloaded for personal non-commercial use;
  - without Cboe's prior written consent, no publishing or distributing;
  - no derivative works (the terms name financial products, services and indices);
  - no use of the Materials to verify or correct other data or information.
- The Methodology PDFs carry a similar notice (Math Methodology v5.0, printed p.20).
- *Gap:*
  - ADR 0003's validation plan item 1 compares our IV with VX\* (`0003-iv-measures.md:474-479`), which is using
    Cboe data to verify other data.
  - ADR 0001 §7 (`:358-359`) plans to export statistics such as a correlation with VXAPL.
  - Whether the VX\* CSV downloads fall under these website terms or under a separate data agreement was not
    established.
  - Not checked: the methodology of the single-stock VX\* indices (the ADR calls them "VIX-method").

**G5. VIXCLS on FRED.** DATA.md:16, "VIXCLS is Cboe data … subject to Cboe's copyright", is CONFIRMED.
- fred.stlouisfed.org/series/VIXCLS, notes: copyright 2016 Chicago Board Options Exchange, reprinted with permission.
  The tag reads "Copyrighted: Citation Required".
- FRED's legal page (paraphrased): series with that tag may be used with proper attribution if no prohibited use
  applies. The prohibited uses include redistributing third parties' proprietary data, which the terms tie to
  commercial use without the provider's written permission.
- DATA.md omits "citation required". No VIX value is committed today (milestone §6.4).

## H. `tools/licensing/check_data_files.py`: what the source shows (read only; hypotheses for Channel B)

**What it reads.** It reads the git index:
- `git ls-files -s -z` (`<repo>/tools/licensing/check_data_files.py:66`), which lists tracked paths and staged blobs;
- then `git cat-file --batch-check=%(objectname) %(objectsize)` (`:76-78`) for the blob sizes;
- and for rule 5, `git hash-object --stdin-paths` (`:104-105`) on vendor files of matching size.

Mode `160000` (submodules) is skipped (`:73`).

**"Cannot be bypassed" (prereg 15) is REFUTED by the module's own docstring** (`:19-21`):
- rule 5 "is skipped when that folder is absent (CI)";
- "a copy that was edited escapes it".

**Bypass hypotheses, untested, for Channel B:**
1. **History.** Only the current index is read. A raw file committed and later deleted stays in history, and other
   branches are never read.
2. **Not a commit hook.** It runs only when the tests run (`tests/test_repo_data_files.py:18-21`).
   - `git commit -a`, or a commit without a test run, is never checked.
   - An intent-to-add entry (`git add -N`) shows the empty blob, size 0, until commit time.
3. **Rule 1** (`:51`) matches only directory parts exactly equal to `raw`, `cache`, `dolt_mirror`, `.dolt` or
   `yfinance`, and is case-sensitive. `Raw/`, `raw_data/`, `caches/` and `vendor/` pass.
4. **Rule 2** (`:53`) uses `fnmatch` on the file name with 4 patterns. On Linux it is case-sensitive, so these pass:
   `vixcls.csv`, `VIXCLS.CSV`, `DTB3.txt`, `VIXCLS.csv.gz`, and any renamed download.
5. **Rule 3** (`:49, :55`) checks only the suffixes `.parquet`, `.csv`, `.feather` and `.arrow`, case-sensitively.
   - These pass anywhere: `.CSV`, `.tsv`, `.txt`, `.xlsx`, `.pkl`, `.npy`/`.npz`, `.h5`, `.sqlite`/`.db`, `.orc`,
     `.ipynb` with data in its outputs, and any compressed file (`.csv.gz` has suffix `.gz`; also `.zip`, `.zst`).
   - `.json` outside `data/derived/`, `data/manual/` and `app/public/data/` has only the 50 MB limit.
6. **Rules 3–4 allow any table under `data/derived/` or `data/manual/`** under 10 MB, whatever its content. Rule 5
   alone guards those folders.
7. **Rule 5 catches exact byte copies only.** Each of these escapes:
   - a modified copy (one byte, line endings, re-encoding);
   - a re-serialised parquet (another compression, row order or column subset);
   - a row subset, a concatenation, a format conversion (CSV → parquet);
   - a compressed copy.
8. **Rule 5 ignores pipeline outputs.** It hashes only `raw/` and `cache/dolt/` (`:82, :90-92`), and the docstring says
   `cache/stage/` and the mirrors are not compared.
   - So a hand-copied `cache/stage/<hash>/market_daily.parquet` (it has the `_cboe` VIX columns), or `chain_expiry`
     (the FRED `df`), renamed into `data/derived/`, passes rules 1–5 if it is under 10 MB.
   - Class-R column *names* (`_yf`, `_cboe`) are never inspected by this tool. Only `store.write_derived` drops them,
     and a hand copy bypasses the writer.
9. **Rule 5 depends on the environment.** It is skipped when `VOL_DATA_DIR` points elsewhere, or when
   `~/data/vol-projects/earnings-vol-study` is absent (`:114-116`).
10. **git-lfs.** An LFS-tracked file is a small pointer blob in the index, so rules 4 and 5 see the pointer's size and
    hash. Rules 1–3 still apply by path.
11. **Submodules** (mode 160000) bypass every rule (`:73`).
12. **Clean filters and line endings.** If `.gitattributes` or `core.autocrlf` normalises a staged CSV, its blob hash
    differs from the raw file's `hash-object` hash, so rule 5 misses it. Uncertain: it depends on how `hash-object`
    treats a path outside the repository.
13. **Robustness, not a bypass.** A `missing` object in `cat-file` output is dropped from `size_of` (`:78`), and
    `size_of[sha]` then raises `KeyError` (`:79`): a crash, not a pass.

The tests cover renamed exact copies and paths (`tests/test_repo_data_files.py:24-105`), with made-up bytes. No test
covers a modified, compressed or LFS copy.

## I. ADR 0003 text against the code (prereg 3a, 3b, 5, 6, 8a, 8b)

`file:line` refers to the working tree. "Documented" means the milestone walkthrough §2 or the data model records the
choice.

| # | ADR 0003 says (line) | Code does (file:line) | Status |
|---|---|---|---|
| 1 | Quadratic "weighted by inverse spread" (153) | weight `1.0 / rel[sel]`, inverse **relative** spread (ask − bid)/mid of the OTM quote (`chain.py:176, 208`) | **Undocumented in the ADR.** The chain.py header (`:22`) says relative. The weighting differs in direction in the wings: cheap wing quotes have small absolute but large relative spreads |
| 2 | 1.5√w and 2√w with w undefined (152-154) | the bracket test uses the bracket's own linear w0 (`chain.py:185`); the quadratic window uses `w_ref` = the too-wide bracket's w0, else the w of the valid strike nearest k = 0 (`chain.py:201-206`); the quadratic also needs `a > 0` (`:209`) | Documented (milestone §2 row 3) |
| 3 | T1\* "on the day −1 snapshot" (168) | at `pre`, the last observed session at day −1, else day −2 (`event_iv.py:85, 138, 185`) | Documented (milestone §2 "Pre / post"; ADR 0004 §4) |
| 4 | T1\* = "the shortest expiry" (168) | the shortest **`ok`** expiry (`event_iv.py:138`, `ok_rows`) | Documented (ADR milestone-2 note, line 56) |
| 5 | Follow T1\* "through the window while τ ≥ 5" (174) | followed to `post` only (`event_iv.py:145-157`); the window path is milestone 3 | Scope, documented |
| 6 | Interpolate T1\* "from that day's expiries of the same event class" (175-176), extrapolation not mentioned | interpolation only, `max_extrap = 0` (`event_iv.py:129`); a same-τ expiry is used exactly | Documented (milestone §2 "never extrapolated") |
| 7 | Spanning: "expiration ≥ day 0" (197) | `sessions.as_of(exp) >= day0` (`tables.py:62`) | Documented. Equivalent by E3c, so there is no behavioural difference |
| 8 | τ = sessions in (t, expiry] (155) | (t, `as_of(expiry)`] (`chain.py:97`) | Documented |
| 9 | T2 = "the next spanning expiry" (361) | the next spanning expiry that is **`ok` with τ ≥ 5** (`tables.py:81-83`, `termstructure.py:200-205`). A `no_atm` spanning expiry is skipped and a later one used | **Not stated anywhere I read.** The data model says only "the two spanning expiries" (`data-model.md:474`). The prereg (8a) says "usable" |
| 10 | "E is read at day −1" (356) | `evar_m1` = E at `pre`, which can be day −2 (`event_iv.py:185, 196-199`; flag `pre_is_m2`) | Consistent with ADR 0004 §4 and data model §3.11a |
| 11 | `cm30_blind_iv` "as CBOE does" (250) | the 10-session extrapolation cap and the flat-σ single-expiry rule apply (`termstructure.py:136-144`); the clock is sessions. Cboe has no cap and counts minutes (C3) | ADR wording partial |
| 12 | E needs τ₂ ≠ τ₁ (implicit) | `event_variance` divides by `tau2 - tau1` with no guard (`termstructure.py:149-150`). `interpolate` dedupes by τ (`:87-89`), the E pair does not. Two `ok` spanning expiries with the same τ (two expirations mapping to one `as_of` session) would raise `ZeroDivisionError` | **Undocumented.** Hypothesis for Channel B: do any two expirations of one (security, session) share a τ? |
| 13 | D-J term structure (references) | no check that T2 expires before the following event (D3) | **Undocumented divergence from the cited source** |
| 14 | data model: `n_strikes_valid` = "strikes passing the quote filter" (`data-model.md:431`) | counts strikes that pass the filter, moneyness, bounds **and** have a root (`chain.py:158, 163`) | The data model is inaccurate. Milestone §2 row 2 describes the code correctly |

**Also noted, without divergence:**
- the OTM split `K >= F` (`chain.py:145`);
- the bounds (`chain.py:151-153`), which match "similarly for puts" with upper DF·K;
- strict root bounds (`black.py:55`);
- the forward from strikes whose call and put both pass (`chain.py:133-134`);
- `fwd_dispersion` > 0.5% (`chain.py:139`);
- the class rule with ≤ 21 (`termstructure.py:191`);
- `two_component` taking the longest clean expiry (`termstructure.py:127-130`);
- `flat_sigma` within 10 (`termstructure.py:131-132`);
- E and σ_d² (`termstructure.py:147-150`);
- the `implied_*` definitions (`termstructure.py:153-165`).

These match ADR 0003.

**Not built, as the milestone says:**
- the 3-expiry least-squares E (ADR line 362);
- the half-session 0.5 and non-session 0.1 sensitivities (lines 156, 353-354).

## What could not be reached

| Source | Why |
|---|---|
| Black (1976), ScienceDirect | HTTP 403; no free copy |
| Dubinsky, Johannes, Kaeck & Seeger (2019), RFS | OUP paywall; the Sussex figshare copy returned 403 |
| Merton (1973) | JSTOR paywall; the MIT DSpace working paper returned HTTP 429 |
| OCC By-Laws and Rules (theocc.com) | HTTP 403. The definitions were taken from Federal Register notices and FINRA 2360 instead |
| scipy 1.18.1 docs page | HTTP 404; the installed source was used |
| scipy `_zeros.c` at tag v1.18.1 | HTTP 404; the installed binary's strings and the installed tests were used |
| DoltHub repository web pages | Rendered by JavaScript; only the title came back |
| Yahoo ToS | The last ~25k of 125k characters were not read |
| Cboe single-stock VX\* methodology | Not sought |

## Next steps that this channel cannot settle

1. **Owner or legal (escalate), on the items G1.1, G1.2, G3 and G4:**
   - the CC BY-SA folder-level LICENSE next to a column under Yahoo's terms;
   - the exported Yahoo-derived share;
   - yfinance's automated access under Yahoo ToS §2(d)(9);
   - Cboe's restriction on using data to "verify or correct other data", set against the VX\* validation plan;
   - the unknown provenance of the DoltHub option quotes.
2. **Channel B (runtime):**
   - A3: the brentq relative error near W_MIN;
   - D3: T2 spanning two events;
   - E3b: AMC events on an expiry day;
   - I#9: E pairs that skip a `no_atm` spanning expiry;
   - I#12: equal-τ spanning pairs;
   - the H bypass hypotheses 1–12.
