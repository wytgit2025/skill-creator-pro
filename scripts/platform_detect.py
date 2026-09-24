#!/usr/bin/env python3
"""
平台检测模块 - 自动识别当前运行在哪个 AI 平台环境里

支持以下平台：
- claude: Claude Code / Cowork（有 claude CLI，或 CLAUDECODE 环境变量）
- codex: OpenAI Codex（有 codex CLI）
- workbuddy: 腾讯 WorkBuddy / CodeBuddy（宿主会话标记，或有 workbuddy / codebuddy CLI）
- openclaw: OpenClaw 开源框架（有 openclaw CLI）
- doubao: 豆包工作（.sessions/ 工作目录）
- qwenwork: 千问办公（只有弱信号，见 detect_platform 里的说明）
- generic: 通用 API 模式（以上都不是）

自动检测原理上分不清的情况（同一台机器装了多个平台的 CLI），用环境变量
SKILL_CREATOR_PLATFORM 显式指定平台——它压过所有自动信号。
"""

import os
import shutil
from pathlib import Path
from typing import Optional

# 显式覆盖入口。平台判错会让整条流程走错分支（元数据写错、测试模式走错、
# 临时文件写到错误的全局目录），而多 CLI 共存时 which 分不清"装了"和"在用"，
# 所以必须留一个不改代码就能纠正的出口。
PLATFORM_OVERRIDE_ENV = "SKILL_CREATOR_PLATFORM"

# 平台全集：detect 能返回的值和覆盖值都必须在这里面。
# 漏加会静默退化成"当作非法值忽略"，改动时必须与 detect 分支和覆盖值同步。
KNOWN_PLATFORMS = frozenset({
    "claude", "codex", "workbuddy", "openclaw", "doubao", "qwenwork", "generic",
})

# CodeBuddy / WorkBuddy 宿主注入的会话标记。和 CLAUDECODE、DOUBAO_* 同级：
# 是"我此刻确实在这个宿主里"的直接证据，比 which 可靠——which 只说明装了。
# 只认会话级标记：CODEBUDDY_SAFE_DELETE_* 是 safe-delete shim 注入的，
# 可能顺 shell 环境带进普通终端，拿它当宿主证据会误判。
CODEBUDDY_HOST_ENV = ("CODEBUDDY_SESSION_ID", "CODEBUDDY_TOOL_CALL_ID")


def override_platform() -> Optional[str]:
    """读显式覆盖的平台名；未设置返回 None。

    这里**不校验合法性**，原样（去空格、转小写）返回——把非法值直接吞掉
    会让用户以为开关生效了。合法性判断在 detect_platform_detail() 里，
    上层也可以拿 override_platform() + KNOWN_PLATFORMS 自己提示拼写问题。
    """
    raw = (os.environ.get(PLATFORM_OVERRIDE_ENV) or "").strip().lower()
    return raw or None


def detect_platform_detail() -> tuple[str, str]:
    """
    检测平台，并给出**置信度**——这是关键：弱信号不能当成确定结论。

    返回 (平台名, 置信度)，置信度 ∈ {"high", "low", "none"}：
    - "high"：环境变量或 CLI 命令明确命中，可以直接按这个平台走流程。
    - "low" ：只命中了弱信号（目录存在 / 路径特征）。很可能是"装了但没在用"，
              **应当先向用户确认**，不要直接按它走（否则会生成错误的元数据、走错测试模式）。
    - "none"：没有任何信号，走通用模式。

    平台名取值：
        "claude" / "codex" / "workbuddy" / "openclaw" / "doubao" / "qwenwork" / "generic"

    环境变量 SKILL_CREATOR_PLATFORM 是显式覆盖，优先于下面所有自动信号；
    取到合法平台名时一律按 "high" 返回（用户说了算）。
    """
    # 优先级从高到低，先检测最特殊的

    # 0. 显式覆盖：用户意志压过一切自动检测
    forced = override_platform()
    if forced in KNOWN_PLATFORMS:
        return forced, "high"

    # 1. Claude Code 环境变量（最权威）
    if os.environ.get("CLAUDECODE"):
        return "claude", "high"

    # 2. CodeBuddy / WorkBuddy 宿主会话标记（同样权威）
    #    少了这一步，在 CodeBuddy 里跑脚本就会因为 CLI 不在 PATH 上而
    #    让 which 全部落空，结论被 ~/.qwenworkcn 这类弱信号抢答成别的平台。
    if any(os.environ.get(k) for k in CODEBUDDY_HOST_ENV):
        return "workbuddy", "high"

    # 3. 豆包工作：环境变量检测（比路径检测更可靠）
    if os.environ.get("DOUBAO_OFFICE_AGENT_NAME") or os.environ.get("DOUBAO_SANDBOX_TYPE"):
        return "doubao", "high"

    # 4. 豆包工作：.sessions/ 工作目录特征（兜底，防止环境变量没设）——弱信号
    cwd = Path.cwd()
    if ".sessions" in str(cwd) and "agents" in str(cwd):
        return "doubao", "low"

    # 5. 检查各个 CLI 命令是否存在（强信号）
    if shutil.which("claude"):
        return "claude", "high"
    if shutil.which("codex"):
        return "codex", "high"
    if shutil.which("workbuddy") or shutil.which("codebuddy"):
        return "workbuddy", "high"
    # 官方二进制就叫 openclaw（`openclaw skills` / `openclaw agent exec`）。
    # 早期这里写的是 which("claw")，跟客户端实际调的 openclaw 不一致——已核对官方 CLI 文档改正。
    if shutil.which("openclaw"):
        return "openclaw", "high"

    # 6. 千问办公：只有弱信号（技能目录是它唯一有文档依据的本地痕迹）。
    #    官方没有公布可用的环境变量或 CLI。目录存在 ≠ 正在用千问办公——
    #    很多人装了桌面端但从没在 Agent 里跑过。所以标 low，交给上层提醒用户确认。
    if (Path.home() / ".qwenworkcn").is_dir():
        return "qwenwork", "low"

    # 7. 无信号
    return "generic", "none"


def detect_platform() -> str:
    """只返回平台名（向后兼容）。

    注意：本函数会把弱信号也当成"确定结果"返回。需要区分强弱时用
    detect_platform_detail()，或在打印时用 describe_detection()。
    """
    return detect_platform_detail()[0]


def format_detection(platform: str, confidence: str) -> str:
    """把已知的 (平台, 置信度) 渲染成一行说明。

    给"已经自己检测过一次"的调用方用——避免为了打印再检测一遍，
    导致打印出来的平台和实际走的分支是两份真相。
    """
    if confidence == "high":
        return f"检测到运行平台：{platform}"
    if confidence == "low":
        return (f"检测到运行平台：{platform}（⚠️ 弱信号——可能是『装了但没在用』，"
                f"请先跟用户确认，别直接按它走流程）")
    return "未检测到已知平台，走通用模式"


def describe_detection() -> str:
    """检测一次并返回说明。已经检测过（拿到了平台和置信度）的调用方请直接
    用 format_detection()，不要再检测一遍。"""
    return format_detection(*detect_platform_detail())


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
    platform, confidence = detect_platform_detail()
    info = get_platform_info()
    conf_label = {"high": "强信号", "low": "弱信号（建议先向用户确认）", "none": "无信号"}[confidence]
    print(f"检测到的平台：{platform}")
    print(f"置信度：{conf_label}")
    print(f"描述：{info['description']}")
    print(f"有原生测试能力：{'是' if info['has_native_eval'] else '否'}")
    if info["cli_command"]:
        print(f"CLI 命令：{info['cli_command']}")
