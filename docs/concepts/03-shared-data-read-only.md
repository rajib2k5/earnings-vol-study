# Reading shared data without writing to it: fingerprints and a private mirror

Concept note for milestone 1. Written 2026-10-29. The decision is
[ADR 0001 §3](../adr/0001-overall-architecture.md); the code is `src/earnings_vol/ingest/dolt.py`.

## 1. The setting

Four projects read the same two DoltHub clones on this machine. A Dolt clone is a database stored as files in a
`.dolt/` folder, much as a git repository lives in `.git/`. If any project writes into it — a stray `INSERT`, a
`dolt pull` in the middle of someone else's read, a garbage collection — the others can read a mixture of two data
versions, or a damaged store.

## 2. Three independent guards

1. **Only read statements.** The query function refuses anything that is not one `SELECT`, `WITH`, `SHOW` or
   `DESCRIBE`: no semicolons (a second statement), no comments (they can hide one), no write keyword anywhere, no
   `dolt_*()` procedure call. Hostile strings are in `tests/test_dolt.py`.
2. **Pin the data version.** Every query reads `table AS OF '<commit>'`. A commit is an immutable snapshot, so a pull
   by someone else between two of our queries cannot mix versions.
3. **Prove nothing changed.** A *fingerprint* is a list of (file, size, modification time) for every file in the
   clone folder, `.dolt/` and anything beside it. Its keys are the set of file names, so a new or deleted file is a
   difference too. Take one before and one after a batch; if they differ, something wrote, and the batch stops.
   (*Widened after the milestone-1 review:* it first covered `.dolt/` only, so a file created beside it went unseen.)

## 3. What the fingerprint found

ADR 0001 planned to run `dolt sql` inside the shared clones. Milestone 1 tested that first on a *copy*. Result
(dolt 2.6.1, 2026-10-29): even `SELECT HASHOF('HEAD')` rewrites four things under `.dolt/` — the manifest, the
journal index, the chunk journal and the statistics store. The bytes come out identical, but the files are written,
so their modification times change. The guard tripped, as designed.

ADR 0001 had decided what to do in that case: switch to a private copy. So the pipeline now

- copies each shared clone into `cache/dolt_mirror/<repo>/` (`refresh_mirror`), checking that the shared clone's
  fingerprint is identical before and after the copy (a pull during the copy would abort it);
- runs every query in the mirror, where dolt may touch whatever it likes;
- checks, around each batch, that the **shared** clone's (size, mtime) fingerprint did not change at all, and that
  the **mirror's** data files kept their bytes (a *content* fingerprint: sizes and SHA-256 of the small metadata
  files, ignoring the modification times dolt touches).

A test reproduces the finding on a throw-away repository made with `dolt init` in a temporary folder
(`test_a_pure_select_touches_files_but_keeps_their_bytes`), so the reason for the mirror is checkable on any machine
with dolt installed.

## 4. Two kinds of fingerprint

| Fingerprint | What it compares | Catches | Used on |
|---|---|---|---|
| stat | path, size, mtime | any write, even of the same bytes | the shared clones: we must not touch them at all |
| content | path, size, SHA-256 of metadata files | a change of data | the mirror: dolt's own touches are harmless there |

The large table files are *content-addressed* (their name is the hash of their contents), so dolt never rewrites one
in place, and their path and size are fingerprinted, not their bytes. That leaves a **known blind spot**: a change of
the same size to one of those files, by something other than dolt, would go unseen in the mirror (the milestone-1
review demonstrated it by flipping bytes). Hashing them would read about 10 GB around every batch, which is too slow.
The shared clones do not depend on this: their stat fingerprint sees any write, whatever its size.

## 5. Things to be able to say in an interview

- The three guards, and why each one alone is not enough.
- Why a test that the guard *can* trip matters: here it did trip, on the first real run.
- Stat versus content fingerprints, and which one protects what.
