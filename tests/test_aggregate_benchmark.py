"""回归测试：文档所述 evals 布局 → aggregate_benchmark 的聚合契约。

跑法（在技能根目录下任选一种）：

    python3 -m unittest discover -s tests -t .
    python3 tests/test_aggregate_benchmark.py

用例自己造 fixture 到临时目录，跑完删除，不依赖 /tmp 里的历史文件。

覆盖两种布局（对应 references/schemas.md 的"目录约定"）：

- 扁平（文档写法）：``<iteration>/<用例目录名>/<config>/grading.json``
- 多轮（旧写法，需保持兼容）：``<iteration>/<eval-*>/<config>/run-N/grading.json``

断言的几条都是此前踩过的坑：run_summary 的配置顺序、delta 方向、
runs[] 首条配置、eval_name 透出、runs_per_configuration、均值数值，
以及"没有真实 token 数据时不能用 output_chars 顶替"（量纲错误）。
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def write_grading(path: Path, passed: int, total: int, tokens: int, seconds: float,
                  with_timing: bool = True) -> None:
    """按 schemas.md 的字段名写一份 grading.json，可选同目录 timing.json。

    with_timing=False 用来复现"只有字符数、没有真实 token 数"的场景。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "expectations": [
            {"text": "输出里包含 X", "passed": True, "evidence": "第 3 步找到"},
            {"text": "用了脚本 Y", "passed": False, "evidence": "未使用"},
        ],
        "summary": {"passed": passed, "failed": total - passed, "total": total,
                    "pass_rate": round(passed / total, 4)},
        "execution_metrics": {"total_tool_calls": 7, "errors_encountered": 0, "output_chars": 999},
        "user_notes_summary": {"uncertainties": ["数据可能过时"]},
    }, ensure_ascii=False))
    if not with_timing:
        return
    (path.parent / "timing.json").write_text(json.dumps(
        {"total_tokens": tokens, "duration_ms": int(seconds * 1000),
         "total_duration_seconds": seconds}))


class AggregateBenchmarkContractTest(unittest.TestCase):
    """跑一次聚合，然后逐条检查产出契约。"""

    @classmethod
    def setUpClass(cls):
        cls.ws = Path(tempfile.mkdtemp(prefix="scp-aggregate-test-"))
        iteration = cls.ws / "iteration-1"

        # ---- 扁平布局：描述性目录名 + 配置目录下直接放 grading.json ----
        flat = iteration / "表格提取-典型情况"
        (flat / "with_skill" / "outputs").mkdir(parents=True)
        (flat / "with_skill" / "outputs" / "result.csv").write_text("a,b\n1,2\n")
        (flat / "eval_metadata.json").write_text(json.dumps({
            "eval_id": 0,
            "eval_name": "表格提取-典型情况",
            "prompt": "把这个 PDF 里的表格提出来存成 csv",
            "expectations": [],
        }, ensure_ascii=False))
        write_grading(flat / "with_skill" / "grading.json", passed=6, total=7, tokens=3800, seconds=42.5)
        (flat / "without_skill" / "outputs").mkdir(parents=True)
        (flat / "without_skill" / "outputs" / "result.csv").write_text("baseline\n")
        write_grading(flat / "without_skill" / "grading.json", passed=2, total=7, tokens=2100, seconds=32.0)

        # ---- 多轮布局：旧写法，验证兼容 ----
        multi = iteration / "eval-1"
        multi.mkdir(parents=True)
        for n, (p, t) in enumerate([(5, 3000), (7, 3400)], start=1):
            write_grading(multi / "with_skill" / f"run-{n}" / "grading.json",
                          passed=p, total=7, tokens=t, seconds=40.0)

        cls.proc = subprocess.run(
            [sys.executable, "-m", "scripts.aggregate_benchmark", str(iteration),
             "--skill-name", "regression-test"],
            cwd=REPO, capture_output=True, text=True)
        cls.bench_path = iteration / "benchmark.json"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def setUp(self):
        if self.proc.returncode != 0:
            self.fail(f"聚合脚本退出码 {self.proc.returncode}\n"
                      f"stdout:\n{self.proc.stdout}\nstderr:\n{self.proc.stderr}")
        self.assertTrue(self.bench_path.exists(), "没有生成 benchmark.json")
        self.bench = json.loads(self.bench_path.read_text())

    def test_run_summary_config_order(self):
        """基线（without_skill）不能排在主配置（with_skill）前面。"""
        keys = [k for k in self.bench["run_summary"] if k != "delta"]
        self.assertEqual(keys[:2], ["with_skill", "without_skill"],
                         f"run_summary 配置顺序不对：{keys}")

    def test_delta_direction(self):
        """with_skill 更好时 delta 必须带 + 号，不能只报绝对值。"""
        self.assertTrue(self.bench["run_summary"]["delta"]["pass_rate"].startswith("+"),
                        f"delta 方向不对：{self.bench['run_summary']['delta']}")

    def test_runs_primary_first(self):
        self.assertEqual(self.bench["runs"][0]["configuration"], "with_skill",
                         "runs[] 首条不是 with_skill")

    def test_eval_name_surfaced(self):
        """扁平布局下 eval_name 要从 eval_metadata.json 透到 runs[]。"""
        for run in self.bench["runs"]:
            self.assertNotIn(run.get("eval_name"), (None, ""), "runs[] 缺 eval_name")
        flat_run = next(r for r in self.bench["runs"]
                        if r["configuration"] == "with_skill"
                        and r["run_number"] == 1
                        and r["result"]["tokens"] == 3800)
        self.assertEqual(flat_run["eval_name"], "表格提取-典型情况")

    def test_runs_per_configuration(self):
        """两种布局混用后，每个配置的运行次数仍要算对。"""
        self.assertEqual(self.bench["metadata"]["runs_per_configuration"], 2)

    def test_mean_pass_rate(self):
        """with_skill 的均值 = (6/7 + 5/7 + 7/7) / 3。"""
        expected = round((6 / 7 + 5 / 7 + 7 / 7) / 3, 4)
        actual = self.bench["run_summary"]["with_skill"]["pass_rate"]["mean"]
        self.assertAlmostEqual(actual, expected, places=4)


