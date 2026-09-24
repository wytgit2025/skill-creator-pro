#!/usr/bin/env python3
"""
平台检测模块 - 自动识别当前运行在哪个 AI 平台环境里

支持以下平台：
- claude: Claude Code / Cowork（有 claude CLI）
- codex: OpenAI Codex（有 codex CLI）
- workbuddy: 腾讯 WorkBuddy / CodeBuddy（有 workbuddy / codebuddy CLI）
- openclaw: OpenClaw 开源框架（有 openclaw CLI）
- doubao: 豆包工作（.sessions/ 工作目录）
- qwenwork: 千问办公（只有弱信号，见 detect_platform 里的说明）
- generic: 通用 API 模式（以上都不是）
"""

import os
import shutil
from pathlib import Path


def detect_platform() -> str:
    """
    检测当前运行在哪个平台环境里。

    返回值：
        "claude"     - Claude Code / Cowork
        "codex"      - OpenAI Codex
        "workbuddy"  - 腾讯 WorkBuddy / CodeBuddy
        "openclaw"   - OpenClaw
        "doubao"     - 豆包工作
        "qwenwork"   - 千问办公（弱信号，见下）
        "generic"    - 通用 API 模式（默认）
    """
    # 优先级从高到低，先检测最特殊的

    # 1. Claude Code 环境变量（最权威）
    if os.environ.get("CLAUDECODE"):
        return "claude"

    # 2. 豆包工作：环境变量检测（比路径检测更可靠）
    if os.environ.get("DOUBAO_OFFICE_AGENT_NAME") or os.environ.get("DOUBAO_SANDBOX_TYPE"):
        return "doubao"

    # 3. 豆包工作：.sessions/ 工作目录特征（兜底，防止环境变量没设）
    cwd = Path.cwd()
    if ".sessions" in str(cwd) and "agents" in str(cwd):
        return "doubao"

    # 4. 检查各个 CLI 命令是否存在
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    if shutil.which("workbuddy") or shutil.which("codebuddy"):
        return "workbuddy"
    # 官方二进制就叫 openclaw（`openclaw skills` / `openclaw agent exec`）。
    # 早期这里写的是 which("claw")，跟客户端实际调的 openclaw 不一致——已核对官方 CLI 文档改正。
    if shutil.which("openclaw"):
        return "openclaw"

    # 5. 千问办公：只有弱信号（技能目录是它唯一有文档依据的本地痕迹）。
    #    官方没有公布可用的环境变量或 CLI，所以这里只在前面的信号都没命中时兜底，
    #    命中也可能只是"装了千问办公桌面端"而已——拿不准就回头问用户。
    if (Path.home() / ".qwenworkcn").is_dir():
        return "qwenwork"

    # 6. 默认通用模式
    return "generic"


def get_platform_info() -> dict:
    """
    获取当前平台的详细信息。

    返回字典：
        name: 平台名
        cli_command: 对应的 CLI 命令（如果有）
        has_native_eval: 是否有原生的 trigger 测试方式
        description: 平台描述
    """
    platform = detect_platform()

    info_map = {
        "claude": {
            "name": "Claude",
            "cli_command": "claude",
            "has_native_eval": True,
            "description": "Claude Code / Cowork 环境，原生支持技能触发测试",
        },
        "codex": {
            "name": "OpenAI Codex",
            "cli_command": "codex",
            "has_native_eval": True,
            "description": "OpenAI Codex CLI 环境，支持 AGENTS.md 技能",
        },
        "workbuddy": {
            "name": "腾讯 WorkBuddy",
            "cli_command": "workbuddy",
            "has_native_eval": True,
            "description": "腾讯 WorkBuddy / CodeBuddy 企业级 Agent 环境",
        },
        "openclaw": {
            "name": "OpenClaw",
            "cli_command": "openclaw",
            "has_native_eval": True,
            "description": "开源 OpenClaw Agent 框架，有 ClawHub 技能市场",
        },
        "doubao": {
            "name": "豆包工作",
            "cli_command": None,
            "has_native_eval": False,
            "description": "豆包 Agent 工作环境，主 Agent 自测模式",
        },
        "qwenwork": {
            "name": "千问办公",
            "cli_command": None,
            "has_native_eval": False,
            "description": "阿里千问办公（QwenWork），原生支持 SKILL.md，触发测试走对话内手动模式",
        },
        "generic": {
            "name": "通用 API 模式",
            "cli_command": None,
            "has_native_eval": False,
            "description": "未知环境，使用通用 OpenAI 兼容 API",
        },
    }

    return info_map.get(platform, info_map["generic"])


if __name__ == "__main__":
    platform = detect_platform()
    info = get_platform_info()
    print(f"检测到的平台：{platform}")
    print(f"描述：{info['description']}")
    print(f"有原生测试能力：{'是' if info['has_native_eval'] else '否'}")
    if info["cli_command"]:
        print(f"CLI 命令：{info['cli_command']}")
