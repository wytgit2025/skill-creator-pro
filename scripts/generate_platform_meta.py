"""从 SKILL.md frontmatter 派生各平台 UI 元数据草稿。

设计原则：
- **只做确定性派生**，不调 LLM、不猜 category / 中文译名 / default_prompt。
  这些字段需要人判断，一律留 TODO 占位，由用户补。
- **默认 dry-run 打印到 stdout**；加 --write 才写文件，且只写到 .draft.* 旁挂文件，
  不覆盖已有的平台元数据——符合"不自动改、出建议用户点头"的纪律。

用法（必须从 skill-creator-pro 根目录跑）：
    python3 -m scripts.generate_platform_meta <skill-dir> [--write]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("需要 PyYAML：pip install pyyaml\n")
    sys.exit(2)


def parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        sys.stderr.write(f"{skill_md}: 找不到 YAML frontmatter（--- 包裹的头部）\n")
        sys.exit(1)
    data = yaml.safe_load(m.group(1)) or {}
    if "name" not in data or "description" not in data:
        sys.stderr.write(f"{skill_md}: frontmatter 必须至少含 name 和 description\n")
        sys.exit(1)
    return data


def display_name_from(slug: str) -> str:
    """pdf-processor -> Pdf Processor；保留常见缩写大写（pdf/xlsx/docx）。"""
    small = {"pdf", "xlsx", "docx", "pptx", "csv", "api", "sdk", "ui", "qa", "ai", "cli"}
    parts = slug.split("-")
    out = []
    for p in parts:
        out.append(p.upper() if p in small else p.capitalize())
    return " ".join(out)


def short_description_from(desc: str, limit: int = 90) -> str:
    """取 description 的第一句/第一分句，截断到 limit 字符。"""
    first = re.split(r"(?<=[。.!?！？.])\s+", desc.strip(), maxsplit=1)[0]
    if len(first) > limit:
        first = first[: limit - 1].rstrip("，,；;：: ") + "…"
    return first


def render_openai_yaml(name: str, display: str, short: str) -> str:
    return (
        "# 由 generate_platform_meta.py 派生；default_prompt 需人工补一句示例问法\n"
        f"display_name: {display}\n"
        f"short_description: {short}\n"
        "default_prompt: TODO 例如：帮我用这个技能处理 <一个具体文件>\n"
    )


def render_qwen_metadata(name: str, desc: str) -> str:
    return (
        "# 千问办公 .skill-metadata.yaml 草稿；中文译名和中文描述需人工补\n"
        f"name_en: {name}\n"
        "name_zh: TODO 中文名\n"
        f"description_en: {desc}\n"
        "description_zh: TODO 中文描述（一句话说清做什么、什么时候触发）\n"
        "argument-hint: TODO 例如：[文件路径或任务描述]\n"
        "argument-hint-en: TODO\n"
        "user-invocable: true\n"
    )


def render_workbuddy_manifest(name: str, display: str) -> str:
    return (
        "# WorkBuddy manifest.yaml 草稿；category/platforms 需按企业实际补\n"
        "version: 0.1.0\n"
        f"name: {display}\n"
        "category: TODO 例如 productivity / development / data\n"
        "platforms: TODO 例如 [web, desktop]\n"
        "agent_created: true\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="从 SKILL.md 派生各平台 UI 元数据草稿")
    ap.add_argument("skill_dir", type=Path, help="技能目录路径（含 SKILL.md）")
    ap.add_argument("--write", action="store_true",
                    help="把草稿写到 <skill_dir>/.draft.* 文件；默认只打印")
    args = ap.parse_args()

    skill_dir: Path = args.skill_dir.resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        sys.stderr.write(f"找不到 {skill_md}\n")
        sys.exit(1)

    fm = parse_frontmatter(skill_md)
    name = fm["name"].strip()
    desc = fm["description"].strip()
    display = display_name_from(name)
    short = short_description_from(desc)

    drafts = {
        skill_dir / ".draft.openai.yaml": render_openai_yaml(name, display, short),
        skill_dir / ".draft.skill-metadata.yaml": render_qwen_metadata(name, desc),
        skill_dir / ".draft.manifest.yaml": render_workbuddy_manifest(name, display),
    }

    print(f"# 技能：{name}")
    print(f"# 派生显示名：{display}")
    print(f"# 派生短描述：{short}\n")
    for path, content in drafts.items():
        print(f"===== {path.name} =====")
        print(content)

    if args.write:
        for path, content in drafts.items():
            path.write_text(content, encoding="utf-8")
            print(f"[写入] {path}", file=sys.stderr)
        print(
            "\n[提醒] 这些是 .draft.* 草稿文件。人工补完 TODO 后，再按各平台规范"
            "重命名为正式文件名（agents/openai.yaml / .skill-metadata.yaml / manifest.yaml）。",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
