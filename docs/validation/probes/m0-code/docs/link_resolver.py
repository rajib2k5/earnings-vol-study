"""Probe: resolve every relative link in one or more Markdown files.

Usage (from the repo root):
    python3 docs/validation/probes/m0-code/docs/link_resolver.py FILE.md [FILE.md ...] [--show]

For each [text](target) link that is not http(s)/mailto:
  - the target file or folder must exist (relative to the Markdown file's folder);
  - "#Lnn" / "#Lnn-Lmm" / "#Lnn-mm": the line range must exist in the target file;
  - "#anchor" on a .md target: a heading with that GitHub-style slug must exist.
--show prints the link text and the target line(s), so a human can judge whether
the line is what the text describes.

Exit code: 0 when every link resolves, 1 otherwise. No network, writes nothing.
"""

import re
import sys
from pathlib import Path

LINK = re.compile(r"(?<!!)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINES = re.compile(r"^L(\d+)(?:-L?(\d+))?$")


def slug(heading: str) -> str:
    """GitHub's heading anchor: lowercase, drop punctuation except - and _, spaces -> -."""
    h = heading.strip().lower()
    h = re.sub(r"[`*_~]", lambda m: "_" if m.group(0) == "_" else "", h)
    h = re.sub(r"[^\w\- ]", "", h, flags=re.UNICODE)
    return h.replace(" ", "-")


def anchors(md: Path) -> set[str]:
    out, seen, fence = set(), {}, False
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        s = slug(m.group(1))
        n = seen.get(s, 0)
        out.add(s if n == 0 else f"{s}-{n}")
        seen[s] = n + 1
    # explicit <a id="..."> / <a name="...">
    for m in re.finditer(r"<a\s+(?:id|name)=\"([^\"]+)\"", md.read_text(encoding="utf-8")):
        out.add(m.group(1))
    return out


def check(md: Path, show: bool) -> tuple[int, int]:
    ok = bad = 0
    text = md.read_text(encoding="utf-8")
    # ignore links inside fenced code
    clean, fence = [], False
    for i, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            clean.append((i, ""))
            continue
        clean.append((i, "" if fence else line))
    for lineno, line in clean:
        for m in LINK.finditer(line):
            label, target = m.group(1), m.group(2)
            if re.match(r"^(https?:|mailto:)", target):
                continue
            path_part, _, frag = target.partition("#")
            dest = (md.parent / path_part).resolve() if path_part else md.resolve()
            problem = None
            snippet = ""
            if not dest.exists():
                problem = "MISSING FILE"
            elif frag:
                lm = LINES.match(frag)
                if lm:
                    a = int(lm.group(1))
                    b = int(lm.group(2) or a)
                    flines = dest.read_text(encoding="utf-8").splitlines()
                    if a < 1 or b < a or b > len(flines):
                        problem = f"LINE RANGE {a}-{b} OUT OF 1-{len(flines)}"
                    else:
                        snippet = " | ".join(s.strip() for s in flines[a - 1:b])[:220]
                elif dest.suffix == ".md":
                    if frag not in anchors(dest):
                        problem = f"MISSING ANCHOR #{frag}"
            if problem:
                bad += 1
                print(f"BROKEN {md}:{lineno} [{label[:60]}]({target}) -> {problem}")
            else:
                ok += 1
                if show:
                    print(f"OK {md}:{lineno} [{label[:70]}]({target})")
                    if snippet:
                        print(f"    => {snippet}")
    return ok, bad


def main(argv: list[str]) -> int:
    show = "--show" in argv
    files = [Path(a) for a in argv if a != "--show"]
    tot_ok = tot_bad = 0
    for f in files:
        ok, bad = check(f, show)
        print(f"SUMMARY {f}: {ok} resolved, {bad} broken")
        tot_ok += ok
        tot_bad += bad
    print(f"TOTAL: {tot_ok} resolved, {tot_bad} broken")
    return 1 if tot_bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
