#!/usr/bin/env python3
"""
LLM 客户端 - 支持五平台原生调用 + OpenAI 兼容 API

支持的平台：
1. Claude（原生 claude CLI）- 用 claude -p 调用，trigger 测试最准
2. OpenAI Codex（原生 codex CLI）
3. 腾讯 WorkBuddy（原生 workbuddy CLI）
4. OpenClaw（原生 claw CLI）
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
import subprocess
import sys
import requests
from typing import Optional

from scripts.platform_detect import detect_platform


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


class NativeCLIClient:
    """
    原生 CLI 客户端基类 - 用平台自己的 CLI 命令调用模型。

    比通用 API 模式更准确，因为用的是平台原生的技能加载和触发机制。
    """

    def __init__(self, cli_command: str, model: Optional[str] = None):
        self.cli_command = cli_command
        self.model = model
        self.platform = "unknown"

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

    def __init__(self, model: Optional[str] = None):
        super().__init__(cli_command="claude", model=model)
        self.platform = "claude"

    def _call_cli(self, prompt: str) -> str:
        """调用 claude -p 执行单次查询。"""
        cmd = ["claude", "-p", prompt, "--output-format", "text"]
        if self.model:
            cmd.extend(["--model", self.model])

        # 去掉 CLAUDECODE 环境变量，允许嵌套调用
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

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

        unique_id = uuid.uuid4().hex[:8]
        clean_name = f"{skill_name}-test-{unique_id}"

        # 找项目根目录（找 .claude/ 目录）
        cwd = Path.cwd()
        project_root = cwd
        for parent in [cwd, *cwd.parents]:
            if (parent / ".claude").is_dir():
                project_root = parent
                break

        commands_dir = project_root / ".claude" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        command_file = commands_dir / f"{clean_name}.md"

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

            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

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

            import select
            start_time = __import__('time').time()
            timeout = kwargs.get("timeout", 60)

            try:
                while __import__('time').time() - start_time < timeout:
                    if process.poll() is not None:
                        remaining = process.stdout.read()
                        if remaining:
                            buffer += remaining.decode("utf-8", errors="replace")
                        break

                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if not ready:
                        continue

                    chunk = os.read(process.stdout.fileno(), 8192)
                    if not chunk:
                        break
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

    def __init__(self, model: Optional[str] = None):
        import shutil
        cli = shutil.which("workbuddy") or shutil.which("codebuddy") or "codebuddy"
        super().__init__(cli_command=cli, model=model)
        self.platform = "workbuddy"

    def _call_cli(self, prompt: str) -> str:
        """调用 codebuddy -p 执行单次查询。"""
        cmd = [self.cli_command, "-p", prompt, "-y"]
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
                "-y",
            ]
            if self.model:
                cmd.extend(["--model", self.model])

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=home,
            )

            triggered = False
            buffer = ""

            import select
            import time as time_mod
            start_time = time_mod.time()
            timeout = kwargs.get("timeout", 60)

            try:
                while time_mod.time() - start_time < timeout:
                    if process.poll() is not None:
                        remaining = process.stdout.read()
                        if remaining:
                            buffer += remaining.decode("utf-8", errors="replace")
                        break

                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if not ready:
                        continue

                    chunk = os.read(process.stdout.fileno(), 8192)
                    if not chunk:
                        break
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
                        # CodeBuddy 的 stream-json 格式和 Claude 类似
                        event_str = json.dumps(event)
                        if clean_name in event_str:
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
        """
        marker = f"[USE_SKILL: {skill_name}]"

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

        full_prompt = system_instruction + user_query

        try:
            output = self._call_cli(full_prompt)
            # 检查输出里有没有触发标记
            return marker in output
        except Exception as e:
            # 如果失败了，降级到纯文本判断
            print(f"Warning: Codex trigger_test 失败，降级到文本判断: {e}", file=__import__('sys').stderr)
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
        """
        marker = f"[USE_SKILL: {skill_name}]"

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

        full_prompt = system_instruction + user_query

        try:
            output = self._call_cli(full_prompt)
            # 检查输出里有没有触发标记
            return marker in output
        except Exception as e:
            print(f"Warning: OpenClaw trigger_test 失败，降级到文本判断: {e}", file=__import__('sys').stderr)
            return self._trigger_test_text_fallback(user_query, skill_name, skill_description)


class GenericNativeCLIClient(NativeCLIClient):
    """
    通用原生 CLI 客户端 - 兜底方案。

    假设 CLI 的用法是：`<cli> -p "prompt"` 返回文本结果。
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


def build_client_from_args(args):
    """
    从命令行参数构建 LLM 客户端。
    自动检测当前平台，优先用原生 CLI 模式，降级到通用 API 模式。
    """
    # 如果用户手动指定了 --api-key，就用通用 API 模式
    api_key = getattr(args, "api_key", None)
    if api_key:
        return LLMClient(
            api_key=api_key,
            base_url=getattr(args, "base_url", None),
            model=getattr(args, "model", None),
        )

    # 自动检测平台
    platform = detect_platform()
    model = getattr(args, "model", None)

    print(f"检测到运行平台：{platform}", file=sys.stderr)

    # 根据平台选择原生客户端
    if platform == "claude":
        print("使用 Claude 原生 CLI 模式", file=sys.stderr)
        return ClaudeNativeClient(model=model)

    elif platform == "codex":
        print("使用 Codex 原生 CLI 模式", file=sys.stderr)
        return CodexNativeCLIClient(model=model)

    elif platform == "workbuddy":
        print("使用 WorkBuddy 原生 CLI 模式", file=sys.stderr)
        return WorkBuddyNativeCLIClient(model=model)

    elif platform == "openclaw":
        print("使用 OpenClaw 原生 CLI 模式", file=sys.stderr)
        return OpenClawNativeCLIClient(model=model)

    # 豆包工作和其他默认走通用 API 模式
    else:
        print("使用通用 OpenAI 兼容 API 模式", file=sys.stderr)
        return LLMClient(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=getattr(args, "base_url", None),
            model=model,
        )


def add_common_args(parser):
    """向 argparse parser 添加通用的 LLM 参数。"""
    parser.add_argument("--api-key", default=None, help="API Key（也可用环境变量 OPENAI_API_KEY）")
    parser.add_argument("--base-url", default=None, help="API Base URL（也可用环境变量 OPENAI_BASE_URL）")
    parser.add_argument("--model", default=None, help="模型名称（也可用环境变量 OPENAI_MODEL）")
    return parser
