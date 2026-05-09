# LLM Wiki 知识库系统

一个基于 Claude Code 的持久化个人知识库。不是 RAG —— 知识**编译一次，永久复用**，不是每次提问时临时检索。

## 核心理念

你把原始素材丢进 `raw/`，Claude Code 将它们编译为结构化 Wiki（概念、实体、总结）。之后所有提问直接基于 Wiki 回答，不重新翻原始素材。

```
原始素材 (raw/)  ──ingest──▶  结构化 Wiki (wiki/)  ──query──▶  回答 & 归档 (outputs/)
```

## 目录结构

```
├── raw/             # 原始素材（只读，手动放入）
│   └── articles/    #   DeepSeek 对话记录、文章等
├── wiki/            # 编译后的知识库（Claude 维护）
│   ├── _index.md    #   总索引
│   ├── concepts/    #   概念页
│   ├── entities/    #   实体页（人物、产品、公司）
│   ├── summaries/   #   来源总结页
│   ├── errors/      #   复盘页面（认知偏差记录）
│   └── log.md       #   变更日志
├── outputs/         # 高质量回答归档
├── .claude/         # Claude Code 配置
│   ├── commands/    #   自定义 slash 命令
│   ├── skills/      #   自定义 skill
│   └── settings.json
└── CLAUDE.md        # 项目指令（Claude 行为规范）
```

Wiki 文件使用 Obsidian 兼容的 `[[双向链接]]`，可直接用 Obsidian 打开浏览。

## 前置条件

- [Claude Code](https://claude.ai/code) CLI（项目指令写在 `CLAUDE.md` 中，Claude Code 启动时自动加载）
- （可选）[Obsidian](https://obsidian.md) — 可视化浏览 Wiki 链接网络
- （仅 `/fetch_deepseek`）Python + Playwright：`pip install playwright && playwright install chromium`

## 初始化

```bash
git clone <your-repo-url> my-knowbase
cd my-knowbase
mkdir -p raw/articles wiki/concepts wiki/entities wiki/summaries wiki/errors outputs
claude
```

Claude Code 启动后自动加载 `CLAUDE.md` 中的全部指令，无需额外配置。

## 使用方式

### 四大核心操作

| 操作 | 命令 | 说明 |
|------|------|------|
| **Ingest（摄入）** | `/ingest` 或说"摄入 raw/xxx" | 读取原始素材，编译为 Wiki 页面，更新索引 |
| **Query（提问）** | 直接提问 | 基于 Wiki 回答，信息不足时建议摄入新素材 |
| **Lint（检查）** | `/lint` | 检查断链、矛盾、孤立页面、过时描述 |
| **Reflect（复盘）** | `/reflect` | 分析对话中的认知偏差，沉淀到 `wiki/errors/` |

### 额外命令

| 命令 | 说明 |
|------|------|
| `/fetch_deepseek` | 拉取 DeepSeek 分享对话到 `raw/articles/` |
| `/reingest` | 重新摄入已更新的文件 |

## 常规使用

### 放入原始素材

将你想要编译成结构化知识的内容（文章、教程、笔记等）放入 `raw/articles/`：

```bash
cp ~/Downloads/some-article.md raw/articles/
# 或直接拖拽文件到 raw/articles/ 目录
```

素材可以是任意 Markdown 文件，没有格式限制。

### 摄入编译

在 Claude Code 中说：

```
/ingest raw/articles/some-article.md
```

或者直接 `/ingest`，Claude 会自动扫描 `raw/` 下未处理的新文件。

Claude 会：
1. 用中文给出不超过 5 个要点的高层总结
2. 提取关键实体（人物、公司、产品、技术术语）
3. 提取核心概念，在 `wiki/concepts/` 下创建概念页
4. 在 `wiki/summaries/` 下创建来源总结页
5. 更新 `wiki/_index.md` 的索引和交叉链接

### 基于 Wiki 提问

摄入完成后，直接基于 Wiki 提问：

```
Rust 的所有权和 Go 的 GC 有什么区别？
trait 和 interface 的对比？
```

Claude 会优先基于已编译的 Wiki 回答，不会重新翻 `raw/`。如果信息不足，会主动建议你摄入相关新素材。

### 归档高质量回答

如果某次回答质量很高，可以主动让 Claude 归档：

```
把刚才的回答归档到 outputs/
```

或者 Claude 觉得某次回答质量高时，会主动建议归档。

### 更新已有素材

如果 `raw/` 中的某个文件被更新了：

```
/reingest raw/articles/some-article.md
```

Claude 会重新读取并更新相关的 Wiki 页面。

### 健康检查

定期运行 `/lint`，检查：
- 断开的 `[[双向链接]]`
- 不同来源对同一概念相互矛盾的定义
- 孤立页面（没有其他页面链接到它）
- 有过时倾向的描述

## 特色功能：DeepSeek 对话学习流水线

`/fetch_deepseek` 和 `/reflect` 是本项目的特色功能，两者配合形成一条完整的"对话学习"流水线：

```
DeepSeek 分享链接 ──fetch──▶  raw/articles/*.md  ──ingest──▶  wiki/  ──reflect──▶  wiki/errors/
                        (拉取对话)               (编译知识)              (复盘认知偏差)
```

### 1. 拉取对话

```
/fetch_deepseek <DeepSeek 分享链接>
```

需要 DeepSeek 的**分享链接**（格式：`https://chat.deepseek.com/share/...`），在 DeepSeek 网页端对话中点击"分享"即可获取。调用 Playwright 脚本从分享页提取完整对话，保存为 Markdown 到 `raw/articles/`，文件保留原始对话格式（`**用户**：` / `**助手**：`），后续复盘依赖此格式。

### 2. 摄入编译

```
/ingest
```

扫描 `raw/` 下未处理的新文件，提取概念和实体，编译为 Wiki 页面。这会创建 `wiki/summaries/` 来源总结页，并增量更新概念页和实体页。

### 3. 复盘偏差

```
/reflect
```

**仅针对 DeepSeek 对话文件**（自动检测 `**用户**：` / `**助手**：` 格式，知识型文档直接跳过）。从对话中提取用户的认知偏差（概念误解、计算错误、思路中断等），执行偏差复现追踪，沉淀到 `wiki/errors/`。

如果对话中没有被纠正的错误或明显偏差，复盘结果为空（"未发现需要复盘的内容"），不强制生成复盘页面。

### 典型工作流示例

```
# 1. 看到一篇有价值的 DeepSeek 对话，分享链接
/fetch_deepseek https://chat.deepseek.com/share/xxxxx
# → 输出：已保存到 raw/articles/xxxxx.md

# 2. 摄入对话内容，编译为 Wiki
/ingest
# → Claude 总结要点，创建概念页，更新索引

# 3. 复盘对话中的认知偏差
/reflect
# → 自动扫描未复盘的对话，提取偏差，追踪复现

# 4. 定期维护
/lint
# → 检查断链、矛盾、孤立页面
```

## Wiki 规范

- 文件名：英文小写 + 连字符，如 `self-attention.md`
- 每个页面首段为摘要
- 使用 `[[双向链接]]` 连接所有页面
- YAML frontmatter 包含 `tags` 和 `source`
- 新知识与现有内容矛盾时，标记 `⚠️ 待确认的矛盾`，不直接覆盖

## 与 Obsidian 配合

用 Obsidian 打开项目根目录，可以看到所有 Wiki 页面的链接图谱。`.obsidian/` 目录已包含基础配置。

## 许可

MIT