class TokensDimensionalTest(unittest.TestCase):
    """没有真实 token 数据时 tokens 必须是 null——不能拿 output_chars 顶替。

    复现场景：只有 grading.json（execution_metrics.output_chars = 999），
    没有 timing.json。旧实现会把 999 当成 token 数写进 tokens，量纲是错的。
    """

    @classmethod
    def setUpClass(cls):
        cls.ws = Path(tempfile.mkdtemp(prefix="scp-tokens-test-"))
        iteration = cls.ws / "iteration-1"
        for config in ("with_skill", "without_skill"):
            write_grading(iteration / f"用例-{config}" / config / "grading.json",
                          passed=6, total=7, tokens=0, seconds=42.5, with_timing=False)
        cls.proc = subprocess.run(
            [sys.executable, "-m", "scripts.aggregate_benchmark", str(iteration)],
            cwd=REPO, capture_output=True, text=True)
        cls.bench_path = iteration / "benchmark.json"
        cls.md_path = iteration / "benchmark.md"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws, ignore_errors=True)

    def setUp(self):
        if self.proc.returncode != 0:
            self.fail(f"聚合脚本退出码 {self.proc.returncode}\n"
                      f"stdout:\n{self.proc.stdout}\nstderr:\n{self.proc.stderr}")
        self.bench = json.loads(self.bench_path.read_text())

    def test_run_tokens_is_null(self):
        """runs[] 里不能出现 output_chars 那个 999。"""
        values = [r["result"]["tokens"] for r in self.bench["runs"]]
        self.assertTrue(all(v is None for v in values), f"tokens 被填了假数据：{values}")

    def test_summary_tokens_is_null(self):
        for config in ("with_skill", "without_skill"):
            self.assertIsNone(self.bench["run_summary"][config]["tokens"],
                              f"{config}.tokens 不该是个数字")

    def test_delta_has_no_tokens_key(self):
        """两边都没数据时 delta 不该给 token 差值。"""
        self.assertNotIn("tokens", self.bench["run_summary"]["delta"],
                         f"delta 里出现了凭空的 token 差值：{self.bench['run_summary']['delta']}")

    def test_markdown_marks_tokens_as_unknown(self):
        self.assertIn("| Tokens | — | — | — |", self.md_path.read_text(),
                      "benchmark.md 的 Tokens 行没有标成 —")


if __name__ == "__main__":
    unittest.main(verbosity=2)
