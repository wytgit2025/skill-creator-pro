---
name: skill-creator-pro
description: "创建新技能、修改和优化已有技能，并严格评估技能效果。当用户说'帮我做个技能''把这个流程固化下来''我的技能不触发''帮我测测这个技能好不好用''优化一下触发描述'，或想要从零创建技能、编辑现有技能、跑测试用例验证、做带技能vs不带技能的基准对比时使用。适配 Claude Code、OpenAI Codex、腾讯 WorkBuddy、豆包工作、千问办公、OpenClaw 等环境。"
license: Apache-2.0
compatibility: 需要 Python 3；脚本校验与打包另需 PyYAML 和 requests。主干流程不绑定特定运行时，任何支持 Agent Skills 开放格式的工具均可用；触发率优化另需可编程调用的 agent 运行时，或对话内手动模式。
metadata:
  version: "2.2.0"
---

# 技能创建器（Skill Creator）

开始工作时先告诉用户："我在用 Skill Creator Pro 处理这个任务。"

一个用于创建新技能并迭代优化的通用指南，适配六种主流 AI 办公环境。本指南以**操作手册**的标准编写——每一步该执行什么命令、什么时机做什么、字段名必须怎么写、哪些坑要避开，都有明确说明。

**核心原则：简洁至上。** 每写一段都问——这个 AI 真的不知道吗？知道的别写，只补充它不知道的。

---

## 开始前：识别运行环境

开始工作前，先判断你运行在哪个环境里，然后切换对应的模式。**这一步必须在做任何实质性工作之前完成。**

| 环境 | 识别特征 | 测试模式 | 优化模式 |
|------|---------|---------|---------|
| **豆包工作** | 有 OrganizerAgent 子任务能力，工作目录在 `.sessions/` 下，有 `present_files` | 主 Agent 自测 + 子任务并行 | 对话内手动，或调 run_loop.py |
| **腾讯 WorkBuddy** | 有 CodeBuddy / WorkBuddy 宿主会话标记（`CODEBUDDY_*`），或 `workbuddy`/`codebuddy` CLI；frontmatter 带 `agent_created` | CLI 跑测试 | CLI 或通用 API 自动迭代 |
| **千问办公** | 有 `~/.qwenworkcn/skills/` 目录，钉钉内可唤起，有 Skill 广场 / 专家套件 | 主 Agent 自测（多智能体并行未验证） | 对话内手动 |
| **OpenAI Codex** | 有 `codex` CLI，技能在 `.agents/skills/`，`AGENTS.md` 管指令 | 调 `codex exec` 跑测试 | 调 Codex CLI 自动迭代 |
| **Claude** | 有 `claude` CLI，看到 `available_skills` 系统提示 | spawn 子进程跑测试 | 调 `claude -p` + run_loop.py |
| **OpenClaw** | `openclaw` CLI，有 ClawHub，模型无关，多消息平台接入 | 通用 API + 子代理并行 | 通用 API 优化循环 |

一台机器装了多个平台的 CLI 时，`which` 只能说明「装了」、分不清你正在哪个里面跑——**自动检测分不清就直接问用户**，并用 `SKILL_CREATOR_PLATFORM=<平台名>` 显式指定（它压过所有自动信号，填错会警告并退回自动检测）。都不确定就默认通用 API 模式。SKILL.md 已是跨厂商事实标准。

### 环境能力矩阵

| 能力 | 影响哪些步骤 | 不具备时怎么办 |
|---|---|---|
| **子 agent** | 并行跑用例、基线对照、盲测 | 串行自己跑，跳过基线与盲测 |
| **可编程调用的 agent 运行时**（`claude -p` 等） | 触发率优化 | 对话内手动模式，或跳过并如实告诉用户 |
| **浏览器 / 显示** | eval viewer 本地服务 | `--static <输出路径>` 生成独立 HTML |
| **`present_files`** | 打包投递 `.skill` | 保留完整文件夹作为交付物 |

### 默认落地位置

用本 Skill 创建的新技能，落在**当前环境已确认有效**的 Skill 发现路径下（豆包工作是 `.user_skills/`，Claude 是 `.claude/skills/`，千问办公是 `~/.qwenworkcn/skills/`，Codex 是 `.agents/skills/` 或 `~/.agents/skills/`，OpenClaw 是工作区 `skills/` 或 `~/.agents/skills/`，WorkBuddy 是 SkillHub 对应本地目录）。优先从当前已知的 Skill 路径反推，不要图省事退回到工作目录；用户没明确指定就不要乱换位置。

