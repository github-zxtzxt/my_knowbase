"""Segment a DeepSeek-style dialogue Markdown file by Q&A turns.

A "turn" here is a block starting with `**用户**：` or `**助手**：` (optional
suffix like 思考过程). Turns are numbered, with line ranges and role.

Usage:
    python .claude/scripts/turns.py <dialogue.md>

Output columns: turn index, role, line range, preview (first ~60 chars).

Used by /ingest Phase A for dialogue sources: candidate concepts are
keyed by turn ranges (e.g., turns 3-5 introduced "Rust ownership")
rather than absolute line numbers, matching how the source is organised.
"""
import sys
import re
import io
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


TURN_RE = re.compile(r'^\*\*(用户|助手)\*\*(（[^）]+）)?\s*[：:]\s*$')


def main():
    if len(sys.argv) < 2:
        print("usage: turns.py <dialogue.md>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(2)

    lines = path.read_text(encoding='utf-8').splitlines()
    turn_starts = []
    for i, line in enumerate(lines, 1):
        m = TURN_RE.match(line.strip())
        if m:
            role = m.group(1)
            suffix = m.group(2) or ''
            turn_starts.append((i, role, suffix))

    if not turn_starts:
        print(f"# no turns found in {path} (expected '**用户**：' / '**助手**：' markers)")
        print("# this file does not look like a dialogue; use outline.py for structured sources")
        sys.exit(0)

    print(f"# turns in {path} ({len(turn_starts)} turns, {len(lines)} lines)")
    for idx, (start_line, role, suffix) in enumerate(turn_starts, 1):
        end_line = turn_starts[idx][0] - 1 if idx < len(turn_starts) else len(lines)
        body = '\n'.join(lines[start_line:end_line]).strip()
        preview = re.sub(r'\s+', ' ', body)[:60]
        print(f"  #{idx:>3}  {role}{suffix}  lines {start_line}-{end_line}  | {preview}")


if __name__ == '__main__':
    main()
