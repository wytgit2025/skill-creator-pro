"""Shared utilities for skill-creator scripts."""

import re
from pathlib import Path

import yaml



def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content).

    用 yaml.safe_load 解析 frontmatter，和 quick_validate.py 保持一致。
    手写逐行解析无法处理多行字符串、嵌套字段、转义等 YAML 边界情况。
    """
    content = (skill_path / "SKILL.md").read_text()

    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md missing or invalid frontmatter (no --- delimiters)")

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        raise ValueError(f"SKILL.md frontmatter YAML parse error: {e}")

    if not isinstance(fm, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")

    name = str(fm.get("name", "")).strip()
    description = str(fm.get("description", "")).strip()

    return name, description, content
