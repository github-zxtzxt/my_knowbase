"""Measure content density of a Markdown file or line range.

Usage:
    python .claude/scripts/density.py <file.md>
    python .claude/scripts/density.py <file.md> --range 595:711

Reports: characters (excluding frontmatter), code blocks, display math
blocks ($$...$$), inline math spans ($...$), tables, bullet items,
numbered list items, images, wikilinks.

Used by /ingest Phase 2 self-check: compare source-section density
against wiki page density. If the source segment has N formulas and
M code blocks, the wiki page should carry most of them.
"""
import sys
import re
import io
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def parse_range(arg: str):
    if ':' not in arg:
        raise ValueError("--range expects start:end")
    a, b = arg.split(':', 1)
    return int(a), int(b)


def strip_frontmatter(text: str) -> str:
    if not text.startswith('---'):
        return text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return text
    return parts[2]


def count(text: str) -> dict:
    lines = text.splitlines()
    chars = len(text)

    code_blocks = 0
    in_code = False
    for ln in lines:
        if ln.lstrip().startswith('```'):
            if not in_code:
                code_blocks += 1
            in_code = not in_code

    display_math = len(re.findall(r'\$\$[\s\S]+?\$\$', text))
    no_display = re.sub(r'\$\$[\s\S]+?\$\$', '', text)
    no_code = re.sub(r'```[\s\S]+?```', '', no_display)
    inline_math = len(re.findall(r'(?<!\$)\$[^\$\n]+?\$(?!\$)', no_code))

    tables = sum(1 for ln in lines if re.match(r'^\s*\|.+\|\s*$', ln))
    bullets = sum(1 for ln in lines if re.match(r'^\s*[-*+]\s+', ln))
    numbered = sum(1 for ln in lines if re.match(r'^\s*\d+\.\s+', ln))
    images = len(re.findall(r'!\[[^\]]*\]\([^)]+\)', text))
    wikilinks = len(re.findall(r'\[\[[^\]]+\]\]', text))

    return {
        'chars': chars,
        'lines': len(lines),
        'code_blocks': code_blocks,
        'display_math': display_math,
        'inline_math': inline_math,
        'tables_rows': tables,
        'bullets': bullets,
        'numbered': numbered,
        'images': images,
        'wikilinks': wikilinks,
    }


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: density.py <file.md> [--range start:end]", file=sys.stderr)
        sys.exit(2)

    path = Path(args[0])
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        sys.exit(2)

    rng = None
    if '--range' in args:
        rng = parse_range(args[args.index('--range') + 1])

    text = path.read_text(encoding='utf-8')
    if rng:
        lines = text.splitlines()
        a, b = rng
        text = '\n'.join(lines[max(0, a - 1):b])
        scope = f"{path} [lines {a}:{b}]"
    else:
        text = strip_frontmatter(text)
        scope = f"{path} (frontmatter stripped)"

    stats = count(text)
    print(f"# density of {scope}")
    width = max(len(k) for k in stats)
    for k, v in stats.items():
        print(f"  {k:<{width}}  {v}")


if __name__ == '__main__':
    main()
