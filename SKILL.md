---
name: skill-creator-pro
description: 创建新技能、修改和优化已有技能，并严格评估技能效果。当用户想要从零创建一个技能、编辑或优化现有技能、运行测试用例验证技能、对技能表现做基准对比、或优化技能的触发描述以提高触发准确率时使用。专业增强版，支持豆包工作、腾讯 WorkBuddy、OpenAI Codex、Claude、OpenClaw 五种运行环境，自动识别并适配。
license: Apache-2.0，源自 Anthropic 官方 skill-creator（Copyright 2026 Anthropic, PBC）的中文化改造，完整条款与署名见 LICENSE.txt
compatibility: 需要 Python 3；脚本校验与打包另需 PyYAML 和 requests。主干流程不绑定特定运行时，任何支持 Agent Skills 开放格式的工具均可用；触发率优化另需可编程调用的 agent 运行时，或对话内手动模式。
metadata:
  version: "2.1.0"
---

# 技能创建器（Skill Creator）

一个用于创建新技能并迭代优化的通用指南，适配五种主流 AI 办公环境。本指南以**操作手册**的标准编写——每一步该执行什么命令、什么时机做什么、字段名必须怎么写、哪些坑要避开，都有明确说明。

**核心原则：简洁至上。** 每写一段都问——这个 AI 真的不知道吗？知道的别写，只补充它不知道的。

---

## 第 0 步：自动识别运行环境

开始工作前，先判断你运行在哪个环境里，然后切换对应的模式。**这一步必须在做任何实质性工作之前完成。**

| 环境 | 识别特征 | 测试模式 | 优化模式 |
|------|---------|---------|---------|
| **豆包工作** | 有 OrganizerAgent 子任务能力，工作目录在 `.sessions/` 下，有 `present_files` | 主 Agent 自测 + 子任务并行 | 对话内手动，或调 run_loop.py |
| **腾讯 WorkBuddy** | 有 `workbuddy`/`codebuddy` CLI，或本地 8080 端口 daemon API，frontmatter 带 `agent_created` | CLI 跑测试 + 本地 API | CLI 或通用 API 自动迭代 |
| **OpenAI Codex** | 有 `codex` CLI，用 `AGENTS.md` 配置 | spawn 子进程跑测试 | 调 Codex CLI 自动迭代 |
| **Claude** | 有 `claude` CLI，看到 `available_skills` 系统提示 | spawn 子进程跑测试 | 调 `claude -p` + run_loop.py |
| **OpenClaw** | `claw` CLI，有 ClawHub，模型无关，多消息平台接入 | 通用 API + 子代理并行 | 通用 API 优化循环 |

都不确定就默认通用 API 模式。SKILL.md 已是跨厂商事实标准。

### 环境能力矩阵

| 能力 | 影响哪些步骤 | 不具备时怎么办 |
|---|---|---|
| **子 agent** | 并行跑用例、基线对照、盲测 | 串行自己跑，跳过基线与盲测 |
| **可编程调用的 agent 运行时**（`claude -p` 等） | 触发率优化 | 对话内手动模式，或跳过并如实告诉用户 |
| **浏览器 / 显示** | eval viewer 本地服务 | `--static <输出路径>` 生成独立 HTML |
| **`present_files`** | 打包投递 `.skill` | 保留完整文件夹作为交付物 |

### 默认落地位置

用本 Skill 创建的新技能，落在**当前环境已确认有效**的 Skill 发现路径下（豆包工作是 `.user_skills/`，Claude 是 `.claude/skills/`，Codex 是项目根或 `~/.codex/`，OpenClaw 是 `~/.claw/skills/`，WorkBuddy 是 SkillHub 对应本地目录）。优先从当前已知的 Skill 路径反推，不要图省事退回到工作目录；用户没明确指定就不要乱换位置。

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

**再判断：走轻量流程还是重量流程？** 不是所有技能都需要完整 eval 闭环——skillsmp 上 300 万个技能里大多数就是一个 SKILL.md。
- **轻量技能**（纯风格/语气、单一格式约束、提示词封装，如"针织海报风""去 AI 味"）：没确定性脚本、输出主观，直接写 SKILL.md + examples/ 交付，**跳过 evals/基线/benchmark**，靠用户反馈迭代。
- **重量技能**（工具类、工作流类、有确定性重复操作、输出有客观对错，如 PDF 处理、数据提取、合同审查）：才走完整 eval 闭环（带技能+基线、benchmark、触发率优化）。

