#!/usr/bin/env python3
"""
Skill Initializer - Creates a new skill from template

Usage:
    init_skill.py <skill-name> --path <path>

Examples:
    init_skill.py my-new-skill --path /path/to/active/workspace/.user_skills
    # Use another location only when the user explicitly requested it:
    init_skill.py custom-skill --path /custom/location
"""

import sys
from pathlib import Path


SKILL_TEMPLATE = """---
name: {skill_name}
version: "0.1.0"
description: "TODO：第三人称写清两件事——这个技能做什么 + 什么时候触发（具体场景/文件类型/用户会说什么话）。宁可比写窄了好，也别写宽。即使用户没点名，只要场景对就应该触发。"
---

# {skill_title}

## Overview

[TODO: 1-2 句话讲清这个技能解决什么问题]

## 结构选择（写完删掉这段）

按技能形态选主结构：
- **流程型**：有明确先后步骤（读文件→处理→写回），按 Step 1/2/3 写
- **任务型**：提供一组操作（合并/拆分/提取），按任务分类写
- **参考型**：标准/规范/指南，按章节写

多数技能是混合的。不用拘泥。

## [TODO: 第一个主章节]

[TODO: 写具体流程或操作。技术技能贴代码示例，复杂流程画决策树，引用 scripts/references 时写清楚路径]

## Quality Checklist（做完自检）

- [ ] [TODO: 这个技能做完后，怎么客观判断"做对了"？列 3-5 条可检查的]
- [ ] [TODO: 比如"所有输入文件都处理了，没有漏"]
- [ ] [TODO: 比如"输出文件格式正确，能被下游工具打开"]

## Common Pitfalls（常见坑）

- **[TODO: 坑 1 名字]**：[为什么容易踩 + 正确做法。比如"别把空值全删了——可能是业务上合法的缺失"]
- **[TODO: 坑 2 名字]**：[为什么 + 怎么做]

## 不要做的事

- [TODO: 明确边界，比如"不要修改原文件，除非用户明确说"]
- [TODO: 比如"不要把 XX 自动翻译成 YY——业务含义不能猜"]

## 资源目录说明（写完删掉这段）

- `scripts/`：确定性、重复性操作写成脚本，不要让模型每次重写
- `references/`：太长、按需查阅的文档（API 参考、复杂流程详解）
- `assets/`：模板、字体、图片等输出时要用到的文件

不需要的目录直接删掉。
"""

EXAMPLE_SCRIPT = '''#!/usr/bin/env python3
"""
Example helper script for {skill_name}

This is a placeholder script that can be executed directly.
Replace with actual implementation or delete if not needed.

Example real scripts from other skills:
- pdf/scripts/fill_fillable_fields.py - Fills PDF form fields
- pdf/scripts/convert_pdf_to_images.py - Converts PDF pages to images
"""

def main():
    print("This is an example script for {skill_name}")
    # TODO: Add actual script logic here
    # This could be data processing, file conversion, API calls, etc.

if __name__ == "__main__":
    main()
'''

EXAMPLE_REFERENCE = """# Reference Documentation for {skill_title}

This is a placeholder for detailed reference documentation.
Replace with actual reference content or delete if not needed.

Example real reference docs from other skills:
- product-management/references/communication.md - Comprehensive guide for status updates
- product-management/references/context_building.md - Deep-dive on gathering context
- bigquery/references/ - API references and query examples

## When Reference Docs Are Useful

Reference docs are ideal for:
- Comprehensive API documentation
- Detailed workflow guides
- Complex multi-step processes
- Information too lengthy for main SKILL.md
- Content that's only needed for specific use cases

## Structure Suggestions

### API Reference Example
- Overview
- Authentication
- Endpoints with examples
- Error codes
- Rate limits

### Workflow Guide Example
- Prerequisites
- Step-by-step instructions
- Common patterns
- Troubleshooting
- Best practices
"""

EXAMPLE_ASSET = """# Example Asset File

This placeholder represents where asset files would be stored.
Replace with actual asset files (templates, images, fonts, etc.) or delete if not needed.

Asset files are NOT intended to be loaded into context, but rather used within
the output the AI agent produces.

Example asset files from other skills:
- Brand guidelines: logo.png, slides_template.pptx
- Frontend builder: hello-world/ directory with HTML/React boilerplate
- Typography: custom-font.ttf, font-family.woff2
- Data: sample_data.csv, test_dataset.json

## Common Asset Types

- Templates: .pptx, .docx, boilerplate directories
- Images: .png, .jpg, .svg, .gif
- Fonts: .ttf, .otf, .woff, .woff2
- Boilerplate code: Project directories, starter files
- Icons: .ico, .svg
- Data files: .csv, .json, .xml, .yaml

Note: This is a text placeholder. Actual assets can be any file type.
"""

EVALS_TEMPLATE = """{
  "skill_name": "%s",
  "evals": [
    {
      "id": 1,
      "prompt": "用户真实会说的一句任务话（不是指令，是口语化的请求）",
      "expected_output": "期望结果的客观描述：成功长什么样、有哪些必须出现的要素",
      "files": [],
      "expectations": []
    },
    {
      "id": 2,
      "prompt": "边界情况：这个技能应该能处理但容易翻车的一种输入",
      "expected_output": "期望结果的客观描述",
      "files": [],
      "expectations": []
    },
    {
      "id": 3,
      "prompt": "不该触发的反例：用户问了个相邻问题，但这个技能其实不该上",
      "expected_output": "期望模型不要强行套这个技能，而是用通用能力回答",
      "files": [],
      "expectations": []
    }
  ]
}
"""

