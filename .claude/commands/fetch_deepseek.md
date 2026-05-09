---
name: fetch-deepseek
description: Fetch a DeepSeek shared conversation and save it as a Markdown file to raw/articles/
---

# Fetch DeepSeek Skill

调用 Python 脚本提取 DeepSeek 分享链接中的完整对话，保存为 Markdown 文件。

## 前置条件

项目需包含 `.claude/scripts/fetch_deepseek.py`。依赖：`pip install playwright && playwright install chromium`。

## 执行

收到 DeepSeek 分享 URL 后，在项目根目录执行：

```bash
python .claude/scripts/fetch_deepseek.py "<URL>"
```

然后将输出结果（文件路径、对话条数、总字符数）汇报给用户。

## 备选方案

如果 `python` 不可用，尝试 `python3`。

如果脚本不在 `.claude/scripts/fetch_deepseek.py`，也尝试项目根目录下的 `fetch_deepseek.py`。

## 文件结构

```
项目根目录/
├── .claude/
│   ├── commands/
│   │   └── fetch-deepseek.md    ← 本 skill 文件
│   └── scripts/
│       └── fetch_deepseek.py    ← Python 提取脚本
└── raw/
    └── articles/
        └── *.md                 ← 输出的 Markdown 文件
```

迁移到其他项目时，把 `.claude/commands/fetch-deepseek.md` 和 `.claude/scripts/fetch_deepseek.py` 一起复制过去即可。

## 踩坑记录（调试脚本时参考）

如果输出有问题，以下是 DeepSeek 分享页的 DOM 结构要点：

1. **虚拟列表** — 页面用 `ds-virtual-list` 只渲染 ~12 条消息。脚本通过 CSS 覆盖 `height: auto !important` 强制全量渲染
2. **消息角色** — 用户消息 `.ds-message` 内无 `.ds-markdown`；助手消息有直接子级 `:scope > .ds-markdown`
3. **思考过程** — `.ds-think-content` 内部也嵌套了 `.ds-markdown`，必须用直接子选择器避开
4. **代码块** — `div.md-code-block` > `pre`（无 `<code>` 子元素，语法高亮用 `<span>`）
5. **表格** — `<table>` 需转 GFM 格式，单元格内保留行内 markdown 并转义 `|`
6. **嵌套列表** — `<li>` 内嵌套 `<ul>/<ol>` 需递归缩进 4 空格
