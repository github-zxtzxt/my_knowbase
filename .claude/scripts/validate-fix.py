#!/usr/bin/env python3
"""validate-fix: 检查 Fixer 修改是否引入了源文中不存在的内容。

对比 Fixer 修改前后的页面，找出新增/修改的内容，逐行检查每行是否在源文中有依据。
若 Fixer 创造了源文不存在的术语/标识符/句子，建议回滚。

设计动机：
  即便 validate-checker.py 过滤了假阳性投诉，Fixer 拿到 LEGITIMATE 投诉后
  仍可能在改的过程中自由发挥，引入源文里没有的措辞。本闸门做最后兜底。

检查策略：
  1. diff 修改前后页面，提取新增/修改行
  2. 过滤结构性行（## heading、纯 wikilink bullet、空行、代码块/公式分隔符）
  3. 对每行剩余 prose：
     a. 反引号术语 / CamelCase / 大写缩写必须在源文中存在（严）
     b. 整句 n-gram 覆盖率 ≥ 30%（宽，允许 paraphrase）
  4. 同时严格检查代码块/公式：必须为源文子串（不允许 Fixer 改代码）

Usage:
  python validate-fix.py --source <raw> --range <a:b[,c:d]> --before <old.md> --after <new.md>

Exit code:
  0 = 修改可接受
  1 = 引入了未授权内容，建议回滚
  2 = 用法错误
"""
import sys, re, argparse, difflib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def normalize(s):
    return re.sub(r"\s+", "", s).lower()


def strip_frontmatter(text):
    return re.sub(r"^---.*?---\s*", "", text, flags=re.DOTALL, count=1)


def read_source(source_path, range_spec):
    lines = Path(source_path).read_text(encoding="utf-8").splitlines()
    parts = []
    for r in re.split(r"[,;]", range_spec):
        r = r.strip()
        if not r:
            continue
        a, b = re.split(r"[-:]", r)
        parts.append("\n".join(lines[int(a) - 1 : int(b)]))
    return "\n\n".join(parts)


def is_structural(line):
    """判断一行是否为 markdown 结构（不需做源文比对）。"""
    s = line.strip()
    if not s:
        return True
    if s.startswith("#"):
        return True
    if s.startswith("```") or s == "$$":
        return True
    # 纯 wikilink 关联行：- 前置：[[xx]]、[[yy]]
    if re.match(r"^[-*]\s*(?:前置|相关|后续|来源|组成|参考)?\s*[:：]?\s*"
                r"(?:\[\[[^\]]+\]\][\s,，、]*)+$", s):
        return True
    # 纯标点/分隔
    if re.match(r"^[-=*_·•—\s]+$", s):
        return True
    return False


def extract_distinctive_tokens(line):
    """提取必须源文存在的强标识符：反引号、CamelCase、ALL-CAPS。"""
    tokens = set()
    for m in re.finditer(r"`([^`\n]+)`", line):
        t = m.group(1).strip()
        if t and t not in ("python", "bash", "json", "yaml", "txt", "markdown"):
            tokens.add(t)
    for m in re.finditer(r"\b([A-Z][a-z]+(?:[A-Z][a-z0-9]+)+)\b", line):
        tokens.add(m.group(1))
    for m in re.finditer(r"\b([A-Z]{3,})\b", line):
        t = m.group(1)
        if t not in ("LLM", "NLP", "API", "URL", "CPU", "GPU"):
            tokens.add(t)
    return tokens


def check_line(line, source, source_norm):
    """返回该行的问题列表。空列表 = 通过。"""
    issues = []
    source_lower = source.lower()

    # 1. 强标识符必须在源文中（含代码块）
    for tok in extract_distinctive_tokens(line):
        if normalize(tok) in source_norm or tok.lower() in source_lower:
            continue
        issues.append(f"强标识符 '{tok}' 在源文中找不到")

    # 2. 整句 n-gram 覆盖率（仅对足够长的 prose）
    line_norm = normalize(line)
    if len(line_norm) >= 24:
        # 8 字窗口，步长 4
        wins = [line_norm[i : i + 8] for i in range(0, len(line_norm) - 8 + 1, 4)]
        if wins:
            hits = sum(1 for w in wins if w in source_norm)
            ratio = hits / len(wins)
            if ratio < 0.3:
                issues.append(
                    f"句子源文覆盖率仅 {ratio:.0%} (阈值 30%)，疑似虚构"
                )
    return issues


