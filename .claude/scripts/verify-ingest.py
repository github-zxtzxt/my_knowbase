#!/usr/bin/env python3
"""Post-ingest density verification.

Re-measures each new page's chars/code_blocks, re-measures source
segment via source_range, reports real ratios, flags anomalies.
Output is designed to be pasted into Phase C6 final report so that
the density table cannot be fabricated.

Usage:
  python verify-ingest.py --source <raw_path> <page.md> [<page.md> ...]

Exit code: 0 if all pass, 1 if any failed, 2 on usage error.
"""
import sys, re, subprocess, io
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DENSITY = Path(__file__).parent / "density.py"


TURNS = Path(__file__).parent / "turns.py"


def density(path, rng=None):
    cmd = [sys.executable, str(DENSITY), str(path)]
    if rng:
        cmd += ["--range", f"{rng[0]}:{rng[1]}"]
    try:
        out = subprocess.check_output(cmd, text=True, encoding="utf-8")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    stats = {}
    for line in out.splitlines():
        m = re.match(r"\s+(\w+)\s+(\d+)", line)
        if m:
            stats[m.group(1)] = int(m.group(2))
    return stats


def turn_line_map(source_path):
    """Return {turn_number: (start_line, end_line)} by running turns.py."""
    try:
        out = subprocess.check_output(
            [sys.executable, str(TURNS), str(source_path)],
            text=True, encoding="utf-8",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    m = {}
    for line in out.splitlines():
        mm = re.match(r"\s*#\s*(\d+)\s+\S+\s+lines\s+(\d+)-(\d+)", line)
        if mm:
            m[int(mm.group(1))] = (int(mm.group(2)), int(mm.group(3)))
    return m


def parse_ranges(page_path, source_path=None):
    """Parse source_range frontmatter → list of (start_line, end_line).

    Supports two formats:
      - "lines 100-200" / "100-200;300-400"  (structured)
      - "turns 3, 9-12" / "turn 42"          (dialogue; needs turns.py)
    """
    text = page_path.read_text(encoding="utf-8")
    m = re.search(
        r'^source_range:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE
    )
    if not m:
        return []
    field = m.group(1).strip()

    if re.search(r"turns?\b", field, re.IGNORECASE):
        if not source_path:
            return []
        tmap = turn_line_map(source_path)
        if not tmap:
            return []
        ranges = []
        # Find turn references: single "N" or range "N-M"
        body = re.sub(r"(?i)turns?\b", "", field)
        for token in re.findall(r"\d+(?:\s*-\s*\d+)?", body):
            if "-" in token:
                a, b = [int(x) for x in re.split(r"\s*-\s*", token)]
                lines = [tmap[t] for t in range(a, b + 1) if t in tmap]
                if lines:
                    ranges.append((min(l[0] for l in lines), max(l[1] for l in lines)))
            else:
                t = int(token)
                if t in tmap:
                    ranges.append(tmap[t])
        return ranges

    # Default: lines format
    return [
        (int(a), int(b))
        for a, b in re.findall(r"(\d+)\s*[-:]\s*(\d+)", field)
    ]


def ratio_bounds(src_cb):
    """Return (lo, hi) chars_ratio bounds based on source code density."""
    # Mirrors B6 副门 thresholds. Upper bound is universal 1.8.
    if src_cb is None or src_cb <= 8:
        return 0.3, 1.8
    return 0.2, 1.8


def verify(pages, source_path):
    rows = []
    fail = False
    for p in pages:
        page = Path(p)
        if not page.exists():
            rows.append((page.name, "MISSING", "", "", "", "FAIL:no-file"))
            fail = True
            continue
        pstats = density(page)
        if pstats is None:
            rows.append((page.name, "DENSITY_ERR", "", "", "", "FAIL"))
            fail = True
            continue

        ranges = parse_ranges(page, source_path)
        src_chars, src_cb = 0, 0
        if source_path and ranges:
            for rng in ranges:
                s = density(source_path, rng)
                if s:
                    src_chars += s.get("chars", 0)
                    src_cb += s.get("code_blocks", 0)
        pchars = pstats.get("chars", 0)
        pcb = pstats.get("code_blocks", 0)
        ratio = (pchars / src_chars) if src_chars else None

        warnings = []
        if pchars < 1200:
            warnings.append(f"chars<1200({pchars})")
        if source_path and not ranges:
            # Empty / missing / unparseable source_range while a source
            # was provided → page has no verifiable grounding. Flag it.
            warnings.append("no-source-grounding")
        if ratio is not None:
            lo, hi = ratio_bounds(src_cb)
            if ratio < lo:
                warnings.append(f"ratio<{lo}")
            if ratio > hi:
                warnings.append(f"ratio>{hi}")
        if src_cb:
            # Relax code retention for code-dense sources (dialogue repeats
            # same patterns across turns). Mirrors ratio_bounds logic.
            code_floor = 0.3 if src_cb > 8 else 0.5
            if pcb < src_cb * code_floor:
                warnings.append(f"code<{src_cb}*{code_floor}")

        status = "PASS" if not warnings else "FAIL:" + ",".join(warnings)
        if warnings:
            fail = True
        rows.append(
            (
                page.stem,
                f"{src_chars}c/{src_cb}cb",
                f"{pchars}c/{pcb}cb",
                f"{ratio:.2f}" if ratio is not None else "-",
                ";".join(f"{a}-{b}" for a, b in ranges) or "-",
                status,
            )
        )
    return rows, fail


def main():
    args = sys.argv[1:]
    source = None
    if args and args[0] == "--source":
        if len(args) < 2:
            print("usage: verify-ingest.py [--source <raw>] <page.md> ...")
            sys.exit(2)
        source = args[1]
        args = args[2:]
    if not args:
        print("usage: verify-ingest.py [--source <raw>] <page.md> ...")
        sys.exit(2)

    rows, fail = verify(args, source)
    hdr = ("slug", "src", "page", "ratio", "range", "status")
    widths = [
        max(len(str(r[i])) for r in [hdr] + rows) for i in range(len(hdr))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print("# verify-ingest report")
    if source:
        print(f"# source: {source}")
    print(f"# pages checked: {len(rows)}")
    print()
    print(fmt.format(*hdr))
    print(fmt.format(*("-" * w for w in widths)))
    for r in rows:
        print(fmt.format(*r))
    print()
    fails = [r for r in rows if r[-1].startswith("FAIL")]
    if fails:
        print(f"FAILED: {len(fails)}/{len(rows)}")
    else:
        print(f"ALL PASS ({len(rows)})")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