### 网页采集类技能默认走浏览器

如果要做的技能是"从网站/Web 应用收集信息"（搜索、刷信息流、读评论、抓小红书/论坛/SaaS 页面内容），**默认用浏览器操作**，不要写成 Python 爬虫题。只有用户明确要"爬虫/API 版"、或浏览器确实不够用时才写脚本；脚本只用来做采集后的确定性后处理（去重、分类、出报告）。

---

## 整体流程（通用）

> 一条底线：**没有基线对比的"我改好了"不算证据。** 要么给出可比较的数据，要么明确说这是主观判断。

高层流程：明确技能做什么 → 写初稿 → 设计测试提示词跑一遍 → 定性+定量评估 → 按反馈重写 → 重复到满意 → 扩大测试集。先判断用户在哪个阶段，直接切入；已有初稿就跳测试/迭代。用户明确说"随便写写"就简化，否则走完整流程。最后（顺序可灵活）再优化 description 触发率。

## 与用户沟通的方式

用户编程背景差异大。"评估/基准测试"能用；"JSON/断言"这种技术词拿不准就加一句解释。

## 平台专属适配

上面的环境识别表和能力矩阵决定走哪条工作模式。具体平台怎么跑测试/优化/交付，按需读：

| 环境 | 详细指引 |
|---|---|
| 豆包工作 | [doubao-work.md](references/platforms/doubao-work.md) |
| 腾讯 WorkBuddy / QClaw（含企业版 manifest.yaml） | [workbuddy.md](references/platforms/workbuddy.md) |
| 千问办公（QwenWork） | [qwenwork.md](references/platforms/qwenwork.md) |
| OpenAI Codex | [codex.md](references/platforms/codex.md) |
| Claude Code / Cowork / Claude.ai | [claude.md](references/platforms/claude.md) |
| OpenClaw | [openclaw.md](references/platforms/openclaw.md) |

**能降级就降级，但"人工看结果"这一步在任何环境下都不能省。**

## 创建技能

### 第一步：捕获意图

先搞清楚用户到底想要什么。如果当前对话里已经有一个用户想固化成技能的工作流（比如他说"把刚才这套流程做成个技能"），那先从对话历史里提取信息——用到了什么工具、步骤顺序、用户做了哪些纠正、观察到的输入输出格式。缺的信息再问用户，确认后再往下走。

需要明确的核心问题：

1. 这个技能要让 AI 能做什么事？
2. 什么时候应该触发这个技能？（用户会说什么话、在什么场景下）
3. 期望的输出格式是什么？
4. 要不要设计测试用例来验证？
   - 输出有客观判断标准的技能（文件转换、数据提取、代码生成、固定工作流步骤）适合做测试用例
   - 输出偏主观的技能（写作风格、艺术设计）通常不太需要
   - 根据技能类型给建议，但最终让用户决定

**动手前先判断：该不该拆？** 官方原则是"多个聚焦的小技能组合起来，胜过一个大而全的技能"。如果你写出来的 description 需要用"和/以及"连接两个不相关的动作（比如"审合同**和**写周报"、"做 PPT**以及**查股价"），那就是两个技能，不要硬塞成一个。判断标准：用户触发这个技能时，是不是 90% 的情况下只用到其中一块？如果是，拆。

**再判断：要做哪些能力模块？** 不给技能贴"轻量/重量"标签——那是二元分类，表达不了现实里的混合技能。改成独立判断 `scripts` / `evals` / 平台字段三个模块，**按结构属性判断，不按领域猜**：判断表、四种组合、方案清单见 `references/capability-modules.md`。

**判断就地做，不用声明。** 要不要这些模块，直接体现在「建不建对应目录」上——有 `scripts/` 就是有脚本，有 `evals/` 就是有测试。**不要往 frontmatter 塞类型字段**（校验器看目录就够了，声明只会引入不一致）。

**判断完先出方案再动手。** 先定模块，再列相关项：技能名、description 方向、调用方式、输入/输出格式、不做什么；要 `scripts` 就写脚本怎么切怎么调，要 `evals` 就写几个用例、断言怎么设计，要发多平台就补哪些平台字段。**模块可以迭代中增减**，别一次判死。

用户说"可以"再写——别上来就写 500 行，方向错了全白写。

### 第二步：访谈与调研

主动问边界情况、输入输出格式、示例文件、成功标准、依赖条件。没搞清楚之前别急着写测试提示词。

