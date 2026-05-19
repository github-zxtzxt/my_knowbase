# Ingest 架构演变与踩坑总结

> 时间跨度：2026-05-09 → 2026-05-19
> 从 V1 单 agent 通读全文，到 V4 LLM 概念表 + 溯源，横跨 4 次架构重构

---

## 1. V1：单 Agent 通读全文（已废弃）

**设计**：一个 agent 一次性读完 7738 行源文 → 列出候选 → 逐个写 wiki 页面。

**产物**：46 个 wiki 页面，每个约 1KB，全是术语卡式的要点列表。源文有完整 PyTorch 实现和数学推导，wiki 只留下一句概括。

**根因**：注意力稀释。源文 7738 行塞在一个 context 里，写到第 30 个页面时模型对源文的记忆已严重退化，开始用训练知识填补空白。

**教训**：架构 > Prompt。不解决 context 规模，prompt 写得再好都没用。

---

## 2. V2：Sub-Agent 隔离架构

**设计**：每个概念 spawn 一个独立 Writer sub-agent，context 里只有 50-300 行源文片段。Writer 互不依赖，可并行。

**新增脚本**：`outline.py`（提取 Markdown 标题大纲 + 行号）、`density.py`（测量页面密度）、`extract-segments.py`（机械提取代码块和公式）。

**效果**：页面质量大幅提升，从 1KB 术语卡变成 3-5KB 迷你百科，代码和公式完整。

**遗留问题**：LLM 手猜 source_range。outline.py 只给标题和行号，不输出起止区间。44 个范围全靠 LLM 通读后凭感觉划。

---

## 3. V3：确定性校验闸门（已废弃）

**设计**：Phase 3 加 `validate-page.py` 做 6 项文本比对——代码块匹配、公式符号匹配、数字一致性、专名白名单、无中生有、数量覆盖。不 PASS 不通过。

**新增**：`validate-checker.py`（Checker sub-agent 语义复核）、`validate-fix.py`（Fixer sub-agent 定向修复）。

**试跑结果**：Chapter 2（13 概念），首次 PASS 只有 4 个，9 个 FAIL。Orchestrator 手动 Edit 修复后全部 PASS。

**踩坑清单**：

| 问题 | 表现 | 根因 |
|------|------|------|
| 公式格式死板 | `$...$` 内联公式被判"公式缺失" | validator 只认 `$$...$$` block |
| 反引号术语假阳性 | 中文被反引号夹断，报"术语未找到" | 正则处理中文反引号有 bug |
| PyTorch vs torch | 散文写"PyTorch"被判，源文代码是 `import torch` | 不分代码语境和散文语境 |
| 背景知识当虚构 | summary 写"2017"（论文年份）被判 | 源文没写年份，LLM 补了领域知识 |
| range 串味 | seq2seq 页面出现 transformer 段的内容 | LLM range 划窄了，validator 跟着瞎 |
| 多段不验 | transformer 跨两段，validator 只验了一段 | `--range` 不支持多段 |

**核心问题**：把字面匹配当语义准确性闸门。LLM 的合法改写（同义表达、领域背景、格式变体）全被判为错误。四个竞品项目没有一个这么做。

---

## 4. 竞品调研（关键转折）

研究 gbrain、wiki-kb、nvk/llm-wiki、atomicstrata/llm-wiki-compiler 四个项目的验证策略：

| 项目 | 验证策略 |
|------|---------|
| **gbrain** | Compiled Truth + Timeline 结构约束。Timeline 不可删改。不验字面 |
| **wiki-kb** | 人工 `wiki_review` draft→active。砍掉了自动 LLM audit |
| **nvk/llm-wiki** | C1-C7 结构 Lint，C7 事实核查是 Suggestion 级，`--deep` 可选 |
| **atomicstrata** | provenance 标注（extracted/inferred），不拦截 |

**共同结论**：都不做字面内容闸门。校验只做结构性的（链接、索引、元数据、frontmatter）。准确性靠证据链可视化和人工复核。

借鉴的增量改进：

| 来源 | 借了什么 |
|------|---------|
| **nvk** | `sources` 指向 raw/（wiki→raw 链接），Lint 校验链接完整性，检索穿透 raw/ |
| **gbrain** | content_hash 去重 |
| **atomicstrata** | sources 列表 + 行号范围 |
| **wiki-kb** | 砍掉 LLM audit（验证了我们的砍闸门决策） |

