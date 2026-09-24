# OpenClaw 环境

**特点：** 开源 AI Agent 框架（MIT 协议，GitHub 30万+ 星），模型无关，自托管，通过消息平台接入。

## 技能系统
- 有 ClawHub 技能市场，6万+ 技能
- 支持 TypeScript / YAML 定义工作流
- 有子代理生成能力（ACP 协议，多 Agent 编排）
- 支持 Claude Code 集成
- 接入 20+ 消息平台（微信、企业微信、钉钉、飞书、WhatsApp、Telegram 等）
- 腾讯有 QClaw 版，字节有 ArkClaw 版

## 跑测试
- 用 `claw` CLI 跑测试
- 支持子代理并行测试
- 结果输出到工作目录

## 优化描述
- 用 `scripts/run_loop.py` 自动跑优化循环
- **触发测试方式：任务中决策模式**——用 `openclaw agent exec` 单次执行，把技能描述注入任务上下文，让模型在真实处理查询的过程中自己判断要不要使用这个技能
- 准确率：85%+
- 因为模型无关，你可以用任何模型来做优化

## 交付
- 整理成标准技能文件夹，发布到 ClawHub
- 或者放到本地技能目录里直接用
