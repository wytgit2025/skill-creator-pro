#!/usr/bin/env python3
"""
根据评估结果改进技能描述。

接收评估结果（来自 run_eval.py），调用 LLM 生成改进后的描述。
自动检测运行平台，优先用原生 CLI 模式，降级到通用 API 模式。
"""

import argparse
import json
import re
import sys
from pathlib import Path

from scripts.utils import parse_skill_md
from scripts.llm_client import build_client_from_args, add_common_args
from scripts.platform_detect import detect_platform


def improve_description(
    skill_name: str,
    skill_content: str,
    current_description: str,
    eval_results: dict,
    history: list[dict],
    model: str | None = None,
    log_dir: Path | None = None,
    iteration: int | None = None,
    allow_auto_approve: bool | None = None,
    allow_nested_claude: bool | None = None,
) -> str:
    """调用 LLM 并根据评估结果改进描述。"""
    failed_triggers = [
        r for r in eval_results["results"]
        if r["should_trigger"] and not r["pass"]
    ]
    false_triggers = [
        r for r in eval_results["results"]
        if not r["should_trigger"] and not r["pass"]
    ]

    train_score = f"{eval_results['summary']['passed']}/{eval_results['summary']['total']}"
    scores_summary = f"当前得分: {train_score}"

    prompt = f"""你正在优化一个名为 "{skill_name}" 的技能的描述。

技能是什么？技能就像一个带渐进式加载的提示词——有一个标题和描述，模型在决定要不要使用这个技能时会看到它们；如果决定用了，才会去读 SKILL.md 文件里的详细内容，以及技能文件夹里的其他辅助文件和脚本。

描述会出现在模型的"可用技能列表"里。用户发一个查询过来，模型只根据标题和这段描述来判断要不要调用技能。你的目标是写一个描述：相关查询能触发，不相关查询不触发。

当前描述：
<current_description>
"{current_description}"
</current_description>

当前得分 ({scores_summary})：
<scores_summary>
"""
    if failed_triggers:
        prompt += "【应该触发但没触发】：\n"
        for r in failed_triggers:
            prompt += f'  - "{r["query"]}"（触发了 {r["triggers"]}/{r["runs"]} 次）\n'
        prompt += "\n"

    if false_triggers:
        prompt += "【不该触发却触发了】：\n"
        for r in false_triggers:
            prompt += f'  - "{r["query"]}"（触发了 {r["triggers"]}/{r["runs"]} 次）\n'
        prompt += "\n"

    if history:
        prompt += "【之前的尝试——不要重复这些，试试结构上不同的写法】：\n\n"
        for h in history:
            train_s = f"{h.get('train_passed', h.get('passed', 0))}/{h.get('train_total', h.get('total', 0))}"
            score_str = f"得分={train_s}"
            prompt += f'<attempt {score_str}>\n'
            prompt += f'描述: "{h["description"]}"\n'
            if "results" in h:
                prompt += "训练集结果:\n"
                for r in h["results"]:
                    status = "通过" if r["pass"] else "未通过"
                    prompt += f'  [{status}] "{r["query"][:80]}"（触发 {r["triggers"]}/{r["runs"]}）\n'
            prompt += "</attempt>\n\n"

    prompt += f"""</scores_summary>

技能内容（供参考，了解这个技能是做什么的）：
<skill_content>
{skill_content}
</skill_content>

根据这些失败案例，写一个新的、改进的描述，让触发更准确。注意——不要过拟合到眼前这几个具体案例上，要从失败中提炼出更宽泛的用户意图类别，说明这个技能在哪些场景下有用、哪些场景下没用。原因有两个：

1. 避免过拟合
2. 这段描述会被注入到所有查询的上下文里，技能很多的时候，别在单个描述上浪费太多空间

具体来说，描述不要超过 100-200 词，就算牺牲一点准确率也没关系。有 1024 字符的硬上限——超过会被截断，所以留足余量。

一些写作技巧：
- 用祈使句——"使用此技能进行..."而不是"这个技能做..."
- 聚焦用户的意图（他们想达成什么），而不是技能怎么实现
- 描述要和其他技能区分开，有辨识度
- 如果试了好几次还不行，换个思路。试试不同的句式和措辞

多试几种风格没关系，最后我们会选得分最高的那个。

请只输出新的描述文本，用 <new_description> 标签包起来，不要别的内容。"""

    # 构建客户端（自动检测平台）
    class FakeArgs:
        api_key = None
        base_url = None

    # 类体里写 `model = model` 会 NameError——类体读不到外层函数作用域，只能在定义之后赋值
    FakeArgs.model = model
    FakeArgs.allow_auto_approve = allow_auto_approve
    FakeArgs.allow_nested_claude = allow_nested_claude

    client = build_client_from_args(FakeArgs())
    text = client.chat_text([{"role": "user", "content": prompt}], temperature=0.7, max_tokens=1024)

    match = re.search(r"<new_description>(.*?)</new_description>", text, re.DOTALL)
    description = match.group(1).strip().strip('"') if match else text.strip().strip('"')

    transcript: dict = {
        "iteration": iteration,
        "prompt": prompt,
        "response": text,
        "parsed_description": description,
        "char_count": len(description),
        "over_limit": len(description) > 1024,
    }

    # 安全网：如果超了 1024 字符，再调一次让它缩短
    if len(description) > 1024:
        shorten_prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"之前的尝试生成了一个描述，有 {len(description)} 字符，超过了 1024 字符的硬上限：\n\n"
            f'"{description}"\n\n'
            f"把它压缩到 1024 字符以内，保留最重要的触发词和意图覆盖。"
            f"只输出新的描述，用 <new_description> 标签包起来。"
        )
        shorten_text = client.chat_text([{"role": "user", "content": shorten_prompt}], temperature=0.5, max_tokens=1024)
        match = re.search(r"<new_description>(.*?)</new_description>", shorten_text, re.DOTALL)
        shortened = match.group(1).strip().strip('"') if match else shorten_text.strip().strip('"')

        transcript["rewrite_prompt"] = shorten_prompt
        transcript["rewrite_response"] = shorten_text
        transcript["rewrite_description"] = shortened
        transcript["rewrite_char_count"] = len(shortened)
        description = shortened

    transcript["final_description"] = description

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"improve_iter_{iteration or 'unknown'}.json"
        log_file.write_text(json.dumps(transcript, indent=2, ensure_ascii=False))

    return description


