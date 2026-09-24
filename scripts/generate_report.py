#!/usr/bin/env python3
"""从 run_loop.py 的输出生成 HTML 报告。

接收 run_loop.py 的 JSON 输出，生成可视化的 HTML 报告，
展示每一次描述尝试，以及每个测试用例的通过/失败情况。
区分训练集和测试集查询。

HTML/CSS 模板从 scripts/report_template.html 加载，不再内嵌在 Python 里。
"""

import argparse
import html
import json
import sys
from pathlib import Path


def _load_template() -> str:
    """从同目录加载 report_template.html。"""
    template_path = Path(__file__).parent / "report_template.html"
    return template_path.read_text(encoding="utf-8")


def _aggregate_runs(results: list[dict]) -> tuple[int, int]:
    """计算跨所有重试的 correct/total。"""
    correct = 0
    total = 0
    for r in results:
        runs = r.get("runs", 0)
        triggers = r.get("triggers", 0)
        total += runs
        if r.get("should_trigger", True):
            correct += triggers
        else:
            correct += runs - triggers
    return correct, total


def _score_class(correct: int, total: int) -> str:
    if total > 0:
        ratio = correct / total
        if ratio >= 0.8:
            return "score-good"
        elif ratio >= 0.5:
            return "score-ok"
    return "score-bad"


def generate_html(data: dict, auto_refresh: bool = False, skill_name: str = "") -> str:
    """Generate HTML report from loop output data. If auto_refresh is True, adds a meta refresh tag."""
    history = data.get("history", [])
    title_prefix = html.escape(skill_name + " \u2014 ") if skill_name else ""
    refresh_tag = '    <meta http-equiv="refresh" content="5">\n' if auto_refresh else ""

    # Get all unique queries from train and test sets, with should_trigger info
    train_queries: list[dict] = []
    test_queries: list[dict] = []
    if history:
        for r in history[0].get("train_results", history[0].get("results", [])):
            train_queries.append({"query": r["query"], "should_trigger": r.get("should_trigger", True)})
        if history[0].get("test_results"):
            for r in history[0].get("test_results", []):
                test_queries.append({"query": r["query"], "should_trigger": r.get("should_trigger", True)})

    # Build summary section
    best_test_score = data.get('best_test_score')
    summary_section = f"""
    <div class="summary">
        <p><strong>原始描述：</strong> {html.escape(data.get('original_description', 'N/A'))}</p>
        <p class="best"><strong>最佳描述：</strong> {html.escape(data.get('best_description', 'N/A'))}</p>
        <p><strong>最佳得分：</strong> {data.get('best_score', 'N/A')} {'（测试集）' if best_test_score else '（训练集）'}</p>
        <p><strong>迭代次数：</strong> {data.get('iterations_run', 0)} | <strong>训练集：</strong> {data.get('train_size', '?')} | <strong>测试集：</strong> {data.get('test_size', '?')}</p>
    </div>
"""

    # Build query column headers
    query_columns_parts = []
    for qinfo in train_queries:
        polarity = "positive-col" if qinfo["should_trigger"] else "negative-col"
        query_columns_parts.append(f'                <th class="{polarity}">{html.escape(qinfo["query"])}</th>')
    for qinfo in test_queries:
        polarity = "positive-col" if qinfo["should_trigger"] else "negative-col"
        query_columns_parts.append(f'                <th class="test-col {polarity}">{html.escape(qinfo["query"])}</th>')
    query_columns = "\n".join(query_columns_parts)

    # Find best iteration for highlighting
    if test_queries:
        best_iter = max(history, key=lambda h: h.get("test_passed") or 0).get("iteration")
    else:
        best_iter = max(history, key=lambda h: h.get("train_passed", h.get("passed", 0))).get("iteration")

    # Build table rows
    table_rows_parts = []
    for h in history:
        iteration = h.get("iteration", "?")
        train_passed = h.get("train_passed", h.get("passed", 0))
        train_total = h.get("train_total", h.get("total", 0))
        test_passed = h.get("test_passed")
        test_total = h.get("test_total")
        description = h.get("description", "")
        train_results = h.get("train_results", h.get("results", []))
        test_results = h.get("test_results", [])

        train_by_query = {r["query"]: r for r in train_results}
        test_by_query = {r["query"]: r for r in test_results} if test_results else {}

        train_correct, train_runs = _aggregate_runs(train_results)
        test_correct, test_runs = _aggregate_runs(test_results)

        train_class = _score_class(train_correct, train_runs)
        test_class = _score_class(test_correct, test_runs)

        row_class = "best-row" if iteration == best_iter else ""

        row_parts = [f"""            <tr class="{row_class}">
                <td>{iteration}</td>
                <td><span class="score {train_class}">{train_correct}/{train_runs}</span></td>
                <td><span class="score {test_class}">{test_correct}/{test_runs}</span></td>
                <td class="description">{html.escape(description)}</td>"""]

        for qinfo in train_queries:
            r = train_by_query.get(qinfo["query"], {})
            did_pass = r.get("pass", False)
            triggers = r.get("triggers", 0)
            runs = r.get("runs", 0)
            icon = "✓" if did_pass else "✗"
            css_class = "pass" if did_pass else "fail"
            row_parts.append(f'                <td class="result {css_class}">{icon}<span class="rate">{triggers}/{runs}</span></td>')

        for qinfo in test_queries:
            r = test_by_query.get(qinfo["query"], {})
            did_pass = r.get("pass", False)
            triggers = r.get("triggers", 0)
            runs = r.get("runs", 0)
            icon = "✓" if did_pass else "✗"
            css_class = "pass" if did_pass else "fail"
            row_parts.append(f'                <td class="result test-result {css_class}">{icon}<span class="rate">{triggers}/{runs}</span></td>')

        row_parts.append("            </tr>")
        table_rows_parts.append("\n".join(row_parts))

    table_rows = "\n".join(table_rows_parts)

    template = _load_template()
    # 用 replace 替代 str.format，因为 CSS 里的 { } 会和 str.format 冲突
    template = template.replace("{refresh_tag}", refresh_tag)
    template = template.replace("{title_prefix}", title_prefix)
    template = template.replace("{summary_section}", summary_section)
    template = template.replace("{query_columns}", query_columns)
    template = template.replace("{table_rows}", table_rows)
    return template


def main():
    parser = argparse.ArgumentParser(description="从 run_loop 输出生成 HTML 报告")
    parser.add_argument("input", help="run_loop.py 的 JSON 输出路径（用 - 表示从标准输入读取）")
    parser.add_argument("-o", "--output", default=None, help="输出 HTML 文件（默认：标准输出）")
    parser.add_argument("--skill-name", default="", help="报告标题里显示的技能名称")
    args = parser.parse_args()

    if args.input == "-":
        data = json.load(sys.stdin)
    else:
        data = json.loads(Path(args.input).read_text())

    html_output = generate_html(data, skill_name=args.skill_name)

    if args.output:
        Path(args.output).write_text(html_output)
        print(f"报告已写入：{args.output}", file=sys.stderr)
    else:
        print(html_output)


if __name__ == "__main__":
    main()