检查可用的 MCP/工具——有搜索/查相似技能的能力就并行调研（有子代理用子代理），带着上下文来找用户。

**技能要调外部系统（爬虫、钉钉/企微/飞书、数据库、SaaS）时，先看有没有现成 MCP/CLI 可用**——国内成熟的有 MediaCrawler、wecom-cli、dingtalk-cli、百炼/钉钉 MCP 广场，登录态/代理池/鉴权别自己写。Skill 只写决策逻辑，连接部分复用现成的。

### 第三步：写 SKILL.md

**先初始化骨架（推荐）**：从零建新技能时，先跑 `scripts/init_skill.py` 一键生成目录和模板：

```bash
python3 -m scripts.init_skill <skill-name> --path <已确认的 .user_skills 目录> --capabilities scripts,evals
```

**脚本统一用 `python3 -m scripts.<脚本名>` 调用，工作目录必须是技能创建器根目录**——直接写 `python scripts/xxx.py` 会因包内导入失败报 `ModuleNotFoundError`。`--capabilities` **必填**（脚手架不预设，避免替你做完判断），决定生成哪些目录：`examples/` 恒建，`scripts/` 只在能力位含 `scripts` 时建，`evals/` 只在含 `evals` 时建；**纯提示词技能传 `--capabilities ""`**（只建 `SKILL.md` + `examples/`）。生成后再按下面的内容填充。如果只是在已有技能上迭代，可以跳过这一步。

根据用户访谈的结果，填充以下内容：

- **name**：技能标识符（kebab-case，小写字母 + 数字 + 连字符）。官方推荐**动名词形式**（`processing-pdfs`、`analyzing-spreadsheets`、`testing-code`），一眼能看出这个技能在做什么动作；避免 `helper`、`utils`、`tools` 这种模糊名。
- **description**：什么时候触发、做什么。这是最主要的触发机制——既要写清楚技能做什么，也要写清楚具体在什么场景下用。所有"什么时候用"的信息都放这里，不要放到正文里。
  - **必须用引号包起来**（`description: "..."`）——否则里面有英文冒号会导致 YAML 解析失败。
  - 大模型通常"触发不足"——description 可以写得稍微"主动"一点。
  - 必须用**第三人称**（"Extracts text from PDFs..."），不要写"我可以帮你..."。
  - 反面例子："如何快速搭建展示内部数据的简单仪表盘。"
  - 正面例子："如何快速搭建展示内部数据的简单仪表盘。当用户提到仪表盘、数据可视化、内部指标，或者想要展示任何类型的公司数据时，都要使用这个技能——即使用户没有明确说'仪表盘'三个字。"
  - **带数据资产的技能，把资产规模量化写进 description**——既是触发信号也是卖点。高星技能 `ui-ux-pro-max` 就写："79 styles, 192 palettes, 74 font pairings..."。打包了样式库/模板库就列出来。
  - **列具体文件类型和用户说法**——官方 xlsx 技能的 description 列了 `.xlsx, .xlsm, .csv, .tsv` 和用户会说的 `"pivot table"`、`"budget"`、`"formulas"`。别只写"处理表格"，把扩展名和典型说法列上。
  - **强工作流技能可以用"前置条件"式触发**——superpowers 的 brainstorming 开头就是 "You MUST use this before any creative work"。适合那种"必须先做 X 才能做 Y"的流程技能，但不要滥用，否则会变成到处误触发。
- **compatibility**：需要的工具、依赖、支持的文件格式、行数/大小上限（可选，但工具类技能建议写）。比如"需要 Python 3 + openpyxl，支持 .xlsx/.xls，上限 10 万行"。
- **平台专属字段**（根据目标平台加）：
  - WorkBuddy 要加：`version`、`category`、`platforms`、`agent_created: true`
  - 千问办公要加：`name_en`/`name_zh`、`description_en`/`description_zh`、`argument-hint`(-en/-zh)、`user-invocable`，并**必须同时产出 `.skill-metadata.yaml`**，缺了 UI 只会给用户一句通用 query
  - Claude 要加：`allowed-tools`（如果需要限定工具）；其他平台按各自规范加
- **正文**：技能的具体指令和流程

### 技能写作指南

#### 技能的基本结构

