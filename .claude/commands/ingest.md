请执行 Ingest 操作，摄入指定的文件或扫描 `raw/` 下未处理的新文件。

## 输入
- 如果用户提供了文件名（例如 `/ingest raw/articles/示例.md`），则摄入该文件。
- 如果用户未提供文件名（仅输入 `/ingest`），则自动扫描 `raw/` 目录，找出所有未被记录在 `wiki/log.md` 中的新文件，并逐篇摄入。

## 执行流程
1. 读取文件，用中文给出不超过 5 个要点的高层总结。
2. 提取所有关键实体（人物/公司/产品/技术术语）。
3. 提取至少 3 个核心概念或论点。
4. 读取 `.claude/templates/summary.md`，按其格式在 `wiki/summaries/` 创建来源总结页。
5. 读取 `.claude/templates/concept.md` 和 `.claude/templates/entity.md`，按其格式增量更新 `wiki/concepts/` 和 `wiki/entities/` 中的相关页面。
6. 更新 `wiki/_index.md` 的链接、分类和矛盾追踪区（如有）。
7. 在 `wiki/log.md` 追加一条更新记录，并更新其 frontmatter 中的 `updated` 日期。
8. 运行 `.claude/scripts/validate-yaml.py` 验证所有页面 YAML frontmatter 合法。

## 注意事项
- 严格遵守 `CLAUDE.md` 中的 Wiki 编写规范。
- 所有阐述和总结使用中文。
