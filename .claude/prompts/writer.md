# Writer Sub-agent 指令

根据提供的源文片段写一个 wiki 概念页。

## 页面结构

```markdown
---
tags:
  - <领域标签>
sources:
  - "[[raw/<源文件路径>#lines <a>-<b>]]"
aliases:
  - <中文译名或缩写>
confidence: high | medium | low
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

<一句话定义>

## 要点

<3-8 个 bullet，概括源文关键信息。每条对应源文中的具体内容。>
```

如果"已提取"列表中有公式，在"要点"前加一节：
```markdown
## 核心公式

<原样复制每个公式，每个后面 1-2 句解释>
```

如果"已提取"列表中有代码块，在"要点"前加一节：
```markdown
## 核心代码

<原样复制每个代码块，每个后面 1-2 句说明>
```

然后加关联节：
```markdown
## 关联

- 前置：[[xxx]]
- 相关：[[yyy]]
```

最后必须加更新记录节：
```markdown
## 更新记录

| 日期 | 来源 | 变化 |
|------|------|------|
| YYYY-MM-DD | [[raw/<源文件路径>#lines <a>-<b>]] | 初始创建 |
```

## 铁律

1. 已提取的代码块和公式原样复制，一字不改
2. `sources` 为 YAML list，每个元素指向 `raw/` 下的源文件路径#行号，不可指向 wiki 页。多来源时列出多条
3. `## 更新记录` 表格只追加不删改已有行。本次 ingest 在表尾新增一行
4. `confidence` 根据信息充分程度和源文清晰度标注：high（源文详细且明确）/ medium（信息较简略）/ low（源文仅提及但缺乏细节）
5. `aliases` 列出概念的中文译名、缩写、别称等，方便搜索和 Obsidian 发现
6. `created` 和 `updated` 为当前日期

## Entity 页面（人物/组织/模型等）

如果 slug 指定写入 `wiki/entities/`，使用以下结构：

```markdown
---
tags:
  - <类型标签>
sources:
  - "[[raw/<源文件路径>#lines <a>-<b>]]"
aliases:
  - <中文译名或缩写>
confidence: high | medium | low
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

<一句话：这是谁/什么>

## 关键事实

<bullet list：源文中提到的具体事实（时间、成果、角色等）>

## 关联

- [[相关概念或实体]]

## 更新记录

| 日期 | 来源 | 变化 |
|------|------|------|
| YYYY-MM-DD | [[raw/<源文件路径>#lines <a>-<b>]] | 初始创建 |
```
