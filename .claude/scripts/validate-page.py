#!/usr/bin/env python3
"""validate-page: 确定性校验 wiki 页面与源文的一致性。

纯文本比对，不使用 LLM。跨领域通用。

检查项：
1. 提取内容完整性：extract-segments 找到的代码/公式必须原样出现在页面中
2. 数字一致性：页面中的数字必须在源文中存在
3. 无中生有：源文没有代码块，页面也不该有
4. 数量覆盖：代码块/公式数量达标

Usage:
  python validate-page.py --source <file> --range <a>:<b> [--range <c>:<d> ...] --page <page.md>

Multiple --range flags are concatenated into one source segment for validation.

Exit code: 0 = PASS, 1 = FAIL
"""
import sys, re, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def normalize_ws(s):
    return re.sub(r"\s+", " ", s).strip()


def extract_code_blocks(text):
    blocks = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("```"):
            i += 1
            body = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                body.append(lines[i])
                i += 1
            blocks.append("\n".join(body))
            i += 1
        else:
            i += 1
    return blocks


def extract_formulas(text):
    formulas = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "$$":
            i += 1
            body = []
            while i < len(lines) and lines[i].strip() != "$$":
                body.append(lines[i])
                i += 1
            formulas.append("\n".join(body).strip())
            i += 1
        else:
            i += 1
    return formulas


def extract_numbers(text):
    """Extract all numbers/quantities from text (dates, percentages, params, etc.)."""
    nums = set()
    # Integers and decimals (3+ chars to avoid noise like "1" "2")
    for m in re.finditer(r"\b\d[\d,.]*\d\b|\b\d{3,}\b", text):
        nums.add(m.group(0))
    # Quantities with units (128K, 13GB, 1024维, 3.5B, 7B)
    for m in re.finditer(r"\b\d+\.?\d*\s*[KMBGTkmb万亿千百]+\b", text):
        nums.add(m.group(0).replace(" ", ""))
    # Years (4-digit starting with 1 or 2)
    for m in re.finditer(r"\b[12]\d{3}\b", text):
        nums.add(m.group(0))
    # Percentages
    for m in re.finditer(r"\d+\.?\d*\s*%", text):
        nums.add(m.group(0).replace(" ", ""))
    return nums


def check_code_integrity(page_code, source_text):
    """Check page code blocks are substrings of source."""
    source_norm = normalize_ws(source_text)
    errors = []
    for i, block in enumerate(page_code):
        block_norm = normalize_ws(block)
        if len(block_norm) < 10:
            continue
        if block_norm not in source_norm:
            block_lines = [l.strip() for l in block.splitlines() if l.strip()]
            if not block_lines:
                continue
            hits = sum(1 for l in block_lines if l in source_text)
            ratio = hits / len(block_lines)
            if ratio < 0.7:
                preview = block[:80].replace("\n", " ")
                errors.append(f"代码块 #{i+1} 与源文不匹配 ({ratio:.0%}): {preview}...")
    return errors


def check_formula_integrity(page_formulas, source_text):
    """Check page formulas exist in source."""
    source_norm = normalize_ws(source_text)
    errors = []
    for i, formula in enumerate(page_formulas):
        formula_norm = normalize_ws(formula)
        formula_clean = re.sub(r"\\tag\s*\{[^}]*\}", "", formula_norm)
        source_clean = re.sub(r"\\tag\s*\{[^}]*\}", "", source_norm)
        if len(formula_clean) < 5:
            continue
        symbols = re.findall(r"[A-Za-z_]\w*", formula_clean)
        if not symbols:
            continue
        hits = sum(1 for s in symbols if s in source_clean)
        ratio = hits / len(symbols) if symbols else 1
        if ratio < 0.6:
            preview = formula[:60].replace("\n", " ")
            errors.append(f"公式 #{i+1} 符号匹配率 {ratio:.0%}: {preview}...")
    return errors


def check_numbers(page_text, source_text):
    """Check numbers in page exist in source."""
    # Strip frontmatter from page
    page_body = re.sub(r"^---.*?---\s*", "", page_text, flags=re.DOTALL)
    page_nums = extract_numbers(page_body)
    source_nums = extract_numbers(source_text)
    source_flat = source_text.lower()
    errors = []
    for n in page_nums:
        if n in source_nums:
            continue
        # Also check if the raw number string appears in source
        if n.lower() in source_flat:
            continue
        # Skip very common numbers
        if n in ("0", "1", "2", "3", "100"):
            continue
        errors.append(f"数字 '{n}' 在源文中未找到")
    return errors