def main():
    parser = argparse.ArgumentParser(
        description="根据评估结果改进技能描述（自动检测平台）"
    )
    parser.add_argument("--eval-results", required=True, help="评估结果 JSON 路径（来自 run_eval.py）")
    parser.add_argument("--skill-path", required=True, help="技能目录路径")
    parser.add_argument("--history", default=None, help="历史记录 JSON 路径（之前的尝试）")
    parser = add_common_args(parser)
    parser.add_argument("--verbose", action="store_true", help="输出调试信息")
    args = parser.parse_args()

    # 先检测平台
    platform = detect_platform()
    print(f"检测到运行平台：{platform}", file=sys.stderr)

    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"错误：在 {skill_path} 找不到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    eval_results = json.loads(Path(args.eval_results).read_text())
    history = []
    if args.history:
        history = json.loads(Path(args.history).read_text())

    name, _, content = parse_skill_md(skill_path)
    current_description = eval_results["description"]

    if args.verbose:
        print(f"当前: {current_description}", file=sys.stderr)
        print(f"得分: {eval_results['summary']['passed']}/{eval_results['summary']['total']}", file=sys.stderr)

    new_description = improve_description(
        skill_name=name,
        skill_content=content,
        current_description=current_description,
        eval_results=eval_results,
        history=history,
        model=args.model,
        allow_auto_approve=args.allow_auto_approve,
        allow_nested_claude=args.allow_nested_claude,
    )

    if args.verbose:
        print(f"改进后: {new_description}", file=sys.stderr)

    output = {
        "description": new_description,
        "history": history + [{
            "description": current_description,
            "passed": eval_results["summary"]["passed"],
            "failed": eval_results["summary"]["failed"],
            "total": eval_results["summary"]["total"],
            "results": eval_results["results"],
        }],
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
