将源文编译为结构化 wiki。每个概念由独立 sub-agent 在隔离 context 中生成，确保源文注意力不被稀释。

## 输入

- `/ingest <path>` → 摄入该文件
- `/ingest` → 扫描 `raw/`，找出 `wiki/log.md` 未记录的文件

## 架构总览

```
Orchestrator（你）
  ├─ Phase 1: LLM 通读源文 → 维护 tmp/concepts.yaml 概念表
  ├─ Phase 2: 对每个概念 spawn Writer sub-agent（并行）
  └─ Phase 3: 写报告 + 更新 _index.md / log.md
```

核心设计：
- Phase 1 不做机械切分，LLM 直接通读全文判断概念边界——什么格式都能读
- 概念表（`tmp/concepts.yaml`）是中间产物，人类可查看可修改。改完表重跑 Phase 2 即可，不用重读全文
- Phase 2 每个 Writer 只看自己的源文片段，上下文隔离

## 只增不改原则

Ingest 只能创建新文件、向 _index.md 和 log.md 追加内容。严禁删除或覆盖已有页面。

---

## Phase 1: 通读全文，维护概念表

0. **Hash 去重**：计算源文 SHA-256：
   ```
   python -c "import hashlib; print(hashlib.sha256(open('<源文>','rb').read()).hexdigest())"
   ```
   读取 `tmp/concepts.yaml`。如果该源文已存在、`ingested: true` 且 `source_hash` 与当前一致，则跳过全部阶段，输出"源文未变化，跳过 ingest"。

1. **通读源文全文**——不分批，不跳段。LLM 一次性读完，理解整篇结构后判断哪些部分构成独立概念、哪些是过渡/引言。

2. **写入 `tmp/concepts.yaml`**，格式：

   ```yaml
   source: raw/articles/happy_llm/chapter2/chapter2-transformer.md
   source_hash: a1b2c3d4e5f6...
   ingested: false

   concepts:
     - slug: attention-mechanism
       ranges:
         - [5, 151]
       type: concept
       action: create
       reason: 注意力机制的核心定义、数学推导与代码实现

     - slug: positional-encoding
       ranges:
         - [601, 785]
       type: concept
       action: create
       reason: 位置编码的 Sinusoidal 编码方案及其数学推导

     - slug: transformer-model
       ranges:
         - [328, 333]
         - [786, 894]
       type: concept
       action: create
       reason: 完整 Transformer 模型组装，跨段落（架构概述在 2.2 导言段，实现在 2.3.3）
   ```

   规则：
   - `slug`：英文小写 + 连字符，与 `wiki/concepts/<slug>.md` 路径一致
   - `ranges`：`[start, end]` 1-based 行号，含两端。跨段落概念写多段
   - `type`：concept | entity | summary
   - `action`：
     - `create` — wiki 页面不存在，新建
     - `merge` — wiki 页面已存在，将当前源文段补充进已有页面
   - `source`：相对项目根目录的源文路径

3. **增量检测**：写入概念表前，检查 `wiki/concepts/<slug>.md` 是否已存在。
   - 不存在 → `action: create`
   - 已存在 → `action: merge`，Phase 2 时把已有页面内容传给 writer，补充而非覆盖

4. 概念表写完后直接进入 Phase 2，不暂停等待确认。

---

## Phase 2: Writer Sub-agents

对概念表中每个条目 spawn 一个 Agent（全部并行运行）：

```
Agent({
  description: "Write wiki page: <slug>",
  prompt: <见下方构造规则>,
  subagent_type: "general-purpose"
})
```

**Writer prompt 构造**（create 模式）：

```
你是一个 wiki 页面 writer。根据源文片段写一个 wiki 概念页。

## 规则
<插入 .claude/prompts/writer.md 的内容>

## 可用的 wikilink 目标（本次 ingest 的其他概念）
<插入概念表中所有 slug 列表，每行一个>

## 源文片段
<根据概念表中的 ranges，Read 源文对应行，如有多段则全部拼接>

## 已提取的代码块和公式（必须原样嵌入页面）
<对每个 range 跑 extract-segments.py，合并后传入>

## 输出
直接输出完整的 .md 文件内容（含 frontmatter）。
source 字段写 raw/ 源文件路径#行号，不可写 wiki 页名。
slug: <slug>
写入路径: wiki/concepts/<slug>.md
```

提取命令：
```
python .claude/scripts/extract-segments.py --source <源文> --range <a>:<b>
```

**merge 模式**：额外传入已有 wiki 页面内容。要求 writer 将新源文信息补充到对应小节、矛盾处标记而非覆盖、保留已有 `## 原文引用` 段并在其后追加新源文段落。

Writer 完成后，orchestrator 把输出写入对应 `wiki/` 路径。

---

## Phase 3: 收尾

1. 输出 ingest 报告：
```
源文: <path>
产出: N 页（X concept + Y entity + Z summary）
新增: A / 合并: B
```

2. 更新 `wiki/_index.md`（追加新页面条目，按概念/实体/来源总结分区）
3. 更新 `wiki/log.md`（追加本次 ingest 记录，同步更新其 frontmatter `updated` 日期）
4. 将 `tmp/concepts.yaml` 中 `ingested` 改为 `true`，`source_hash` 写入当前源文 SHA-256
5. 运行 `python .claude/scripts/validate-yaml.py` 校验所有 wiki 页面 YAML frontmatter 合法
6. 如有矛盾（新知识与已有 wiki 冲突），在报告末尾逐条列出

---

## 关键约束

- **Writer 的 context 里只有它负责的那段源文**，不含其他章节、不含其他页面的输出
- **代码和公式必须从 extract-segments 输出原样复制**，writer 不得自行重写
- **source 字段必须指向 raw/ 源文件#行号**，不可指向另一个 wiki 页
- **每个页面必须包含 `## 原文引用` 节**，保留源文原始段落
- **Phase 1 概念表可改**——用户修改 `tmp/concepts.yaml` 后直接重跑 Phase 2，无需重读全文
- **禁止任何 LLM sub-agent 修改已有页面**
- **每个 sub-agent 独立运行**，互不依赖，可并行
