#!/usr/bin/env python3
"""
LLM 客户端 - 支持四平台原生调用 + OpenAI 兼容 API

支持的平台：
1. Claude（原生 claude CLI）- 用 claude -p 调用，trigger 测试最准
2. OpenAI Codex（原生 codex CLI）
3. 腾讯 WorkBuddy（原生 workbuddy CLI）
4. OpenClaw（原生 openclaw CLI）
5. 通用 API 模式（豆包/通义/DeepSeek/Kimi 等 OpenAI 兼容接口）

自动检测当前运行环境，优先用原生 CLI 模式。
检测不到 CLI 的时候，降级到通用 OpenAI API 模式。

配置方式（通用 API 模式）：
1. 环境变量：OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
2. 命令行参数 --api-key, --base-url, --model
3. 直接在代码里传参
"""

import os
import json
import re
import shutil
import subprocess
import sys
import tempfile
import requests
from typing import Optional

from scripts.platform_detect import (
    KNOWN_PLATFORMS,
    PLATFORM_OVERRIDE_ENV,
    detect_platform,
    detect_platform_detail,
    format_detection,
    override_platform,
)

# 已提示过"OPENAI_API_KEY 覆盖了原生平台检测"，避免并行 worker 刷屏
_warned_api_key_override = False


def _env_flag(name: str) -> bool:
    """读布尔型环境变量（1/true/yes 都算开）。"""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


