# History rewrite of 2026-11-09: old to new commit IDs

The owner decided on 2026-11-09 to rewrite this repository's history. The rewritten `main` was pushed on 2026-11-10
and replaced the old `main` (`3d174da`). Every commit got a new ID. This page maps each old ID to its new ID.

## What changed, and why

1. **Commit messages.** The `Co-Authored-By: Claude …` trailer and the "Generated with Claude Code" line were removed
   from every commit message. Old IDs in four subject lines were replaced by the new IDs. Authors and dates did not
   change.
2. **ADR 0003, by owner decision.** In every commit, `docs/adr/0003-iv-measures.md` quoted two per-day
   `volatility_history.iv_current` values from DoltHub (AAPL, 2025-10-30 and 2025-10-31). The rewrite removed them.
   In every commit, that bullet now has the wording of the 2026-11-09 fix: `iv_current` sat about 1 vol point below our
   ATM IV for the ~29-day expiry on both dates. The other per-day option-chain quotes in ADR 0003 stay, as the
   2026-10-29 data rule allows.

No other file changed in any commit. Measured on 2026-11-10 with the old commits still in the local object store:
for each of the 14 pairs, `git diff --name-only <old> <new>` lists only `docs/adr/0003-iv-measures.md`. The new
messages have no Claude line. Neither value is in ADR 0003 in any of the 14 new commits.

**The old commits can still be seen.** GitHub can serve an old commit, with the old ADR 0003 text, to anyone who has
its ID or a direct link. This stays possible until GitHub Support purges the old commits. A clone made before
2026-11-10 also keeps them.

## The map

In commit order, oldest first. A short ID is the first 7 characters of the full ID.

| Old ID | New ID | Date | Subject of the new commit |
|---|---|---|---|
| `6e4ef9db8a49adeccaac7b717177f0920d8f852d` | `6982c7300e91aab6b5e87aa2a8dc7a6e1a26661e` | 2026-10-28 | Milestone 0: scaffold, design ADRs, data model and app shell |
| `3636e983d6117e28d308436e4f2880aa2c7cef18` | `e49a560c3b9494ca1aae5505ece4a3672650b650` | 2026-10-28 | Re-export meta.json so it names the milestone-0 commit |
| `678c26386ce0c7f51ee8eb2ecbe4896eeeab2847` | `db8ca9b036705d2d8eae85a66199906776d1c02c` | 2026-10-29 | Milestone 1: universe, events, timing labels and the sample funnel |
| `040962722df6f197d8a723457b3ae39404d1325a` | `b48f765ae89484dd990770fb514dac18a90ea017` | 2026-10-29 | Re-export app data so it names the milestone-1 commit |
| `1579080d4dd3ad3ce40ca8471026a7cdc09c22c0` | `20aecb903992703a269dbce7809196cea99a69e4` | 2026-10-29 | Milestone 2: IV measures, event variance and the usable-IV funnel step |
| `fca9972c54419fd32f180468e783dda15dc00827` | `9441774165fca896ff09da05a6565cc8dea2a99a` | 2026-10-29 | Re-export app data so it names the milestone-2 commit |
| `d6d5ea419f441980f990a4c33aacbf6d8c804808` | `a58c655442b1f226f1ddd8bbd494f730a7edc429` | 2026-10-29 | Milestone 3: event study, gate G1 and the hypothesis tests |
| `8c3221b9f480b7bea88c2cef367b040cf759eedf` | `4e79f6171adb8cf2e3d1b72126303fb91d699fd7` | 2026-10-29 | Re-export the app data from a58c655 |
| `28e06b3b87ab02ebec9dabd216a1fb0dc375ca80` | `ca25cdddfc8b8d82ae94e3246b430978e72fe1b1` | 2026-10-29 | Milestone 4: drivers of the crush and implied vs realised moves |
| `4a241276e46443816d3e0e5bfb9a706075e68c80` | `1da32c8d8b92dfb309fe572633ae88392f7783b7` | 2026-10-29 | Re-export the app data from ca25cdd |
| `75948b3ef1655c8fa9ba9bffefa67d492d436be4` | `d53cc0e47243cd992447e442969fec75795827e7` | 2026-10-29 | Milestone 5: report draft, exports, screenshots, README and PR/FAQ |
| `71703130abba9da4efc38fa89ac1d4e0693880a4` | `24b88a4d36fbc5f0e8b7cc956f4c413fb063112f` | 2026-10-29 | Re-export the app data from d53cc0e |
| `4c59e781c4b6bf28311698dee715fe0ee51b912e` | `717e4f5f7aa836b9a87cbb01c99c278dde94a02e` | 2026-10-29 | Rebuild the report after the re-export of 24b88a4 |
| `3d174da7f731988f152ac5e361b9fa8d92324c03` | `6b8453f31d3f126e31df4f0d813ba11f376b0f4f` | 2026-10-29 | Learning log: milestones 3-5 checkpoints queued; fix build_report line links |

## Old IDs in the files of this repository

The commit after this page replaces every old ID in the tracked files with its new ID. That includes the ledgers,
milestone pages, ADR 0001, probe scripts, the app's JSON files, `data/derived/results.parquet` (`code_commit`), the
report (Markdown, PDF and DOCX) and the app screenshots whose footer prints the source commit.

Old IDs stay only on this page and in frozen evidence files. A frozen file is not edited, because its text is the
record. A pre-registration was fixed before its run. A probe output and an environment pin hold what a command
printed at the time. A `HISTORY-REWRITE.md` note beside each of these files gives the new IDs:

| Frozen file | Old ID in it | Note beside it |
|---|---|---|
| `probes/m1/p11.out.txt` | `3636e98` | `probes/m1/HISTORY-REWRITE.md` |
| `probes/m2/env-pin.txt` | `0409627` | `probes/m2/HISTORY-REWRITE.md` |
| `probes/m3/env-pin.txt` | `fca9972` (full ID) | `probes/m3/HISTORY-REWRITE.md` |
| `probes/m4/00-preregistration.md`, `probes/m4/out/p10.txt` | `8c3221b` | `probes/m4/HISTORY-REWRITE.md` |
| `probes/m5/env-pin.txt`, `probes/m5/out/p01_oracle.txt`, `probes/m5/out/p11_graph.txt` | `4a24127` (full ID in `p11_graph.txt`), `28e06b3` | `probes/m5/HISTORY-REWRITE.md` |

All paths in this table are under `docs/validation/`.