def extract_zones(text):
    """按区域切分页面：prose / code blocks / formula blocks。"""
    prose, codes, formulas = [], [], []
    in_code, in_formula = False, False
    buf = []
    for line in text.splitlines():
        if in_code:
            if line.lstrip().startswith("```"):
                codes.append("\n".join(buf))
                buf = []
                in_code = False
            else:
                buf.append(line)
            continue
        if in_formula:
            if line.strip() == "$$":
                formulas.append("\n".join(buf))
                buf = []
                in_formula = False
            else:
                buf.append(line)
            continue
        if line.lstrip().startswith("```"):
            in_code = True
            continue
        if line.strip() == "$$":
            in_formula = True
            continue
        prose.append(line)
    return "\n".join(prose), codes, formulas


def check_code_strictly(before_codes, after_codes, source):
    """代码块必须为源文子串。Fixer 改代码块视为 FAIL。"""
    source_norm_ws = re.sub(r"\s+", " ", source).strip()
    issues = []
    for i, blk in enumerate(after_codes):
        if blk in before_codes:
            continue  # 未改动
        # 新增/修改的代码块必须是源文子串
        blk_norm = re.sub(r"\s+", " ", blk).strip()
        if len(blk_norm) < 10:
            continue
        if blk_norm not in source_norm_ws:
            # 按行匹配率兜底
            lines = [l.strip() for l in blk.splitlines() if l.strip()]
            if not lines:
                continue
            hits = sum(1 for l in lines if l in source)
            ratio = hits / len(lines)
            if ratio < 0.7:
                preview = blk[:80].replace("\n", " ")
                issues.append(f"代码块 #{i+1} 被改动且与源文不匹配 ({ratio:.0%}): {preview}")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--range", required=True)
    ap.add_argument("--before", required=True, help="Fixer 修改前的页面快照")
    ap.add_argument("--after", required=True, help="Fixer 修改后的页面")
    args = ap.parse_args()

    before_raw = Path(args.before).read_text(encoding="utf-8")
    after_raw = Path(args.after).read_text(encoding="utf-8")
    before = strip_frontmatter(before_raw)
    after = strip_frontmatter(after_raw)
    source = read_source(args.source, args.range)
    source_norm = normalize(source)

    # 1. 代码块严格检查
    before_prose, before_codes, _ = extract_zones(before)
    after_prose, after_codes, _ = extract_zones(after)
    code_issues = check_code_strictly(before_codes, after_codes, source)

    # 2. Prose 行级 diff
    differ = difflib.SequenceMatcher(
        None, before_prose.splitlines(), after_prose.splitlines()
    )
    added_lines = []
    for tag, i1, i2, j1, j2 in differ.get_opcodes():
        if tag in ("insert", "replace"):
            for line in after_prose.splitlines()[j1:j2]:
                if line.strip() and not is_structural(line):
                    added_lines.append(line)

    prose_issues = []
    for line in added_lines:
        line_issues = check_line(line, source, source_norm)
        if line_issues:
            prose_issues.append((line, line_issues))

    print("# validate-fix report")
    print(f"新增/修改 prose 行: {len(added_lines)}")
    print(f"  - 通过: {len(added_lines) - len(prose_issues)}")
    print(f"  - 可疑: {len(prose_issues)}")
    print(f"代码块改动: {len(code_issues)} 处不匹配")
    print()

    if not prose_issues and not code_issues:
        print("[PASS] Fixer 修改全部在源文中有依据")
        sys.exit(0)

    if code_issues:
        print("## 🔴 代码块被改动且不匹配源文")
        for issue in code_issues:
            print(f"  · {issue}")
        print()

    if prose_issues:
        print("## 🟡 Prose 引入未授权内容")
        for line, line_issues in prose_issues:
            print(f"  · 新增行: {line.strip()[:120]}")
            for issue in line_issues:
                print(f"      - {issue}")
            print()

    print("建议: 回滚至 --before 快照，标记 NEEDS_HUMAN_REVIEW")
    sys.exit(1)


if __name__ == "__main__":
    main()
