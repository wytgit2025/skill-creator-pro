# 腾讯 WorkBuddy / QClaw 环境

**特点：** 有 CLI 工具和本地 daemon API，技能格式和 Claude 兼容，多了几个元数据字段。分个人版和企业版，包结构不一样。

## 个人版 frontmatter 字段（必须加）

```yaml
---
name: my-skill
description: 技能描述
version: "1.0.0"        # 比 Claude 版多的
category: productivity  # 比 Claude 版多的
platforms: desktop,im  # 比 Claude 版多的
agent_created: true     # 必须加，否则 WorkBuddy 不能后续修改
---
```

> 这四个额外字段已加入 `scripts/quick_validate.py` 的白名单，校验时不会报错。

## 依赖声明字段（可选，国内企业环境常用）

frontmatter 里还可以声明运行依赖，平台会在安装时检查：

```yaml
requires:
  env: ["MY_API_TOKEN"]     # 必需的环境变量，缺了直接报错
  bins: ["curl", "git"]     # 必须存在的 CLI 二进制
install: "brew install jq"  # 依赖怎么装（brew/node/go/uv）
os: ["macos", "linux"]      # 操作系统限制
emoji: "🛠️"                # 客户端显示图标
```

## 企业版：多一个 manifest.yaml

如果要发到 **WorkBuddy Enterprise**（企业内部技能库），包结构不是只有 SKILL.md，而是：

```
my-enterprise-skill/
├── SKILL.md          # [必填] 名称 + 描述 + 使用说明
├── manifest.yaml     # [必填] 版本、依赖、元数据（企业版独有）
├── scripts/          # [可选] 可执行脚本
├── references/       # [可选] 参考文档
└── assets/           # [可选] 图标、模板等资源
```

`manifest.yaml` 最小示例：

```yaml
name: my-enterprise-skill
version: 1.0.0
description: "企业内部专用的数据处理 Skill"
category: data-processing
author: enterprise-admin
```

个人版只需要 frontmatter；企业版必须额外带这个 manifest.yaml。

## 上架与安全扫描

- 上传到 SkillHub 或企业版后，平台会做**格式校验 + 安全扫描**
- `scripts/` 里的脚本会在客户端沙箱里执行——不要硬编码凭据，不要假设能访问任意本地文件
- 含敏感操作的技能，企业管理员会配白名单/黑名单下发；做的时候自己就按"可能被限制范围"来写
- 不再用的技能要及时停用，企业版管理员会定期清理

## 跑测试
- 有 CLI 的话，用 `workbuddy run --skill ./my-skill "测试提示词"` 来跑
- 没有 CLI 的话，用本地 daemon API（`http://localhost:8080/api/v1/...`）
- 结果输出到 workspace 目录

## 优化描述
- 用 `scripts/run_loop.py` 自动跑优化循环
- **触发测试方式：原生端到端检测**——和 Claude 一样，往 `~/.codebuddy/commands/` 里放临时命令文件，然后用 `codebuddy -p --output-format stream-json` 跑查询，检测模型有没有真的调用这个技能
- 准确率：95%+，和 Claude 同级

## 触发测试的权限边界
- 会往**用户全局命令目录**写临时文件 `~/.codebuddy/commands/<技能>-test-<id>.md`（跑完即删，进程被强杀可能残留）
- 嵌套 `codebuddy -p` 的工作目录是新建的临时目录（`tempfile.mkdtemp(prefix="skill-creator-trigger-")`），跑完删除——**不要**让它落在用户家目录
- `-y`（自动确认）**默认不加**。加了（`--allow-auto-approve` 或 `SKILL_CREATOR_ALLOW_AUTO_APPROVE=1`）等于关掉该子进程的确认提示、它可以不经确认执行工具，**必须先跟用户讲明并拿到同意**

## 交付
- 个人版：打包成文件夹，用户导入到 WorkBuddy SkillHub
- 企业版：按上面的结构打 ZIP，上传到企业控制台的"AI 资源管理 > Skill 管理"
- 也可以发布到公开 SkillHub 技能市场