def check_no_phantom_code(page_code, src_code_count):
    """If source has no code, page shouldn't have code (prevents invented examples)."""
    errors = []
    if src_code_count == 0 and len(page_code) > 0:
        errors.append(f"源文无代码块，但页面有 {len(page_code)} 个（可能编造）")
    return errors


def check_proper_nouns(page_text, source_text):
    """Check that specific names in page exist in source.

    Catches fabricated library names, tool names, person names, etc.
    Generic across all domains.
    """
    # Strip frontmatter and wikilinks from page
    page_body = re.sub(r"^---.*?---\s*", "", page_text, flags=re.DOTALL)
    page_body = re.sub(r"\[\[([^\]]+)\]\]", r"\1", page_body)

    source_lower = source_text.lower()
    errors = []

    # 1. Backtick content (tool names, function names, commands)
    for m in re.finditer(r"`([^`\n]{2,40})`", page_body):
        term = m.group(1)
        if term.lower() not in source_lower:
            # Skip markdown/formatting artifacts
            if term in ("python", "bash", "json", "yaml", "markdown", "toml"):
                continue
            errors.append(f"反引号术语 `{term}` 在源文中未找到")

    # 2. CamelCase words (ChromaDB, VectorStore, BlackScholes, etc.)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b", page_body):
        term = m.group(1)
        if term.lower() not in source_lower:
            errors.append(f"专有名词 '{term}' 在源文中未找到")

    # 3. ALL-CAPS acronyms 3+ chars not in source (LSTM, RLHF, etc.)
    for m in re.finditer(r"\b([A-Z]{3,})\b", page_body):
        term = m.group(1)
        if term.lower() not in source_lower and term not in ("LLM", "NLP", "API"):
            errors.append(f"缩写 '{term}' 在源文中未找到")

    return errors[:10]  # cap to avoid noise


def check_coverage(page_code, page_formulas, src_code_n, src_formula_n):
    """Check quantity coverage."""
    errors = []
    if src_code_n > 0:
        ratio = len(page_code) / src_code_n
        if ratio < 0.7:
            errors.append(f"代码块不足: 页面 {len(page_code)}/{src_code_n} ({ratio:.0%})")
    if src_formula_n > 0:
        ratio = len(page_formulas) / src_formula_n
        if ratio < 0.8:
            errors.append(f"公式不足: 页面 {len(page_formulas)}/{src_formula_n} ({ratio:.0%})")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--range", action="append", required=True, help="a:b (can be repeated)")
    ap.add_argument("--page", required=True)
    args = ap.parse_args()

    ranges = []
    for r in args.range:
        a, b = map(int, r.split(":"))
        ranges.append((a, b))
    src_lines = Path(args.source).read_text(encoding="utf-8").splitlines()
    segments = []
    for a, b in ranges:
        segments.append("\n".join(src_lines[a - 1 : b]))
    source_segment = "\n".join(segments)
    page_text = Path(args.page).read_text(encoding="utf-8")

    src_code = extract_code_blocks(source_segment)
    src_formulas = extract_formulas(source_segment)
    page_code = extract_code_blocks(page_text)
    page_formulas = extract_formulas(page_text)

    all_errors = []
    all_errors.extend(check_code_integrity(page_code, source_segment))
    all_errors.extend(check_formula_integrity(page_formulas, source_segment))
    all_errors.extend(check_numbers(page_text, source_segment))
    all_errors.extend(check_proper_nouns(page_text, source_segment))
    all_errors.extend(check_no_phantom_code(page_code, len(src_code)))
    all_errors.extend(check_coverage(page_code, page_formulas, len(src_code), len(src_formulas)))

    slug = Path(args.page).stem
    if not all_errors:
        print(f"[PASS] {slug}")
        sys.exit(0)
    else:
        print(f"[FAIL] {slug}: {len(all_errors)} errors")
        for e in all_errors:
            print(f"  - {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
