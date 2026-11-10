# Channel B: runtime audit of the EDGAR claims E1-E8

Auditor: Channel B (empirical only). No documentation, SEC page or network request was used. Evidence: the cached
submissions files, the code under validation, `data/manual/press_release_checks.csv`, `data/derived/events.parquet`,
`data/derived/session.parquet` and EDGAR's own `filingDate` field. Not read: `edgar-ledger.md`, `probes/edgar/`,
`channel-a.md`, milestone or ADR prose. The claims ledger was not edited. Contact string: never printed or searched for.

Toolchain: Python 3.12.13 (`.venv/bin/python`, env-pin.txt), pandas 3.1.0, exchange_calendars not used. Probes run through
`probes/run_probe.sh` (clean env, `unshare --user --map-root-user --net`, TZ=UTC, `-B -I`, a fresh `-X pycache_prefix`
per run against the stale-pyc trap, 300 s timeout). Self-test: `probes/out/selftest_sandbox.stdout` shows the code and
cache load inside the wrapper and only the loopback interface present (rc 0).

## Verdicts

| ID | Verdict | Mutant | falsifier_rc |
|---|---|---|---|
| E1 | CONFIRMED (payload shape; the URL itself is only indirectly evidenced) | M5_field_rename | 1 |
| E2 | CONFIRMED (cached pages; pages older than 2019-12-25 were never fetched, so not probed) | M3_recent_only | 1 |
| E3 | CONFIRMED | M1_utc_to_ny | 1 |
| E4 | CONFIRMED, with 25 recorded exceptions to the "next business day" rule | M2_fixed_offset | 1 (M2), 1 (M1b) |
| E5 | CONFIRMED | M4_split_semicolon | 1 |
| E6 | CONFIRMED for the operational claim (Item 2.02 carries the earnings releases); UNVERIFIABLE for the wording of the item title (no title in the cache) | M6_item_502 | 1 |
| E7 | CONFIRMED for 2020-2026 through 2026-11-06 (Veterans Day 2026-11-11 is in the future of the cache and not testable) | M7_drop_veterans | 1 |
| E8 | POLICY HALF UNVERIFIABLE (needs the SEC site, i.e. a network request or documentation). CLIENT HALF CONFIRMED. | M8a_no_sleep (rate) and M8b_no_ua (User-Agent) | 1 (M8a), 1 (M8b) |

Every mutation was applied to the real `src/earnings_vol/ingest/edgar.py`, the probe run against it, and the original bytes
restored; SHA-256 of the file before every mutant and after the last: `dcd28cf327aa4c78b0b4d79380b18332b030d64881cb16117e422299007db5fe`
(identical each time, `restored_identical=True` in every `probes/out/falsify_*.txt`). No other file in the repo was written.
Cache files were opened read-only; the cache directory holds no probe script.

## Mutants

| Mutant | Edit in edgar.py | Probe | falsifier_rc | Probe verdict on the mutant |
|---|---|---|---|---|
| M1_utc_to_ny | `.replace(tzinfo=timezone.utc)` -> `.replace(tzinfo=NY)` (acceptanceDateTime read as New York wall time) | e3_timezone.py | 1 | RESULT: REFUTED: (a) code reading disagrees with a press-release label/date; (a) code reading is >60 min from a release stamp; (b) filingDate cut-off consistency below 0.995/0.85; (c) calendar-label a |
| M1b_utc_to_ny_e4 | same as M1 | e4_after_cutoff.py | 1 | RESULT: REFUTED: after-cut-off rate; after-cut-off rate in EDT (summer); after-cut-off rate in EST (winter) |
| M2_fixed_offset | `NY = ZoneInfo("America/New_York")` -> `NY = timezone(timedelta(hours=-4))` | e4_after_cutoff.py | 1 | RESULT: REFUTED: after-cut-off rate; after-cut-off rate in EST (winter) |
| M3_recent_only | `blocks = [recent, *pages]` -> `blocks = [recent]` (read only filings.recent) | e2_extra_pages.py | 1 | RESULT: REFUTED |
| M4_split_semicolon | items split on ";" instead of "," | e5_items_format.py | 1 | RESULT: REFUTED: code selection != independent census |
| M5_field_rename | FILING_KEYS "acceptanceDateTime" -> "acceptedDateTime" | e1_recent_shape.py | 1 | RESULT: REFUTED |
| M6_item_502 | item test "2.02" -> "5.02" | e6_item202.py | 1 | RESULT: REFUTED: event vs placebo contrast |
| M7_drop_veterans | edgar_holidays() without Veterans Day | e7_holidays.py | 1 | RESULT: REFUTED: ('Veterans', '2020-11-11'); ('Veterans', '2021-11-11'); ('Veterans', '2022-11-11'); ('Veterans', '2023-11-10'); ('Veterans', '2024-11-11'); ('Veterans', '2025-11-11') |
| M8a_no_sleep | `sleep(1.0 / MAX_PER_SECOND)` -> `sleep(0.0)` | e8_client_rate_ua.py | 1 | RESULT: CLIENT HALF REFUTED: over 10 requests in a 1 s window |
| M8b_no_ua | User-Agent dropped from the request headers | e8_client_rate_ua.py | 1 | RESULT: CLIENT HALF REFUTED: a request without the User-Agent |

