# Knowbase — 你的知识副脑

> 受 Karpathy [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) 理念启发，参考 gbrain / nvk / atomicstrata / wiki-kb 的设计，基于 Claude Code 构建的个人知识管理系统。

不是 RAG——知识**编译一次，持续复用，复利增长**。

## 为什么不是 RAG

RAG 每次提问现翻书找答案，翻完就忘。Knowbase 事先读完素材，编译为结构化 wiki，后续所有提问直接基于 wiki 回答。wiki 页面链回 raw 源文，可随时穿透对证。

## 目录结构

```
├── raw/                 # 原始素材（只读）
│   └── articles/        #   文章、教程、DeepSeek 对话
├── wiki/                # 编译后的知识库
│   ├── _index.md        #   总索引
│   ├── concepts/        #   概念页 + _index.md
│   ├── entities/        #   实体页 + _index.md
│   ├── summaries/       #   来源总结页
│   ├── errors/          #   认知偏差追踪 + _index.md
│   └── log.md           #   操作日志
├── outputs/             # 高质量回答 & 对话总结归档
├── tmp/                 # Ingest 中间产物（concepts.yaml 概念表）
├── .claude/             # Claude Code 配置
│   ├── commands/        #   slash 命令（ingest / query / lint / reflect / reingest）
│   ├── prompts/         #   sub-agent prompt
│   ├── templates/       #   wiki 页面模板
│   └── scripts/         #   Python 工具脚本
└── CLAUDE.md            #   项目指令
```

Wiki 文件使用 Obsidian 兼容的 `[[双向链接]]`。

## 命令

| 命令 | 说明 |
|------|------|
| `/ingest [path]` | 编译源文为 wiki。LLM 通读 → 写概念表 → 并行 Writer sub-agent 生成 |
| `/query [--quick\|--deep]` | 3 跳导航检索 wiki。`--deep` 穿透到 raw 对证。`--save` 归档回答 |
| `/lint` | 健康检查：YAML 合法性、断链、wiki→raw 链接、更新记录、孤立页面、矛盾 |
| `/reflect [file]` | 复盘对话：提炼知识沉淀 + 追踪认知偏差。整合了对话总结与错误追踪 |
| `/reingest <file>` | 重新摄入已更新的文件 |
| `/fetch_deepseek <url>` | 拉取 DeepSeek 分享对话到 raw/ |

## 初始化

```bash
git clone <your-repo-url> my-knowbase
cd my-knowbase
mkdir -p raw/articles wiki/concepts wiki/entities wiki/summaries wiki/errors outputs tmp
claude
```

Claude Code 启动后自动加载 `CLAUDE.md`，无需额外配置。

## 使用方式

### 摄入编译

```
/ingest raw/articles/some-article.md
```

Claude 通读全文 → 生成 `tmp/concepts.yaml` 概念表（可人工修改） → 每个概念由独立 sub-agent 并行生成 wiki 页面 → 更新索引和 log。

每个 wiki 页面包含：
- **sources** — 指向 raw/ 源文件#行号，支持多来源
- **aliases** — 中文译名、缩写、别称
- **confidence** — high / medium / low
- **## 更新记录** — 只追加的时间追踪表

### 提问

```
/query --deep self-attention 的原理是什么
```

默认 3 跳导航（_index → 分类 index → 3-8 篇文章），不翻 raw。不确定时说"wiki 暂无记录"并建议 ingest，不靠训练知识编造。回答引用 sources。

### 复盘

```
/reflect              # 复盘当前对话
/reflect raw/articles/xxx.md  # 复盘指定文件
```

产出：对话总结（outputs/） + 错误追踪（wiki/errors/，含复现次数）。Query 时自动检查涉及概念的已知错误并提醒。

### 健康检查

```
/lint
```

检查：YAML 语法、断链、wiki→raw 链接完整性、`## 更新记录` 存在性、孤立页面、矛盾信息。

## Wiki 页面 frontmatter 规范

```yaml
tags: [nlp, transformer]
sources:
  - "[[raw/articles/happy_llm/chapter2/chapter2-transformer#lines 5-151]]"
aliases:
  - 注意力机制
confidence: high
related_errors: []
created: 2026-05-19
updated: 2026-05-19
```

- 文件命名：英文小写 + 连字符
- 每个页面首段为摘要
- 用 `[[双向链接]]` 连接 wiki 网络
- YAML 中含 `[[wikilink]]` 必须用引号包裹
- 新知识与已有内容矛盾时标记 `⚠️ 待确认的矛盾`，不直接覆盖
- 生成/修改 wiki 后运行 `validate-yaml.py`

## 架构原则

1. **Sub-agent 隔离**：每个概念由独立 Writer 在隔离 context 生成，防止注意力稀释
2. **不做内容闸门**：不验字面一致性。页面 source 链回 raw，读者可对证原文
3. **概念表中间可改**：`tmp/concepts.yaml` 人工调整后重跑 Phase 2，无需重读全文
4. **只增不改**：ingest 只创建新文件和追加索引，不覆盖已有页面

## 与 Obsidian 配合

用 Obsidian 打开项目根目录，可浏览 wiki 链接图谱。`.obsidian/` 已包含基础配置。

## 许可

MIT
