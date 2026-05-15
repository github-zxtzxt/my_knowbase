将源文编译为结构化 wiki。每个概念由独立 sub-agent 在隔离 context 中生成，确保源文注意力不被稀释。

## 输入

- `/ingest <path>` → 摄入该文件
- `/ingest` → 扫描 `raw/`，找出 `wiki/log.md` 未记录的文件

## 架构总览

```
Orchestrator（你）
  ├─ Phase 1:   扫描源文，生成候选清单
  ├─ Phase 2:   对每个候选 spawn Writer sub-agent（并行）
  ├─ Phase 3:   对每个产出跑 validate-page.py（确定性校验）
  ├─ Phase 4:   对确定性 PASS 的 spawn Checker sub-agent（并行）
  ├─ Phase 4.5: validate-checker.py 过滤 Checker 假阳性
  ├─ Phase 5:   对 LEGITIMATE FAIL 项 spawn Fixer，改完跑 validate-fix.py 回验
  └─ Phase 6:   写报告 + 更新 _index.md / log.md
```

**关键纠错原则**：Checker 是 LLM，会出假阳性把对的判错；Fixer 是 LLM，会改写时引入源文里没有的内容。Phase 4.5 和 Phase 5 的回验**用确定性脚本兜底**，防止 LLM 把已正确的页面改坏。

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

5. 对每个候选跑：
```
python .claude/scripts/extract-segments.py --source <源文> --range <a>:<b>
```
记录每个候选的 code_blocks 数和 formulas 数。

**跨段落处理**：如果同一概念在源文多处出现（如第 2 章引入、第 5 章扩展），source_range 写多段 `lines 595-712, 2870-2918`，extract-segments 对每段分别跑，结果合并传给 writer。

**增量检测**：对每个候选，检查 `wiki/concepts/<slug>.md` 或 `wiki/entities/<slug>.md` 是否已存在。
- 不存在 → 标记为 `create`
- 已存在 → 标记为 `merge`，Phase 2 时把已有页面内容也传给 writer

---

## Phase 2: Writer Sub-agents

对每个候选，spawn 一个 Agent：

```
Agent({
  description: "Write wiki page: <slug>",
  prompt: <见下方构造规则>,
  subagent_type: "general-purpose"
})
```

**Writer prompt 构造**（每次 spawn 时动态拼接）：

创建模式（页面不存在）：
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

合并模式（页面已存在）：
```
你是一个 wiki 页面 writer。已有页面需要根据新源文补充或纠正。

## 规则
<插入 .claude/prompts/writer.md 的内容>

## 已有页面内容
<插入当前 wiki 页面的完整内容>

## 新源文片段（lines <a>-<b>）
<插入新源文该段原文>

## 已提取的代码块和公式
<插入 extract-segments.py 的 JSON 输出>

## 合并规则
1. 新信息补充到对应小节（新公式加到"核心公式"，新代码加到"核心代码"）
2. 如果新源文与已有内容矛盾，不要默默覆盖，在页面末尾加"## 矛盾待解决"标记
3. 更新 frontmatter 的 source 和 source_range（追加新来源）
4. 保留已有内容中来自其他来源的信息

## 输出
输出合并后的完整 .md 文件内容。
```

Writer 完成后，把输出写入 `wiki/concepts/<slug>.md`。

---

## Phase 3: 确定性校验

对每个产出的页面跑：
```
python .claude/scripts/validate-page.py --source <源文> --range <a>:<b> --page wiki/concepts/<slug>.md
```

脚本检查：
1. 代码块精确匹配（页面代码是否为源文子串）
2. 公式匹配（页面公式是否在源文中存在）
3. 命名实体白名单（页面出现的库名/工具名是否在源文中）
4. 数量覆盖（代码块数 ≥ 源文×0.7，公式数 ≥ 源文×0.8）

退出码 0 = PASS，非 0 = FAIL（输出具体错误）。

---

## Phase 4: Checker Sub-agents

对确定性 PASS 的页面，spawn Checker agent 做语义核对：

```
Agent({
  description: "Check wiki page: <slug>",
  prompt: <动态拼接>,
  subagent_type: "general-purpose"
})
```

**Checker prompt 构造**：

```
你是一个 wiki 页面 checker。对比源文和页面，找出语义错误。

## 规则
<插入 .claude/prompts/checker.md 的内容>

## 源文片段（lines <a>-<b>）
<插入源文该段原文>

## 待检查页面
<插入页面内容>

## 输出格式
严格按 .claude/prompts/checker.md "## 输出" 一节的格式输出，特别注意：
- "页面写的" 必须是页面中逐字出现的字符串
- "源文实际" 必须是源文中逐字出现的字符串
- 必须给出 "源文行号"
- 代码标识符（类名/函数名）与散文术语是两套词汇，不要混淆
```

