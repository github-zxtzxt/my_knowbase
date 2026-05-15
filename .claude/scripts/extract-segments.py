#!/usr/bin/env python3
"""extract-segments: 从源文指定行范围内机械提取代码块和公式。

输出 JSON，每项带行号。这些内容将直接注入 wiki 页面的原文区，
不经过 LLM 生成，确保代码和公式的精确性。

Usage:
  python extract-segments.py --source <file> --range <a>:<b>
  python extract-segments.py --source raw/xxx.md --range 6350:6610

Output (stdout): JSON array of segments
"""
import sys, re, json, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def extract(lines, offset):
    """Extract code blocks and display math from lines (0-indexed internally).
    offset = the 1-based line number of lines[0] in the original file.
    """
    segments = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        stripped = ln.lstrip()

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            start = i
            body_lines = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                body_lines.append(lines[i])
                i += 1
            end = i  # closing ```
            segments.append({
                "type": "code",
                "lang": lang if lang else None,
                "content": "\n".join(body_lines),
                "line_start": start + offset,
                "line_end": end + offset,
            })
            i += 1
            continue

        # Display math $$ ... $$
        if stripped.strip() == "$$":
            start = i
            math_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                math_lines.append(lines[i])
                i += 1
            end = i  # closing $$
            segments.append({
                "type": "formula",
                "content": "\n".join(math_lines).strip(),
                "line_start": start + offset,
                "line_end": end + offset,
            })
            i += 1
            continue

        i += 1

    return segments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--range", required=True, help="a:b (1-based, inclusive)")
    ap.add_argument("--out", help="output file (default: stdout)")
    args = ap.parse_args()

    a, b = args.range.split(":")
    a, b = int(a), int(b)

    src = Path(args.source).read_text(encoding="utf-8").splitlines()
    if a < 1 or b > len(src):
        print(f"ERROR: range {a}:{b} out of bounds (file has {len(src)} lines)", file=sys.stderr)
        sys.exit(1)

    chunk = src[a - 1 : b]
    segments = extract(chunk, offset=a)

    summary = {
        "source": args.source,
        "range": [a, b],
        "total_lines": b - a + 1,
        "code_blocks": sum(1 for s in segments if s["type"] == "code"),
        "formulas": sum(1 for s in segments if s["type"] == "formula"),
        "segments": segments,
    }

    out_text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_text, encoding="utf-8")
        print(f"wrote {len(segments)} segments → {args.out}")
    else:
        print(out_text)


if __name__ == "__main__":
    main()
