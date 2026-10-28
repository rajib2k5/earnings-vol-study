# data/derived

This folder holds **small tables derived from two DoltHub databases**:

- [post-no-preference/earnings](https://www.dolthub.com/repositories/post-no-preference/earnings)
- [post-no-preference/options](https://www.dolthub.com/repositories/post-no-preference/options)

The pipeline tables will be made by the code in `src/` and `tools/`, not by hand.

At milestone 0 it holds one file:

| File | What it is | How it was made |
|---|---|---|
| `earnings_calendar_30_large_caps.json` | 336 rows of `earnings_calendar` (`act_symbol`, `date`, `when`) for 30 large caps, queried for 2024-01-01 → 2026-10-27 (the rows run 2024-01-12 → 2026-10-27), as returned by DoltHub's SQL API | The exact query and the commit it ran against are inside the file: `commit_ref` is only the branch name (`master`, which moves), and `resolved_commit` is the commit hash that `master` pointed to when the file was fetched, with `resolved_commit_note` saying how it was chosen. It is the input to `research/prototypes/spacing.py`, the gap analysis behind ADR 0004. |

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
folder or anywhere else. That covers the CBOE single-stock volatility indices
and the prices downloaded with `yfinance`. (A handful of single prices are
quoted in prose as worked examples, in ADR 0002 and `research/prototypes/worked.py`;
no series is.) We read them from the
sources on our own computer and use them there. They stay outside git: the
downloads live under `VOL_DATA_DIR` (see `src/earnings_vol/config.py`), which
is outside the repository, and `.gitignore` also blocks `data/raw/` and
`data/cache/`. If you want them, get them from the sources yourself and follow
their terms.

Raw DoltHub clones are not committed either; only the small derived tables
that belong here are.
