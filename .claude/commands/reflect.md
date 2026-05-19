复盘对话，提取知识沉淀和认知偏差。整合了对话总结与错误追踪。

## 输入

- `/reflect` — 复盘当前对话 session
- `/reflect <file>` — 复盘指定文件（DeepSeek 对话或知识文章）

## 执行流程

### 0. 上下文检查

若当前对话轮次已很长（>100 轮），先提示用户：reflect 消费 context 本身，建议在对话早期或自然中断点使用。不阻断，仅提醒。

### 1. 准备对话内容

- `/reflect` 无参数：复盘"自上次 reflect 以来的对话"。若无上次记录，复盘全部。提取对话中所有用户发言和关键回答，构造对话记录文本
- `/reflect <file>`：读取指定文件

### 2. Spawn Reflector sub-agent

```
Agent({
  description: "Reflect on conversation",
  prompt: <见下方>,
  subagent_type: "general-purpose"
})
```

**Reflector prompt 构造：**

```
你是一个对话复盘专家。分析以下对话。

## 规则
<插入 .claude/prompts/reflector.md 的内容>

## 对话记录
<对话文本>

## 可用的 wiki 概念列表（用于匹配 error.concept）
<扫描 wiki/concepts/ 和 wiki/entities/ 下的所有 slug，每行一个>
```

### 3. 处理 Reflector 输出

收到 YAML 后：

**对话总结 → outputs/：**

写 `outputs/session-YYYY-MM-DD-<topic>.md`：

```markdown
---
tags: [session, <主题>]
date: YYYY-MM-DD
related:
  - "[[concept-a]]"
  - "[[concept-b]]"
---

# 对话总结：<主题>

## 关键决策

- **决策**：原因
- ...

## 关键洞察

- ...
- ...

## 涉及概念

- [[concept-a]]
- [[concept-b]]
```

**错误追踪 → wiki/errors/：**

对每条 error，执行复现追踪：
1. 提取核心概念关键词
2. 扫描 `wiki/errors/_index.md` 复盘追踪表，判断是否已有相似主题
3. 若 **new**：创建 `wiki/errors/<slug>.md`，在追踪表新增一行
4. 若 **recurring**：更新已有页面，追加复现记录，追踪表复现次数 +1
5. 更新对应 wiki concept 页面的 `related_errors` 字段

### 4. 更新索引

- 更新 `wiki/errors/_index.md` 追踪表
- 更新 `wiki/log.md`（追加本次 reflect 记录，更新 frontmatter `updated`）
- 运行 `.claude/scripts/validate-yaml.py`

### 5. 报告

用中文报告：
- 本次复盘来源（对话 session / 文件路径）
- 对话主题
- 发现偏差数（新建 X / 复现 Y）
- 沉淀的决策和洞察数

---

## 注意事项

- 严格遵守 `CLAUDE.md` 中的 Wiki 编写规范
- 若对话中无 devation，在 `log.md` 记录"已复盘，无偏差"，不强制生成 error 页面
- 对话总结是知识提炼（从对话中得到了什么新认知），不是操作日志（执行了什么操作）
