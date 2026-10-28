"""Channel A probe for C2.3: does every pinned version exist on PyPI, and does PyPI
list a wheel this box can use (cp312 / abi3 / py3-none-any, manylinux aarch64 or any)?

Usage: python pypi_pins.py <path-to-pyproject.toml>
Reads [project].dependencies and [dependency-groups].dev, queries
https://pypi.org/pypi/<name>/<version>/json, prints one line per pin.
"""
import json
import sys
import tomllib
import urllib.request

def pins(pyproject):
    d = tomllib.load(open(pyproject, "rb"))
    specs = list(d["project"]["dependencies"]) + list(d.get("dependency-groups", {}).get("dev", []))
    out = []
    for s in specs:
        if "==" not in s:
            out.append((s, None))
            continue
        name, ver = s.split("==")
        out.append((name.strip(), ver.strip()))
    return out, d.get("build-system", {}).get("requires", [])

def usable(fn):
    if fn.endswith(".tar.gz"):
        return "sdist"
    tags = fn[:-4].split("-")[-3:]
    py, abi, plat = tags
    py_ok = any(t in py.split(".") for t in ("cp312", "py3", "py2.py3")) or "py3" in py
    abi_ok = abi in ("cp312", "abi3", "none")
    plat_ok = plat == "any" or "aarch64" in plat
    return "wheel" if (py_ok and abi_ok and plat_ok) else None

def main():
    specs, build = pins(sys.argv[1])
    print("build-system.requires:", build)
    bad = 0
    for name, ver in specs:
        if ver is None:
            print(f"NOT-EXACT {name}")
            bad += 1
            continue
        url = f"https://pypi.org/pypi/{name}/{ver}/json"
        try:
            data = json.load(urllib.request.urlopen(url, timeout=30))
        except Exception as e:  # 404 -> version does not exist
            print(f"MISSING {name}=={ver}: {e}")
            bad += 1
            continue
        files = [u["filename"] for u in data["urls"]]
        kinds = {usable(f) for f in files} - {None}
        upload = min((u["upload_time"] for u in data["urls"]), default="?")
        yanked = data["info"].get("yanked")
        print(f"OK {name}=={ver} uploaded={upload} yanked={yanked} usable={sorted(kinds)} nfiles={len(files)}")
        if not kinds:
            bad += 1
    print("bad:", bad)
    return 1 if bad else 0

if __name__ == "__main__":
    raise SystemExit(main())
