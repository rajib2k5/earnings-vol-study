# Data notice

This repository is a public portfolio. It holds the real data that the app and the docs need: the exported
app JSON in `app/public/data/`, small derived tables in `data/derived/`, the hand look-ups in `data/manual/`, and
real values quoted in the docs. It holds no bulk raw files. Vendor downloads, the Dolt clones and their private
copies, and the local cache stay in git-ignored folders under `$VOL_DATA_DIR`. `tools/licensing/check_data_files.py`
checks this on every test run (ADR 0001 §7, owner decision of 2026-10-29).

**The data is not covered by this repository's MIT licence.** Each source keeps its own terms:

| Source | What we use | What is committed | Terms, in one line |
|---|---|---|---|
| DoltHub `post-no-preference/earnings` and `post-no-preference/options` | Earnings calendar, EPS history and estimates, option chains | Derived tables in `data/derived/`, the app JSON | CC BY-SA 4.0. Tables derived from them in `data/derived/` are shared under CC BY-SA 4.0 too (`data/derived/LICENSE`, `data/derived/README.md`). |
| Wikipedia, "List of S&P 500 companies" | Company names, GICS sectors, CIK numbers | Those columns of `security.parquet` | Text under CC BY-SA 4.0. |
| Yahoo Finance, read with `yfinance` | Daily prices and market capitalisations | Two labels made from them: `security.in_universe` and `timing_check.gap_verdict_yf` (and the funnel's share built from it). They fall under Yahoo's terms, not CC BY-SA | Yahoo's terms of service apply. `yfinance` is not affiliated with Yahoo. |
| FRED, Federal Reserve Bank of St. Louis: `DTB3` | The 3-month Treasury bill rate | No `DTB3` value; it is an input to the committed IVs and moves (the discount factor and the carry) | Public domain (Federal Reserve Board data); FRED asks for a citation, given in `data/derived/LICENSE`. |
| FRED: `VIXCLS` | The VIX close | Nothing | `VIXCLS` is Cboe data and stays subject to Cboe's copyright. |
| Cboe Global Markets | VIX and single-stock volatility indices (VX\*) | Nothing | Cboe's terms of use apply. |
| Company press releases and newswires | Release dates and times, cited by URL in `data/manual/press_release_checks.csv` | Dates, times, URLs and short notes in our own words | Facts quoted with a link to the source page. The pages keep their owners' copyright. |
| SEC EDGAR | 8-K filing times (accepted 2026-10-28; no request made yet) | Nothing yet | US government public data. Access follows SEC's fair-access policy. |
| NYSE trading calendar, via `exchange_calendars` | Session dates | `session.parquet` | Public facts. The library is Apache-2.0. |

## What each source's terms restrict

One line per source. "Channel A" is the milestone-2 review's reading of the primary sources, retrieved 2026-10-29
([`docs/validation/probes/m2/channel-a.md`](docs/validation/probes/m2/channel-a.md) §G); the restrictions are
paraphrased, and whether a committed use is allowed is the owner's call, not legal advice.

- **DoltHub (CC BY-SA 4.0):** credit the creators and indicate changes (legal code §3(a)(1)); adapted material must be
  shared under CC BY-SA or a compatible licence, with no additional or different terms (§3(b)(1), §3(b)(3)). Who
  supplied the uploaded option quotes, and so whether they could license them, is not stated: not checked.
- **Wikipedia (CC BY-SA 4.0):** the same attribution and ShareAlike conditions; Wikimedia's own terms of use: not
  checked.
- **Yahoo Finance:** the terms of service bar reproducing, modifying or distributing Yahoo content without explicit
  written permission (§2(h)), any commercial use (§2(e)), and automated collection such as scrapers without permission
  (§2(d) item 9); the `yfinance` README says the API is for personal use (Channel A §G3). Whether the two committed
  labels count as distributing Yahoo content is an open owner question.
- **FRED `DTB3`:** marked "Public Domain: Citation Requested"; FRED's legal page asks for attribution of FRED content
  (Channel A §G2).
- **FRED `VIXCLS`:** marked "Copyrighted: Citation Required" (Cboe data reprinted with permission); FRED's legal page
  bars redistributing third parties' proprietary data for commercial use without the provider's permission (Channel A
  §G5).
- **Cboe:** the website terms (last updated 2022-11-16) allow one copy for personal, non-commercial use, and bar
  publishing or distributing without Cboe's prior written consent, creating derivative works, and **using the
  materials to verify or correct other data** (Channel A §G4). That last term bears on the planned VX\* validation
  (data model §6); whether the VX\* downloads fall under these website terms or a separate data agreement: not checked.
- **Company press releases:** each company's site terms: not checked. We store facts (dates, times, URLs) and no quoted
  text.
- **SEC EDGAR:** at most 10 requests a second, with a contact address in the User-Agent, as recorded at milestone 0
  (data model §1.3); not re-checked (no SEC request has been made).
- **`exchange_calendars`:** the library is Apache-2.0 (Channel A §F1); the session dates are facts.
- **Kaggle and OptionsDX:** named in the owner's data decision of 2026-10-29, but not used by this repository yet: not
  checked.

Tests use hand-worked, made-up values, not vendor data.
