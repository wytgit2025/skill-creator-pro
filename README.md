# Skill Creator Pro

把重复工作固化成可复用的 Agent 技能。覆盖从需求捕获、编写、测试、评审、触发率优化到上线后经验沉淀的完整流程，同时适配六个主流 Agent 平台。

基于 [Anthropic 官方 skill-creator](https://github.com/anthropics/skills) 中文化与工程化改造，Apache-2.0。

- **版本**：3.1.0
- **平台**：Claude Code / 豆包工作 / 腾讯 WorkBuddy / 千问办公 / OpenAI Codex / OpenClaw
- **依赖**：Python 3；`PyYAML` 与 `requests`（仅脚本校验、打包、触发率自动优化时需要）

---

## 它做什么

- **造技能**：访谈需求 → 建骨架 → 写 `SKILL.md` → 写测试用例 → 跑带技能 vs 不带技能基线对比 → 根据反馈迭代 → 打包。
- **优化触发描述**：自动构造正/反例查询集，按测试集得分迭代 `description`，防止过拟合。
- **上线后留痕与巡检**：每次调用写入 `runtime/trace.jsonl`；巡检聚合失败、变慢、被批评三类信号；跨多次请求的普遍问题才提修改建议。
- **两层经验沉淀**：业务层把下游技能的反复失败归纳成 `patterns/*.md`（问题+根因+解法，不回滚）；Meta 层把造技能本身踩的坑沉淀到 `runtime/build-patterns/`，下次开新任务前先读。
- **人在环**：所有自动环节只到"出信号 / 提建议"，改 `SKILL.md`、改描述、部署新版本都需要人工确认，回归不退化才放行。

---

## 安装

把整个目录放进你的技能发现路径即可：

| 平台 | 路径 |
|---|---|
| Claude Code | `.claude/skills/` |
| 豆包工作 | `.user_skills/` |
| 腾讯 WorkBuddy | SkillHub 对应目录 |
| 千问办公 | `~/.qwenworkcn/skills/` |
| OpenAI Codex | `.agents/skills/` 或 `~/.agents/skills/` |
| OpenClaw | 工作区 `skills/` 或 `~/.agents/skills/` |

需要脚本能力时安装依赖：

```bash
pip install -r requirements.txt
```

---

## 快速开始

在本技能根目录下执行脚本（统一用 `python3 -m scripts.<name>`，不要直接 `python scripts/xxx.py`）。

### 1. 建一个新技能骨架

```bash
python3 -m scripts.init_skill <skill-name> \
  --path <你的技能目录> \
  --capabilities scripts,evals,runtime
```

`--capabilities` 可选值，逗号分隔：

| 值 | 生成什么 |
|---|---|
| `scripts` | `scripts/` 目录 + 示例脚本 |
| `evals` | `evals/evals.json`（3 条模板用例） |
| `runtime` | 复制 `runtime_log.py`、`scan_signals.py` 进 `scripts/`，并在 `SKILL.md` 注入留痕小节（隐含 `scripts`） |
| `""`（空字符串） | 只建 `SKILL.md` + `examples/`，纯提示词技能 |

判断要哪些能力位，见 `references/capability-modules.md`。

### 2. 写内容

填充 `SKILL.md`：frontmatter 的 `name`（kebab-case）和 `description`（第三人称、写清做什么+什么时候触发）；正文按"做什么 → 怎么做 → 不要做什么"组织。写作规范见 `SKILL.md` 内"技能写作指南"与 `references/authoring-checklist.md`。

`examples/example-pair.md` 写真实的 input/output 对，不要留 TODO。

### 3. 校验

```bash
python3 -m scripts.quick_validate <技能目录>          # 语法层
python3 -m scripts.quick_validate <技能目录> --deep   # 内容层（行数/触发词/占位符/嵌套引用）
```

### 4. 测试与迭代

完整流程见 `references/testing-workflow.md`。有子 agent 能力时，带技能与不带技能两组用例同轮并行；结果落到 `<skill>-workspace/iteration-N/`，用 `eval-viewer/generate_review.py` 生成评审页交给人看。两条红线：

1. 评审结果先给人看，再自己动手改技能；
2. 没有基线对比的"我改好了"不算证据。

### 5. 打包交付

```bash
python3 -m scripts.package_skill <技能目录>
```

产物是 `.skill` 文件；`evals/`、`tests/`、`runtime/` 里的真实 trace 会被排除。

---

## 运行期闭环（带 runtime 的技能）

### 每次调用后留痕

```bash
python3 scripts/runtime_log.py --skill-root . \
  --status success \
  --input-summary "脱敏输入摘要" \
  --output-summary "脱敏输出摘要" \
  --duration-seconds 12.3
```

造技能类任务可附加元数据：`--build-kind new_skill`、`--skill-category workflow`、`--skill-built <name>`、`--rework-points "..."`。

### 巡检

```bash
python3 scripts/scan_signals.py --skill-root . --window-days 7 --out runtime/signals.md
```

输出三类信号：失败按原因聚合、p95 耗时与上一窗对比、被批评原话。样本不足 5 条时只列原始信号，不下退化结论。

### 沉淀反复出现的问题

```bash
python3 scripts/consolidate_patterns.py --skill-root . --min-requests 3
```

跨 ≥3 个请求的同类问题才建 `patterns/<slug>.md`；已存在的 pattern 只更新计数，不覆盖人工填写的根因与解法。

完整规则、阈值、防漂移机制见 `references/runtime-loop.md`。

---

## 目录结构

```
skill-creator-pro/
├── SKILL.md
├── README.md
├── LICENSE.txt
├── requirements.txt
│
├── agents/                   # 子代理指引（按需加载）
│   ├── grader.md             #   对照断言打分
│   ├── comparator.md          #   盲测 A/B
│   ├── analyzer.md           #   为什么某一版更好
│   └── flow-auditor.md       #   审查流程是否被跳步
│
├── references/              # 参考文档（按需加载）
│   ├── authoring-checklist.md
│   ├── capability-modules.md
│   ├── chinese-context.md
│   ├── lessons-learned.md
│   ├── output-patterns.md
│   ├── runtime-loop.md
│   ├── schemas.md
│   ├── skill-collections.md
│   ├── testing-workflow.md
│   ├── trigger-optimization.md
│   ├── workflows.md
│   └── platforms/            # 六个平台的跑测/优化/交付细节
│
├── examples/                 # 本技能自己的写作示例
├── assets/                  # 评审页等静态资源
├── eval-viewer/             # HTML 评审页生成器
│
├── evals/                   # 本技能的测试语料（不进打包产物）
│   ├── evals.json
│   ├── golden.json          # 冒烟金标准集
│   ├── trigger_eval.json    # description 触发率正/反例
│   └── paired_ab/
│
├── scripts/
│   ├── init_skill.py          # 脚手架
│   ├── quick_validate.py     # 校验
│   ├── runtime_log.py        # 留痕（母版）
│   ├── scan_signals.py        # 巡检（母版）
│   ├── consolidate_patterns.py # 失败模式聚类
│   ├── run_eval.py            # 触发率评估
│   ├── run_loop.py            # 评估+改进循环
│   ├── improve_description.py # 描述优化
│   ├── aggregate_benchmark.py  # 汇总基准
│   ├── paired_ab.py           # 配对 A/B
│   ├── package_skill.py       # 打包
│   ├── platform_detect.py     # 平台检测
│   ├── llm_client.py          # 多平台 CLI / 通用 API 客户端
│   ├── generate_platform_meta.py # 生成平台专属元数据
│   ├── generate_report.py
│   ├── gen_eval_review.py
│   └── utils.py
│
└── runtime/                 # 本机运行数据（trace/signals 不进版本库）
    ├── build-patterns/     #   Meta 层：造技能踩过的坑
    ├── patterns/           #   业务层：下游技能反复失败模式
    ├── candidates.md       #   新技能雷达
    ├── change-log.md       #   改进提案审计
    └── trace.jsonl         #   调用留痕
```

---

## 命令速查

| 目的 | 命令 |
|---|---|
| 建新技能骨架 | `python3 -m scripts.init_skill <name> --path <dir> --capabilities ...` |
| 校验（语法） | `python3 -m scripts.quick_validate <dir>` |
| 校验（内容） | `python3 -m scripts.quick_validate <dir> --deep` |
| 打包 | `python3 -m scripts.package_skill <dir>` |
| 留痕一次调用 | `python3 scripts/runtime_log.py --skill-root <dir> ...` |
| 巡检近 7 天 | `python3 scripts/scan_signals.py --skill-root <dir> --window-days 7` |
| 聚类失败模式 | `python3 scripts/consolidate_patterns.py --skill-root <dir>` |

---

## 与官方 skill-creator 的区别

| 维度 | Anthropic 官方 | Skill Creator Pro |
|---|---|---|
| 平台 | 仅 Claude | 六平台自动识别，弱信号会向用户确认 |
| 语言 | 英文 | 中文（代码保持英文） |
| 测试 | 文本判断 | 各平台原生 CLI 检测；无 CLI 环境走对话内手动模式 |
| 描述优化 | 手动 | 自动循环 + 手动双模式 |
| 文档 | 单文件 SKILL.md | 三层渐进式加载（元数据 / 主文件 / references） |
| 上线后 | 止于打包 | 两层经验沉淀、巡检、门禁、防漂移 |
| 新技能识别 | 无 | 重复工作流雷达，累计出现 ≥2 次才提议固化 |

---

## 许可证

Apache License 2.0，继承自 Anthropic 官方上游。
