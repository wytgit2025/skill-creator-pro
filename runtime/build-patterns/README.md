# build-patterns/ — Meta 层经验沉淀

这是 skill-creator-pro **自己**的 wiki 层。沉淀的是"帮人造技能这件事"上反复出现的问题，**不是**下游业务技能在任务里的失败（那些在业务技能自己的 `runtime/patterns/` 里）。

## 它解决什么

每次帮人造技能，我们都在踩同一类坑：网页采集类技能忘了问反爬、豆包环境测触发率全是假阴性、单人低频工具被硬塞了 runtime……这些坑散在对话里，下次还踩。本目录把它们结构化沉淀下来，目标是：**下次造技能前，先读这里，把已知教训带进访谈和设计。**

## 文件约定

一个反复出现的 meta 问题一个 md 文件，kebab-case 命名：

```markdown
# <一句话问题>

- 类别: web-scrape | docx | spreadsheet | trigger-optimization | runtime | platform-* | other
- 出现次数: N
- 涉及技能: [<name>, ...]
- 现象: <从 build-trace 汇总：哪类任务、卡在哪一步、用户怎么纠正的>
- 根因: <巡检时由 agent 补，不自动猜>
- 对策: <已经写进 SKILL.md / references 哪一节；或待补>
- 状态: open | absorbed
```

## 规则

- **open**：还在积累证据，巡检时优先看，访谈相关类别任务时主动问。
- **absorbed**：对策已经写进 SKILL.md 或 lessons-learned.md，证据保留但不再每次必读。
- 计数和涉及技能列表由巡检时更新；**根因和对策只由 agent/人填写，脚本不猜**。
- 已有的 `references/lessons-learned.md` 是"已确认、已吸收"的教训；本目录是"还在积证据"的观察。反复确认后，把结论提炼成一条 lessons-learned 条目，并把对应 pattern 标 absorbed。
- 本目录内容**不进打包产物**，只在本机积累。
