#!/usr/bin/env python3
"""把触发测试集渲染成一个独立的可视化确认页。

读 assets/eval_review.html 模板，替换其中的占位符，写出一个独立 HTML 文件。
用户在浏览器里编辑查询、切换「应触发」、增删条目，点导出得到 eval_set.json。

这是确定性操作（纯字符串替换），所以脚本化——别让每个 Agent 各写一遍。

用法（在技能创建器根目录下执行）：
    python3 -m scripts.gen_eval_review <测试集.json> --skill-path <技能目录> [-o 输出.html]

测试集 JSON 格式（和 run_eval.py 一致）：
    [{"query": "...", "should_trigger": true}, ...]

省略 -o 时输出到临时文件并打印路径。
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

from scripts.utils import parse_skill_md

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "eval_review.html"

PLACEHOLDER_EVAL = "__EVAL_DATA_PLACEHOLDER__"
PLACEHOLDER_NAME = "__SKILL_NAME_PLACEHOLDER__"
PLACEHOLDER_DESC = "__SKILL_DESCRIPTION_PLACEHOLDER__"


def render(eval_set: list, skill_name: str, skill_description: str) -> str:
    """把模板里的三个占位符替换成真实内容。"""
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"找不到模板 {TEMPLATE}")
    template = TEMPLATE.read_text(encoding="utf-8")
    # __EVAL_DATA_PLACEHOLDER__ 是 JS 变量赋值位置（const EVAL_DATA = ...），不加引号
    return (template
            .replace(PLACEHOLDER_EVAL, json.dumps(eval_set, ensure_ascii=False))
            .replace(PLACEHOLDER_NAME, skill_name)
            .replace(PLACEHOLDER_DESC, skill_description))


def main():
    parser = argparse.ArgumentParser(description="把触发测试集渲染成独立确认页")
    parser.add_argument("eval_set", type=Path, help="测试集 JSON 路径")
    parser.add_argument("--skill-path", type=Path, required=True, help="技能目录（读 name / description）")
    parser.add_argument("-o", "--output", type=Path, default=None, help="输出 HTML（默认写到临时文件）")
    args = parser.parse_args()

    if not args.eval_set.exists():
        print(f"错误：找不到测试集 {args.eval_set}", file=sys.stderr)
        sys.exit(2)
    if not (args.skill_path / "SKILL.md").exists():
        print(f"错误：{args.skill_path} 里找不到 SKILL.md", file=sys.stderr)
        sys.exit(2)

    try:
        eval_set = json.loads(args.eval_set.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误：测试集 JSON 解析失败：{e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(eval_set, list):
        print("错误：测试集 JSON 顶层必须是数组 [{\"query\":...,\"should_trigger\":...}]", file=sys.stderr)
        sys.exit(2)

    name, description, _ = parse_skill_md(args.skill_path)
    html = render(eval_set, name, description)

    output = args.output or (Path(tempfile.gettempdir()) / f"eval_review_{name}.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")

    trigger = sum(1 for e in eval_set if e.get("should_trigger"))
    print(f"已生成确认页：{output}")
    print(f"共 {len(eval_set)} 条查询（{trigger} 应触发 / {len(eval_set) - trigger} 不应触发）")


if __name__ == "__main__":
    main()
