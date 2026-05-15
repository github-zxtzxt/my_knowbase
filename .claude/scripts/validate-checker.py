#!/usr/bin/env python3
"""validate-checker: 过滤 Checker 假阳性，挡在 Fixer 前面。

Checker（Phase 4 sub-agent）按 checker.md 格式输出投诉：
  FAIL
  - 页面写的: <引用页面原文>
    源文实际: <引用源文原文>
    错误类型: ...

本脚本：
  1. 解析每条投诉
  2. 若 "页面写的" 逐字（normalize 后）在源文中存在 → FALSE_POSITIVE，丢弃
  3. 若 "源文实际" 在源文中不存在 → FABRICATED_CITATION，丢弃
  4. 剩余 LEGITIMATE 才交给 Fixer

设计动机：
  Checker 是 LLM 子 agent，会把源文代码块里的标识符（如 `PositionalEncoding`）
  和散文术语（如 "Positional Embedding"）混为一谈，把对的判错。
  本闸门用确定性 substring 检查替 Checker 做最后一道复核。

Usage:
  python validate-checker.py --source <raw> --range <a:b[,c:d]> --checker-output <file|->

Exit code:
  0 = 无 LEGITIMATE 投诉，页面通过，跳过 Fixer
  1 = 存在 LEGITIMATE 投诉，交给 Fixer
  2 = 用法错误
"""
import sys, re, argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def normalize(s):
    """去空白、转小写，使 substring 比较忽略格式差异。"""
    return re.sub(r"\s+", "", s).lower()


def parse_complaints(text):
    """解析 Checker FAIL 输出为投诉列表。

    宽容匹配：允许多种格式变体（页面写的/源文实际/源文依据/错误类型）。
    """
    complaints = []
    # 主格式：- 页面写的: ... 源文实际: ... 错误类型: ...
    pattern = re.compile(
        r"页面写的\s*[:：]\s*(?P<page>.+?)\s*\n"
        r"\s*(?:源文实际|源文依据)\s*[:：]\s*(?P<src>.+?)"
        r"(?:\s*\n\s*错误类型\s*[:：]\s*(?P<kind>[^\n]+))?"
        r"(?=\n\s*[-*•]|\n\s*\n|\Z)",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        complaints.append({
            "page": m.group("page").strip().strip('`"\'""'),
            "src": (m.group("src") or "").strip().strip('`"\'""'),
            "kind": (m.group("kind") or "").strip(),
        })
    return complaints


def read_source(source_path, range_spec):
    """读源文指定行号范围，支持多段 'a:b,c:d' 或 'a-b,c-d'。"""
    lines = Path(source_path).read_text(encoding="utf-8").splitlines()
    parts = []
    for r in re.split(r"[,;]", range_spec):
        r = r.strip()
        if not r:
            continue
        a, b = re.split(r"[-:]", r)
        a, b = int(a), int(b)
        parts.append("\n".join(lines[a - 1 : b]))
    return "\n\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--range", required=True)
    ap.add_argument("--checker-output", required=True,
                    help="文件路径或 '-' 表示从 stdin 读取")
    args = ap.parse_args()

    if args.checker_output == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.checker_output).read_text(encoding="utf-8")

    # Checker 整体 PASS 直接放行
    if re.search(r"^\s*PASS\s*$", text, re.MULTILINE) and "FAIL" not in text.upper():
        print("[PASS] Checker 无投诉")
        sys.exit(0)

    source = read_source(args.source, args.range)
    source_norm = normalize(source)

    complaints = parse_complaints(text)
    if not complaints:
        print("[WARN] Checker 标记 FAIL 但未解析到结构化投诉，保守起见交给 Fixer")
        print("--- 原始 Checker 输出 ---")
        print(text)
        sys.exit(1)

    legitimate, false_positive, fabricated = [], [], []
    for c in complaints:
        page_t = normalize(c["page"])
        src_t = normalize(c["src"])
        # 短 token（<4 chars）不可靠，跳过 false-positive 判定，按 LEGITIMATE 处理
        if len(page_t) >= 4 and page_t in source_norm:
            false_positive.append(c)
        elif src_t and len(src_t) >= 4 and src_t not in source_norm:
            fabricated.append(c)
        else:
            legitimate.append(c)

    print("# validate-checker report")
    print(f"投诉总数: {len(complaints)}")
    print(f"  - LEGITIMATE (交给 Fixer):   {len(legitimate)}")
    print(f"  - FALSE_POSITIVE (页面对的): {len(false_positive)}")
    print(f"  - FABRICATED  (Checker 编造): {len(fabricated)}")
    print()

    if false_positive:
        print("## 🟢 FALSE_POSITIVE — 丢弃（页面用词逐字在源文中）")
        for c in false_positive:
            print(f"  · 页面写的: {c['page'][:100]}")
            print(f"    Checker 声称错误，但该文本在源文中确实存在")
            print()

    if fabricated:
        print("## 🟡 FABRICATED — 丢弃（Checker 编造了'源文实际'）")
        for c in fabricated:
            print(f"  · 页面写的: {c['page'][:100]}")
            print(f"    Checker 声称源文是: {c['src'][:100]}")
            print(f"    但该'源文实际'在源文中找不到")
            print()

    if legitimate:
        print("## 🔴 LEGITIMATE — 交给 Fixer")
        for c in legitimate:
            print(f"  · 页面写的: {c['page'][:120]}")
            print(f"    源文实际: {c['src'][:120]}")
            if c["kind"]:
                print(f"    错误类型: {c['kind']}")
            print()
        sys.exit(1)
    else:
        print("[PASS] 所有 Checker 投诉均被闸门过滤，无需修复")
        sys.exit(0)


if __name__ == "__main__":
    main()
