"""E8, CLIENT HALF ONLY: our client (a) sends a User-Agent on every request, (b) stays at or under 10 requests per second.
The POLICY half (SEC allows at most 10/s and requires a contact in the User-Agent) cannot be probed without a network
request: UNVERIFIABLE.  No network, no real contact string: edgar.user_agent is replaced by a non-email sentinel.
Virtual clock: the fake `sleep` advances it, the fake `get` is instantaneous (zero latency = the fastest possible client).
Exit 0 = client half survives."""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib import *

SENT = "PROBE-SENTINEL-UA"
edgar.user_agent = lambda: SENT
clock = [0.0]
reqs = []
FIVE = ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "items")


class Resp:
    def __init__(s, d): s.d = d
    def raise_for_status(s): pass
    def json(s): return s.d


def get(url, headers=None, timeout=None, **kw):
    reqs.append((clock[0], url, dict(headers or {})))
    name = url.rsplit("/", 1)[1]
    empty = {k: [] for k in FIVE}
    if name.count("-submissions-"):
        return Resp(empty)
    n = int(name[3:13]) % 4  # 0..3 extra pages
    files = [{"name": f"CIK{int(name[3:13]):010d}-submissions-{i:03d}.json", "filingCount": 0,
              "filingFrom": "2021-01-01", "filingTo": "2024-01-01"} for i in range(1, n + 1)]
    return Resp({"filings": {"recent": dict(empty), "files": files}})


def sleep(dt): clock[0] += dt


pairs = [(f"S{i}", str(1000 + i)) for i in range(60)]
with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR", "/tmp")) as td:
    out = edgar.fetch_universe(pairs, Path(td), get=get, sleep=sleep, log=lambda *_: None)
    n1 = len(reqs)
    edgar.fetch_universe(pairs, Path(td), get=get, sleep=sleep, log=lambda *_: None)
    n2 = len(reqs) - n1
fails = []
ts = [r[0] for r in reqs]
worst = 0
j = 0
for i in range(len(ts)):
    # requests in the half-open window [ts[i], ts[i]+1s), tolerance 1e-9 for float accumulation
    cnt = sum(1 for t in ts[i:] if t < ts[i] + 1.0 - 1e-9)
    worst = max(worst, cnt)
print(f"requests {n1}; virtual duration {ts[-1]:.2f}s; worst count in any half-open 1 s window: {worst}; min gap {min(b-a for a,b in zip(ts,ts[1:])):.4f}s")
ua_ok = all(h.get("User-Agent") == SENT for _, _, h in reqs)
print("every request carries the User-Agent header:", ua_ok, "; header names:", sorted(reqs[0][2]))
print("second run over the same cache makes", n2, "requests")
if worst > 10: fails.append("over 10 requests in a 1 s window")
if not ua_ok: fails.append("a request without the User-Agent")
if n2 != 0: fails.append("cache not honoured")
# the real fetch log (coarse, whole seconds)
log = json.loads((EDG / "fetch_log.json").read_text())
for run in log.get("earlier_runs", []):
    t0 = datetime.strptime(run["started_utc"], "%Y-%m-%dT%H:%M:%SZ"); t1 = datetime.strptime(run["finished_utc"], "%Y-%m-%dT%H:%M:%SZ")
    secs = (t1 - t0).total_seconds()
    print(f"real run {run['started_utc']}..{run['finished_utc']}: {run['requests']} requests in {secs:.0f}s = {run['requests']/max(secs,1):.2f}/s average")
    if run["requests"] / max(secs, 1) > 10: fails.append("real run average above 10/s")
print("RESULT:", "CLIENT HALF SURVIVES" if not fails else "CLIENT HALF REFUTED: " + "; ".join(fails))
sys.exit(0 if not fails else 1)
