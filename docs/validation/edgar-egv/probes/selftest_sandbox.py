"""Wrapper self-test: the sandbox sees the repo code and the cache, and has no network interface except loopback."""
import os, sys
sys.path.insert(0, "/home/rajib2k5/dev/earnings-vol-study/src")
from earnings_vol.ingest import edgar
ifs = sorted(l.split(":")[0].strip() for l in open("/proc/net/dev").read().splitlines()[2:])
print("python", sys.version.split()[0], "| edgar module:", edgar.__file__, "| TZ", os.environ.get("TZ"), "| interfaces:", ifs)
print("cache readable:", os.path.exists("/home/rajib2k5/data/vol-projects/earnings-vol-study/raw/edgar/fetch_log.json"))
sys.exit(0 if ifs in (["lo"], []) else 1)