## Probe records

### E1

```
claim_id:      E1
probe_cmd:     probes/run_probe.sh e1_recent_shape.py <fresh-pycache-prefix>   (script: probes/e1_recent_shape.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  51 CIK main files; total recent rows 120329
  first file keys of recent: ['acceptanceDateTime', 'accessionNumber', 'act', 'core_type', 'fileNumber', 'filingDate'] ...
  rows read via edgar.merge_filings: 390040; non-str form/items: 0
  RESULT: SURVIVES
stderr: |
wall_time:     .766874942s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M5_field_rename  (mutation: FILING_KEYS "acceptanceDateTime" -> "acceptedDateTime"; verbatim record in probes/out/falsify_M5_field_rename.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED
verdict:       CONFIRMED (payload shape; the URL itself is only indirectly evidenced)
```

Mutant: FILING_KEYS "acceptanceDateTime" renamed "acceptedDateTime" in edgar.py (code read of the arrays fails).

Evidence: All 51 cached CIK files carry filings.recent with the four arrays, equal lengths, 120,329 rows; 390,040 merged rows read through the code; every 8-K acceptanceDateTime parses. URL half: the cache cannot show the HTTP URL (no network). Indirect only: each file name equals its internal `cik`, and each file is byte-identical to the code fetch path's serialisation, so it was written by `_fetch_json` from a `https://data.sec.gov/submissions/` URL. That the host serves that exact path is not probed.

### E2

```
claim_id:      E2
probe_cmd:     probes/run_probe.sh e2_extra_pages.py <fresh-pycache-prefix>   (script: probes/e2_extra_pages.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  pages listed 256; cached 135; on disk 135
  newest filing of each cached page minus its CIK's oldest `recent` filing (days): min -2117 max -1 (<=0 means page is entirely older)
  events dated before their `recent` block starts: 234; with an Item 2.02 8-K within +-1 day via the code: 232
  RESULT: SURVIVES
stderr: |
wall_time:     8.844468458s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M3_recent_only  (mutation: `blocks = [recent, *pages]` -> `blocks = [recent]` (read only filings.recent); verbatim record in probes/out/falsify_M3_recent_only.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED
verdict:       CONFIRMED (cached pages; pages older than 2019-12-25 were never fetched, so not probed)
```

Mutant: merge_filings reads only filings.recent (`blocks = [recent]`).