别让一个"风格提示词"技能也背上跑 3 个用例 + 基线对比的负担。

**判断完先出方案再动手。** 先判断轻量/重量，然后只列相关项：
- **轻量**（纯风格/提示词）：技能名、description 方向、调用方式、输入/输出格式、不做什么
- **重量**（工具类/工作流）：上面 + 要不要脚本、拆几个 references、依赖什么外部工具、要不要 examples/evals

**边界情况问用户：** 写作类技能有固定格式但没脚本——问一句"这个要不要写脚本？"用户说要就重量，不要就轻量。

用户说"可以"再写——别上来就写 500 行，方向错了全白写。

### 第二步：访谈与调研

主动问边界情况、输入输出格式、示例文件、成功标准、依赖条件。没搞清楚之前别急着写测试提示词。

检查可用的 MCP/工具——有搜索/查相似技能的能力就并行调研（有子代理用子代理），带着上下文来找用户。

**技能要调外部系统（爬虫、钉钉/企微/飞书、数据库、SaaS）时，先看有没有现成 MCP/CLI 可用**——国内成熟的有 MediaCrawler、wecom-cli、dingtalk-cli、百炼/钉钉 MCP 广场，登录态/代理池/鉴权别自己写。Skill 只写决策逻辑，连接部分复用现成的。

### 第三步：写 SKILL.md

**先初始化骨架（推荐）**：从零建新技能时，先跑 `scripts/init_skill.py` 一键生成目录和模板：

```bash
python3 -m scripts.init_skill <skill-name> --path <已确认的 .user_skills 目录>
```

**脚本统一用 `python3 -m scripts.<脚本名>` 调用，工作目录必须是技能创建器根目录**——直接写 `python scripts/xxx.py` 会因包内导入失败报 `ModuleNotFoundError`。它会自动建出 `SKILL.md`（带 TODO 占位符和结构选择建议）以及 `scripts/`、`references/`、`assets/`、`evals/`、`examples/` 五个目录。生成后再按下面的内容填充。如果只是在已有技能上迭代，可以跳过这一步。

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
  - Claude 要加：`allowed-tools`（如果需要限定工具）
  - 其他平台按各自规范加
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

这些字数只是大概参考，内容需要的话可以适当长一点。

**关键原则：**
- SKILL.md 控制在 500 行以内；快到上限了，就把内容拆到下一层级，写清楚指引说"遇到 XX 情况去读 XX 文件"
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

**⚠️ 重要提醒：这一节是一个连续的流程，不要中途停下来。不要使用 `/skill-test` 或任何其他测试技能——就用这里写的流程。**

根据你识别到的环境，选择对应的测试方案。

**跨模型验证（不要漏）：** 同一个技能在不同档位的模型上表现可能天差地别——旗舰模型能跟上的指令，便宜模型可能直接漏掉。官方要求至少在两档模型上各跑一遍 evals。豆包环境就是旗舰版和轻量版各一次；Claude 环境对应 Opus 和 Haiku。如果只跑了一个模型就发布，等于只验证了一半。

### 工作目录结构

把结果放在**当前项目工作目录**下的 `<技能名>-workspace/` 里（不要放技能安装目录旁边——它可能只读，workspace 是临时迭代文件）。按 `iteration-1/`、`iteration-2/` 组织，每个用例一个子目录，用到哪个建哪个。各平台的"当前项目工作目录"：豆包工作是 `.sessions/<会话ID>/agents/<当前agent>/`，Claude Code / Codex 是项目根目录，WorkBuddy 是工作区根目录，OpenClaw 是当前工作目录。

---

### 方案一：有并行子任务能力的环境

适用：豆包工作、Claude Code、WorkBuddy 企业版、Cowork

#### Step 1：同一轮里 spawn 所有 run（带技能 + 基线）

每个测试用例跑两次——一次带技能，一次不带（基线）。**重要：不要先跑带技能的再补基线，一起启动，差不多同时跑完。**

**带技能运行模板：**
```
执行这个任务：
- 技能路径：<技能路径>
- 任务：<测试提示词>
- 输入文件：<有就列，没有就写"无">
- 输出保存到：<workspace>/iteration-<N>/<eval目录名>/with_skill/outputs/
- 需要保存的输出：<用户关心的东西——比如".docx 文件"、"最终 CSV">
```

