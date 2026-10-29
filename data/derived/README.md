# data/derived

This folder holds **small tables derived from two DoltHub databases**:

- [post-no-preference/earnings](https://www.dolthub.com/repositories/post-no-preference/earnings)
- [post-no-preference/options](https://www.dolthub.com/repositories/post-no-preference/options)

The pipeline tables are made by the code in `src/` and `tools/`, not by hand. Each file is the committed part of a
table in the schema registry (`src/earnings_vol/schema.py`): class-R columns (Yahoo or CBOE values, names ending in
`_yf` or `_cboe`) are dropped by `store.write_derived`, which also refuses local-only tables. The same inputs give the
same bytes.

| File | What it is | Made by |
|---|---|---|
| `security.parquet` | The 499 S&P 500 constituents of Wikipedia revision 1382178819 (one share class per company): name, GICS sector and sub-industry, CIK, and the universe flag (the 50 of the study, chosen by a one-time Yahoo market-cap rank; the flag is a class-F label, and the rank itself is not committed) | `python -m earnings_vol.events.run` |
| `ticker_alias.parquet` | ticker → security over time (FB → META, UTX → RTX) | same |
| `session.parquet` | NYSE sessions 2016–2027 from `exchange_calendars` (XNYS), with half days and the snapshot era | same |
| `events.parquet` | 1,353 announcements of the 50 companies from `earnings_calendar`, with day 0, the timing label and its status, links, sample and exclusion reason. Timing labels are provisional: 20 were checked against press releases (`data/manual/press_release_checks.csv`), the rest are the calendar's (`not_checked`) | same |
| `eps.parquet` | one row per company and fiscal period from `eps_history`, matched to its announcement, with the last weekly consensus before day −1 from `eps_estimate` | same |
| `session_snapshot.parquet` | for every company and session 2020-01-02 → 2026-10-26: is an option snapshot there (`ok`, `stale_repeat`, `missing`)? From `option_chain` | `python -m earnings_vol.measures.run --only snapshots` |
| `earnings_calendar_30_large_caps.json` | 336 rows of `earnings_calendar` (`act_symbol`, `date`, `when`) for 30 large caps, queried for 2024-01-01 → 2026-10-27 (the rows run 2024-01-12 → 2026-10-27), as returned by DoltHub's SQL API (milestone 0) | The exact query and the commit it ran against are inside the file: `commit_ref` is only the branch name (`master`, which moves), and `resolved_commit` is the commit hash that `master` pointed to when the file was fetched, with `resolved_commit_note` saying how it was chosen. It is the input to `research/prototypes/spacing.py`, the gap analysis behind ADR 0004. |

The DoltHub commits read are pinned in `params.yaml` (`dolt`), and every table records them (`events.calendar_commit`;
the stage manifests). The Wikipedia columns of `security.parquet` are CC BY-SA 4.0 as well (attribution: Wikipedia,
"List of S&P 500 companies", revision 1382178819).

## Licence: CC BY-SA 4.0 (ShareAlike)

Both DoltHub repositories declare the licence *Attribution-ShareAlike 4.0
International* (each has a `LICENSE.md` with that title). Files here are
**derived / modified** from them, so they are shared under the same licence:

- **Attribution**: the original data is from DoltHub, repositories
  `post-no-preference/earnings` and `post-no-preference/options` (links above).
  We selected and filtered it. DoltHub and the original authors do not endorse
  our changes.
- **ShareAlike**: if you build on these files, share your version under
  CC BY-SA 4.0 or a compatible licence.
- Licence text: <https://creativecommons.org/licenses/by-sa/4.0/legalcode>

See [`LICENSE`](LICENSE) in this folder. The code in the rest of the repository
is MIT-licensed (root `LICENSE`); the MIT licence does not apply here.

## What is never committed here

**No CBOE or Yahoo Finance dataset is committed to this repository**, in this
folder or anywhere else (the `in_universe` flag in `security.parquet` is a label, not a value; the market-cap rank behind it is not committed). That covers the CBOE single-stock volatility indices
and the prices downloaded with `yfinance`. (Since the milestone-1 review the
worked examples in ADR 0002 and `research/prototypes/worked.py` no longer
quote Yahoo prices, and `tools/licensing/scan_real_rows.py` checks the tree
against the local raw files.) We read them from the
sources on our own computer and use them there. They stay outside git: the
downloads live under `VOL_DATA_DIR` (see `src/earnings_vol/config.py`), which
is outside the repository, and `.gitignore` also blocks `data/raw/` and
`data/cache/`. If you want them, get them from the sources yourself and follow
their terms.

Raw DoltHub clones are not committed either; only the small derived tables
that belong here are.
