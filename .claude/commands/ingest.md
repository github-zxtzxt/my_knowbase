请执行 Ingest 操作，摄入指定的文件或扫描 `raw/` 下未处理的新文件。

## 输入
- 如果用户提供了文件名（例如 `/ingest raw/articles/示例.md`），则摄入该文件。
- 如果用户未提供文件名（仅输入 `/ingest`），则自动扫描 `raw/` 目录，找出所有未被记录在 `wiki/log.md` 中的新文件，并逐篇摄入。

## 执行流程
1. 读取文件，用中文给出不超过 5 个要点的高层总结。
2. 提取所有关键实体（人物/公司/产品/技术术语）。
3. 提取至少 3 个核心概念或论点。
4. **增量合并**：对每个要写入的概念页和实体页，先 `Read` 检查是否已存在：
   - **完全重复** → 不修改该页面
   - **同一观点，不同来源佐证** → 追加来源引用，可选补充一两个新例证
   - **新角度 / 新细节** → 新增一个小节，或扩展现有小节
   - **与现有内容矛盾** → 不覆盖原文，在页面内标记 `**⚠️ 待确认的矛盾：** ...` 并附带两个冲突来源；同时在 `wiki/_index.md` 的矛盾追踪区新增一行记录。完成后向用户报告所有新增矛盾，等待人工定夺
5. 读取 `.claude/templates/summary.md`，按其格式在 `wiki/summaries/` 创建来源总结页。
6. 读取 `.claude/templates/concept.md` 和 `.claude/templates/entity.md`，按其格式增量更新 `wiki/concepts/` 和 `wiki/entities/` 中的相关页面。
7. 更新 `wiki/_index.md` 的链接和分类索引。
8. 在 `wiki/log.md` 追加一条更新记录，并更新其 frontmatter 中的 `updated` 日期。
9. 运行 `.claude/scripts/validate-yaml.py` 验证所有页面 YAML frontmatter 合法。

## 注意事项
- 严格遵守 `CLAUDE.md` 中的 Wiki 编写规范。
- 所有阐述和总结使用中文。