把 Checker 完整输出保存到临时文件 `.claude/tmp/checker-<slug>.txt`，供 Phase 4.5 使用。

---

## Phase 4.5: Checker 假阳性闸门

Phase 4 的 Checker 是 LLM 子 agent，**可能产生假阳性**（把对的判错，例如把页面引用源文散文的术语误判为应该改成代码里的标识符）。本闸门用确定性脚本过滤：

```
python .claude/scripts/validate-checker.py \
  --source <源文> --range <a:b> \
  --checker-output .claude/tmp/checker-<slug>.txt
```

脚本对每条 Checker 投诉做两步检查：
1. "页面写的"字段是否**逐字**存在于源文（normalize 后） → 是则丢弃为 FALSE_POSITIVE
2. "源文实际"字段是否真的在源文里 → 不在则丢弃为 FABRICATED

退出码：
- `0`：所有投诉被过滤为假阳性/编造，页面视为 PASS，**跳过 Phase 5**
- `1`：存在 LEGITIMATE 投诉，把脚本 stdout 中的 "## 🔴 LEGITIMATE" 段作为错误列表传给 Phase 5

**绝对不允许**跳过 Phase 4.5 直接把 Checker 原始输出送给 Fixer——这是导致 Fixer 把对的改错的根本原因。

---

## Phase 5: 修复

只对 Phase 4.5 输出的 LEGITIMATE 投诉、或 Phase 3 的确定性 FAIL，spawn Fixer agent：

**Step 1: 修改前快照**

```
cp wiki/concepts/<slug>.md .claude/tmp/before-<slug>.md
```

**Step 2: Spawn Fixer**

```
Agent({
  description: "Fix wiki page: <slug>",
  prompt: <动态拼接>,
  subagent_type: "general-purpose"
})
```

**Fixer prompt 构造**：

```
你是一个 wiki 页面 fixer。根据错误列表修正页面，只改错误处，不重写整页。

## 源文片段
<插入源文该段>

## 当前页面
<插入页面内容>

## 错误列表
<插入 validate-page.py 输出 或 Phase 4.5 过滤后的 LEGITIMATE 投诉列表>

## 铁律
1. 只改错误列表中明确指出的问题，其他内容一字不动
2. 改完后，每一段修改后的文本必须能在源文中找到逐字依据
3. 不要把代码标识符（类名/函数名）当成散文术语使用
4. 不要"顺手"美化、扩写、重写

## 输出
输出修正后的完整 .md 文件内容。
```

**Step 3: 修复后回验**

```
python .claude/scripts/validate-fix.py \
  --source <源文> --range <a:b> \
  --before .claude/tmp/before-<slug>.md \
  --after wiki/concepts/<slug>.md
```

退出码：
- `0`：修改可接受
- `1`：Fixer 引入了源文中找不到的内容，**立即回滚**：
  ```
  cp .claude/tmp/before-<slug>.md wiki/concepts/<slug>.md
  ```
  并标记该页 NEEDS_HUMAN_REVIEW，附上 validate-fix 的输出作为审核依据。

修复后重新跑 Phase 3 + Phase 4（含 4.5）。**最多 2 轮修复**，仍 FAIL 则标记 NEEDS_HUMAN_REVIEW。

用户审核后可在页面 frontmatter 加 `reviewed: <YYYY-MM-DD>`，后续 verify-ingest 和 lint 将跳过该页的 FAIL 判定（状态显示为 REVIEWED）。

---

## Phase 6: 收尾

1. 统计并输出正确率报告：
```
总页数: N
首次通过: X (X/N%)
修复后通过: Y
需人工审核: Z
最终通过率: (X+Y)/N%
```

2. 更新 `wiki/_index.md`（追加新页面条目）
3. 更新 `wiki/log.md`（追加本次 ingest 记录）
4. 如有 NEEDS_HUMAN_REVIEW 页面，在报告中列出具体错误

---

## 关键约束

- **Writer 的 context 里只有它负责的那段源文**，不含其他章节、不含其他页面的输出
- **代码和公式必须从 extract-segments 输出原样复制**，writer 不得自行重写
- **确定性校验不可绕过**——脚本说代码不匹配就是不匹配，不接受解释
- **每个 sub-agent 独立运行**，互不依赖，可并行
