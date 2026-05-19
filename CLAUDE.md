# Knowbase — 知识副脑

## 核心理念

这不是 RAG。我不会每次提问时去 raw/ 检索现拼答案。我的工作方式：
1. 事先读完你喂给的原始素材
2. 把内容**编译**为结构化的 Markdown wiki（总结、概念、实体、关系）
3. 后续所有提问基于 wiki 回答，不重新翻 raw/

知识编译一次，永久复用，复利增长。

## 目录结构

- `raw/`：原始素材，**只读**，永远不修改。
- `wiki/`：由我生成和维护的 Markdown wiki，所有页面互相链接。
- `outputs/`：高质量回答归档。

## Wiki 编写规范

1. **文件命名**：英文小写 + 连字符，例如 `self-attention.md`。
2. **页面类型**：
   - `wiki/concepts/`：概念页，解释单个关键术语
   - `wiki/entities/`：实体页，记录人物、公司、产品
   - `wiki/summaries/`：来源总结，每篇原始文章对应一页
   - `wiki/errors/`：复盘页面（认知偏差记录）
   - `wiki/_index.md`：总索引，每次摄入都必须更新
3. **链接规范**：使用 Obsidian 兼容的双向链接 `[[页面名]]`，把所有页面连成网络。
4. **格式要求**：每个页面首段必须是摘要；YAML frontmatter 包含 `tags` 和 `source`。生成页面前读取 `.claude/templates/` 下对应类型的模板文件。
5. **YAML frontmatter 中的 wikilink**：YAML 中 `[` 是 flow sequence 起始符。含有 `[[wikilink]]` 的字段值必须用引号包裹。多值字段（如 `related`）使用 YAML list 格式：
   ```yaml
   related:
     - "[[page1]]"
     - "[[page2]]"
   ```
   生成或修改 wiki 页面后，运行 `.claude/scripts/validate-yaml.py` 验证 frontmatter 合法性。
6. **矛盾处理**：新知识和已有内容矛盾时，不直接覆盖，遵循 AI+人协作流程：
   - 在相关页面标记 `**⚠️ 待确认的矛盾：**`，列出两个冲突来源和分歧要点
   - 在 `wiki/_index.md` 的"矛盾追踪区"表格新增一行，格式：

     | 日期         | 涉及页面                   | 矛盾描述 | 状态  |
     |------------|------------------------|------|-----|
     | YYYY-MM-DD | [[page-a]], [[page-b]] | 分歧要点 | 待定夺 |

   - Ingest 结束时向用户报告所有新增矛盾，由用户通过讨论或直接编辑来定夺，解决后标记为"已解决"
7. **log.md 维护**：每次在 `wiki/log.md` 追加记录时，同步将其 frontmatter 中 `updated` 字段更新为当前日期。

## 操作

所有操作通过 slash command 触发，完整规则在 `.claude/commands/` 目录下：

| 命令 | 说明 |
|------|------|
| `/ingest` | 摄入新素材，编译为 wiki |
| `/reingest` | 重新摄入已更新的文件 |
| `/reflect` | 复盘 DeepSeek 对话中的认知偏差 |
| `/lint` | 健康检查 wiki/ 目录 |

## Query（提问）

详细规则在 `.claude/commands/query.md`。简要：

- `/query` — 3 跳导航检索 wiki，引用出处，不翻 raw/
- `/query --quick` — 只看 _index.md
- `/query --deep` — 穿透到 raw/ 原文对证
- 信息不足时说"wiki 暂无记录"并建议 `/ingest`，不编造
- `/query --save` 归档高质量回答到 `outputs/`
