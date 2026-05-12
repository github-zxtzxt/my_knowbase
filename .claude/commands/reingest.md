请重新摄取用户指定的已更新文件。

## 执行流程

1. 重新读取该文件。
2. 对比现有 wiki 中的相关内容，明确指出这次更新带来的主要变化。
3. 按 Ingest 流程更新所有受影响页面（实体、概念、摘要等）。
4. 如发现与 wiki 现有知识矛盾，在相关页面标注 `**⚠️ 待确认的矛盾：**...` 并更新 `_index.md` 中的矛盾追踪区。
5. 在 `wiki/log.md` 中记录一次单独的"重新摄取"条目，并更新其 frontmatter 中 `updated` 日期。
6. 运行 `.claude/scripts/validate-yaml.py` 验证所有页面 YAML frontmatter 合法。

## 注意事项

- 严格遵守 `CLAUDE.md` 中的 Wiki 编写规范。
- 所有阐述和总结使用中文。