Evidence: 135 of 256 listed pages are cached (the rest are older than the code's SINCE cut and were never fetched); every cached page has the same key set as recent, equal-length arrays, filingCount and filingFrom equal to the listing, and is entirely older than its CIK's oldest `recent` filing. 232 of 234 calendar events dated before their `recent` block starts find an Item 2.02 8-K only through the pages (99.1%). The mutant that reads recent only fails the probe. Served-at-URL half: indirect only, as E1.

### E3

```
claim_id:      E3
probe_cmd:     probes/run_probe.sh e3_timezone.py <fresh-pycache-prefix>   (script: probes/e3_timezone.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  == (a) press-release ground truth: code reading (UTC instant -> NY) vs rival (wall clock = NY)
  CRWD  release 2024-08-28 nan   AMC | raw 2024-08-28T20:07:19.000Z | code 08-28 16:07 AMC            ok=True | rival 08-28 20:07 AMC            ok=True
  NVDA  release 2024-08-28 16:20 AMC | raw 2024-08-28T20:21:16.000Z | code 08-28 16:21 AMC            ok=True | rival 08-28 20:21 AMC            ok=True | delta_min code +1 rival +241
  DELL  release 2024-08-29 nan   AMC | raw 2024-08-29T20:14:00.000Z | code 08-29 16:14 AMC            ok=True | rival 08-29 20:14 AMC            ok=True
  AVGO  release 2024-09-05 nan   AMC | raw 2024-09-05T20:21:56.000Z | code 09-05 16:21 AMC            ok=True | rival 09-05 20:21 AMC            ok=True
  ORCL  release 2024-09-09 16:05 AMC | raw 2024-09-09T20:17:34.000Z | code 09-09 16:17 AMC            ok=True | rival 09-09 20:17 AMC            ok=True | delta_min code +13 rival +253
  MU    release 2024-09-25 16:07 AMC | raw 2024-09-25T20:00:27.000Z | code 09-25 16:00 AMC            ok=True | rival 09-25 20:00 AMC            ok=True | delta_min code -7 rival +233
  COST  release 2024-09-26 nan   AMC | raw 2024-09-26T20:17:15.000Z | code 09-26 16:17 AMC            ok=True | rival 09-26 20:17 AMC            ok=True
  JPM   release 2024-10-11 06:55 BMO | raw 2024-10-11T10:46:16.000Z | code 10-11 06:46 BMO            ok=True | rival 10-11 10:46 during_session ok=False | delta_min code -9 rival +231
  WFC   release 2024-10-11 07:03 BMO | raw 2024-10-11T10:45:18.000Z | code 10-11 06:45 BMO            ok=True | rival 10-11 10:45 during_session ok=False | delta_min code -18 rival +222
  BAC   release 2024-10-15 06:45 BMO | raw 2024-10-15T10:46:39.000Z | code 10-15 06:46 BMO            ok=True | rival 10-15 10:46 during_session ok=False | delta_min code +2 rival +242
  GS    release 2024-10-15 nan   BMO | raw 2024-10-15T11:32:34.000Z | code 10-15 07:32 BMO            ok=True | rival 10-15 11:32 during_session ok=False
  JNJ   release 2024-10-15 nan   BMO | raw 2024-10-15T11:37:20.000Z | code 10-15 07:37 BMO            ok=True | rival 10-15 11:37 during_session ok=False
  UNH   release 2024-10-15 05:55 BMO | raw 2024-10-15T10:03:51.000Z | code 10-15 06:03 BMO            ok=True | rival 10-15 10:03 during_session ok=False | delta_min code +9 rival +249
  MS    release 2024-10-16 07:29 BMO | raw 2024-10-16T11:28:47.000Z | code 10-16 07:28 BMO            ok=True | rival 10-16 11:28 during_session ok=False | delta_min code -0 rival +240
  NFLX  release 2024-10-17 16:00 AMC | raw 2024-10-17T20:01:18.000Z | code 10-17 16:01 AMC            ok=True | rival 10-17 20:01 AMC            ok=True | delta_min code +1 rival +241
  PG    release 2024-10-18 06:55 BMO | raw 2024-10-18T11:02:32.000Z | code 10-18 07:02 BMO            ok=True | rival 10-18 11:02 during_session ok=False | delta_min code +8 rival +248
  GE    release 2024-10-22 nan   BMO | raw 2024-10-22T10:34:48.000Z | code 10-22 06:34 BMO            ok=True | rival 10-22 10:34 during_session ok=False
  PM    release 2024-10-22 06:59 BMO | raw 2024-10-22T11:01:37.000Z | code 10-22 07:01 BMO            ok=True | rival 10-22 11:01 during_session ok=False | delta_min code +3 rival +243
  RTX   release 2024-10-22 nan   BMO | raw 2024-10-22T11:00:03.000Z | code 10-22 07:00 BMO            ok=True | rival 10-22 11:00 during_session ok=False
  GOOGL release 2024-10-29 nan   AMC | raw 2024-10-29T20:01:46.000Z | code 10-29 16:01 AMC            ok=True | rival 10-29 20:01 AMC            ok=True
  label+date agreement: code 20/20, rival 9/20
  time-stamped rows within +-60 min of the release stamp: code 11/11, rival 0/11
  == (b) EDGAR filingDate consistency (8-K, weekday, 17:30 NY cut-off)
  code : before-17:30 same-day 6934/6935 (0.9999); at/after-17:30 later-day 223/248 (0.8992); violations 26
  rival: before-17:30 same-day 2387/2389 (0.9992); at/after-17:30 later-day 132/4785 (0.0276); violations 4655
  == (c) calendar labels: events with timing_raw in BMO/AMC and exactly one Item 2.02 8-K on announce_date
  events compared 1297; label agreement code 1292/1297 (0.9961); rival 669/1297 (0.5158)
  RESULT: SURVIVES
stderr: |
wall_time:     2.954356766s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M1_utc_to_ny  (mutation: `.replace(tzinfo=timezone.utc)` -> `.replace(tzinfo=NY)` (acceptanceDateTime read as New York wall time); verbatim record in probes/out/falsify_M1_utc_to_ny.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: (a) code reading disagrees with a press-release label/date; (a) code reading is >60 min from a release stamp; (b) filingDate cut-off consistency below 0.995/0.85; (c) calendar-label a
verdict:       CONFIRMED
```

Mutant: parse_acceptance attaches New York time instead of UTC to the wall clock (`.replace(tzinfo=NY)`).

Evidence: Three independent comparisons, each able to go either way. (a) 20 press releases: UTC reading agrees on date and label 20/20 and sits within +-60 min of the release stamp for 11/11 time-stamped rows (deltas -18..+13 min); the rival NY-wall reading agrees 9/20 and is +222..+253 min off on 11/11. (b) EDGAR filingDate: UTC reading is consistent with the 17:30 NY cut-off in 6,934/6,935 pre-cut-off 8-Ks and 223/248 post-cut-off; the rival reading 132/4785 post-cut-off. (c) calendar BMO/AMC labels: UTC reading agrees 1292/1297, rival 669/1297.

### E4

```
claim_id:      E4
probe_cmd:     probes/run_probe.sh e4_after_cutoff.py <fresh-pycache-prefix>   (script: probes/e4_after_cutoff.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  {'before_n': 6935, 'before_ok': 6934, 'after_n': 248, 'after_ok': 223, 'weekend_skipped': 0, 'before_rate': 0.9998558038932949, 'after_rate': 0.8991935483870968}
  violations: 26
     ('AAPL', '2020-07-30T22:55:04.000Z', '2020-07-30', '2020-07-30 18:55:04')
     ('AMGN', '2018-05-22T21:30:55.000Z', '2018-05-22', '2018-05-22 17:30:55')
     ('AMZN', '2020-07-30T23:05:15.000Z', '2020-07-30', '2020-07-30 19:05:15')
     ('AMZN', '2019-10-24T23:53:55.000Z', '2019-10-24', '2019-10-24 19:53:55')
     ('AMZN', '2004-04-12T21:30:32.000Z', '2004-04-12', '2004-04-12 17:30:32')
     ('CSCO', '2013-08-14T21:46:29.000Z', '2013-08-14', '2013-08-14 17:46:29')
     ('DELL', '2016-07-11T21:30:03.000Z', '2016-07-11', '2016-07-11 17:30:03')
     ('GOOGL', '2020-07-30T22:40:20.000Z', '2020-07-30', '2020-07-30 18:40:20')
     ('GS', '2020-06-29T22:47:00.000Z', '2020-06-29', '2020-06-29 18:47:00')
     ('IBM', '2019-04-04T21:30:23.000Z', '2019-04-04', '2019-04-04 17:30:23')
     ('IBM', '2018-10-17T21:31:00.000Z', '2018-10-17', '2018-10-17 17:31:00')
     ('IBM', '2018-07-19T21:30:41.000Z', '2018-07-19', '2018-07-19 17:30:41')
     ('JPM', '2020-06-29T22:17:19.000Z', '2020-06-29', '2020-06-29 18:17:19')
     ('JPM', '2020-06-29T22:15:54.000Z', '2020-06-29', '2020-06-29 18:15:54')
     ('MA', '2020-02-24T22:30:40.000Z', '2020-02-24', '2020-02-24 17:30:40')
     ('META', '2020-07-30T23:18:23.000Z', '2020-07-30', '2020-07-30 19:18:23')
     ('MS', '2020-06-29T22:16:57.000Z', '2020-06-29', '2020-06-29 18:16:57')
     ('MSFT', '2023-10-16T21:30:10.000Z', '2023-10-16', '2023-10-16 17:30:10')
     ('PG', '2015-11-16T14:01:44.000Z', '2015-11-13', '2015-11-16 09:01:44')
     ('RTX', '2019-10-11T21:30:50.000Z', '2019-10-11', '2019-10-11 17:30:50')
     ('TSLA', '2019-04-19T21:31:09.000Z', '2019-04-19', '2019-04-19 17:31:09')
     ('UNH', '2011-02-15T00:25:37.000Z', '2011-02-14', '2011-02-14 19:25:37')
     ('WFC', '2022-08-15T21:41:32.000Z', '2022-08-15', '2022-08-15 17:41:32')
     ('WFC', '2020-08-07T22:10:44.000Z', '2020-08-07', '2020-08-07 18:10:44')
     ('WFC', '2020-06-29T22:16:44.000Z', '2020-06-29', '2020-06-29 18:16:44')
     ('WMT', '2022-08-17T21:30:43.000Z', '2022-08-17', '2022-08-17 17:30:43')
  EDT (summer): after-cut-off (by the code's local time) 151/174 carry a later filingDate
  EST (winter): after-cut-off (by the code's local time) 72/74 carry a later filingDate
  distinct minutes of day among after-cut-off acceptances: 157 min 1050 max 1318
  RESULT: SURVIVES
stderr: |
wall_time:     2.142246296s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M2_fixed_offset  (mutation: `NY = ZoneInfo("America/New_York")` -> `NY = timezone(timedelta(hours=-4))`; verbatim record in probes/out/falsify_M2_fixed_offset.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: after-cut-off rate; after-cut-off rate in EST (winter)
falsifier_cmd: probes/falsify.py M1b_utc_to_ny_e4  (mutation: same as M1; verbatim record in probes/out/falsify_M1b_utc_to_ny_e4.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: after-cut-off rate; after-cut-off rate in EDT (summer); after-cut-off rate in EST (winter)
verdict:       CONFIRMED, with 25 recorded exceptions to the "next business day" rule
```

Mutant: edgar.NY replaced by a fixed UTC-4 offset (also M1b: UTC->NY on the same probe).

Evidence: 223 of 248 weekday 8-Ks read at/after 17:30 NY carry a later filingDate (summer 151/174, winter 72/74); 6,934/6,935 before 17:30 carry the same-day filingDate. After-cut-off times spread over 157 distinct minutes between 17:30 and 21:58 NY, so the stamp is a real time of day, not a collapsed value. Exceptions: 25 filings at/after 17:30 NY with a same-day filingDate (listed in the output; 13 accepted 17:30:00 to 17:46 NY, just after the cut-off; 12 accepted 18:10 to 19:53 NY, of which 10 fall on 2020-06-29, 2020-07-30 and 2020-08-07 and the other 2 on 2019-10-24 and 2011-02-14), and 1 filing accepted Monday 09:01 NY dated the previous Friday. Their cause cannot be settled from the cache. The claim's content (acceptanceDateTime is the true acceptance instant) holds; "after 17:30 means next-day filingDate" is a strong tendency (89.9%), not a law. The 0.85/0.80 pass levels were fixed after a first look at the data; the separation from the rival reading (2.8%) does not depend on them.

### E5

```
claim_id:      E5
probe_cmd:     probes/run_probe.sh e5_items_format.py <fresh-pycache-prefix>   (script: probes/e5_items_format.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  8-K rows 7183; empty items 0; items not matching comma-separated item numbers 0 []
  rows with a comma 5120; rows with '2.02,9.01' exactly 1594; rows with ; | / or space 0
  8-K rows carrying item 2.02 (independent split on ','): 2312; selected by edgar.item_202_filings: 2312; sets equal: True
  RESULT: SURVIVES
stderr: |
wall_time:     .962859398s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M4_split_semicolon  (mutation: items split on ";" instead of ","; verbatim record in probes/out/falsify_M4_split_semicolon.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: code selection != independent census
verdict:       CONFIRMED
```

Mutant: item_202_filings splits `items` on ";" instead of ",".

Evidence: 7,183 8-K rows: 0 empty, 0 with any separator other than a comma, 5,120 with a comma, 1,594 exactly "2.02,9.01". Some rows use bare numbers ("5,7", "12", 53 rows) but are still comma-separated. The code's Item 2.02 selection equals an independent comma-split census (2,312 = 2,312, same accessions).

### E6

```
claim_id:      E6
probe_cmd:     probes/run_probe.sh e6_item202.py <fresh-pycache-prefix>   (script: probes/e6_item202.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  CRWD  2024-08-28 8-Ks that day: ['2.02,9.01']  has 2.02: True
  NVDA  2024-08-28 8-Ks that day: ['2.02,9.01']  has 2.02: True
  DELL  2024-08-29 8-Ks that day: ['2.02,9.01']  has 2.02: True
  AVGO  2024-09-05 8-Ks that day: ['2.02,8.01,9.01']  has 2.02: True
  ORCL  2024-09-09 8-Ks that day: ['2.02,8.01,9.01']  has 2.02: True
  MU    2024-09-25 8-Ks that day: ['2.02,9.01']  has 2.02: True
  COST  2024-09-26 8-Ks that day: ['2.02,9.01']  has 2.02: True
  JPM   2024-10-11 8-Ks that day: ['7.01,9.01', '2.02,9.01']  has 2.02: True
  WFC   2024-10-11 8-Ks that day: ['2.02,7.01,9.01']  has 2.02: True
  BAC   2024-10-15 8-Ks that day: ['2.02,7.01,9.01']  has 2.02: True
  GS    2024-10-15 8-Ks that day: ['2.02,7.01,9.01']  has 2.02: True
  JNJ   2024-10-15 8-Ks that day: ['2.02,9.01']  has 2.02: True
  UNH   2024-10-15 8-Ks that day: ['2.02,9.01']  has 2.02: True
  MS    2024-10-16 8-Ks that day: ['2.02,9.01']  has 2.02: True
  NFLX  2024-10-17 8-Ks that day: ['2.02,9.01']  has 2.02: True
  PG    2024-10-18 8-Ks that day: ['7.01,9.01', '2.02,9.01']  has 2.02: True
  GE    2024-10-22 8-Ks that day: ['2.02,9.01']  has 2.02: True
  PM    2024-10-22 8-Ks that day: ['2.02,9.01']  has 2.02: True
  RTX   2024-10-22 8-Ks that day: ['2.02,9.01']  has 2.02: True
  GOOGL 2024-10-29 8-Ks that day: ['2.02,8.01,9.01']  has 2.02: True
  ground-truth releases with a 2.02 8-K on the release date: 20/20
  events 1353: Item 2.02 8-K within +-1 day of announce_date 1311 (0.9690); at announce_date+45d (placebo) 0 (0.0000)
  RESULT: SURVIVES
stderr: |
wall_time:     11.876691581s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M6_item_502  (mutation: item test "2.02" -> "5.02"; verbatim record in probes/out/falsify_M6_item_502.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: event vs placebo contrast
verdict:       CONFIRMED for the operational claim (Item 2.02 carries the earnings releases); UNVERIFIABLE for the wording of the item title (no title in the cache)
```

Mutant: item_202_filings matches "5.02" instead of "2.02".

Evidence: 20/20 ground-truth press releases have an 8-K with 2.02 accepted on the release date. 1,311 of 1,353 calendar events (96.9%) have an Item 2.02 8-K within +-1 day of the announce date, against 0 of 1,353 at announce date + 45 days. This shows 2.02 marks earnings releases; whether the 42 events without one are a gap in the 8-K record or in the calendar is outside this claim.

### E7

```
claim_id:      E7
probe_cmd:     probes/run_probe.sh e7_holidays.py <fresh-pycache-prefix>   (script: probes/e7_holidays.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  cached acceptances span 1998-03-06 .. 2026-11-09 ; total 390105
  Columbus  2020-10-12 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2020-11-11 Wed NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 12, 0) in edgar_holidays=True
  Columbus  2021-10-11 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2021-11-11 Thu NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 21, 0) in edgar_holidays=True
  Columbus  2022-10-10 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2022-11-11 Fri NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 10, 0) in edgar_holidays=True
  Columbus  2023-10-09 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2023-11-10 Fri NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 5, 0) in edgar_holidays=True
  Columbus  2024-10-14 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2024-11-11 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Columbus  2025-10-13 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans  2025-11-11 Tue NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 9, 0) in edgar_holidays=True
  Columbus  2026-10-12 Mon NYSE session=True acceptances(NY date, UTC date, filingDate)=(0, 0, 0) in edgar_holidays=True
  Veterans 2026-11-11: after the last cached acceptance, not testable
  control: 1710 other sessions, min acceptances 0, median 180; sessions with zero acceptances (other than targets): [datetime.date(2020, 12, 24), datetime.date(2021, 6, 18), datetime.date(2021, 12, 31), datetime.date(2024, 12, 24), datetime.date(2025, 12, 24), datetime.date(2025, 12, 26)]
  RESULT: SURVIVES
stderr: |
wall_time:     2.767152475s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M7_drop_veterans  (mutation: edgar_holidays() without Veterans Day; verbatim record in probes/out/falsify_M7_drop_veterans.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: REFUTED: ('Veterans', '2020-11-11'); ('Veterans', '2021-11-11'); ('Veterans', '2022-11-11'); ('Veterans', '2023-11-10'); ('Veterans', '2024-11-11'); ('Veterans', '2025-11-11')
verdict:       CONFIRMED for 2020-2026 through 2026-11-06 (Veterans Day 2026-11-11 is in the future of the cache and not testable)
```

Mutant: edgar_holidays() drops Veterans Day (`out = {columbus} | ...`).

Evidence: All 6 Columbus Days (2020-2025) and 2026-10-12, and 6 Veterans Days (2020-2025; observed Fri 2023-11-10): each an NYSE session, with 0 cached acceptances by New York date and 0 by filingDate, while the median ordinary session has 180 acceptances. A UTC-date count above 0 on 11 Nov (5 to 21) is the evening of 10 Nov in New York, not an acceptance on the day. Other zero-acceptance sessions exist (2020-12-24, 2021-06-18, 2021-12-31, 2024-12-24, 2025-12-24, 2025-12-26): the claim is silent on them. Limit: 51 companies, not all filers; zero among 51 filers on a day with a median of 180 is strong but not proof that no filer got a filing accepted.

### E8

```
claim_id:      E8
probe_cmd:     probes/run_probe.sh e8_client_rate_ua.py <fresh-pycache-prefix>   (script: probes/e8_client_rate_ua.py)
sandbox:       probes/run_probe.sh (env -i, unshare --user --map-root-user --net, TZ=UTC, python -B -I)
rc:            0
stdout: |
  requests 150; virtual duration 14.90s; worst count in any half-open 1 s window: 10; min gap 0.1000s
  every request carries the User-Agent header: True ; header names: ['Accept-Encoding', 'User-Agent']
  second run over the same cache makes 0 requests
  real run 2026-11-09T19:16:22Z..2026-11-09T19:17:16Z: 183 requests in 54s = 3.39/s average
  RESULT: CLIENT HALF SURVIVES
stderr: |
wall_time:     .122392729s
toolchain:     python 3.12.13 (.venv), pandas 3.1.0
falsifier_cmd: probes/falsify.py M8a_no_sleep  (mutation: `sleep(1.0 / MAX_PER_SECOND)` -> `sleep(0.0)`; verbatim record in probes/out/falsify_M8a_no_sleep.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: CLIENT HALF REFUTED: over 10 requests in a 1 s window
falsifier_cmd: probes/falsify.py M8b_no_ua  (mutation: User-Agent dropped from the request headers; verbatim record in probes/out/falsify_M8b_no_ua.txt)
falsifier_rc:  1   restored sha256 identical: True   mutant result line: RESULT: CLIENT HALF REFUTED: a request without the User-Agent
verdict:       POLICY HALF UNVERIFIABLE (needs the SEC site, i.e. a network request or documentation). CLIENT HALF CONFIRMED.
```

Mutant: M8a: `sleep(1.0 / MAX_PER_SECOND)` -> `sleep(0.0)`; M8b: User-Agent removed from the request headers.

Evidence: Probed: our client only. With a fake `get`/`sleep` (virtual clock, zero latency, edgar.user_agent replaced by a non-email sentinel) 150 requests across 60 fake CIKs and their extra pages: worst count in any half-open one-second window is 10, minimum gap 0.1 s, every request carries a User-Agent header, a second run over the cache makes 0 requests. Real log: the one logged earlier run made 183 requests in 54 s (3.39/s average, 1 s granularity; the log does not hold per-request times, and 186 files are cached against 183 logged requests, so the log is not a complete record). A request-spacing of exactly 0.1 s plus latency means at most 10 per second only under the half-open window reading. Not probed: that SEC allows 10/s, and that it requires a contact in the User-Agent.

## Notes and limits

- E3 and E4 are decided on three independent grounds that agree; the NY-wall-clock reading fails each of them, so the
  probes could have come out the other way.
- The exceptions to E4's "next business day" tendency are real data; they do not touch what the timing layer relies on
  (the instant), but they mean a filing-date rule cannot stand in for acceptance time.
- The Item 2.02 8-K counts quoted elsewhere (labels resolved or changed) were not audited here, by design.
