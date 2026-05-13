"""Print heading outline with line numbers for a Markdown file.

Usage:
    python .claude/scripts/outline.py <path/to/file.md>

Output columns: line number, heading level (indent), heading text.
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
    if len(sys.argv) < 2:
        print("usage: outline.py <file.md>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(2)

    heading = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
    in_code = False
    lines = path.read_text(encoding='utf-8').splitlines()
    total = len(lines)

    print(f"# outline of {path} ({total} lines)")
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
            indent = '  ' * (level - 1)
            print(f"{i:>6}  {indent}{'#' * level} {text}")


if __name__ == '__main__':
    main()
