"""Probe C9/C10/C10b/C10c: resolve the cited DOIs through the Crossref REST API (runtime evidence, independent of
reading the papers), dimension-check MacKinlay eq. (8) as printed, and recompute the Dubinsky-Johannes Intel example.
Run: uv run --no-sync --frozen python docs/validation/probes/m0-methodology/p10_citations.py
Network: GET https://api.crossref.org/works/<doi> (read-only, one request per DOI).
"""
import time

import numpy as np
import requests

DOIS = {
    "DJKS 2019": "10.1093/rfs/hhy060", "KP 2010": "10.1093/rfs/hhq072", "BMP 1991": "10.1016/0304-405X(91)90032-F",
    "Patell 1976": "10.2307/2490543", "GXZ 2018": "10.1017/S0022109018000285", "Barth-So 2014": "10.2308/accr-50758",
    "Petersen 2009": "10.1093/rfs/hhn053", "CGM 2011": "10.1198/jbes.2010.07136", "Corrado 1989": "10.1016/0304-405X(89)90064-0",
    "Cowan 1992": "10.1007/BF00939016", "Donders-Vorst 1996": "10.1016/S0378-4266(96)00011-8",
    "KP 2011": "10.1016/j.jempfin.2011.08.003", "Brown-Warner 1985": "10.1016/0304-405X(85)90042-X",
    "HKZ 2019": "10.1007/s11142-019-9487-1", "Alexiou 2025": "10.1093/rof/rfaf016",
    "KPP 2018 (SSRN)": "10.2139/ssrn.3167271", "Pynnonen 2021 (SSRN)": "10.2139/ssrn.3802405",
    "Pynnonen 2022 JRFM (found by Channel A)": "10.3390/jrfm15040149",
}
H = {"User-Agent": "earnings-vol-study-validation-probe (mailto:not-provided)"}
for k, d in DOIS.items():
    try:
        r = requests.get(f"https://api.crossref.org/works/{d}", headers=H, timeout=30)
        if r.status_code != 200:
            print(f"{k:28s} {d:34s} HTTP {r.status_code}"); continue
        m = r.json()["message"]
        au = ", ".join(a.get("family", "?") for a in m.get("author", []))
        print(f"{k:28s} {d:34s} | {au} | {m.get('title',[''])[0][:90]} | {(m.get('container-title') or ['-'])[0]} "
              f"{m.get('volume','')}({m.get('issue','')}) {m.get('page','')} | {m.get('issued',{}).get('date-parts',[[None]])[0][0]}")
        if "ssrn" in d or "jrfm" in d:
            ab = (m.get("abstract") or "")
            for kw in ("overlap", "percentage", "partially"):
                if kw in ab:
                    i = ab.index(kw); print(f"{'':28s}   abstract ...{ab[max(0,i-60):i+60]}...")
    except Exception as e:  # network failure is reported, never silently passed
        print(f"{k:28s} {d:34s} ERROR {e!r}")
    time.sleep(0.3)

# C10b: dimension check of MacKinlay (1997) eq. (8). AR in return units (e.g. % per day). Printed (per Channel A):
#   sigma^2(AR) = sigma_eps^2 + (1/L1) [1 + (R_m - mu_m)^2 / sigma_m^2]
# Scale returns by c (e.g. decimal -> percent, c = 100): LHS and sigma_eps^2 scale by c^2, the bracket is unit-free.
c = 100.0; s_eps2, L1, Rm, mu, sm2 = 0.02**2, 120, 0.01, 0.0005, 0.01**2
printed = lambda k: (k**2) * s_eps2 + (1 / L1) * (1 + ((k * Rm - k * mu) ** 2) / ((k**2) * sm2))
fixed = lambda k: (k**2) * s_eps2 * (1 + (1 / L1) * (1 + ((k * Rm - k * mu) ** 2) / ((k**2) * sm2)))
print(f"\nC10b printed eq.(8): ratio after rescaling by c=100: {printed(c)/printed(1):.2f} (should be {c**2:.0f}); "
      f"with sigma_eps^2 factor: {fixed(c)/fixed(1):.2f}")

# C10c: Intel (Dubinsky-Johannes WP, p. 26 inputs)
T1, T2, s1, s2, spost = 0.0198, 0.0992, 0.7115, 0.4519, 0.4296
E = T1 * T2 * (s1**2 - s2**2) / (T2 - T1); sd = np.sqrt((s2**2 * T2 - s1**2 * T1) / (T2 - T1))
print(f"C10c term-structure sigma_E {np.sqrt(E):.4%}, sigma_d {sd:.4f}; ex-post T1*(pre^2-post^2) {np.sqrt(T1*(s1**2-spost**2)):.4%}; "
      f"ex-post with T = 4/252 {np.sqrt(4/252*(s1**2-spost**2)):.4%}; T needed for 7.2%: {0.072**2/(s1**2-spost**2)*252:.2f} trading days")
