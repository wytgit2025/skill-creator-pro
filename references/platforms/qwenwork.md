# 千问办公（QwenWork，阿里）

**特点：** 阿里的一站式 AI 办公平台（2026-08-03 公测），桌面端 + 网页端 + 钉钉内唤起。**原生支持 SKILL.md**，但比通用 Agent Skills 多几个强制的元数据字段，不是"丢进去就能用"。

## 技能存放位置
按运行环境分三处，SDK 会在运行时给出 `--resource-dir`，拿得到就用它：

| 环境 | 路径 |
|---|---|
| macOS / Linux 主机 | `~/.qwenworkcn/skills/<技能名>/` |
| Windows | `%USERPROFILE%\.qwenworkcn\skills\<技能名>\` |
| VM / 容器 | `/root/.qwenworkcn/skills/<技能名>/` |

## 比通用规范多出来的硬要求
**1. frontmatter 必须中英双语齐全**（缺了用户可见的技能在 UI 里显示不全）：

```yaml
---
name: code-review              # 仍是最多 64 字符的 ASCII kebab-case
name_en: Code Review
name_zh: 代码审查
description: Review code for quality...        # 英文，兼容/默认值
description_en: Review code for quality...
description_zh: 按团队标准审查代码质量...
argument-hint: Paste a diff or attach the files to review
argument-hint-en: Paste a diff or attach the files to review
argument-hint-zh: 粘贴差异内容或附上待审查文件
user-invocable: true           # 内部技能才设 false
---
```

英文那几项是"Global English 版"的兜底默认值，所以不能让中文版覆盖 `description`。**Global English 环境里正文也要写成英文**，中文只出现在 `*_zh` 字段和技能的运行输出里。

**2. 必须同时产出 `.skill-metadata.yaml`**（注意开头那个点，和 `SKILL.md` 同级）。用户在技能卡片上点「使用」时，产品读它把推荐 query 预填进输入框；**没有这个文件就退化成一句通用 query，技能的上下文全丢**。做法是每个主要能力写一条中英双语文案，一般 2–5 条：

```yaml
examples:
  - id: extract-text
    title:
      zh: 提取文本内容
      en: Extract Text Content
    description:
      zh: 从 PDF 中提取正文，支持多栏排版
      en: Extract body text from a PDF, including multi-column layouts
    prompt:
      zh: |-
        请从这份 PDF 中提取文本：
        PDF 文件：{{PDF 文件路径}}
      en: |-
        Please extract the text from this PDF:
        PDF file: {{PDF file path}}
```

`{{占位符}}` 只留给用户必须提供的东西（文件路径、输出路径、目标格式、业务参数）。本机 `~/.qwenworkcn/skills/pdf/.skill-metadata.yaml` 是现成的范例。唯一例外是"不需要用户输入"的技能（语气/风格/主题类），才用单条默认 query——判断标准很实在：只要能写出一句"用户指着自己的文件说"的话，就不算例外。

## 跑测试
- **没有独立的可编程 CLI，也没有对外的技能触发测试接口**，走对话内手动模式（见 trigger-optimization.md 的模式 B）
- 官方提到"多智能体模式可并行处理复杂任务"，但能不能给测试用例开并行子任务要在实际环境里确认；不确定就串行自己跑
- 执行能力：桌面端可读写本地文件、支持浏览器自动化（官方注明浏览器自动化**仅客户端支持**）；网页端和钉钉端没有本地文件这一层
- **`scripts/` 是支持的**：本机预装的 `pdf` / `docx` / `xlsx` / `pptx` / `find-skills` / `dingtalk-*` 等 11 个技能都带 `scripts/`，官方规范里也贴了 `python scripts/analyze_form.py` 这种调用。所以重量技能在这一样能脚本化。

## 优化描述
- 用对话内手动模式（模式 B）——你自己就是模型，逐条判触发，严谨度和脚本模式一样
- **要改的不是一个 description，是三个**：`description`、`description_en`、`description_zh` 得同步改，别只改中文那条
- **企业旗舰版 OpenAPI 不能用来做触发测试**：它的 41 个 scope / 103 个接口全是资产管理（技能与专家套件的增删改查、开放策略、上架审核、组织/用户/部门、限额、模型策略、安全管控），**没有"执行任务"的接口**。别看到权限动作里有个 `execute` 就以为能跑 agent
- 拿不到基线对比就如实说明，别编分数

## 交付
- 个人版：在「扩展 > 技能 > 安装技能」上传技能文件夹（`SKILL.md` + `.skill-metadata.yaml` + 辅助文件）；也可以直接放进上面那张表里的目录
- 企业旗舰版：走控制台的技能上架与开放策略（对应 OpenAPI 的 `skill-upload-reviews` / `skill-policies`）
- 要成组分发（多技能 + 数据连接 + 输出标准）时用专家套件 `.zip`，包内需含 `.qwen-plugin/plugin.json` 或 **`.claude-plugin/plugin.json`**——后者说明它能吃 Claude 插件格式，多技能打包可以复用

## 触发竞争（先看一眼再动手）
千问办公**预装了 26 个技能**，其中 `create-skill`、`plugin-creator`、`find-skills`、`qwenwork-guidance` 和本技能功能重叠。尤其 `create-skill`（v1.2.0）就是官方版的"创建技能"引导，它的 description 里写着 "Use when the user wants to create, write, or author a new skill" ——**和本技能抢同一批触发词**。在这个环境里做技能创建类技能时，description 必须比它更具体（写清是哪种技能、什么场景），否则会被它截胡。

## 未验证项（别当成已知事实）
- **环境识别没有可靠信号**：官方没公布可用的环境变量或 CLI，`scripts/platform_detect.py` 目前只能靠 `~/.qwenworkcn/` 目录存在这种弱信号兜底（命中也可能只是"装了千问办公桌面端"）。优先靠上下文（Skill 广场、钉钉内唤起、技能目录）判断。
- **`.skill-metadata.yaml` 之外的字段是否有校验**：上面那份 frontmatter 规范来自本机预装的 `create-skill` 技能，产品端会不会对缺字段报错、报错长什么样，还没实测。
- **企业版是否另有未公开的执行接口**：开发者文档里没列，先按"没有"处理；要用得先跟企业管理员确认。