EXAMPLE_PAIR = """# Examples: 完整对话样例

<!--
删掉这段说明，换成真实例子。
官方要求：至少 2 个——一个典型、一个边界。
每个样例要写完整的"用户问什么 → AI 回什么"，不要只写要点。
模型看一遍就知道输出该长什么样。
-->

## 例子 1：典型情况

**用户：**
> （一句真实用户会说的话，比如"把这个 PDF 里的表格提出来存成 csv"）

**AI 应该这样回：**
> （写完整回复长什么样，包括开场白、关键中间步骤、最终输出。比如：
> "我先扫一遍 PDF 确认有多少页表格……提取完成，3 个表格已存到 output.csv，列名是：..."）

**检查点：**
- （客观可查：所有页覆盖了）
- （客观可查：输出文件叫什么格式）

## 例子 2：边界情况

**用户：**
> （容易翻车的输入，比如"这个 PDF 是扫描件"）

**AI 应该这样回：**
> （写清楚这时候该走哪条路、为什么不直接走默认路径）
"""


def title_case_skill_name(skill_name):
    """Convert hyphenated skill name to Title Case for display."""
    return ' '.join(word.capitalize() for word in skill_name.split('-'))


def init_skill(skill_name, path):
    """
    Initialize a new skill directory with template SKILL.md.

    Args:
        skill_name: Name of the skill
        path: Path where the skill directory should be created

    Returns:
        Path to created skill directory, or None if error
    """
    # Determine skill directory path
    skill_dir = Path(path).resolve() / skill_name

    # Check if directory already exists
    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        return None

    # Create skill directory
    try:
        skill_dir.mkdir(parents=True, exist_ok=False)
        print(f"✅ Created skill directory: {skill_dir}")
    except Exception as e:
        print(f"❌ Error creating directory: {e}")
        return None

    # Create SKILL.md from template
    skill_title = title_case_skill_name(skill_name)
    skill_content = SKILL_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title
    )

    skill_md_path = skill_dir / 'SKILL.md'
    try:
        skill_md_path.write_text(skill_content)
        print("✅ Created SKILL.md")
    except Exception as e:
        print(f"❌ Error creating SKILL.md: {e}")
        return None

    # Create resource directories with example files
    try:
        # Create scripts/ directory with example script
        scripts_dir = skill_dir / 'scripts'
        scripts_dir.mkdir(exist_ok=True)
        example_script = scripts_dir / 'example.py'
        example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name))
        example_script.chmod(0o755)
        print("✅ Created scripts/example.py")

        # Create references/ directory with example reference doc
        references_dir = skill_dir / 'references'
        references_dir.mkdir(exist_ok=True)
        example_reference = references_dir / 'api_reference.md'
        example_reference.write_text(EXAMPLE_REFERENCE.format(skill_title=skill_title))
        print("✅ Created references/api_reference.md")

        # Create assets/ directory with example asset placeholder
        assets_dir = skill_dir / 'assets'
        assets_dir.mkdir(exist_ok=True)
        example_asset = assets_dir / 'example_asset.txt'
        example_asset.write_text(EXAMPLE_ASSET)
        print("✅ Created assets/example_asset.txt")

        # Create evals/ directory with a starter evals.json (3 cases)
        evals_dir = skill_dir / 'evals'
        evals_dir.mkdir(exist_ok=True)
        evals_file = evals_dir / 'evals.json'
        evals_file.write_text(EVALS_TEMPLATE % skill_name)
        print("✅ Created evals/evals.json")

        # Create examples/ directory with an input/output pair template
        examples_dir = skill_dir / 'examples'
        examples_dir.mkdir(exist_ok=True)
        example_pair = examples_dir / 'example-pair.md'
        example_pair.write_text(EXAMPLE_PAIR)
        print("✅ Created examples/example-pair.md")
    except Exception as e:
        print(f"❌ Error creating resource directories: {e}")
        return None

    # Print next steps
    print(f"\n✅ Skill '{skill_name}' initialized successfully at {skill_dir}")
    print("\nNext steps:")
    print("1. Edit SKILL.md to complete the TODO items and update the description")
    print("   - description 必须第三人称，写清'做什么' + '什么时候用'（Use when / 用于...）")
    print("   - name 推荐动名词形式（如 processing-pdfs），避免 helper/utils 这种模糊名")
    print("2. 改 evals/evals.json 里的 3 个测试用例成真实场景")
    print("3. 改 examples/example-pair.md 成真实的 input/output 对")
    print("4. 列一下这个技能里哪些是每次都重复做的确定性动作——能写成脚本的必须写进 scripts/")
    print("5. 准备好后跑：python -m scripts.quick_validate <skill-dir> --deep")
    print("   （在技能创建器根目录下执行；直接写 python scripts/xxx.py 会报 ModuleNotFoundError）")

    return skill_dir


def main():
    if len(sys.argv) < 4 or sys.argv[2] != '--path':
        print("Usage: init_skill.py <skill-name> --path <path>")
        print("\nSkill name requirements:")
        print("  - Hyphen-case identifier (e.g., 'data-analyzer')")
        print("  - Lowercase letters, digits, and hyphens only")
        print("  - Max 40 characters")
        print("  - Must match directory name exactly")
        print("\nExamples:")
        print("  init_skill.py my-new-skill --path /path/to/active/workspace/.user_skills")
        print("  # Use another location only when the user explicitly requested it:")
        print("  init_skill.py custom-skill --path /custom/location")
        sys.exit(1)

    skill_name = sys.argv[1]
    path = sys.argv[3]

    print(f"🚀 Initializing skill: {skill_name}")
    print(f"   Location: {path}")
    print()

    result = init_skill(skill_name, path)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
