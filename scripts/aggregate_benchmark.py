#!/usr/bin/env python3
"""
把多次运行的结果汇总成基准测试统计数据。

从运行目录里读取 grading.json 文件，产出：
- run_summary：每个指标的平均值、标准差、最小值、最大值
- delta：有技能和没技能两种配置之间的差值

用法：
    python aggregate_benchmark.py <基准测试目录>

示例：
    python aggregate_benchmark.py benchmarks/2026-01-15T10-30-00/

脚本支持两种目录结构：

    工作区结构（skill-creator 迭代用的）：
    <基准测试目录>/
    └── eval-N/
        ├── with_skill/
        │   ├── run-1/grading.json
        │   └── run-2/grading.json
        └── without_skill/
            ├── run-1/grading.json
            └── run-2/grading.json

    旧版结构（带 runs/ 子目录）：
    <基准测试目录>/
    └── runs/
        └── eval-N/
            ├── with_skill/
            │   └── run-1/grading.json
            └── without_skill/
                └── run-1/grading.json
"""

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def calculate_stats(values: list[float]) -> dict:
    """Calculate mean, stddev, min, max for a list of values."""
    if not values:
        return {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0

    return {
        "mean": round(mean, 4),
        "stddev": round(stddev, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4)
    }


# 配置名排序用：带技能的版本必须排在它的基线版本前面，
# 评审页面按这个顺序分组、delta 也按这个顺序做减法。
# 注意先判基线——"without_skill" 也以 "with" 开头。
_BASELINE_PREFIXES = ("without", "old")
_PRIMARY_PREFIXES = ("with", "new")


def order_configs(configs: list[str]) -> list[str]:
    """把带技能的配置排到基线前面。认不出的命名排在中间，同档按名字排。"""
    def rank(name: str) -> int:
        lowered = name.lower()
        if lowered.startswith(_BASELINE_PREFIXES):
            return 2
        if lowered.startswith(_PRIMARY_PREFIXES):
            return 0
        return 1

    return sorted(configs, key=lambda name: (rank(name), name))


def _iter_run_dirs(eval_dir: Path):
    """产出 (config 名, run 目录, run 序号)。

    支持两种布局：SKILL.md 里写的扁平布局 <eval-dir>/<config>/grading.json
    （一个配置一次运行），以及配置下再分 run-N 的多轮布局。
    """
    for config_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
        if (config_dir / "grading.json").exists():
            yield config_dir.name, config_dir, 1
            continue

        for run_dir in sorted(config_dir.glob("run-*")):
            if not (run_dir / "grading.json").exists():
                print(f"警告：{run_dir} 里找不到 grading.json")
                continue
            try:
                run_number = int(run_dir.name.split("-", 1)[1])
            except ValueError:
                run_number = 1
            yield config_dir.name, run_dir, run_number


def _read_eval_meta(eval_dir: Path, fallback_index: int):
    """读 eval_metadata.json 的 eval_id / eval_name，缺了就退回目录名和序号。"""
    meta = {}
    metadata_path = eval_dir / "eval_metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path) as mf:
                meta = json.load(mf)
        except (json.JSONDecodeError, OSError):
            meta = {}

    eval_id = meta.get("eval_id")
    if eval_id is None and eval_dir.name.startswith("eval-"):
        try:
            eval_id = int(eval_dir.name.split("-", 1)[1])
        except ValueError:
            eval_id = None
    if eval_id is None:
        eval_id = fallback_index

    # 目录名是描述性的（SKILL.md 要求），当 eval_name 用正合适
    return eval_id, meta.get("eval_name") or eval_dir.name


def load_run_results(benchmark_dir: Path) -> dict:
    """
    Load all run results from a benchmark directory.

    Returns dict keyed by config name (e.g. "with_skill"/"without_skill",
    or "new_skill"/"old_skill"), each containing a list of run results.
    """
    # Support both layouts: eval dirs directly under benchmark_dir, or under runs/
    runs_dir = benchmark_dir / "runs"
    search_dir = runs_dir if runs_dir.exists() else benchmark_dir

    results: dict[str, list] = {}
    eval_dirs = []

    # 用例目录名不做前缀限制（文档要求用描述性名字）：
    # 有 eval_metadata.json、或下面挂着带 grading.json 的配置目录，就算一个用例目录。
    for candidate in sorted(p for p in search_dir.iterdir() if p.is_dir()):
        if candidate.name == "runs":
            continue
        if (candidate / "eval_metadata.json").exists() or any(_iter_run_dirs(candidate)):
            eval_dirs.append(candidate)

    if not eval_dirs:
        print(f"在 {search_dir} 里找不到测试用例目录（需要 eval_metadata.json，或含 grading.json 的配置目录）")
        return results

    for eval_idx, eval_dir in enumerate(eval_dirs):
        eval_id, eval_name = _read_eval_meta(eval_dir, eval_idx)

        # Discover config directories dynamically rather than hardcoding names
        for config, run_dir, run_number in _iter_run_dirs(eval_dir):
            if config not in results:
                results[config] = []

            grading_file = run_dir / "grading.json"
            try:
                with open(grading_file) as f:
                    grading = json.load(f)
            except json.JSONDecodeError as e:
                print(f"警告：{grading_file} 里的 JSON 格式无效：{e}")
                continue

            # Extract metrics
            result = {
                "eval_id": eval_id,
                "eval_name": eval_name,
                "run_number": run_number,
                "pass_rate": grading.get("summary", {}).get("pass_rate", 0.0),
                "passed": grading.get("summary", {}).get("passed", 0),
                "failed": grading.get("summary", {}).get("failed", 0),
                "total": grading.get("summary", {}).get("total", 0),
            }

            # Extract timing — check grading.json first, then sibling timing.json
            # (兼容两个位置：run 根目录 / outputs/ 子目录)
            timing = grading.get("timing", {})
            result["time_seconds"] = timing.get("total_duration_seconds", 0.0)
            result["tokens"] = timing.get("total_tokens", 0)
            for timing_file in (run_dir / "timing.json", run_dir / "outputs" / "timing.json"):
                if result["time_seconds"] > 0 and result["tokens"] > 0:
                    break
                if timing_file.exists():
                    try:
                        with open(timing_file) as tf:
                            timing_data = json.load(tf)
                        if result["time_seconds"] == 0.0:
                            result["time_seconds"] = timing_data.get("total_duration_seconds", 0.0)
                        if result["tokens"] == 0:
                            result["tokens"] = timing_data.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass

            # Extract metrics if available
            metrics = grading.get("execution_metrics", {})
            result["tool_calls"] = metrics.get("total_tool_calls", 0)
            # 拿不到 token 数就留 None。execution_metrics.output_chars 是"字符数"不是 token 数，
            # 拿它顶上去会让这个指标量纲错掉（中英文差好几倍），宁可缺数据也不报假数。
            if not result.get("tokens"):
                result["tokens"] = None
            result["errors"] = metrics.get("errors_encountered", 0)

            # Extract expectations — viewer requires fields: text, passed, evidence
            raw_expectations = grading.get("expectations", [])
            for exp in raw_expectations:
                if "text" not in exp or "passed" not in exp:
                    print(f"警告：{grading_file} 里的断言缺少必填字段（text, passed, evidence）：{exp}")
            result["expectations"] = raw_expectations

            # Extract notes from user_notes_summary
            notes_summary = grading.get("user_notes_summary", {})
            notes = []
            notes.extend(notes_summary.get("uncertainties", []))
            notes.extend(notes_summary.get("needs_review", []))
            notes.extend(notes_summary.get("workarounds", []))
            result["notes"] = notes

            results[config].append(result)

    return results


def aggregate_results(results: dict) -> dict:
    """
    Aggregate run results into summary statistics.

    Returns run_summary with stats for each configuration and delta.
    """
    run_summary = {}
    # 顺序即语义：带技能的配置在前，基线在后（评审页面分组和 delta 都依赖这个顺序）
    configs = order_configs(list(results.keys()))

    for config in configs:
        runs = results.get(config, [])

        if not runs:
            run_summary[config] = {
                "pass_rate": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "time_seconds": {"mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0},
                "tokens": None
            }
            continue

        pass_rates = [r["pass_rate"] for r in runs]
        times = [r["time_seconds"] for r in runs]
        # 只统计真实采到的 token 数；一个都没有就给 None，让评审页把整行隐掉，
        # 而不是显示一个假的 0（也避免 delta 拿两个不存在的数相减）
        token_values = [r.get("tokens") for r in runs if r.get("tokens") is not None]

        run_summary[config] = {
            "pass_rate": calculate_stats(pass_rates),
            "time_seconds": calculate_stats(times),
            "tokens": calculate_stats(token_values) if token_values else None
        }

    # 前一个是带技能的版本，后一个是它的基线
    if len(configs) >= 2:
        primary = run_summary.get(configs[0], {})
        baseline = run_summary.get(configs[1], {})
    else:
        primary = run_summary.get(configs[0], {}) if configs else {}
        baseline = {}

    delta_pass_rate = primary.get("pass_rate", {}).get("mean", 0) - baseline.get("pass_rate", {}).get("mean", 0)
    delta_time = primary.get("time_seconds", {}).get("mean", 0) - baseline.get("time_seconds", {}).get("mean", 0)

    run_summary["delta"] = {
        "pass_rate": f"{delta_pass_rate:+.2f}",
        "time_seconds": f"{delta_time:+.1f}",
    }
    # 两边都有真实 token 数据才给差值，否则整个键不出现（评审页显示为 —）
    primary_tokens = primary.get("tokens") or {}
    baseline_tokens = baseline.get("tokens") or {}
    if primary_tokens and baseline_tokens:
        delta_tokens = primary_tokens.get("mean", 0) - baseline_tokens.get("mean", 0)
        run_summary["delta"]["tokens"] = f"{delta_tokens:+.0f}"

    return run_summary


def generate_benchmark(benchmark_dir: Path, skill_name: str = "", skill_path: str = "") -> dict:
    """
    Generate complete benchmark.json from run results.
    """
    results = load_run_results(benchmark_dir)
    run_summary = aggregate_results(results)

    # Build runs array for benchmark.json
    # 同样按"带技能在前"的顺序输出，评审页面直接按数组顺序渲染
    ordered_configs = order_configs(list(results.keys()))
    runs = []
    for config in ordered_configs:
        for result in results[config]:
            runs.append({
                "eval_id": result["eval_id"],
                "eval_name": result["eval_name"],
                "configuration": config,
                "run_number": result["run_number"],
                "result": {
                    "pass_rate": result["pass_rate"],
                    "passed": result["passed"],
                    "failed": result["failed"],
                    "total": result["total"],
                    "time_seconds": result["time_seconds"],
                    "tokens": result.get("tokens"),
                    "tool_calls": result.get("tool_calls", 0),
                    "errors": result.get("errors", 0)
                },
                "expectations": result["expectations"],
                "notes": result["notes"]
            })

    # Determine eval IDs from results
    eval_ids = sorted(set(
        r["eval_id"]
        for config in results.values()
        for r in config
    ))

    # 每个用例在每个配置下实际跑了几次（不写死 3——扁平布局下就是 1 次）
    per_eval_config: dict[tuple, int] = {}
    for config in ordered_configs:
        for result in results[config]:
            key = (result["eval_id"], config)
            per_eval_config[key] = per_eval_config.get(key, 0) + 1

    benchmark = {
        "metadata": {
            "skill_name": skill_name or "<skill-name>",
            "skill_path": skill_path or "<path/to/skill>",
            "executor_model": "<model-name>",
            "analyzer_model": "<model-name>",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "evals_run": eval_ids,
            # 每个用例在每个配置下跑几次，取实际最大值
            "runs_per_configuration": max(per_eval_config.values(), default=0)
        },
        "runs": runs,
        "run_summary": run_summary,
        "notes": []  # To be filled by analyzer
    }

    return benchmark


def generate_markdown(benchmark: dict) -> str:
    """Generate human-readable benchmark.md from benchmark data."""
    metadata = benchmark["metadata"]
    run_summary = benchmark["run_summary"]

    # Determine config names (excluding "delta")
    configs = [k for k in run_summary if k != "delta"]
    config_a = configs[0] if len(configs) >= 1 else "config_a"
    config_b = configs[1] if len(configs) >= 2 else "config_b"
    label_a = config_a.replace("_", " ").title()
    label_b = config_b.replace("_", " ").title()

    lines = [
        f"# Skill Benchmark: {metadata['skill_name']}",
        "",
        f"**Model**: {metadata['executor_model']}",
        f"**Date**: {metadata['timestamp']}",
        f"**Evals**: {', '.join(map(str, metadata['evals_run']))} ({metadata['runs_per_configuration']} runs each per configuration)",
        "",
        "## Summary",
        "",
        f"| Metric | {label_a} | {label_b} | Delta |",
        "|--------|------------|---------------|-------|",
    ]

    a_summary = run_summary.get(config_a, {})
    b_summary = run_summary.get(config_b, {})
    delta = run_summary.get("delta", {})

    # Format pass rate
    a_pr = a_summary.get("pass_rate", {})
    b_pr = b_summary.get("pass_rate", {})
    lines.append(f"| Pass Rate | {a_pr.get('mean', 0)*100:.0f}% ± {a_pr.get('stddev', 0)*100:.0f}% | {b_pr.get('mean', 0)*100:.0f}% ± {b_pr.get('stddev', 0)*100:.0f}% | {delta.get('pass_rate', '—')} |")

    # Format time
    a_time = a_summary.get("time_seconds", {})
    b_time = b_summary.get("time_seconds", {})
    lines.append(f"| Time | {a_time.get('mean', 0):.1f}s ± {a_time.get('stddev', 0):.1f}s | {b_time.get('mean', 0):.1f}s ± {b_time.get('stddev', 0):.1f}s | {delta.get('time_seconds', '—')}s |")

    # Format tokens（没采到真实 token 数时整行标 —，不编数字）
    a_tokens = a_summary.get("tokens") or {}
    b_tokens = b_summary.get("tokens") or {}
    if a_tokens or b_tokens:
        lines.append(f"| Tokens | {a_tokens.get('mean', 0):.0f} ± {a_tokens.get('stddev', 0):.0f} | {b_tokens.get('mean', 0):.0f} ± {b_tokens.get('stddev', 0):.0f} | {delta.get('tokens', '—')} |")
    else:
        lines.append("| Tokens | — | — | — |")

    # Notes section
    if benchmark.get("notes"):
        lines.extend([
            "",
            "## Notes",
            ""
        ])
        for note in benchmark["notes"]:
            lines.append(f"- {note}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="把基准测试运行结果汇总成统计数据"
    )
    parser.add_argument(
        "benchmark_dir",
        type=Path,
        help="基准测试目录路径"
    )
    parser.add_argument(
        "--skill-name",
        default="",
        help="被测技能的名称"
    )
    parser.add_argument(
        "--skill-path",
        default="",
        help="被测技能的路径"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="benchmark.json 的输出路径（默认：<基准测试目录>/benchmark.json）"
    )

    args = parser.parse_args()

    if not args.benchmark_dir.exists():
        print(f"找不到目录：{args.benchmark_dir}")
        sys.exit(1)

    # Generate benchmark
    benchmark = generate_benchmark(args.benchmark_dir, args.skill_name, args.skill_path)

    # Determine output paths
    output_json = args.output or (args.benchmark_dir / "benchmark.json")
    output_md = output_json.with_suffix(".md")

    # Write benchmark.json
    with open(output_json, "w") as f:
        json.dump(benchmark, f, indent=2)
    print(f"已生成：{output_json}")

    # Write benchmark.md
    markdown = generate_markdown(benchmark)
    with open(output_md, "w") as f:
        f.write(markdown)
    print(f"已生成：{output_md}")

    # Print summary
    run_summary = benchmark["run_summary"]
    configs = [k for k in run_summary if k != "delta"]
    delta = run_summary.get("delta", {})

    print(f"\n汇总：")
    for config in configs:
        pr = run_summary[config]["pass_rate"]["mean"]
        label = config.replace("_", " ")
        print(f"  {label}: 通过率 {pr*100:.1f}%")
    print(f"  差值:         {delta.get('pass_rate', '—')}")


if __name__ == "__main__":
    main()
