#!/usr/bin/env bash
# p15: plant files in the index of a SCRATCH copy of the repository and run
# tools/licensing/check_data_files.py against it (claim 15). Never touches the real repository's index.
# Usage: p15_datafiles.sh <scratch repo copy with .git> <python>
set -uo pipefail
R=$1; PY=$2
case "$R" in */scratchpad/*) ;; *) echo "refusing: not a scratch copy"; exit 2;; esac
V=${VOL_DATA_DIR:-$HOME/data/vol-projects}/earnings-vol-study
cd "$R"
run() {  # $1 label; the checker's last line and exit code
  out=$("$PY" tools/licensing/check_data_files.py 2>&1); rc=$?
  printf '%-62s rc=%d  %s\n' "$1" "$rc" "$(echo "$out" | tail -1)"
}
echo "hooks installed: $(ls .git/hooks | grep -v '\.sample$' | tr '\n' ' ')(none means no pre-commit check)"
echo "untracked M2 data files right now: $(git status --porcelain --untracked-files=all | grep -cE '^\?\? .*\.(parquet|json|csv)$')"
run "T0  index as it is (M2 data files untracked)"
git add -A >/dev/null 2>&1
run "T0b everything staged (what a commit of the tree would hold)"
echo "     largest staged blobs:"; git ls-files -z | xargs -0 du -b 2>/dev/null | sort -rn | head -4 | sed 's/^/       /'
git reset -q
AAPL=$V/raw/yfinance/AAPL.parquet
DTB3=$V/raw/fred/DTB3.csv
MONTH=$V/cache/dolt/options@msfqpodh24viv7prdqdan8517rkjp861/option_chain/2021-02.parquet
cp "$AAPL" docs/notes.txt && git add -f docs/notes.txt
run "T1  exact copy of a Yahoo price file as docs/notes.txt"
VOL_DATA_DIR=/nonexistent "$PY" tools/licensing/check_data_files.py >/dev/null 2>&1; echo "T2  same, no vendor folder (CI)                               rc=$?"
git rm -q --cached docs/notes.txt; rm docs/notes.txt
gzip -c "$DTB3" > data/derived/rates.csv.gz && git add -f data/derived/rates.csv.gz
run "T3  gzip copy of FRED DTB3.csv in data/derived/"
git rm -q --cached data/derived/rates.csv.gz; rm data/derived/rates.csv.gz
{ cat "$DTB3"; echo; } > data/manual/t_bill.csv && git add -f data/manual/t_bill.csv
run "T4  DTB3.csv plus one newline, renamed, in data/manual/"
git rm -q --cached data/manual/t_bill.csv; rm data/manual/t_bill.csv
"$PY" -c "import pyarrow.parquet as pq, sys; pq.write_table(pq.read_table(sys.argv[1]), sys.argv[2], compression='gzip')" "$MONTH" data/derived/quotes_2021_02.parquet
git add -f data/derived/quotes_2021_02.parquet
echo "     re-serialised raw option_chain month: $(du -b data/derived/quotes_2021_02.parquet | cut -f1) bytes, $("$PY" -c "import pyarrow.parquet as pq,sys; print(pq.read_metadata(sys.argv[1]).num_rows)" data/derived/quotes_2021_02.parquet) rows"
run "T5  a whole raw option_chain month re-serialised (bulk raw)"
git rm -q --cached data/derived/quotes_2021_02.parquet; rm data/derived/quotes_2021_02.parquet
cp "$V/cache/stage/8286751e4eaca31e/market_daily.parquet" data/derived/market.parquet && git add -f data/derived/market.parquet
run "T6  stage market_daily (class-R Cboe VIX column) in data/derived"
git rm -q --cached data/derived/market.parquet; rm data/derived/market.parquet
mkdir -p Raw && cp "$DTB3" Raw/DTB3.CSV && git add -f Raw/DTB3.CSV
run "T7  exact DTB3 copy as Raw/DTB3.CSV (case variants)"
VOL_DATA_DIR=/nonexistent "$PY" tools/licensing/check_data_files.py >/dev/null 2>&1; echo "T7b same, no vendor folder (CI)                               rc=$?"
git rm -q --cached Raw/DTB3.CSV; rm -r Raw
git status --porcelain | grep -v '^??' | head -3; echo "index restored to the copy's original state: $([ -z "$(git diff --cached --name-only)" ] && echo yes || echo NO)"
