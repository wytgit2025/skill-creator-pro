# OpenAI Codex 环境

**特点：** OpenAI 出品的本地代码 Agent，有 CLI、桌面应用（Mac/Windows）、IDE 扩展、网页版四种形态。技能格式就是 Agent Skills 开放格式（`SKILL.md` + YAML frontmatter），和本技能产出的一致。

## 技能系统
- 技能目录结构：`SKILL.md`（必填）+ `scripts/` / `references/` / `assets/`（可选），和本仓库同一套
- 发现路径按优先级（高的覆盖低的）：

  | 优先级 | 路径 | 范围 |
  |---|---|---|
  | 1 | `$CWD/.agents/skills/` | 当前目录 |
  | 2 | 各级父目录的 `.agents/skills/` | 上层目录 |
  | 3 | `$REPO_ROOT/.agents/skills/` | 仓库根 |
  | 4 | `$HOME/.agents/skills/` | 用户级 |
  | 5 | `/etc/codex/skills/` | 系统 / 管理员 |
  | 6 | 内置技能 | 最低 |

- `AGENTS.md` 管的是**指令和上下文**，不是技能：`~/.codex/AGENTS.md` 是个人全局指引，仓库根的 `AGENTS.md` 是项目共享约定，当前目录的 `AGENTS.md` 补子模块细节
- 装 CLI：`npm install -g @openai/codex`（或 `brew install --cask codex`）
- 有插件（Plugins）生态和插件市场，桌面版里用 `$` 唤起技能

> 上面的路径优先级来自社区对 Codex CLI 的梳理，不是官方 changelog 逐条列出的清单。版本升级后建议用 `codex --help` 或官方文档复核一次再依赖它。

## 跑测试
- headless 入口是 `codex exec "<提示词>"`，结果输出到工作目录；`-m` 指定模型
- 桌面版可以同时管多个 Agent 并行测试
- 装技能就是放进上面的发现路径，不需要额外注册

## 优化描述
- 用 `scripts/run_loop.py` 自动迭代优化
- **触发测试方式：任务中决策模式**——把技能描述注入到任务上下文里，让模型在真实处理用户查询的过程中自己判断要不要使用这个技能，靠输出标记（`[USE_SKILL: ...]`）检测它的决策。不是事后问一句"该不该触发"
- 准确率：85%+，比纯文本判断高一个档次

## 基线对比与评审页面
- **触发率**（`run_eval.py` / `run_loop.py`）不需要基线对照——基线等于"根本不装这个技能"，对触发率没有意义
- **任务质量的基线对比**走方案一：子代理跑 `with_skill` 和 `without_skill` 两套配置，grader 打分后用 `python -m scripts.aggregate_benchmark <iteration-N>` 聚合
- **评审页面**用 `eval-viewer/generate_review.py`；跑在远程/无显示环境时加 `--static <输出路径>` 生成独立 HTML，再把路径给用户
- 反馈读取：静态页面导出的 `feedback.json` 由用户交回，你从那里读
- 没有并行能力就退到方案二：串行自己跑、跳过基线、对话内直接展示结果

## 交付
- 技能：按标准目录结构整理，放进 `.agents/skills/`（项目级）或 `~/.agents/skills/`（用户级）即可被发现
- 需要常驻指令 / 上下文约定时，另写 `AGENTS.md` 放项目根或 `~/.codex/AGENTS.md`
- 打包用 `scripts/package_skill.py` 生成 `.skill`，或直接按目录结构分发
- 要发到插件市场，就按插件格式再包一层

## 注意事项
- 别把 `AGENTS.md` 当成技能载体：它是指令文件，技能必须是带 frontmatter 的 `SKILL.md` 目录
- 同名技能按上面的优先级取高优先级那份，被覆盖是预期行为——建技能前先确认路径上有没有重名
- Windows 上官方建议走 WSL2