class LLMClient:
    """通用 LLM 客户端，兼容 OpenAI Chat Completions API 格式。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                "未找到 API Key。请通过以下方式之一提供：\n"
                "1. 设置环境变量 OPENAI_API_KEY\n"
                "2. 命令行传入 --api-key\n"
                "3. 代码中传入 api_key 参数"
            )

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> dict:
        """
        调用 Chat Completions 接口，返回完整响应。

        Args:
            messages: 消息列表，格式 [{"role": "user", "content": "..."}]
            temperature: 采样温度
            max_tokens: 最大生成 token 数
            stream: 是否流式（当前实现只返回完整文本）
            tools: 可选的工具定义列表（OpenAI function calling 格式）
            tool_choice: 工具选择策略 ("auto" / "none" / "required")

        Returns:
            完整的 API 响应 JSON
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = response.text[:500]
            except Exception:
                pass
            raise RuntimeError(
                f"API 调用失败 (HTTP {response.status_code}): {e}\n"
                f"响应内容: {error_body}"
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"网络请求失败: {e}")

    def chat_text(
        self,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """便捷方法：只返回文本内容。"""
        data = self.chat(messages, **kwargs)
        return data["choices"][0]["message"]["content"] or ""

    def chat_with_system(
        self,
        system_prompt: str,
        user_prompt: str,
        **kwargs,
    ) -> str:
        """便捷方法：带系统提示词的单轮对话。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat_text(messages, **kwargs)

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        include_distractors: bool = True,
    ) -> bool:
        """
        全真模拟触发测试：用 function calling 模拟技能选择。

        把技能描述包装成一个工具定义，再加上几个干扰工具，
        让模型在真实的工具选择场景下做决策——看它会不会选这个技能工具。

        这比"事后让裁判模型猜"更真实，因为它测的是模型在真实推理
        过程中的工具选择行为。

        Args:
            user_query: 用户的查询
            skill_name: 技能名称
            skill_description: 技能描述
            include_distractors: 是否加入干扰工具（模拟真实环境中有多个技能的情况）

        Returns:
            True 如果模型选择调用了这个技能，False 如果没有
        """
        # 把技能包装成一个 function calling 工具
        skill_tool = {
            "type": "function",
            "function": {
                "name": skill_name,
                "description": skill_description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "用户要完成的具体任务描述",
                        }
                    },
                    "required": ["task"],
                },
            },
        }

        tools = [skill_tool]

        # 加入几个干扰工具，模拟真实环境中有多个可用技能的情况
        if include_distractors:
            distractor_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "搜索公司内部知识库和文档。当用户查找内部规定、流程、历史决策或公司特定信息时使用。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "搜索关键词"}
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "读取本地文件内容。当用户提供了文件路径、要求查看文件内容、或需要读取文档时使用。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {"type": "string", "description": "文件路径"}
                            },
                            "required": ["path"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "搜索互联网上的公开信息。当用户需要查找最新新闻、外部资料、行业数据或公开事实时使用。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "搜索关键词"}
                            },
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "write_code",
                        "description": "编写或修改代码。当用户要求写脚本、调试程序、实现算法或代码相关任务时使用。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string", "description": "代码任务描述"}
                            },
                            "required": ["task"],
                        },
                    },
                },
            ]
            tools.extend(distractor_tools)

        messages = [
            {"role": "user", "content": user_query},
        ]

        try:
            data = self.chat(
                messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.0,
                max_tokens=200,
            )
            message = data["choices"][0]["message"]

            # 检查模型有没有选择调用我们的技能工具
            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                return False

            for call in tool_calls:
                if call.get("function", {}).get("name") == skill_name:
                    return True

            return False

        except Exception as e:
            # 如果 API 不支持 function calling，降级到文本判断模式
            print(f"Warning: function calling 失败，降级到文本判断模式: {e}", file=__import__('sys').stderr)
            return self._trigger_test_text_fallback(user_query, skill_name, skill_description)

    def _trigger_test_text_fallback(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
    ) -> bool:
        """降级方案：当 API 不支持 function calling 时，用文本判断。"""
        system_prompt = (
            "你是一个智能助手的技能路由系统。你的任务是判断："
            "给定用户的查询，以及一个可用技能的描述，模型是否应该调用这个技能来完成用户的任务。\n\n"
            "判断规则：\n"
            "- 如果用户的任务确实需要这个技能的专业能力、流程框架或工具集，返回 'YES'\n"
            "- 如果用户的任务用基础能力就能直接完成，或者和这个技能不相关，返回 'NO'\n"
            "- 简单的一步任务（读个文件、写个简单文本）通常不需要技能\n"
            "- 复杂的、多步骤的、专业领域的任务通常需要技能\n\n"
            "只回答 YES 或 NO，不要解释。"
        )

        user_prompt = (
            f"可用技能：{skill_name}: {skill_description}\n\n"
            f"用户查询：{user_query}\n\n"
            f"模型应该调用这个技能吗？"
        )

        result = self.chat_with_system(system_prompt, user_prompt, temperature=0.0, max_tokens=10).strip().upper()
        return "YES" in result


def _iter_stdout_chunks(process: subprocess.Popen, timeout: float):
    """
    跨平台地从子进程 stdout 逐块取数据，直到进程结束或超时。

    原来触发测试用的是 `select.select([process.stdout], ...)` + `os.read`，
    这在 Windows 上直接不可用——Windows 的 select 只认 socket，传管道会抛 OSError。
    改成后台线程阻塞读、主线程轮询，Unix 和 Windows 行为一致。

    超时后主线程返回，_pump 线程可能还阻塞在 os.read 上。
    调用方在 finally 里 kill 进程会让管道关闭、os.read 返回空，
    但存在时间窗口。这里在生成器终止时确保等待线程退出。
    """
    import threading
    import time as time_mod

    fd = process.stdout.fileno()
    chunks: list = []
    finished = threading.Event()

    def _pump():
        try:
            while True:
                chunk = os.read(fd, 8192)
                if not chunk:
                    break
                chunks.append(chunk)
        except OSError:
            pass  # 进程被杀 / 管道关闭，正常收尾
        finally:
            finished.set()

    pump_thread = threading.Thread(target=_pump, daemon=True)
    pump_thread.start()

    deadline = time_mod.time() + timeout
    try:
        while True:
            if chunks:
                yield chunks.pop(0)
                continue
            if finished.is_set():
                return
            remaining = deadline - time_mod.time()
            if remaining <= 0:
                return
            finished.wait(min(0.1, remaining))
    finally:
        # 确保泵线程退出：等待最多 2 秒让管道关闭后线程自然结束。
        # 调用方通常在 finally 里 process.kill()，管道关闭后 os.read 返回空。
        # 如果 2 秒后仍在阻塞（异常情况），daemon 线程会在进程退出时被回收。
        finished.wait(2.0)


class NativeCLIClient:
    """
    原生 CLI 客户端基类 - 用平台自己的 CLI 命令调用模型。

    比通用 API 模式更准确，因为用的是平台原生的技能加载和触发机制。

    嵌套调用会扩大权限边界，下面两个开关默认都是关的，必须由用户显式打开：
    - `allow_auto_approve`：是否给子进程加自动确认参数（如 codebuddy 的 `-y`）
    - `allow_nested_claude`：是否剔除 CLAUDECODE，以在 Claude Code 内部嵌套调用

    对应环境变量：`SKILL_CREATOR_ALLOW_AUTO_APPROVE`、`SKILL_CREATOR_ALLOW_NESTED_CLAUDE`。
    """

    def __init__(
        self,
        cli_command: str,
        model: Optional[str] = None,
        allow_auto_approve: Optional[bool] = None,
        allow_nested_claude: Optional[bool] = None,
    ):
        self.cli_command = cli_command
        self.model = model
        self.platform = "unknown"
        self.allow_auto_approve = (
            allow_auto_approve if allow_auto_approve is not None
            else _env_flag("SKILL_CREATOR_ALLOW_AUTO_APPROVE")
        )
        self.allow_nested_claude = (
            allow_nested_claude if allow_nested_claude is not None
            else _env_flag("SKILL_CREATOR_ALLOW_NESTED_CLAUDE")
        )
        self._notices: set = set()

    def _notice_once(self, key: str, message: str) -> None:
        """同一类提示只打一次，避免并行 worker 里刷屏。"""
        if key not in self._notices:
            self._notices.add(key)
            print(message, file=sys.stderr)

    def _nested_env(self) -> dict:
        """构造子进程的环境变量。

        CLAUDECODE 是宿主（Claude Code）的递归护栏标记，默认原样传给子进程。
        静默剔除它等于让嵌套调用绕过宿主限制，必须由用户显式同意。
        """
        if not self.allow_nested_claude:
            return dict(os.environ)
        self._notice_once(
            "nested-claude",
            "⚠️ 已启用 --allow-nested-claude：这次嵌套调用剔除了 CLAUDECODE，绕过了宿主递归护栏",
        )
        return {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    def _auto_approve_args(self) -> list:
        """返回自动确认参数。默认不加，并在首次跳过时说明后果。"""
        if self.allow_auto_approve:
            self._notice_once(
                "auto-approve-on",
                "⚠️ 已启用 --allow-auto-approve：嵌套 CLI 的确认提示被关闭，该子进程可以不经确认执行工具",
            )
            return ["-y"]
        self._notice_once(
            "auto-approve-off",
            "提示：未开启自动确认（-y）。若嵌套 CLI 因此停下来等确认，本次触发判定会失败。"
            "确需开启请加 --allow-auto-approve，并知悉它会关闭该子进程的确认提示。",
        )
        return []

    def chat(self, messages: list[dict], **kwargs) -> dict:
        """调用 CLI，返回统一格式的响应。"""
        # 把 messages 拼成一个 prompt
        prompt = "\n\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages
        )
        text = self._call_cli(prompt)
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": text,
                    }
                }
            ]
        }

    def chat_text(self, messages: list[dict], **kwargs) -> str:
        data = self.chat(messages, **kwargs)
        return data["choices"][0]["message"]["content"] or ""

    def chat_with_system(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat_text(messages, **kwargs)

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        **kwargs,
    ) -> bool:
        """原生触发测试 - 让平台 CLI 真的去加载技能，看它会不会触发。"""
        # 基类用文本判断，子类可以重写为更准确的原生检测
        return self._trigger_test_text_fallback(user_query, skill_name, skill_description)

    def _call_cli(self, prompt: str) -> str:
        """调用 CLI 命令，返回文本输出。子类实现具体逻辑。"""
        raise NotImplementedError

    def _trigger_test_text_fallback(self, user_query, skill_name, skill_description) -> bool:
        """降级方案：用文本判断。"""
        system_prompt = (
            "你是一个智能助手的技能路由系统。你的任务是判断："
            "给定用户的查询，以及一个可用技能的描述，模型是否应该调用这个技能来完成用户的任务。\n\n"
            "判断规则：\n"
            "- 如果用户的任务确实需要这个技能的专业能力、流程框架或工具集，返回 'YES'\n"
            "- 如果用户的任务用基础能力就能直接完成，或者和这个技能不相关，返回 'NO'\n"
            "- 简单的一步任务通常不需要技能\n"
            "- 复杂的、多步骤的、专业领域的任务通常需要技能\n\n"
            "只回答 YES 或 NO，不要解释。"
        )
        user_prompt = (
            f"可用技能：{skill_name}: {skill_description}\n\n"
            f"用户查询：{user_query}\n\n"
            f"模型应该调用这个技能吗？"
        )
        result = self.chat_with_system(system_prompt, user_prompt, temperature=0.0, max_tokens=10).strip().upper()
        return "YES" in result


class ClaudeNativeClient(NativeCLIClient):
    """Claude Code 原生客户端 - 用 claude -p 调用。"""

    def __init__(
        self,
        model: Optional[str] = None,
        allow_auto_approve: Optional[bool] = None,
        allow_nested_claude: Optional[bool] = None,
    ):
        super().__init__(
            cli_command="claude",
            model=model,
            allow_auto_approve=allow_auto_approve,
            allow_nested_claude=allow_nested_claude,
        )
        self.platform = "claude"

    def _call_cli(self, prompt: str) -> str:
        """调用 claude -p 执行单次查询。"""
        cmd = ["claude", "-p", prompt, "--output-format", "text"]
        if self.model:
            cmd.extend(["--model", self.model])

        env = self._nested_env()

        result = subprocess.run(
            cmd,
            input="",
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude -p 退出码 {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )
        return result.stdout

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        **kwargs,
    ) -> bool:
        """
        Claude 原生触发测试 - 真的把技能加到 .claude/commands/ 里，
        然后用 claude -p 跑查询，看它会不会选这个技能。
        """
        import uuid
        from pathlib import Path

        # 在 Claude Code 里跑嵌套调用会撞上宿主的递归护栏（CLAUDECODE）。
        # 默认不静默绕开它——需要用户显式同意，否则明说这次没跑，而不是假装"没触发"。
        if "CLAUDECODE" in os.environ and not self.allow_nested_claude:
            print(
                "❌ 触发测试需要嵌套调用 `claude -p`，但当前进程在 Claude Code 内运行。\n"
                "   去掉 CLAUDECODE 才能嵌套，那会绕过宿主的递归护栏，所以默认不做。\n"
                "   同意的话加参数 --allow-nested-claude（或设 SKILL_CREATOR_ALLOW_NESTED_CLAUDE=1）后重跑。\n"
                "   注意：本条的判定结果不可信（不是「没触发」，是压根没跑成），请勿据此改 description。",
                file=sys.stderr,
            )
            return False

        unique_id = uuid.uuid4().hex[:8]
        clean_name = f"{skill_name}-test-{unique_id}"

        # 找项目根目录（找 .claude/ 目录），但向上找的边界卡在家目录之前。
        # 很多人 `~/.claude` 是全局配置，一路找到那里就等于往用户的**全局命令目录**
        # 写文件、还让嵌套进程以家目录为工作目录——那两件事都不该静默发生。
        # 项目里没有 `.claude` 就用当前目录兜底，副作用始终留在项目内。
        cwd = Path.cwd()
        home = Path.home()
        project_root = cwd
        for parent in [cwd, *cwd.parents]:
            if parent == home:
                break
            if (parent / ".claude").is_dir():
                project_root = parent
                break

        commands_dir = project_root / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        command_file = commands_dir / f"{clean_name}.md"

        # 明示会动到哪个目录，别让它在后台默认发生
        scope = "你的全局命令目录" if project_root == home else "当前项目"
        self._notice_once(
            "claude-project-commands",
            f"提示：Claude 触发测试会在{scope}里写临时命令文件 {command_file}，跑完即删（进程被强杀可能残留）。",
        )

        try:
            # 写一个临时 command 文件
            indented_desc = "\n  ".join(skill_description.split("\n"))
            command_content = (
                f"---\n"
                f"description: |\n"
                f"  {indented_desc}\n"
                f"---\n\n"
                f"# {skill_name}\n\n"
                f"This skill handles: {skill_description}\n"
            )
            command_file.write_text(command_content)

            # 跑 claude -p，检测有没有调用这个技能
            cmd = [
                "claude",
                "-p", user_query,
                "--output-format", "stream-json",
                "--verbose",
            ]
            if self.model:
                cmd.extend(["--model", self.model])

            env = self._nested_env()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=project_root,
                env=env,
            )

            triggered = False
            buffer = ""
            pending_tool_name = None
            accumulated_json = ""

            timeout = kwargs.get("timeout", 60)

            try:
                for chunk in _iter_stdout_chunks(process, timeout):
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # 检查 stream 事件
                        if event.get("type") == "stream_event":
                            se = event.get("event", {})
                            se_type = se.get("type", "")

                            if se_type == "content_block_start":
                                cb = se.get("content_block", {})
                                if cb.get("type") == "tool_use":
                                    tool_name = cb.get("name", "")
                                    if tool_name in ("Skill", "Read"):
                                        pending_tool_name = tool_name
                                        accumulated_json = ""

                            elif se_type == "content_block_delta" and pending_tool_name:
                                delta = se.get("delta", {})
                                if delta.get("type") == "input_json_delta":
                                    accumulated_json += delta.get("partial_json", "")
                                    if clean_name in accumulated_json:
                                        return True

                        # 完整 assistant 消息
                        elif event.get("type") == "assistant":
                            message = event.get("message", {})
                            for content_item in message.get("content", []):
                                if content_item.get("type") != "tool_use":
                                    continue
                                tool_name = content_item.get("name", "")
                                tool_input = content_item.get("input", {})
                                if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                                    triggered = True
                                elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                                    triggered = True
                                return triggered

                        elif event.get("type") == "result":
                            return triggered
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

            return triggered
        finally:
            if command_file.exists():
                command_file.unlink()


class WorkBuddyNativeCLIClient(NativeCLIClient):
    """
    WorkBuddy / CodeBuddy 原生客户端 - 用 codebuddy -p 调用。

    比通用模式更准确，因为可以往 ~/.codebuddy/commands/ 里放临时命令文件，
    然后真的让模型在技能列表里选，检测触发行为。
    """

    def __init__(
        self,
        model: Optional[str] = None,
        allow_auto_approve: Optional[bool] = None,
        allow_nested_claude: Optional[bool] = None,
    ):
        cli = shutil.which("workbuddy") or shutil.which("codebuddy") or "codebuddy"
        super().__init__(
            cli_command=cli,
            model=model,
            allow_auto_approve=allow_auto_approve,
            allow_nested_claude=allow_nested_claude,
        )
        self.platform = "workbuddy"

    def _call_cli(self, prompt: str) -> str:
        """调用 codebuddy -p 执行单次查询。"""
        cmd = [self.cli_command, "-p", prompt, *self._auto_approve_args()]
        if self.model:
            cmd.extend(["--model", self.model])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{self.cli_command} 退出码 {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )
        return result.stdout

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        **kwargs,
    ) -> bool:
        """
        WorkBuddy 原生触发测试 - 真的把技能加到 ~/.codebuddy/commands/ 里，
        然后用 codebuddy -p 跑查询，看它会不会选这个技能。
        """
        import uuid
        from pathlib import Path

        unique_id = uuid.uuid4().hex[:8]
        clean_name = f"{skill_name}-test-{unique_id}"

        # 找 commands 目录
        home = Path.home()
        commands_dir = home / ".codebuddy" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        command_file = commands_dir / f"{clean_name}.md"

        # 嵌套进程的工作目录放在临时目录里，别让相对路径落到用户家目录
        run_dir = tempfile.mkdtemp(prefix="skill-creator-trigger-")

        # 明示会动到你机器上的哪个位置
        self._notice_once(
            "codebuddy-commands",
            f"提示：WorkBuddy 触发测试会在你的全局命令目录写临时文件 {command_file}，"
            f"跑完即删（进程被强杀可能残留）；嵌套进程工作目录为临时目录 {run_dir}。",
        )

        try:
            # 写一个临时 command 文件
            indented_desc = "\n  ".join(skill_description.split("\n"))
            command_content = (
                f"---\n"
                f"description: |\n"
                f"  {indented_desc}\n"
                f"---\n\n"
                f"# {skill_name}\n\n"
                f"This skill handles: {skill_description}\n"
            )
            command_file.write_text(command_content)

            # 跑 codebuddy -p，检测有没有调用这个技能
            cmd = [
                self.cli_command,
                "-p", user_query,
                "--output-format", "stream-json",
                "--verbose",
                *self._auto_approve_args(),
            ]
            if self.model:
                cmd.extend(["--model", self.model])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=run_dir,
            )

            triggered = False
            buffer = ""

            timeout = kwargs.get("timeout", 60)

            try:
                for chunk in _iter_stdout_chunks(process, timeout):
                    buffer += chunk.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        # 检查 stream 事件里有没有调用自定义命令
                        # CodeBuddy 的 stream-json 格式和 Claude 类似，
                        # 但不再用 json.dumps 全文搜索——太粗放，
                        # stderr 回显、命令日志里出现 clean_name 都会误判。
                        # 改成结构化解析：只在 tool_use / command 调用字段里检查。
                        event_type = event.get("type", "")
                        se = event.get("event", {}) if event_type == "stream_event" else event

                        # 1) stream_event 里的 content_block_start / assistant
                        se_type = se.get("type", "")
                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if clean_name in tool_name:
                                    triggered = True
                                    break
                        elif se_type == "content_block_delta":
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                partial = delta.get("partial_json", "")
                                # 积累到一定程度时尝试解析
                                if clean_name in partial and len(partial) > 20:
                                    triggered = True
                                    break
                        elif event_type == "assistant" or se_type == "assistant":
                            message = se.get("message", se)
                            for content_item in message.get("content", []):
                                if content_item.get("type") != "tool_use":
                                    continue
                                tool_name = content_item.get("name", "")
                                tool_input = content_item.get("input", {})
                                if clean_name in tool_name:
                                    triggered = True
                                    break
                                # 检查 command / skill 字段
                                for field in ("command", "skill", "file_path"):
                                    val = str(tool_input.get(field, ""))
                                    if clean_name in val:
                                        triggered = True
                                        break
                            if triggered:
                                break
                        elif event_type == "result":
                            # 最终结果事件，检查有没有 command 调用
                            for cmd_info in event.get("commands_used", []):
                                if clean_name in str(cmd_info.get("name", "")):
                                    triggered = True
                                    break

                # 最后再检查一下剩余 buffer
                if clean_name in buffer:
                    triggered = True

            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

            return triggered
        finally:
            if command_file.exists():
                command_file.unlink()
            shutil.rmtree(run_dir, ignore_errors=True)


class CodexNativeCLIClient(NativeCLIClient):
    """
    OpenAI Codex 原生客户端 - 用 codex exec 调用。

    比通用模式更准确，因为用的是"任务中决策"模式——
    不是事后问模型"该不该触发"，而是让它在真实处理任务的过程中
    自己判断要不要使用这个技能。
    """

    def __init__(self, model: Optional[str] = None):
        super().__init__(cli_command="codex", model=model)
        self.platform = "codex"

    def _call_cli(self, prompt: str) -> str:
        """调用 codex exec 执行单次查询。"""
        cmd = ["codex", "exec", prompt]
        if self.model:
            cmd.extend(["-m", self.model])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"codex exec 退出码 {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )
        return result.stdout

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        **kwargs,
    ) -> bool:
        """
        Codex 触发测试 - 任务中决策模式。

        不是事后问模型"该不该触发"，而是把技能描述注入到任务上下文里，
        让模型在真实处理用户查询的过程中自己判断要不要使用这个技能。
        通过输出标记来检测它的决策。

        安全措施：用随机 UUID 标记替代可预测格式，并在 user_query 中
        剥离标记前缀，防止 prompt injection 伪造触发结果。
        """
        import uuid

        # 用随机 UUID 生成不可预测的标记，防止 user_query 里包含标记导致误判
        marker_id = uuid.uuid4().hex[:12]
        marker = f"[SKILL_TRIGGER:{marker_id}]"

        # 从 user_query 里剥离任何看起来像触发标记的内容，防注入
        sanitized_query = re.sub(r'\[SKILL_TRIGGER:[^\]]*\]', '', user_query)

        # 构造一个带技能选择的 prompt
        # 让模型在真实处理任务的过程中做决策，而不是事后当裁判
        system_instruction = f"""你现在是一个智能助手。你有一个可用的技能：

【技能：{skill_name}】
{skill_description}

【使用规则】
- 如果用户的查询确实需要这个技能的专业能力、流程框架或工具集，请在回答的**第一行**写：{marker}
- 然后再给出正常的回答内容
- 如果用户的查询用基础能力就能直接完成，或者和这个技能不相关，就直接回答，不要写上面的标记
- 简单的一步任务（读个文件、写个简单文本）通常不需要技能
- 复杂的、多步骤的、专业领域的任务通常需要技能

现在请处理下面的用户查询：
"""

        full_prompt = system_instruction + sanitized_query

        try:
            output = self._call_cli(full_prompt)
            # 检查输出里有没有触发标记
            return marker in output
        except Exception as e:
            # 如果失败了，降级到纯文本判断
            print(f"Warning: Codex trigger_test 失败，降级到文本判断: {e}", file=sys.stderr)
            return self._trigger_test_text_fallback(user_query, skill_name, skill_description)


class OpenClawNativeCLIClient(NativeCLIClient):
    """
    OpenClaw 原生客户端 - 用 openclaw agent exec 调用。

    比通用模式更准确，因为用的是"任务中决策"模式——
    不是事后问模型"该不该触发"，而是让它在真实处理任务的过程中
    自己判断要不要使用这个技能。
    """

    def __init__(self, model: Optional[str] = None):
        super().__init__(cli_command="openclaw", model=model)
        self.platform = "openclaw"

    def _call_cli(self, prompt: str) -> str:
        """调用 openclaw agent exec 执行单次查询。"""
        cmd = ["openclaw", "agent", "exec", prompt, "--json"]
        if self.model:
            cmd.extend(["--model", self.model])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"openclaw agent exec 退出码 {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )
        return result.stdout

    def trigger_test(
        self,
        user_query: str,
        skill_name: str,
        skill_description: str,
        **kwargs,
    ) -> bool:
        """
        OpenClaw 触发测试 - 任务中决策模式。

        不是事后问模型"该不该触发"，而是把技能描述注入到任务上下文里，
        让模型在真实处理用户查询的过程中自己判断要不要使用这个技能。
        通过输出标记来检测它的决策。

        安全措施：用随机 UUID 标记替代可预测格式，并在 user_query 中
        剥离标记前缀，防止 prompt injection 伪造触发结果。
        """
        import uuid

        # 用随机 UUID 生成不可预测的标记，防止 user_query 里包含标记导致误判
        marker_id = uuid.uuid4().hex[:12]
        marker = f"[SKILL_TRIGGER:{marker_id}]"

        # 从 user_query 里剥离任何看起来像触发标记的内容，防注入
        sanitized_query = re.sub(r'\[SKILL_TRIGGER:[^\]]*\]', '', user_query)

        # 构造一个带技能选择的 prompt
        system_instruction = f"""你现在是一个智能助手。你有一个可用的技能：

【技能：{skill_name}】
{skill_description}

【使用规则】
- 如果用户的查询确实需要这个技能的专业能力、流程框架或工具集，请在回答的**第一行**写：{marker}
- 然后再给出正常的回答内容
- 如果用户的查询用基础能力就能直接完成，或者和这个技能不相关，就直接回答，不要写上面的标记
- 简单的一步任务（读个文件、写个简单文本）通常不需要技能
- 复杂的、多步骤的、专业领域的任务通常需要技能

现在请处理下面的用户查询：
"""

        full_prompt = system_instruction + sanitized_query

        try:
            output = self._call_cli(full_prompt)
            # 检查输出里有没有触发标记
            return marker in output
        except Exception as e:
            print(f"Warning: OpenClaw trigger_test 失败，降级到文本判断: {e}", file=sys.stderr)
            return self._trigger_test_text_fallback(user_query, skill_name, skill_description)


class GenericNativeCLIClient(NativeCLIClient):
    """
    通用原生 CLI 客户端 - 兜底方案。

    假设 CLI 的用法是：`<cli> -p "prompt"` 返回文本结果。

    预留：当前 build_client_from_args 尚未接入本类——已识别的平台各有专门客户端，
    未识别的平台走通用 API 模式。等有通用 CLI 平台需要时再启用。
    """

    def __init__(self, cli_command: str, platform_name: str, model: Optional[str] = None):
        super().__init__(cli_command=cli_command, model=model)
        self.platform = platform_name

    def _call_cli(self, prompt: str) -> str:
        """调用 CLI，假设是 <cli> -p "prompt" 这种格式。"""
        cmd = [self.cli_command, "-p", prompt]
        if self.model:
            cmd.extend(["--model", self.model])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"{self.cli_command} 退出码 {result.returncode}\n"
                f"stderr: {result.stderr[:500]}"
            )
        return result.stdout


from dataclasses import dataclass


@dataclass
class ClientConfig:
    """LLM 客户端配置，替代旧的 FakeArgs 模式。

    所有字段都有默认值 None，表示"未显式设置"，
    让 build_client_from_args 能区分"用户没传"和"用户传了 None"。
    """
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    allow_auto_approve: Optional[bool] = None
    allow_nested_claude: Optional[bool] = None


def _get_attr(args, name: str, default=None):
    """从 args 对象（argparse Namespace 或 ClientConfig）统一取属性。"""
    return getattr(args, name, default)


def _explicit_flag(args, name: str) -> Optional[bool]:
    """只在用户显式传了开关时返回 True，否则返回 None 让客户端去读环境变量。"""
    val = _get_attr(args, name, False)
    return True if val else None


def _print_spawn_boundary(client) -> None:
    """把嵌套子进程的权限边界明示出来，不让它在后台默认发生。"""
    if not isinstance(client, NativeCLIClient):
        return
    auto = "开（该子进程的确认提示被关闭）" if client.allow_auto_approve else "关"
    nested = "开（已绕过宿主递归护栏）" if client.allow_nested_claude else "关"
    print(f"嵌套子进程权限边界：自动确认={auto} / 剔除 CLAUDECODE={nested}", file=sys.stderr)


def _announce_platform_override(platform: str) -> None:
    """显式覆盖必须在 stderr 里说清楚。

    两头都要防：拼错的值不能静默失效（用户会以为开关生效了，实际走了自动检测）；
    生效的值也要留痕——.zshrc 里残留的覆盖会长期劫持自动检测，不说不出来没人发现。
    """
    forced = override_platform()
    if forced is None:
        return
    if forced not in KNOWN_PLATFORMS:
        print(
            f"警告：{PLATFORM_OVERRIDE_ENV}={forced} 不是已知平台，已忽略并退回自动检测；"
            f"可选值：{'、'.join(sorted(KNOWN_PLATFORMS))}",
            file=sys.stderr,
        )
    elif forced == platform:
        print(f"平台由 {PLATFORM_OVERRIDE_ENV}={forced} 显式指定（非自动检测）", file=sys.stderr)


def build_client_from_args(args):
    """
    从命令行参数或 ClientConfig 构建 LLM 客户端。
    自动检测当前平台，优先用原生 CLI 模式，降级到通用 API 模式。

    Args:
        args: argparse.Namespace（命令行）或 ClientConfig（编程式调用）
    """
    # 如果用户手动指定了 --api-key，就用通用 API 模式
    api_key = _get_attr(args, "api_key")
    if api_key:
        global _warned_api_key_override
        native = detect_platform()
        if native in ("claude", "codex", "workbuddy", "openclaw") and not _warned_api_key_override:
            _warned_api_key_override = True
            print(
                f"提示：检测到 {native} 平台，但存在 OPENAI_API_KEY，已改用通用 API 模式；"
                "如需原生触发测试（精度更高），请 unset OPENAI_API_KEY。",
                file=sys.stderr,
            )
        return LLMClient(
            api_key=api_key,
            base_url=_get_attr(args, "base_url"),
            model=_get_attr(args, "model"),
        )

    # 自动检测平台（只检测这一次：下面打印和分支选择共用同一份结果，
    # 否则打印出的平台可能和实际走的分支对不上）
    platform, confidence = detect_platform_detail()
    model = _get_attr(args, "model")
    spawn_flags = {
        "allow_auto_approve": _explicit_flag(args, "allow_auto_approve"),
        "allow_nested_claude": _explicit_flag(args, "allow_nested_claude"),
    }

    # 显式覆盖（如果有）要和检测结果一起说清楚，且必须在结果行之前
    _announce_platform_override(platform)
    print(format_detection(platform, confidence), file=sys.stderr)

    # 根据平台选择原生客户端
    if platform == "claude":
        print("使用 Claude 原生 CLI 模式", file=sys.stderr)
        client = ClaudeNativeClient(model=model, **spawn_flags)

    elif platform == "codex":
        print("使用 Codex 原生 CLI 模式", file=sys.stderr)
        client = CodexNativeCLIClient(model=model)

    elif platform == "workbuddy":
        print("使用 WorkBuddy 原生 CLI 模式", file=sys.stderr)
        client = WorkBuddyNativeCLIClient(model=model, **spawn_flags)

    elif platform == "openclaw":
        print("使用 OpenClaw 原生 CLI 模式", file=sys.stderr)
        client = OpenClawNativeCLIClient(model=model)

    # 豆包工作和其他默认走通用 API 模式
    else:
        print("使用通用 OpenAI 兼容 API 模式", file=sys.stderr)
        client = LLMClient(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=_get_attr(args, "base_url"),
            model=model,
        )

    _print_spawn_boundary(client)
    return client


def add_common_args(parser):
    """向 argparse parser 添加通用的 LLM 参数。"""
    parser.add_argument("--api-key", default=None, help="API Key（也可用环境变量 OPENAI_API_KEY）")
    parser.add_argument("--base-url", default=None, help="API Base URL（也可用环境变量 OPENAI_BASE_URL）")
    parser.add_argument("--model", default=None, help="模型名称（也可用环境变量 OPENAI_MODEL）")
    parser.add_argument(
        "--allow-auto-approve",
        action="store_true",
        help="允许嵌套 CLI 关闭确认提示（如 codebuddy 的 -y）。默认关闭：开了等于让该子进程不经确认执行工具",
    )
    parser.add_argument(
        "--allow-nested-claude",
        action="store_true",
        help="允许剔除 CLAUDECODE，以在 Claude Code 内部嵌套调用。默认关闭：开了等于绕过宿主递归护栏",
    )
    return parser
