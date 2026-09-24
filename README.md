# 🚀 Skill Creator Pro

> **把重复工作固化成可复用的 AI 技能——六平台适配、严谨测试闭环、触发率自动优化。**

![Version](https://img.shields.io/badge/version-v2.1.0-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![Platforms](https://img.shields.io/badge/platforms-6-orange)
![Status](https://img.shields.io/badge/status-production%20ready-brightgreen)

---

## ✨ 为什么需要这个？

你有没有遇到过这些痛点：

- **每次做类似任务都要重新描述一遍流程**？为什么不能把它固化下来，下次直接调用？
- **做出来的技能到底好不好用**？怎么客观评估？凭感觉吗？
- **技能描述写了半天，就是不触发**？改了又改，到底怎么优化？
- **换个 AI 平台就不能用了**？每个平台格式还不一样？

**Skill Creator Pro 就是解决这些问题的。** 它是一个专业级的技能创建工具箱——从需求分析 → 编写 → 测试 → 评审 → 迭代优化 → 打包发布，全流程覆盖。

基于 Anthropic 官方原版 `skill-creator` 深度改造，**不是玩具，是生产级工具**。

---

## 🌟 核心特性

### 🎯 六平台自动识别，一套代码到处跑

| 平台 | 原生触发测试 | 自动化程度 |
|------|-------------|---------|
| **Claude Code** | ✅ 端到端 95%+ 准确率 | ✅ 全自动 |
| **腾讯 WorkBuddy / CodeBuddy** | ✅ 端到端 95%+ 准确率 | ✅ 全自动 |
| **OpenAI Codex** | ✅ 任务中决策 85%+ | ✅ 全自动 |
| **OpenClaw** | ✅ 任务中决策 85%+ | ✅ 全自动 |
| **豆包工作** | ✅ 对话内手动模式 | ✅ 主 Agent 自测 |
| **千问办公（QwenWork）** | ✅ 对话内手动模式 | ✅ 主 Agent 自测 |

**自动检测运行环境，优先用原生 CLI，降级到通用 API——你不用管细节，它自己会选最优方案。**

### 🧪 严谨测试闭环，不是凭感觉

- **带技能 vs 不带技能** 基线对比，客观量化技能到底有没有用
- **每次查询跑 3 次**，算触发率，不是一次定生死
- **训练集 / 测试集分层拆分**，防止描述过拟合
- **HTML 评审页面**，可视化看每个用例的通过/失败情况
- **自动汇总基准报告**：通过率、耗时、token 用量的均值 ± 标准差（采不到真实 token 数时那一行显示 `—`，不拿字符数顶替）

### 🎯 触发率自动优化，描述不再靠玄学

- 自动生成 20 个真实感测试用例（8-10 正例 + 8-10 反例）
- 最多迭代 5 轮，每轮根据失败案例改进描述
- **按测试集得分选最优**，不是训练集——防止过拟合
- 两种模式：脚本自动跑（有 CLI 的环境）+ 对话内手动跑（豆包工作、千问办公）

### 📦 一键打包发布

校验 → 打包 → 生成 `.skill` 文件，一条龙搞定（`evals/`、`tests/` 不会进产物）。

---

## 🚀 快速开始

### 第一步：安装

把整个文件夹放到你的技能目录下即可：

| 平台 | 技能目录位置 |
|------|-------------|
| **Claude Code** | `.claude/skills/`（项目根目录下） |
| **豆包工作** | `.user_skills/`（用户技能目录） |
| **腾讯 WorkBuddy** | SkillHub 对应目录（上传即可） |
| **千问办公（QwenWork）** | `~/.qwenworkcn/skills/` |
| **OpenAI Codex** | `.agents/skills/`（项目级）或 `~/.agents/skills/`（用户级） |
| **OpenClaw** | 工作区 `skills/` 或 `~/.agents/skills/` |

### 第二步：开始使用

直接用自然语言说就行，技能会自动触发。下面是几个真实使用场景：

---

### 📖 使用场景示例

#### 场景 1：从零创建一个新技能

**你说：**
> "帮我做个技能，把'周报自动生成'这个流程固化下来——每周五下午自动汇总本周的飞书文档、会议记录、待办完成情况，生成一份周报草稿。"

**技能会自动帮你：**
1. 先问你几个问题：这个技能什么时候触发？期望输出什么格式？有没有边界情况？
2. 帮你写出 `SKILL.md` 初稿（带正确的 YAML 前置元数据）
3. 帮你设计 3 个测试用例
4. 帮你跑一遍，看看效果
5. 根据你的反馈迭代优化
6. 最后打包成 `.skill` 文件给你

---

#### 场景 2：优化现有技能的触发描述

**你说：**
> "我那个'周报生成'的技能，用户明明说了'帮我写周报'，它就是不触发，怎么回事？"

**技能会自动帮你：**
1. 先读一下你现在的技能描述
2. 帮你生成 20 个测试查询（10 个应该触发的，10 个不应该触发的）
3. 跑一遍评估，看看哪些用例没通过
4. 根据失败案例，自动改进描述
5. 迭代 5 轮，选得分最高的那个版本
6. 给你看可视化的对比报告

---

#### 场景 3：测试技能到底有没有用

**你说：**
> "我不确定这个技能是不是真的有用，还是说不用它我也能做得一样好？帮我测一下。"

**技能会自动帮你：**
1. 跑两组对比测试：一组带技能，一组不带
2. 每个测试用例跑 3 次，算平均通过率
3. 输出基准报告：通过率提升了多少？耗时多了还是少了？token 用量呢？
4. 生成 HTML 评审页面，你可以直观地看每个用例的情况

---

#### 场景 4：把技能打包发布

**你说：**
> "我这个技能做好了，想分享给同事用，怎么打包？"

**技能会自动帮你：**
1. 先跑一遍快速校验（检查 SKILL.md 格式、命名规范、描述长度、`scripts/` 里的语法错误）
2. 校验通过后，自动打成 `.skill` 文件（zip 格式）
3. 告诉你怎么分发、怎么安装

---

## 📁 目录结构

```
skill-creator-pro/
├── SKILL.md              # 主技能文件（509 行，渐进式加载）
├── README.md             # 你正在看的这个文件
├── LICENSE.txt           # Apache License 2.0
├── requirements.txt      # Python 依赖（PyYAML, requests）
│
├── agents/               # 子代理指引文档（按需加载）
│   ├── grader.md         #   怎么对照断言打分
│   ├── comparator.md     #   怎么做盲测 A/B 对比
│   └── analyzer.md       #   怎么分析为什么赢了
│
├── references/           # 参考文档（按需加载）
│   ├── schemas.md                #   evals / grading / benchmark 的 JSON 结构
│   ├── trigger-optimization.md   #   触发率优化完整指南
│   ├── authoring-checklist.md    #   交稿前自检清单
│   ├── workflows.md              #   流程怎么组织
│   ├── output-patterns.md        #   输出模板怎么写
│   ├── skill-collections.md      #   多个相关技能怎么打包成集合
│   ├── chinese-context.md        #   中文各文体区别 + 国内合规底线
│   └── platforms/                #   六个运行环境的跑测/优化/交付细节
│       ├── claude.md             #     Claude Code / Cowork / Claude.ai
│       ├── workbuddy.md          #     腾讯 WorkBuddy / QClaw（含企业版）
│       ├── qwenwork.md           #     千问办公（QwenWork）
│       ├── codex.md              #     OpenAI Codex
│       ├── openclaw.md           #     OpenClaw
│       └── doubao-work.md        #     豆包工作
│
├── assets/               # 静态资源
│   └── eval_review.html  #   触发测试集编辑页面
│
├── eval-viewer/          # 可视化评审工具
│   ├── generate_review.py  # 评审页面生成器 + HTTP 服务（--static 可出独立 HTML）
│   └── viewer.html         #   前端模板（完整单页应用）
│
├── tests/                # 回归测试（不进打包产物）
│   ├── test_aggregate_benchmark.py  # benchmark 聚合契约、tokens 量纲
│   └── __init__.py
│
└── scripts/              # Python 脚本（12 个）
    ├── llm_client.py     #   四平台原生 CLI 客户端 + 通用 API 模式
    ├── platform_detect.py #   平台自动检测
    ├── init_skill.py     #   技能脚手架（生成目录骨架）
    ├── run_eval.py       #   跑触发率评估
    ├── run_loop.py       #   评估 + 改进循环
    ├── improve_description.py # 根据失败案例优化描述
    ├── aggregate_benchmark.py # 汇总基准统计
    ├── generate_report.py #   生成 HTML 报告
    ├── package_skill.py  #   打包成 .skill 文件
    ├── quick_validate.py #   技能快速校验（含 scripts/*.py 语法检查）
    ├── utils.py          #   共享工具函数
    └── __init__.py
```

---

## ❓ 常见问题

### Q: 豆包工作 / 千问办公里能用吗？需要 API Key 吗？

**A: 可以用，不需要 API Key。** 这两个平台走的是对话内手动模式——主 Agent 自己就是模型，不需要外部调用。脚本自动模式只在有 CLI 的环境（Claude、Codex、WorkBuddy、OpenClaw）才需要。

### Q: 我不会写代码，能用吗？

**A: 完全可以。** 你不需要碰任何脚本。直接用自然语言说你想干嘛，技能会自动处理所有细节。脚本是给进阶用户用的，想自动化的时候才需要。

### Q: 触发测试会不会在后台自动执行危险操作？

**A: 默认不会。** 触发测试需要嵌套启动平台 CLI，这方面默认值一律收紧：不加自动确认参数（如 `-y`）、不移除宿主的递归护栏变量、嵌套进程的工作目录是临时目录、临时命令文件跑完即删。确实需要放开时必须显式加 `--allow-auto-approve` 或 `--allow-nested-claude`，而且它会把权限影响先告诉你。

### Q: 和 Anthropic 官方原版有什么区别？我该用哪个？

**A: 如果你只用 Claude，用官方原版就够了。** 如果你用多个平台（豆包工作 + Claude + Codex），或者需要更严谨的测试流程，那用 Pro 版。Pro 版是完全兼容的，官方原版能做的它都能做，只是多了多平台适配和工程化增强。

### Q: 我的技能是中文的，能优化吗？

**A: 当然可以。** 整个技能都是中文写的，所有测试、优化、报告都是中文。

---

## 🆚 和官方原版有什么区别？

| 特性 | Anthropic 官方原版 | Skill Creator Pro |
|------|-------------------|-------------------|
| 平台支持 | 仅 Claude | **6 平台自动适配** |
| 豆包工作 | ❌ | ✅ 原生支持（对话内手动模式） |
| 千问办公 | ❌ | ✅ 原生支持（中英双语元数据 + `.skill-metadata.yaml`） |
| 触发测试 | 仅文本判断 | **各平台原生检测**（Claude/WorkBuddy 端到端 95%+） |
| 触发率优化 | 手动对话 | **脚本自动循环** + 手动模式双支持 |
| 语言 | 英文 | **中文**（代码保持英文） |
| 文档 | 单文件 SKILL.md | **渐进式加载**（元数据 / 主文件 / 参考文档三层） |
| 评审页面 | 基础版 | **完整单页应用**（支持基准对比、XLSX 渲染、键盘导航） |
| 严谨度 | 够用 | **生产级**（训练/测试拆分、多轮重试、统计显著性） |

---

## 🧪 开发者：跑回归测试

```bash
python3 -m unittest discover -s tests        # benchmark 聚合契约、tokens 量纲
python3 -m scripts.quick_validate . --deep    # 技能自身的格式与语法校验
```

---

## 📄 许可证

Apache License 2.0（继承自 Anthropic 官方上游）

---

## 🙏 致谢

本项目基于 [Anthropic 官方 skill-creator](https://github.com/anthropics/skills) 深度改造，致敬原版的设计哲学，在其基础上做了多平台适配和工程化增强。