```
技能名/
├── SKILL.md（必需）
│   ├── YAML 前置元数据（name、description 必需）
│   └── Markdown 正文指令
├── scripts/    - 可执行代码，用于确定性的、重复性的任务
├── references/ - 按需加载的参考文档
├── assets/     - 输出时用到的文件（模板、图标、字体等）
├── evals/      - 测试用例（evals.json，至少 3 个）
└── examples/   - 具体的 input/output 对（不是抽象描述）
```

#### 确定性操作必须脚本化（事前硬门槛）

写 SKILL.md **之前**，先列一张清单：这个技能里哪些动作是每次都要重复做、输入输出确定、不需要模型临场判断的？

- 文件格式转换、表格解析、PDF 填表、批量重命名、数据清洗、调固定 API 拿结构化结果——**这些必须写成 `scripts/` 下的脚本**，SKILL.md 只负责告诉模型"遇到 X 就跑 scripts/xxx.py"。
- 顶级技能（pdf/docx/xlsx）真正省 token、保稳定的原因就在这：模型不重复写代码，只做决策。
- 反过来，如果某个动作每次都需要模型根据上下文自由发挥（比如判断文风、写文案、做产品判断），那就不要脚本化，写进正文。

这条是**事前要求**，不是事后优化——别等测试跑出来发现三个用例各自写了一份差不多的 `create_docx.py` 才想起来打包。

**脚本写好后，正文里贴一个调用样例**——官方 xlsx 技能就在 CAPABILITIES 段贴了 `createSpreadsheet({...})` 的完整调用。模型看一眼就知道参数怎么传，不用去翻脚本源码。

**领域知识要拆到多细？** 别写 5 条概括就交差。高星技能：①**枚举所有情况**——不是"处理 CSV"，是"CSV 有 UTF-8/GBK/BOM 三种编码、逗号/分号/Tab 三种分隔符，分别怎么处理"；不是"写 PR"，是"PR 有 bugfix/feature/docs/refactor/chore 五种模板"。②每种情况带 before/after，放 `references/patterns.md`，正文只放最常用的 10 条。③**机械判断写脚本**——编码检测、类型判断、正则匹配写进 `scripts/` 自动跑，模型只做需要上下文判断的部分。

#### 渐进式加载原则

技能采用三层加载机制：

1. **元数据层**（name + description）——始终在上下文中（约 100 词）
2. **SKILL.md 正文**——技能触发时才加载（理想 < 500 行）
3. **附属资源**——需要时才加载（无限制，脚本甚至可以不用加载就直接执行）

**关键原则：**
- SKILL.md 控制在 500 行以内（这些字数只是大概参考，内容需要可以适当长一点）；快到上限了，就把内容拆到下一层级，写清楚指引说"遇到 XX 情况去读 XX 文件"
- 在 SKILL.md 里明确标注什么时候该去读哪个参考文件
- 大的参考文件（>300 行）最好带个目录

**多领域组织方式**：当一个技能支持多个领域 / 框架时，按变体拆分：

```
cloud-deploy/
├── SKILL.md（主流程 + 选择指引）
└── references/
    ├── aws.md
    ├── gcp.md
    └── azure.md
```

模型只会读取相关的那个参考文件，不用全加载。

#### 无意外原则

技能里不能包含恶意代码、漏洞利用，或者任何可能危及系统安全的内容。技能的内容在意图上不应该让用户感到意外——不要做误导性的技能，也不要做用来做未授权访问、数据窃取或其他恶意行为的技能。角色扮演类的技能是可以的。

**面向中文用户的技能，**写之前看一眼 [references/chinese-context.md](references/chinese-context.md)——里面有中文写作各文体的区别（公文/周报/小红书/邮件）和国内合规底线（数据不出境、个保法、企业敏感数据）。

#### 写作模式

指令尽量用祈使句。

**定义输出格式**：要固定输出时用 Markdown 模板写死；要展示输入输出关系时用 input→output 对（如 `输入：加了JWT认证 → 输出：feat(auth): 实现JWT认证`）。

### 写作风格

尽量向模型解释"为什么要这么做"，而不是干巴巴地堆 MUST / MUST NOT。现在的大模型理解力都很强，有良好的意图理解能力，给它一个好的框架，它能超出死记硬背指令的水平。**别把每步都规定死——它知道怎么写邮件、怎么调 API，你只需要告诉它什么不能写。**

先写个初稿，然后隔一会儿用新的眼光看一遍，再改进。写完过一遍 [references/authoring-checklist.md](references/authoring-checklist.md)——No Placeholders 黑名单、触发后宣布在用技能、技能间显式引用、作者 self-review 四步。

