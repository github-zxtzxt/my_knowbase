基于已编译的 wiki 回答用户问题。不翻 raw/，不做 RAG。

## 输入

- `/query <问题>` — 默认深度
- `/query --quick <问题>` — 只用索引
- `/query --deep <问题>` — 穿透到 raw 原文对证

## 检索策略

### 默认（3 跳导航）

逐级缩小范围，不扫全目录：

```
Hop 1: 读 wiki/_index.md → 锁定相关分类（概念/实体/总结）
Hop 2: 读 wiki/<分类>/_index.md → 匹配摘要和 tag
       如分类 index 不存在，改为扫描对应目录的文件列表
Hop 3: 读 3-8 篇匹配的 .md 文件 → 综合回答
```

### `--quick`

只读 `wiki/_index.md`，从摘要和 tag 回答。适合"有哪些概念"、"XX 是什么"这类标题级问题。

### `--deep`

默认 3 跳 + 穿透 raw/。当 wiki 页面信息不足以支撑结论时，通过 `sources` frontmatter 定位到 `raw/` 源文件对应行号，直接读原文对证。

## 回答规则

1. **引用出处**：每个关键结论必须注明来自哪个 wiki 页面。格式：`（来源：[[page-slug]]）`
2. **不确定就说不知道**：wiki 没覆盖的内容，不靠训练知识编造。回答"wiki 暂无记录"并建议 `/ingest` 相关素材
3. **矛盾不掩盖**：如果多个 wiki 页面对同一问题有冲突陈述，列出双方及其 `sources`，不自行裁决
4. **`--save` 归档**：在回答末尾标注 `[[outputs/<slug>]]`，将回答写入 `outputs/` 目录
5. **错误提醒**：回答中引用的每个 wiki 概念，检查其 frontmatter 中 `related_errors` 是否有且 `status: active`。若有，在回答末尾附加：

   > ⚠️ 注意：你曾在以下认知偏差中涉及这些概念，留意本次回答中的相关部分：
   > - [[error/xxx]]：简要说明
   > - ...

   不提醒已标记 `status: resolved` 的错误。
