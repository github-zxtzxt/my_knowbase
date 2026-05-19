将源文编译为结构化 wiki。每个概念由独立 sub-agent 在隔离 context 中生成，确保源文注意力不被稀释。

## 输入

- `/ingest <path>` → 摄入该文件
- `/ingest` → 扫描 `raw/`，找出 `wiki/log.md` 未记录的文件

## 架构总览

```
Orchestrator（你）
  ├─ Phase 1: 扫描源文，生成候选清单
  ├─ Phase 2: 对每个候选 spawn Writer sub-agent（并行）
  ├─ Phase 3: validate-page.py 确定性校验（唯一闸门，不可跳过）
  ├─ Phase 4: （可选）Checker sub-agent 语义复核，只写报告不改页面
  └─ Phase 5: 写报告 + 更新 _index.md / log.md
```

**核心设计**：流水线里只有 Writer 创建页面、Orchestrator 用 Edit 修复确定性错误。不存在任何"LLM agent 自动修改页面"的环节——那是正确内容被改坏的根源。

## 只增不改原则

Ingest 只能创建新文件、向 _index.md 和 log.md 追加内容。严禁删除或覆盖已有页面。

---

## Phase 1: 扫描与候选清单

1. 判断源文类型（structured / dialogue / note）
2. 跑 `python .claude/scripts/outline.py <源文>` 得到章节结构
3. 通读源文（按章节分段 Read）
4. 输出候选清单表格：

| slug | source_range | 类型 | 理由 |
|------|-------------|------|------|

**source_range 必须覆盖完整章节边界**（从该章标题到下一同级标题前一行）。

5. 对每个候选跑 `python .claude/scripts/extract-segments.py --source <源文> --range <a>:<b>`，记录 code_blocks 数和 formulas 数。

**跨段落处理**：如果同一概念在源文多处出现，source_range 写多段 `lines 595-712, 2870-2918`，extract-segments 对每段分别跑，结果合并传给 writer。

**增量检测**：对每个候选检查 `wiki/concepts/<slug>.md` 或 `wiki/entities/<slug>.md` 是否已存在。
- 不存在 → 标记为 `create`
- 已存在 → 标记为 `merge`，Phase 2 时把已有页面内容也传给 writer

---

## Phase 2: Writer Sub-agents

对每个候选 spawn 一个 Agent：

```
Agent({
  description: "Write wiki page: <slug>",
  prompt: <见下方构造规则>,
  subagent_type: "general-purpose"
})
```

**Writer prompt 构造**（创建模式）：

```
你是一个 wiki 页面 writer。根据源文片段写一个 wiki 概念页。

## 规则
<插入 .claude/prompts/writer.md 的内容>

## 可用的 wikilink 目标（本次 ingest 的其他概念）
<插入候选清单的 slug 列表，每行一个>

## 源文片段（lines <a>-<b>）
<插入源文该段原文，如有多段则全部拼接>

## 已提取的代码块和公式（必须原样嵌入页面）
<插入 extract-segments.py 的 JSON 输出>

## 输出
直接输出完整的 .md 文件内容（含 frontmatter）。
slug: <slug>
写入路径: wiki/concepts/<slug>.md
```

**合并模式**（页面已存在）：额外传入已有页面内容，要求新信息补充到对应小节、矛盾处标记而非覆盖、保留已有来源信息。

Writer 完成后，把输出写入 `wiki/concepts/<slug>.md`。

---

## Phase 3: 确定性校验（唯一闸门）

**每个页面必须跑，不可跳过。** 这是流水线唯一的 PASS/FAIL 判定点。

```
python .claude/scripts/validate-page.py \
  --source <源文> --range <a>:<b> \
  --page wiki/concepts/<slug>.md
```

脚本做 6 项纯文本比对（不使用 LLM）：

| # | 检查项 | 阈值 |
|---|--------|------|
| 1 | 代码块精确匹配 | 行匹配率 ≥ 70% |
| 2 | 公式符号匹配 | 符号命中率 ≥ 60% |
| 3 | 数字一致性 | 页面数字必须在源文中存在 |
| 4 | 命名实体白名单 | 反引号术语/CamelCase/缩写必须在源文中 |
| 5 | 无中生有 | 源文无代码块则页面也不能有 |
| 6 | 数量覆盖 | 代码块 ≥ 源文×0.7，公式 ≥ 源文×0.8 |

**PASS 后的处理**：

- `exit 0` = PASS → 进入 Phase 4（或直接收尾）
- `exit 1` = FAIL → 根据错误类型分两路处理：

**确定性错误**（代码块不匹配、公式缺失、数字错误、反引号术语拼错）→ Orchestrator 用 Edit 直接修复，修完重跑 Phase 3 直到 PASS。

**语义问题**（归因错误、因果反转、事实偏差）→ 不修，在报告中标记 NEEDS_HUMAN_REVIEW。这些留给用户审核，不让 LLM 自动修改。

---

## Phase 4: Checker 语义复核（可选，只报告不改）

Phase 3 全部 PASS 后，可选择性 spawn Checker agent 做语义核对。Checker 输出**只写入报告，绝不触发页面修改**。

```
Agent({
  description: "Check wiki page: <slug>",
  prompt: <动态拼接>,
  subagent_type: "general-purpose"
})
```

**Checker prompt 构造**：

```
你是一个 wiki 页面 checker。对比源文和页面，找出事实性语义错误。

## 规则
<插入 .claude/prompts/checker.md 的内容>

## 源文片段（lines <a>-<b>）
<插入源文该段原文>

## 待检查页面
<插入页面内容>

## 输出格式
严格按 .claude/prompts/checker.md "## 输出" 一节的格式输出。
```

Checker 报错 → 原样写入 Phase 5 报告的"语义问题"段，页面内容不动。

---

## Phase 5: 收尾
```
总页数: N
Phase 3 首次通过: X
Edit 修复后通过: Y
Checker 报语义问题: Z（均已标记 NEEDS_HUMAN_REVIEW，未修改页面）
最终通过率: (X+Y)/N
```

2. 更新 `wiki/_index.md`（追加新页面条目）
3. 更新 `wiki/log.md`（追加本次 ingest 记录，含正确率统计）
4. 如有 NEEDS_HUMAN_REVIEW 页面，在报告中逐条列出 Checker 投诉

---

## 关键约束

- **Writer 的 context 里只有它负责的那段源文**，不含其他章节、不含其他页面的输出
- **代码和公式必须从 extract-segments 输出原样复制**，writer 不得自行重写
- **Phase 3 validate-page.py 不可跳过**——每个页面必须跑并 PASS，不 PASS 不写入报告
- **Orchestrator 用 Edit 修复后必须重跑 Phase 3**，验证修改引入的内容在源文中有依据
- **禁止任何 LLM sub-agent 修改已有页面**——只有 Orchestrator 可以对确定性错误做 Edit
- **每个 sub-agent 独立运行**，互不依赖，可并行
