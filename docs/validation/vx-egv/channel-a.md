# Channel A (documentation audit), VX* cross-check

Retrieval date for every record: 2026-11-09. Written before reading any Channel B output. No code run, no CSV downloaded.
Environment: env-pin.txt (Python 3.12.13, dolt 2.6.1); the claims concern external products, so the version that matters is the
version of each documentation page, recorded per claim.

Retrieval notes (what worked, what did not):
- Cboe methodology PDF: WebFetch could not extract text (compressed PDF). I saved the PDF to the harness tool-results folder and
  read pages 1-5 and 8-15 as images. Pages 6-7 (2.1 table) were read; page 7 and pages 16+ were not needed.
- cboe.com historical-data page: read via WebFetch (a small model summarises the page; the quotes below are its extraction, not my own
  reading of the raw HTML).
- cboe.com VXAPL/VXGOG dashboards: read, they carry no definition and no CSV description.
- DoltHub: WebFetch got only the title (JS-rendered page). I read the repo docs with the Browser pane instead. The schema URL I guessed
  returned 404; the repo root data page timed out. No column-level documentation page was retrieved.
- Projecteuclid (Künsch 1989): WebFetch returned an empty page twice. Only a search-engine paraphrase exists, which is not admissible.
- A web search summary also claimed Cboe changed strike selection effective 2025-02-10 (notice "Modifications to the Strike Selection in
  Volatility Index Calculations", cdn.cboe.com/resources/release_notes/2025/). I did NOT read that notice. Not used for any verdict.

Primary document used for C1-C3, C5: Cboe, "Cboe Selected Broad-Based Index, Equity and ETF Volatility Indices Methodology",
https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Selected_Broad_Based_Index_Equity_and_ETF_Volatility_Indices.pdf
Version 9.0, last revised March 30, 2026 (Appendix 2, p.15). It applies to the five indices as of that revision.

---

claim_id:    C1
verdict:     CONFIRMED
source:      the methodology PDF above, section 1.1 (p.5) and 2.1 table (p.6)
source_tier: 1
version:     9.0, 2026-03-30
quote:       "designed to measure the market's 30-day expected volatility on the applicable underlying index, equity or ETF"
retrieved:   2026-11-09
note:        Table p.5 lists VXAPL, VXAZN, VXGOG, VXGS, VXIBM as "Cboe Apple/Amazon/Google/Goldman Sachs/IBM VIX Index". Table p.6 gives
             Constant Maturity "30 days" and one option class each (AAPL, AMZN, GOOG, GS, IBM). One stock each.

claim_id:    C2
verdict:     CONFIRMED
source:      the methodology PDF, section 2 (p.5) and section 3 formula definitions (p.9)
source_tier: 1
version:     9.0, 2026-03-30
quote:       "The methodology used for these calculations is the same as that used for the VIX® Index."
retrieved:   2026-11-09
note:        p.9 defines K_i as "Strike price of the ith out-of-the-money option" and Q(K_i) as the bid-ask midpoint. p.10 lists the five as
             "2(a) Bracket Method". Caveat for the code under validation: p.6 says "30 Day Bracket Method", so near/next terms are
             weekly expiries bracketing 30 days, not the monthly-only SPX terms.

claim_id:    C3
verdict:     CONFIRMED
source:      the methodology PDF, section 2.1 table (p.6)
source_tier: 1
version:     9.0, 2026-03-30
quote:       "PM-settled GOOG option contracts expiring at end of week"
retrieved:   2026-11-09
note:        Row VXGOG. GOOGL is not named anywhere in the pages I read (pp.1-6, 8-15). This is a positive statement of GOOG.

claim_id:    C4
verdict:     UNVERIFIABLE
source:      https://www.cboe.com/tradable-products/vix/vix-historical-data
source_tier: 1
version:     undated page (footer "2026 Cboe Exchange, Inc."); the page says VIX data is "Updated Daily"
quote:       "Cboe Global Markets calculates and disseminates dozens of volatility indices, including the seven indices listed below."
retrieved:   2026-11-09
note:        Three separate gaps. (1) The page lists only VXAPL and VXAZN of the five; VXGOG, VXGS, VXIBM are not listed. (2) The documented
             links use host cdn-api.cboe.com/api/global/us_indices/daily_prices/<SYM>_History.csv, not cdn.cboe.com as in the claim.
             (3) No page I read documents the file's columns, so a CLOSE column is undocumented. Whether the cdn.cboe.com host serves
             the same files is an empirical question for Channel B. Note the claim has a testable core that the docs cannot decide.

claim_id:    C5
verdict:     UNVERIFIABLE
source:      the methodology PDF, section 3 (p.9)
source_tier: 1
version:     9.0, 2026-03-30
quote:       "Vol index = σ × 100"
retrieved:   2026-11-09
note:        Supported half: p.9 defines T as "Time to expiration (in years)" and the index as 100 times sigma, so the index level is
             annualised vol in percentage points and level/100 is a decimal annualised vol (as a 30-day constant-maturity risk-neutral
             measure). Unsupported half: no page I read says the CSV `CLOSE` column equals the published index level (not, e.g., a
             rescaled value). Hence UNVERIFIABLE for the claim as worded. Index-level scale is documented; CLOSE-column mapping is not.

claim_id:    C6
verdict:     UNVERIFIABLE
source:      the methodology PDF, section 5 (p.12-13); historical-data page
source_tier: 1
version:     9.0, 2026-03-30
quote:       "Between 9:31 a.m. and 4:00 p.m. ET" (dissemination hours for all five, RTH)
retrieved:   2026-11-09
note:        Cboe documents live dissemination every 15 seconds in RTH. Nothing I read defines the daily-history file's date or says the
             value for date D is the end-of-session value of D. The VIX history page only says "daily closing values" for VIX. Also, the
             index is computed with P.M.-settled weeklies deemed to expire at the 4:00 p.m. ET close (Appendix 3, p.16), consistent with a
             close value at 16:00 ET, but that is an inference, not a statement about the CSV. The "Cboe Volatility Index Mathematics
             Methodology" document, which might define a closing value, was referenced (p.5) but I did not retrieve it.

claim_id:    C7
verdict:     UNVERIFIABLE
source:      the methodology PDF, section 6 (p.14)
source_tier: 1
version:     9.0, 2026-03-30
quote:       "Prior to 2010" (First Value Date for VXAPL, VXAZN, VXGOG, VXIBM; VXGS "Prior to 2014", launch February 1, 2014)
retrieved:   2026-11-09
note:        Documents that each index has existed, with values, since before 2020-01-02. Does not document the history file's coverage,
             its end date, or completeness on "most sessions". The history page gives no start or end date for the single-stock files.
             Coverage to 2026-10-26 is an empirical fact for Channel B.

claim_id:    C8
verdict:     UNVERIFIABLE
source:      https://www.dolthub.com/repositories/post-no-preference/options/doc/master/README.md ; data page .../data/master/volatility_history (header only)
source_tier: 1
version:     repo branch master as served 2026-11-09 (README undated)
quote:       "volatility_history: This table contains both current, week ago, month ago, and year ago high/low implied vols and historical variance."
retrieved:   2026-11-09
note:        The README describes the table at one sentence of granularity and says nothing about maturity, days to expiry or constant
             maturity (full README text read: "About" section, three paragraphs). It has no section describing `iv_current` itself.
             Per the brief, CONFIRMED needs a quotable column-description section; I could not reach one (schema page 404 at my guessed URL,
             repo root timed out, no column comments seen). The data page shows column names only (date, act_symbol, hv_*, iv_*), no
             descriptions. A repo AGENT.md is generic Dolt usage text, nothing on columns. Supporting but not decisive: the README
             is silent on maturity. Dolt version 2.6.1 in the pin does not alter the hosted README.

claim_id:    C9
verdict:     UNVERIFIABLE (primary text not retrievable; reference statement written below for comparison with the code)
source:      Künsch 1989, Ann. Statist. 17(3), 1217-1241, doi 10.1214/aos/1176347265 (projecteuclid.org; page returned empty to WebFetch twice)
source_tier: 4
version:     1989
quote:       (none retrieved. I do not have verbatim text from the paper.)
retrieved:   2026-11-09
note:        A search-engine summary (not admissible) agreed with the reference statement below. Reference statement, from the standard
             definition of the moving-block bootstrap (Künsch 1989; Liu and Singh 1992), stated from my knowledge and flagged as such:
             Given series x_1..x_n and block length l, form the n-l+1 overlapping blocks B_i = (x_i..x_{i+l-1}), i = 1..n-l+1. Draw
             k = ceil(n/l) block start indices i.i.d. uniformly with replacement from {1..n-l+1}, concatenate the blocks, and truncate
             to length n. Block length is fixed, blocks overlap in the source (every start index is allowed, not only multiples of l), and
             there is no wrap-around in the original MBB (circular wrap is the Politis-Romano circular variant, a different
             procedure). Points to check in the code: start-index range is n-l+1 (not n // l), draws are with replacement, truncation to
             exactly n, and l fixed within a repetition. A claim that wraps around should be called circular, not Künsch's.
             Verdict on the wording of C9: the wording "overlapping blocks of fixed length with replacement, joined until length reached"
             matches that reference statement. Status of the claim about THE CODE: pending code.

claim_id:    C10
verdict:     MATCHES BY READING (not a documentation claim; reading only, nothing run)
source:      src/earnings_vol/stats/vx_crosscheck.py (block_counts, session_sums, moment_stats, spread_stats); tools/vx_crosscheck.py lines 170-235, 377
retrieved:   2026-11-09
note:        block_counts is called once per block length (line 377, one rng seeded vx.SEED), giving a (reps, n_sessions) matrix `counts`.
             The same matrix is passed to bar_i_ii and level_block for every name and for "pooled". Pooled changes are stacked and dated by
             session position (`pos = end - w0`), so replicate r weights session j by counts[r, j] for all names alike: the same dates for
             all five names in each repetition. Per-name rows also use the same replicate draws. Caveat: level_block pooled
             (by_year False) stacks the per-name positions the same way, so it is also consistent. Not checked: that tests exercise this,
             and the bar-iv event bootstrap (event_bootstrap_ratio) resamples events, not dates, and is outside C10 as worded.

(C9 code comparison, added after the code was provided, reading only)
claim_id:    C9 (code vs reference statement)
verdict:     MATCHES the reference statement; primary text still not retrieved
source:      src/earnings_vol/stats/vx_crosscheck.py block_counts (lines 116-133)
retrieved:   2026-11-09
note:        Reference points checked: n-l+1 start positions: rng.integers(0, n - block + 1) gives 0..n-block, correct. With replacement and
             independent: starts drawn i.i.d. of shape (reps, nb). nb = ceil(n/block) via -(-n // block). Fixed block length `block`,
             consecutive sessions s..s+block-1, concatenated and truncated with [:, :n]; no modulo/wrap, so not circular. Guard 1<=block<=n.
             Counts (bincount of the drawn session indices per replicate) are the sufficient summary for statistics that depend only on
             multiplicities; weighted statistics are valid only if the statistic does not depend on order within the series, which holds for
             the moments, medians and shares used here but not for anything lag-dependent computed on the resampled series.
             Künsch 1989 / Lahiri 2003 / Davison and Hinkley 1997: I could not retrieve any of them (Project Euclid returned an empty page
             three times); C9 therefore stays on my stated reference statement, not a quoted primary text.
