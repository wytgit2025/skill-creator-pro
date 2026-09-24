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
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md
from scripts.llm_client import build_client_from_args, add_common_args, ClientConfig
from scripts.platform_detect import detect_platform, describe_detection

# 已提示过"未配置 API Key"一次，避免并行 worker 刷屏
_warned_no_api_key = False

# 正例通过率低于这个比例，说明测试工具的刻度盘塌到地板了：
# 负例只要"不触发"就全部算通过，所以「从不触发」的假描述也能白拿约一半总分；
# 正例通过率不过半时，真描述和假描述的总分处在同一数量级，差异无法解读。
_MIN_POSITIVE_PASS_RATE = 0.5


def diagnose_results(results: list[dict]) -> dict:
    """
    对「测试工具本身」做自检。

    这套工具会照常吐出一个百分比，即使它已经失去区分度——
    所以必须主动判断"这次测量到底可不可信"，而不是把数字直接当结论。
    """
    positives = [r for r in results if r["should_trigger"]]
    negatives = [r for r in results if not r["should_trigger"]]
    pos_passed = sum(1 for r in positives if r["pass"])
    neg_passed = sum(1 for r in negatives if r["pass"])
    warnings: list[str] = []

    if not positives:
        warnings.append("测试集没有正例（should_trigger=true），正负分层失效")
    if not negatives:
        warnings.append("测试集没有负例（should_trigger=false），正负分层失效")

    if results and all(r["triggers"] == 0 for r in results):
        warnings.append(
            "所有查询触发率均为 0——通常是客户端/网络故障，或测试工具无区分度；"
            "不要把它读成「技能不触发」"
        )

    if positives:
        pos_rate = pos_passed / len(positives)
        if pos_rate < _MIN_POSITIVE_PASS_RATE:
            warnings.append(
                f"正例通过率仅 {pos_rate:.0%}（低于 {_MIN_POSITIVE_PASS_RATE:.0%}）："
                "该环境下测试工具区分度不足，改前改后都会落在这个区间，结论不可用"
            )

    return {
        "positives": len(positives),
        "positives_passed": pos_passed,
        "negatives": len(negatives),
        "negatives_passed": neg_passed,
        "discriminative": not warnings,
        "warnings": warnings,
    }


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
    allow_auto_approve: bool | None = None,
    allow_nested_claude: bool | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> bool:
    """
    运行单个查询，返回是否触发了技能。

    自动检测当前平台，用对应的原生方式或通用 API 模式做触发测试。

    api_key / base_url 优先于环境变量：命令行传了 `--api-key` 就必须生效，
    否则会静默退回无凭据状态（本函数历史上只读环境变量，导致 `--api-key` 是空操作）。
    """
    try:
        config = ClientConfig(
            api_key=api_key or os.environ.get("OPENAI_API_KEY") or None,
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
            model=model,
            allow_auto_approve=allow_auto_approve,
            allow_nested_claude=allow_nested_claude,
        )
        client = build_client_from_args(config)
        # 触发测试：原生 CLI 模式会用真实验证，通用模式用 function calling 模拟
        triggered = client.trigger_test(query, skill_name, skill_description)
        return triggered
    except ValueError as e:
        global _warned_no_api_key
        if "API Key" in str(e) and not _warned_no_api_key:
            _warned_no_api_key = True
            print(
                "提示：未配置 API Key（且无原生 CLI），触发测试无法真正执行，"
                "结果不可信，请勿据此改 description。这类环境请改用对话内手动模式。"
                f"详情：{e}",
                file=sys.stderr,
            )
            return False
        print(f"Warning: 查询失败: {e}", file=sys.stderr)
        return False
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
    allow_auto_approve: bool | None = None,
    allow_nested_claude: bool | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict:
    """运行完整的测试集并返回结果。"""
    results = []

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
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
                    allow_auto_approve,
                    allow_nested_claude,
                    api_key,
                    base_url,
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
        "diagnostics": diagnose_results(results),
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

    # 先检测平台（弱信号会提示）
    print(describe_detection(), file=sys.stderr)

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
        allow_auto_approve=args.allow_auto_approve,
        allow_nested_claude=args.allow_nested_claude,
        api_key=args.api_key,
        base_url=args.base_url,
    )

    # 测量本身不可信时必须说出来，不能只吐一个看着正常的百分比
    for warning in output.get("diagnostics", {}).get("warnings", []):
        print(f"⚠️ 测试工具自检未通过：{warning}", file=sys.stderr)

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
