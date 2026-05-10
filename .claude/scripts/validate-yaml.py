"""Validate YAML frontmatter in all wiki/*.md files. Exit 1 if any invalid."""
import yaml, glob, sys

bad = []
good = 0
for f in glob.glob('wiki/**/*.md', recursive=True):
    content = open(f, encoding='utf-8').read()
    if not content.startswith('---'):
        continue
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f'  SKIP: {f} (no frontmatter)')
        continue
    try:
        yaml.safe_load(parts[1])
        good += 1
    except yaml.YAMLError as e:
        bad.append((f, str(e)))

print(f'Total: {good + len(bad)}, Valid: {good}, Invalid: {len(bad)}')
if bad:
    print()
    for f, err in bad:
        print(f'  BAD: {f}')
        print(f'       {err.split(chr(10))[0][:150]}')
    sys.exit(1)
