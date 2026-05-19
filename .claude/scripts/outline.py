"""Print heading outline with line numbers for a Markdown file.

Usage:
    python .claude/scripts/outline.py <path/to/file.md>
    python .claude/scripts/outline.py --ranges <path/to/file.md>

Output columns: line number, heading level (indent), heading text.
With --ranges: adds end-line for each heading so callers get
section boundaries mechanically without guessing.

Useful for locating section ranges in long source files (raw/) without
reading the whole file. Combine with Read offset/limit to jump to sections.
"""
import sys
import re
import io
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def main():
    args = sys.argv[1:]
    do_ranges = False
    if args and args[0] == '--ranges':
        do_ranges = True
        args = args[1:]

    if len(args) < 1:
        print("usage: outline.py [--ranges] <file.md>", file=sys.stderr)
        sys.exit(2)

    path = Path(args[0])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(2)

    heading = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
    in_code = False
    lines = path.read_text(encoding='utf-8').splitlines()
    total = len(lines)

    # Collect (line_no, level, text)
    headings = []
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = heading.match(line)
        if m:
            level = len(m.group(1))
            text = m.group(2)
            headings.append((i, level, text))

    if do_ranges:
        print(f"# outline of {path} ({total} lines) --ranges")
        for idx, (start, level, text) in enumerate(headings):
            # End is the line before the next heading of same or higher level,
            # or EOF
            end = total
            for j in range(idx + 1, len(headings)):
                if headings[j][1] <= level:
                    end = headings[j][0] - 1
                    break
            indent = '  ' * (level - 1)
            print(f"lines {start}-{end}  {indent}{'#' * level} {text}")
    else:
        print(f"# outline of {path} ({total} lines)")
        for i, level, text in headings:
            indent = '  ' * (level - 1)
            print(f"{i:>6}  {indent}{'#' * level} {text}")


if __name__ == '__main__':
    main()