**基线运行**（同一个提示词，但基线分情况）：
- **创建新技能**：完全不带技能。同样的提示词，不指定技能路径，保存到 `<eval目录名>/without_skill/outputs/`
- **优化已有技能**：用旧版本做基线。编辑前先把技能快照一份（`cp -r <技能路径> <workspace>/skill-snapshot/`），然后让基线任务指向这个快照，保存到 `<eval目录名>/old_skill/outputs/`

每个测试用例写一个 `eval_metadata.json`（断言可以先空着）。**每个测试用例起个描述性的名字——别就叫"eval-0"。目录名也用这个描述性名字。**

```json
{
  "eval_id": 0,
  "eval_name": "描述性-名字-这里放测试什么",
  "prompt": "用户的任务提示词",
  "expectations": []
}
```

**如果这一轮用了新的或修改过的测试提示词，就要为每个新的 eval 目录创建这些文件——不要假设它们会自动从之前的迭代带过来。**

#### Step 2：跑的同时，起草断言

别干等着——利用这段时间设计量化评估指标，并向用户解释。如果 `evals/evals.json` 里已经有断言了，就审查一遍，解释它们在测什么。

好的断言是可以客观验证的，名字要有描述性——一眼看过去就知道每条在测什么。主观类的技能（写作风格、设计质量）更适合定性评估，别硬塞断言。

起草完断言后，更新 `eval_metadata.json` 文件和 `evals/evals.json`。同时向用户解释一下他会在评审页面里看到什么——包括定性输出和定量基准。

#### Step 3：任务完成时，立即捕获 timing 数据

每个子代理任务完成时，你会收到一个通知，里面包含 `total_tokens` 和 `duration_ms`。**这是唯一能拿到这些数据的机会——它通过任务通知传入，不会持久化在别处。收到通知就立即处理，不要批量处理。**

把数据存到对应运行目录下的 `timing.json`：

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3
}
```

#### Step 4：打分、聚合、分析、生成评审页面

全部跑完之后，按顺序做这四件事：

**4.1 逐次打分**

spawn 一个 grader 子代理（或者自己内联打分），让它读 `agents/grader.md`，然后对照每条断言评估输出。结果存到每个运行目录下的 `grading.json`。

**⚠️ 字段名必须精确：** `grading.json` 里的 `expectations` 数组必须用 `text`、`passed`、`evidence` 这三个字段名——评审页面依赖这些精确的字段名。不要用 `name`/`met`/`details` 或其他变体。

能程序化检查的断言，就写脚本跑——脚本更快、更可靠，还能跨迭代复用。

**4.2 聚合成基准报告**

从技能创建器目录运行聚合脚本：
```bash
python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <技能名>
```

会生成 `benchmark.json` 和 `benchmark.md`，包含通过率、耗时、token 用量的均值 ± 标准差，以及两组配置的差值。

**排序要求：** 把每个 `with_skill` 版本放在它的基线版本前面。

如果你要手动生成 `benchmark.json`，参考 `references/schemas.md` 里的精确 schema（评审页面依赖这个格式）。

**4.3 做一轮分析解读**

读基准数据，发现汇总统计可能掩盖的模式。看 `agents/analyzer.md` 里的"分析基准结果"部分，重点关注：
- 不管有没有技能都通过的断言（没有区分度）
- 方差很大的测试用例（可能不稳定）
- 耗时 / token 的取舍

**4.4 生成并启动评审页面**

用 `eval-viewer/generate_review.py` 生成评审页面。**不要自己写自定义 HTML。**

> **⚠️ 极其重要：跑完测试后，必须先生成 eval viewer 给用户看，然后你自己再去评估输出、做修改。**
>
> 不要自己看完输出就直接改技能——先把结果交给用户评审。用户的定性反馈比你自己的判断更重要。
>
> 用 `generate_review.py`（不要自己写自定义 HTML）。

```bash
nohup python <技能创建器路径>/eval-viewer/generate_review.py \
  <workspace>/iteration-N \
  --skill-name "我的技能" \
  --benchmark <workspace>/iteration-N/benchmark.json \
  > /dev/null 2>&1 &
