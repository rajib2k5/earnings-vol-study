"""p06b: the calendar rows behind the EPS-match findings, read from the project's MIRROR (never the shared clone).

  uv run python docs/validation/probes/m1/p06b_calendar_rows.py
"""
from earnings_vol import config, params as params_mod
from earnings_vol.ingest import dolt

p = params_mod.load()
m = config.cache_dir() / "dolt_mirror" / "earnings"
c = p["dolt"]["earnings_commit"]
for sym, lo, hi in (("COST", "2025-02-01", "2025-06-30"), ("COST", "2024-02-01", "2024-06-30"),
                    ("ORCL", "2024-08-15", "2024-12-31"), ("CSCO", "2021-01-15", "2021-03-15")):
    t = dolt.query(m, f"SELECT act_symbol, `date`, `when` FROM {dolt.as_of('earnings_calendar', c)} "
                      f"WHERE `date` BETWEEN '{lo}' AND '{hi}' AND act_symbol = '{sym}'")
    print(sym, lo, hi, [(str(r['date']), r['when']) for r in t.to_pylist()])
    e = dolt.query(m, f"SELECT period_end_date, reported, estimate FROM {dolt.as_of('eps_history', c)} "
                      f"WHERE act_symbol = '{sym}' AND period_end_date BETWEEN DATE_SUB('{lo}', INTERVAL 200 DAY) AND '{hi}'")
    print("   eps_history:", [(str(r['period_end_date']), r['reported']) for r in e.to_pylist()])
