#!/usr/bin/env python3
"""
runtime_log.py — 运行期留痕（skill-creator-pro 母版脚本）

把技能的一次调用追加到 <skill-root>/runtime/trace.jsonl（每行一个 JSON）。
纯标准库实现，可被复制进任意技能的 scripts/ 后独立运行：

    python3 scripts/runtime_log.py --skill-root <技能根目录> \
        --status success \
        --input-summary "脱敏输入摘要" \
        --output-summary "脱敏输出摘要" \
        --duration-seconds 12.3 \
        [--feedback "用户反馈"] [--error "错误摘要"] [--request-id "ID"]

设计约束：
- 失败安全：留痕出任何问题只向 stderr 打印警告并以 0 退出，绝不阻断主任务。
- 隐私：只记录调用方传入的"摘要"，并做长度截断；不主动读取用户文件原文。
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SUMMARY_LEN = 500


def truncate(text, limit):
    if text is None:
        return None
    text = str(text).replace("\n", " ").strip()
    if limit and len(text) > limit:
        return text[:limit] + "…"
    return text


def read_skill_version(skill_root: Path):
    """从 SKILL.md frontmatter 提取 version，读不到返回 None。不依赖 PyYAML。"""
    skill_md = skill_root / "SKILL.md"
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return None
    m = re.search(r"^\s*version:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", content, re.MULTILINE)
    return m.group(1).strip() if m else None


def log_record(args) -> None:
    skill_root = Path(args.skill_root).resolve()
    runtime_dir = skill_root / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    status = args.status
    error = truncate(args.error, DEFAULT_SUMMARY_LEN)
    # status 未显式指定但给了 error 时，视为失败
    if error and status == "success":
        status = "failure"

    record = {
        "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "skill_version": read_skill_version(skill_root),
        "status": status,
        "input_summary": truncate(args.input_summary, args.max_summary_len),
        "output_summary": truncate(args.output_summary, args.max_summary_len),
        "duration_seconds": args.duration_seconds,
        "error": error,
        "feedback": truncate(args.feedback, args.max_summary_len),
        "request_id": args.request_id,
        # Meta 层可选字段：仅 skill-creator-pro 自身留痕时使用，业务技能不传即为空
        "build_kind": args.build_kind,
        "skill_category": args.skill_category,
        "skill_built": args.skill_built,
        "rework_points": truncate(args.rework_points, args.max_summary_len),
    }

    trace_path = runtime_dir / "trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[runtime_log] trace appended: {trace_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="记录一次技能调用到 runtime/trace.jsonl")
    parser.add_argument("--skill-root", required=True, help="技能根目录（含 SKILL.md）")
    parser.add_argument("--status", choices=("success", "failure"), default="success")
    parser.add_argument("--input-summary", default=None, help="脱敏输入摘要")
    parser.add_argument("--output-summary", default=None, help="脱敏输出摘要")
    parser.add_argument("--duration-seconds", type=float, default=None, help="耗时（秒）")
    parser.add_argument("--feedback", default=None, help="用户反馈 / 评分")
    parser.add_argument("--error", default=None, help="失败时的错误摘要")
    parser.add_argument("--request-id", default=None, help="去重 / 关联用 ID")
    parser.add_argument("--max-summary-len", type=int, default=DEFAULT_SUMMARY_LEN)
    # Meta 层可选：skill-creator-pro 自身留痕时标记这次调用在做什么；业务技能不传
    parser.add_argument("--build-kind", default=None,
                        choices=("new_skill", "patch_skill", "self_modify"),
                        help="（仅 pro 自身用）本次调用：造新技能 / 改已有技能 / 改 pro 自己")
    parser.add_argument("--skill-category", default=None,
                        help="（仅 pro 自身用）所造技能的类别，如 web-scrape / docx / spreadsheet / workflow")
    parser.add_argument("--skill-built", default=None,
                        help="（仅 pro 自身用）本次产出的技能名，new_skill 时填")
    parser.add_argument("--rework-points", default=None,
                        help="（仅 pro 自身用）本次返工/被用户纠正的环节，逗号分隔")
    args = parser.parse_args()

    try:
        log_record(args)
    except Exception as exc:  # 失败安全：不阻断主任务
        print(f"[runtime_log] warning: 留痕失败（已忽略）：{exc}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