VIEWER_PID=$!
```

第 2 轮及以后，再加 `--previous-workspace <workspace>/iteration-<N-1>`。

**无显示器 / 无头环境（如 Cowork、远程服务器）：** 用 `--static <输出路径>` 生成一个独立的 HTML 文件，而不是启动服务器。

告诉用户："我把结果打开了，Outputs 标签页逐个看测试用例并留反馈，Benchmark 标签页看通过率/耗时/token 对比，看完点 Submit All Reviews 就行。"空反馈 = 没问题。

#### Step 5：读用户反馈，关闭评审页面

用户说看完了之后，读下载下来的 `feedback.json`（结构是 `reviews[]`，每条带 `run_id`、`feedback`、`timestamp`）。空 feedback = 用户觉得没问题，改进重点放在有具体意见的用例上。用完关掉服务器：`kill $VIEWER_PID 2>/dev/null`。

---

### 方案二：没有并行执行能力的环境

适用：WorkBuddy 轻量版、OpenClaw 单用户版、其他无并行能力的环境、Claude.ai

那就简化流程：

- **跑测试**：每个测试用例自己跑一遍（读了技能 SKILL.md 之后，按指令完成测试提示词）。一次跑一个。不如独立子任务严谨（你自己写技能自己跑，自带完整上下文），但作为初步验证够用了——反正有人工评审环节兜底。
- **跳过基线对比**——直接用技能完成任务就行。
- **评审结果**：没法开浏览器的话，直接在对话里展示。每个测试用例把提示词和输出都展示出来。如果输出是文件，存到文件系统里告诉用户路径，让他自己去看。直接在对话里问："这个效果怎么样？要改什么吗？"
- **跳过量化基准**——没有基线对比就没意义了，重点放在用户的定性反馈上。
- **迭代循环**：还是一样——改技能 → 重跑测试 → 要反馈——只是中间没有浏览器评审环节。

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
- 观测不到"技能被激活"的信号时，只能退化为哨兵探测，且此时测的是"执行了"而非"触发了"，语义不同，必须向用户讲明。
- 全都做不到就**跳过并如实说没跑**，不要编造分数。

---

## 进阶：技能集合（可选）

要做一组相关技能而不是单个技能时（参考 superpowers、brand-build 59-skill library 等），读 [references/skill-collections.md](references/skill-collections.md)——里面有 meta-skill 路由结构和国内"视觉风格包"形态的说明。只是做单个技能就跳过。

---

## 打包和交付

根据你所在的环境选择交付方式：

### 有 present_files 的环境（如豆包工作）

用 `present_files` 工具直接交付技能文件夹或 `.skill` 文件：

```bash
python -m scripts.package_skill <技能文件夹路径>
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
   python -m scripts.quick_validate <技能文件夹路径>          # 语法层
   python -m scripts.quick_validate <技能文件夹路径> --deep   # 内容层：行数/触发词/examples/evals/嵌套引用
   ```
   deep 模式报的 warning 不阻断，但每条都要看一眼再决定要不要修。

**更新已有技能时注意：**
- **保留原始名称**——目录名和 frontmatter 里的 `name` 不要改（`research-helper.skill`，不要叫 `research-helper-v2.skill`）。
- **先复制到可写位置再编辑**——已安装路径可能只读，改完打包再装回去。
- **WorkBuddy 专属**：必须保留 `agent_created: true` 字段。

---

## 参考文件

按需读取，不要全背：
- `agents/grader.md` — 对照断言打分；`agents/comparator.md` — 盲测 A/B；`agents/analyzer.md` — 为什么一版更好
- `references/schemas.md` — evals/grading/benchmark 的 JSON 结构
- `references/trigger-optimization.md` — description 触发率优化方法与环境前提
- `references/workflows.md` / `references/output-patterns.md` — 流程组织与模板写法
- `references/platforms/` — 五个运行环境的跑测/优化/交付细节
- `references/skill-collections.md` — 多个相关技能怎么打包成集合
- `references/chinese-context.md` — 中文写作各文体区别 + 国内合规底线

---

## 核心循环（别漏）

识别环境 → 判断轻量/重量 → 搞清楚技能做什么 → 写初稿 → 跑测试（重量技能才带基线同轮启动）→ **先把 eval viewer 交给用户看，再自己动手改** → 迭代到满意 → 优化 description 触发率 → 交付。有 TodoList 就记进去。

本 Skill 基于 Anthropic 官方 `skill-creator` 中文化改造，适配豆包工作 / WorkBuddy / Codex / Claude / OpenClaw。祝顺利！