---

## 5. V4：LLM 概念表 + 溯源（当前）

**核心改动**：

1. **删闸门**：删 `validate-page.py`、`verify-ingest.py`、`validate-checker.py`、`validate-fix.py`、`checker.md`、`fixer.md`。不做字面校验。

2. **删无用脚本**：`density.py`、`outline.py`。

3. **Phase 1 改 LLM 概念表**：不再机械切分。LLM 通读全文 → 维护 `tmp/concepts.yaml`。不限格式、不限 `#` 标题。

4. **source → sources**：单来源变多来源 YAML list，直接指向 `raw/` 源文件路径#行号。

5. **原文引用 → 更新记录**：底部不再嵌源文，改为时间追踪表（日期 | 来源 | 变化），只追加不删改。

6. **新增字段**：`aliases`（别名）、`confidence`（可信度）、`created`/`updated`（时间戳）、`source_hash`（SHA-256 去重）。

7. **Lint 改造**：加 wiki→raw 链接完整性检查、更新记录段存在性检查。

8. **检索增强**：CLAUDE.md Query 段加穿透 raw/ 对证逻辑。

**不再做的事**：
- 不当闸门：不验字面一致性
- 不分 status：单人场景不需要 draft/active
- 不嵌原文：source 链回 raw，想看自己点

---

## 6. 关键教训

1. **架构 > Prompt**：V1 的问题不是 prompt 不够好，是 context 太大了。把每个概念隔离到独立 agent 里根本解决了幻觉。

2. **字面匹配 ≠ 准确性**：三个月的尝试证明，把机械字符串比对当语义闸门，误报率远高于真实错误检出率。

3. **竞品调研要做早**：五个项目里四个都不做内容闸门。这个信息在 V2 就该知道，而不是写完整个 validate pipeline 才发现。

4. **脚本要共享不要重复**：extract-segments.py 和 validate-page.py 各写了一遍代码块/公式提取逻辑。最终通过删除 validate-page 解决了这个问题。

5. **range 不能靠 LLM 猜**：V2 的 LLM 手划行号在多段概念和边界场景下反复出错。V4 改为概念表 YAML，人类可查可改。

6. **产物链回源文**：wiki→raw 链接从"要不要"变成"必须有"。它是准确性信心的来源——宁可让读者自己对照原文，也不靠脚本替读者判断。

---

## 7. 最终文件清单

| 文件 | 状态 | 作用 |
|------|------|------|
| `.claude/commands/ingest.md` | ✅ 重写 | V4 三阶段流程：概念表 → Writer 并行 → 收尾 |
| `.claude/commands/lint.md` | ✅ 改造 | 加 wiki→raw 链接 + 更新记录检查 |
| `.claude/commands/reflect.md` | 不变 | 认知偏差复盘 |
| `.claude/commands/reingest.md` | 不变 | 更新文件重新摄入 |
| `.claude/prompts/writer.md` | ✅ 重写 | sources YAML list、更新记录表、aliases、confidence |
| `.claude/templates/concept.md` | ✅ 新增 | 概念页模板 |
| `.claude/templates/entity.md` | ✅ 改造 | 实体页模板 |
| `.claude/templates/summary.md` | ✅ 改造 | 来源总结模板 |
| `.claude/templates/error.md` | 不变 | 复盘页面模板 |
| `.claude/scripts/extract-segments.py` | 不变 | 机械提取代码块和公式 |
| `.claude/scripts/validate-yaml.py` | 不变 | YAML frontmatter 语法校验 |
| `.claude/scripts/turns.py` | 保留 | DeepSeek 对话轮次分段 |
| `.claude/scripts/fetch_deepseek.py` | 不变 | DeepSeek 分享链接抓取 |
| `CLAUDE.md` | ✅ 微调 | Query 段加 raw/ 穿透逻辑 |
| `tmp/concepts.yaml` | ✅ 新增 | Phase 1 概念表产物 |

已删除：`validate-page.py`、`verify-ingest.py`、`validate-checker.py`、`validate-fix.py`、`checker.md`、`fixer.md`、`density.py`、`outline.py`
