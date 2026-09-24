#!/usr/bin/env python3
"""
运行技能描述的触发率评估。

测试某个技能的 description 面对一组查询时，触发准确率如何。
输出结果为 JSON。

自动检测运行平台，优先用原生 CLI 模式（Claude/Codex/WorkBuddy/OpenClaw），
降级到通用 OpenAI API 模式。
"""

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md
from scripts.llm_client import build_client_from_args, add_common_args
from scripts.platform_detect import detect_platform


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
) -> bool:
    """
    运行单个查询，返回是否触发了技能。

    自动检测当前平台，用对应的原生方式或通用 API 模式做触发测试。
    """
    try:
        # 构建一个简化的 args 对象传给 build_client_from_args
        import os
        class FakeArgs:
            pass
        FakeArgs.api_key = os.environ.get("OPENAI_API_KEY")
        FakeArgs.base_url = os.environ.get("OPENAI_BASE_URL")
        FakeArgs.model = model

        client = build_client_from_args(FakeArgs())
        # 触发测试：原生 CLI 模式会用真实验证，通用模式用 function calling 模拟
        triggered = client.trigger_test(query, skill_name, skill_description)
        return triggered
    except Exception as e:
        print(f"Warning: 查询失败: {e}", file=sys.stderr)
        return False


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    model: str | None = None,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
) -> dict:
    """运行完整的测试集并返回结果。"""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_triggers: dict[str, list[bool]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_triggers:
                query_triggers[query] = []
            try:
                query_triggers[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_triggers[query].append(False)

    for query, triggers in query_triggers.items():
        item = query_items[query]
        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        results.append({
            "query": query,
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        })

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="运行技能描述的触发率评估（自动检测平台）"
    )
    parser.add_argument("--eval-set", required=True, help="测试集 JSON 文件路径")
    parser.add_argument("--skill-path", required=True, help="技能目录路径")
    parser.add_argument("--description", default=None, help="覆盖要测试的描述")
    parser.add_argument("--num-workers", type=int, default=5, help="并行 worker 数量")
    parser.add_argument("--timeout", type=int, default=60, help="每个查询的超时时间（秒）")
    parser.add_argument("--runs-per-query", type=int, default=3, help="每个查询跑几次")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="触发率通过阈值")
    parser = add_common_args(parser)
    parser.add_argument("--verbose", action="store_true", help="输出进度信息")
    args = parser.parse_args()

    # 先检测平台
    platform = detect_platform()
    print(f"检测到运行平台：{platform}", file=sys.stderr)

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"错误：在 {skill_path} 找不到 SKILL.md", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"正在评估: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        model=args.model,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"结果: {summary['passed']}/{summary['total']} 通过", file=sys.stderr)
        for r in output["results"]:
            status = "通过" if r["pass"] else "未通过"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] 触发率={rate_str} 预期={'触发' if r['should_trigger'] else '不触发'}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
