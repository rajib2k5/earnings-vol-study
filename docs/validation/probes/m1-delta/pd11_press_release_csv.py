# pd11 (claim 8a): basis/time consistency of data/manual/press_release_checks.csv,
# and timing.parse_checks on rows with an inconsistent pair.
#
# Run: uv run --frozen python docs/validation/probes/m1-delta/pd11_press_release_csv.py
import csv
import io
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "src"))
from earnings_vol import params as params_mod  # noqa: E402
from earnings_vol.events import calendar, timing  # noqa: E402

text = (REPO / "data/manual/press_release_checks.csv").read_text(encoding="utf-8")
rows = list(csv.DictReader(io.StringIO(text)))
p = params_mod.load()
t = calendar.build_session_table(p.day("sessions", "start"), p.day("sessions", "end"), p["snapshot_eras"])
S = calendar.Sessions(t["session_date"].tolist())
close = dict(zip(t["session_date"], t["close_time_et"]))
parsed = timing.parse_checks(text, S, close)
print(f"parse_checks on the committed CSV: {len(parsed)} rows, no error")
print(f"{'event':18s} {'basis':15s} {'time':6s} {'kind':10s} host / note flags")
for r in rows:
    host = urlparse(r["url"]).netloc
    flags = []
    note = r["note"].lower()
    if r["basis"] == "time_stamp" and "no time stamp shown" in note:
        flags.append("time NOT on the url page")
    if "read by the milestone-1 review" in note:
        flags.append("time source = review ledger, no URL")
    if any(w in r["url"].lower() for w in ("to-host", "to-announce", "earnings-call")):
        flags.append("url is a call/pre-announcement page, not the release")
    if r["source_kind"] == "aggregator" and ("403" in note or "refused" in note):
        flags.append("aggregator kept though a company/newswire page exists (403)")
    print(f"{r['security_id'] + ':' + r['announce_date']:18s} {r['basis']:15s} {r['release_time_et'] or '-':6s} "
          f"{r['source_kind']:10s} {host}  {'; '.join(flags)}")

header, body = text.splitlines()[0], text.splitlines()[1:]
orcl = next(line for line in body if line.startswith("ORCL,"))
gs = next(line for line in body if line.startswith("GS,"))
nflx = next(line for line in body if line.startswith("NFLX,"))
mutants = {
    "time_stamp without a time": orcl.replace(",16:05,time_stamp,", ",,time_stamp,"),
    "call_time with a time": gs.replace(",,call_time,", ",09:30,call_time,"),
    "release_text with a time": gs.replace(",,call_time,", ",07:00,release_text,"),
    "announced_time without a time": nflx.replace(",16:00,announced_time,", ",,announced_time,"),
    "time contradicts the label (16:05 BMO)": orcl.replace(",AMC,", ",BMO,"),
    "unknown basis": orcl.replace(",time_stamp,", ",wire_time,"),
}
for name, line in mutants.items():
    assert line != {"time_stamp without a time": orcl, "call_time with a time": gs,
                    "release_text with a time": gs, "announced_time without a time": nflx,
                    "time contradicts the label (16:05 BMO)": orcl, "unknown basis": orcl}[name], name
    try:
        timing.parse_checks("\n".join([header, line]) + "\n", S, close)
        print(f"MUTANT ACCEPTED  {name}")
    except ValueError as e:
        print(f"mutant refused   {name}: {str(e)[:110]}")