#### 写作时可参考的模式文档

写复杂流程或输出格式时，按需查阅本目录下的参考文档，不要把这些模式全背下来：

- `references/workflows.md` —— 顺序流程、条件分支怎么组织成清晰的步骤
- `references/output-patterns.md` —— 严格模板 vs 灵活模板、input/output 对示例怎么写

### 测试用例

写完技能初稿后，想 2-3 个真实用户会说的测试提示词。给用户看看："这几个测试用例你觉得合适吗？要不要再加几个？"然后跑起来。

测试用例存到 `evals/evals.json`。**先别写断言——只写提示词就行。断言等跑测试的时候再写。**

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "用户的任务提示词",
      "expected_output": "期望结果的描述",
      "files": []
    }
  ]
}
```

完整 schema 见 `references/schemas.md`。断言字段名统一用 `expectations`（跑测试时再补，别用 `assertions`）。

---

## 运行和评估测试用例

完整的测试执行流程（环境判断、并行 spawn、基线对比、打分聚合、评审页面生成、用户反馈读取）见 [references/testing-workflow.md](references/testing-workflow.md)。按需读取，不要全背。

**两条红线（任何环境都不能违反）：**

1. **跑完测试后必须先把评审结果交给用户看，再自己动手改技能。** 用户的定性反馈比你自己的判断更重要。
2. **没有基线对比的"我改好了"不算证据。** 要么给出可比较的数据，要么明确说这是主观判断。

**跨模型验证：** 至少在两档模型上各跑一遍（旗舰版 + 轻量版）。只跑一个模型就发布，等于只验证了一半。

---

## 改进技能

这是整个循环的核心。你跑完了测试，用户也评完了，现在要根据反馈把技能改得更好。

### 改进的思路

1. **从反馈中提炼普遍性。** 目标是做通用技能，不是只适配这几个例子。不要过拟合、抠细节，也不要堆一堆压抑的 MUST；遇到顽固问题换个角度、换个比喻试试。
2. **保持精简。** 看完整执行过程（transcripts）而不只是最终输出——发现技能让模型浪费时间做没用的事，就删掉那部分。
3. **解释为什么。** 把每条指令背后的"为什么"讲清楚。如果你发现自己在写全大写的 ALWAYS/NEVER 或特别僵硬的结构，那是危险信号——换成讲道理的说法。
4. **注意跨用例的重复劳动。** 多个用例都写了差不多的辅助脚本，就打包进 `scripts/`（事前判断见前面"确定性操作必须脚本化"）。

可以先写个修改稿，过一会儿用新眼光再看一遍。

### 迭代循环

改完技能后：把改进应用上 → 所有用例重跑到新的 `iteration-<N+1>/`（新技能基线永远是 `without_skill`，优化已有技能自己判断用初始版还是上一版做基线）→ 评审页面加 `--previous-workspace` 指向上版 → 等用户评审 → 读新反馈再改。直到用户满意、反馈全空、或再改也没实质进步。

---

## 进阶：盲测对比

如果需要更严格地比较两个版本的技能（比如用户问"新版本真的更好吗？"），有一套盲测对比系统。读 `agents/comparator.md` 和 `agents/analyzer.md` 了解细节。

**基本思路：** 把两个版本的输出给一个独立的评判者，不告诉他哪个是哪个，让他判断质量。然后分析为什么赢的那个赢了。

这是可选功能，需要并行任务能力（子代理），大多数用户用不上。人工评审通常就够了。

---

## 描述优化

SKILL.md 前置元数据里的 `description` 字段，是决定模型会不会触发技能的最主要因素。创建或改进完技能之后，**主动提出优化描述**，提高触发准确率。

**完整方法与执行器说明见 [references/trigger-optimization.md](references/trigger-optimization.md)。** 动手前先读它的"环境前提"一节，要点是：

- **方法**（造 20 条 should-trigger / should-not-trigger 的写实 query → 和用户过一遍 → 切 60/40 → 每条跑 3 次算触发率 → 基于失败项改进 → 按测试集分数选最优）不依赖任何特定运行时。
- **执行器**强依赖运行时。有 CLI 的环境用脚本自动模式，没有 CLI 的环境（如豆包工作）用对话内手动模式——严谨度完全一样。
- 观测不到"技能被激活"的信号只能退化为哨兵探测，此时测的是"执行了"而非"触发了"，必须向用户讲明；全都做不到就**跳过并如实说没跑**，不要编造分数。
- **脚本自动模式会在用户机器上起嵌套子进程**（子进程提示词里含技能 description）。默认不加自动确认 `-y`、不剔 `CLAUDECODE`、嵌套进程的工作目录不放用户家目录、临时文件收工即删；要开这两个开关必须先拿到用户同意。边界明细见 trigger-optimization.md 的边界表。

---

## 进阶：技能集合（可选）

要做一组相关技能而不是单个技能时（参考 superpowers、brand-build 59-skill library 等），读 [references/skill-collections.md](references/skill-collections.md)——里面有 meta-skill 路由结构和国内"视觉风格包"形态的说明。只是做单个技能就跳过。

---

## 打包和交付

根据你所在的环境选择交付方式：

### 有 present_files 的环境（如豆包工作）

用 `present_files` 工具直接交付技能文件夹或 `.skill` 文件：

```bash
python3 -m scripts.package_skill <技能文件夹路径>
```

打包完，把生成的 `.skill` 文件路径告诉用户，方便他安装。

### 没有 present_files 的环境

以完整文件夹作为交付物：保持目录结构完整、可被直接加载，**不要**压成 zip 或 `.skill` 文件。

### 国内企业内部分发

国内 B 端常发到企业内部技能库而非公开市场。WorkBuddy 企业版要带 `manifest.yaml`、脚本过沙箱扫描；含敏感操作的技能按最小权限写。详见 [workbuddy.md](references/platforms/workbuddy.md)。

### 交付前自查（两种交付方式都要做）

交付前按这个清单自查一遍：

1. 目录里有必需的 `SKILL.md`，`scripts/`、`references/`、`assets/`、`evals/`、`examples/` 按需就位。
2. 占位文件、没用上的示例资源、`__pycache__/` 和临时产物都已删除。
3. 需要测试的脚本都跑过了，或者说明了为什么没跑。
4. **安全审查**（community skill 像开源代码一样，别人会直接跑）：scripts 里有没有读 `.env`/密钥文件、有没有往外发数据、有没有硬编码凭据或 token、有没有要求 `chmod 777` 或 sudo。有就改成从环境变量读，并在 compatibility 里写清楚需要什么权限。
5. 跑两遍校验——先语法，再内容：

   ```bash
   python3 -m scripts.quick_validate <技能文件夹路径>          # 语法层：frontmatter + scripts/*.py 语法
   python3 -m scripts.quick_validate <技能文件夹路径> --deep   # 内容层：行数/触发词/examples/evals/嵌套引用
   ```
   deep 模式报的 warning 不阻断，但每条都要看一眼再决定要不要修。

**更新已有技能时注意：**
- **保留原始名称**——目录名和 frontmatter 里的 `name` 不要改（`research-helper.skill`，不要叫 `research-helper-v2.skill`）。
- **先复制到可写位置再编辑**——已安装路径可能只读，改完打包再装回去。
- **WorkBuddy 专属**：必须保留 `agent_created: true` 字段。

---

## 参考文件

按需读取，不要全背：
- `references/testing-workflow.md` — 完整测试执行流程（并行 spawn、基线对比、打分聚合、评审页面）
- `agents/grader.md` — 对照断言打分；`agents/comparator.md` — 盲测 A/B；`agents/analyzer.md` — 为什么一版更好；`agents/flow-auditor.md` — 审这一轮流程有没有被跳步
- `references/schemas.md` — evals/grading/benchmark 的 JSON 结构
- `references/trigger-optimization.md` — description 触发率优化方法与环境前提
- `references/workflows.md` / `references/output-patterns.md` — 流程组织与模板写法
- `references/platforms/` — 六个运行环境的跑测/优化/交付细节
- `references/skill-collections.md` — 多个相关技能怎么打包成集合
- `references/chinese-context.md` — 中文写作各文体区别 + 国内合规底线

---

## 核心循环（别漏）

识别环境 → 判断能力模块（scripts / evals / 平台字段）→ 搞清楚技能做什么 → 写初稿 → 跑测试（有并行子任务能力时，基线与带技能同轮启动）→ **先把 eval viewer 交给用户看，再自己动手改** → 迭代到满意 → 优化 description 触发率 → 交付。有 TodoList 就记进去。

本 Skill 基于 Anthropic 官方 `skill-creator` 中文化改造（Apache-2.0，完整条款与署名见 LICENSE.txt），适配豆包工作 / WorkBuddy / 千问办公 / Codex / Claude / OpenClaw。祝顺利！
