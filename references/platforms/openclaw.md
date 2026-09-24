# OpenClaw 环境

**特点：** 开源 AI Agent 框架（MIT 协议），模型无关，自托管，通过消息平台接入。技能格式是标准的 `SKILL.md` + YAML frontmatter，和本技能产出的一致。

## 技能系统
- CLI 是 **`openclaw`**（不是 `claw`）：`openclaw skills install @owner/<slug>` 装技能，`openclaw skills list/check/verify` 查状态
- 发布走**另一个 CLI**：`clawhub`（`npm i -g clawhub`），`clawhub skill publish ./my-skill --slug my-skill --name "..." --changelog "..."`；`--dry-run` 可先预览
- ClawHub 技能市场
- 技能发现路径按优先级：`<工作区>/skills` > `<工作区>/.agents/skills` > `~/.agents/skills` > `<state-dir>/skills` > 内置技能 > `skills.load.extraDirs`
- 支持分组目录（`SKILL.md` 在配置根下 6 层内都能被发现）；技能名取 frontmatter 的 `name`，缺了才用目录名
- 有子代理 / ACP 多 Agent 编排、Skill Workshop（Agent 起草技能提案给人审）
- 接入 20+ 消息平台（微信、企业微信、钉钉、飞书、WhatsApp、Telegram 等）
- 腾讯有 QClaw 版，字节有 ArkClaw 版

## 跑测试
- 用 `openclaw agent exec "<提示词>"` 跑单次执行——它是官方推荐的 headless 入口，不连 Gateway，自带 setup/cleanup，支持 `--json`、`--message-file`、`--cwd`
- 支持子代理并行测试
- 结果输出到工作目录

## 优化描述
- 用 `scripts/run_loop.py` 自动跑优化循环
- **触发测试方式：任务中决策模式**——用 `openclaw agent exec` 单次执行，把技能描述注入任务上下文，让模型在真实处理查询的过程中自己判断要不要使用这个技能
- 准确率：85%+
- 因为模型无关，你可以用任何模型来做优化

## 基线对比与评审页面
- **触发率**（`run_eval.py` / `run_loop.py`）不需要基线对照——基线等于"根本不装这个技能"，对触发率没有意义
- **任务质量的基线对比**走方案一：子代理跑 `with_skill` 和 `without_skill` 两套配置，grader 打分后用 `python -m scripts.aggregate_benchmark <iteration-N>` 聚合。OpenClaw 有子代理能力，这条能跑
- **评审页面**用 `eval-viewer/generate_review.py`；OpenClaw 常部署在服务器/容器里、没显示器，用 `--static <输出路径>` 生成独立 HTML，再把路径给用户
- 反馈读取：静态页面导出的 `feedback.json` 由用户交回，你从那里读
- 单用户版 / 没有并行能力的环境退到方案二：串行自己跑、跳过基线、对话内直接展示结果

## 交付
- 整理成标准技能文件夹（`SKILL.md` + 辅助文件），直接放进上面的发现路径就能用
- 要发布到 ClawHub 用 `clawhub skill publish`；发布前在 frontmatter 里声明清楚所需的环境变量、工具和权限
- 多技能打包用 `scripts/package_skill.py` 生成 `.skill`，或按目录结构直接分发

## 注意事项
- 报告里别把 `openclaw`（Agent CLI）和 `clawhub`（注册表 CLI）混着写，两个是不同的工具
- 技能名冲突时按上面的优先级取高优先级那份，同名技能被覆盖是预期行为——建技能前先 `openclaw skills list` 看看有没有重名的
