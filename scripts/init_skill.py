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


def init_skill(skill_name, path, capabilities=()):
    """
    Initialize a new skill directory with template SKILL.md.

    Args:
        skill_name: Name of the skill
        path: Path where the skill directory should be created
        capabilities: 能力位集合，如 {"scripts", "evals"} / {"scripts"} / ()。
                      缺省为空 = 不预设（只建 SKILL.md + examples/），由调用方判断后显式传入。
                      决定生成哪些目录：scripts → scripts/；evals → evals/；examples/ 恒建。

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
    caps = set(capabilities)
    skill_content = SKILL_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title,
    )

    skill_md_path = skill_dir / 'SKILL.md'
    try:
        skill_md_path.write_text(skill_content)
        print("✅ Created SKILL.md")
    except Exception as e:
        print(f"❌ Error creating SKILL.md: {e}")
        return None

    # Create resource directories（按能力位）
    try:
        # examples/ 恒建
        examples_dir = skill_dir / 'examples'
        examples_dir.mkdir(exist_ok=True)
        example_pair = examples_dir / 'example-pair.md'
        example_pair.write_text(EXAMPLE_PAIR)
        print("✅ Created examples/example-pair.md")

        # scripts/：声明了 scripts 能力位才建
        if 'scripts' in caps:
            scripts_dir = skill_dir / 'scripts'
            scripts_dir.mkdir(exist_ok=True)
            example_script = scripts_dir / 'example.py'
            example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name))
            example_script.chmod(0o755)
            print("✅ Created scripts/example.py")

        # evals/：声明了 evals 能力位才建
        if 'evals' in caps:
            evals_dir = skill_dir / 'evals'
            evals_dir.mkdir(exist_ok=True)
            evals_file = evals_dir / 'evals.json'
            evals_file.write_text(EVALS_TEMPLATE % skill_name)
            print("✅ Created evals/evals.json")

        if not caps:
            print("   （未声明任何能力位：只建 SKILL.md + examples/；按需再加 scripts/ evals/ references/ assets/）")
    except Exception as e:
        print(f"❌ Error creating resource directories: {e}")
        return None

    # Print next steps
    print(f"\n✅ Skill '{skill_name}' initialized successfully at {skill_dir}")
    print("\nNext steps:")
    print("1. Edit SKILL.md to complete the TODO items and update the description")
    print("   - description 必须第三人称，写清'做什么' + '什么时候用'（Use when / 用于...）")
    print("   - name 推荐动名词形式（如 processing-pdfs），避免 helper/utils 这种模糊名")
    step = 2
    print(f"{step}. 改 examples/example-pair.md 成真实的 input/output 对")
    step += 1
    if 'evals' in caps:
        print(f"{step}. 改 evals/evals.json 里的 3 个测试用例成真实场景")
    else:
        print(f"{step}. 未声明 evals 能力位——跳过基线 / benchmark，靠用户反馈迭代")
    step += 1
    if 'scripts' in caps:
        print(f"{step}. 列一下技能里每次都重复做的确定性动作——能写成脚本的必须写进 scripts/")
        step += 1
    print(f"{step}. 准备好后跑：python3 -m scripts.quick_validate <skill-dir> --deep")
    print("   （在技能创建器根目录下执行；直接写 python scripts/xxx.py 会报 ModuleNotFoundError）")

    return skill_dir


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Initialize a new skill from template",
        usage="init_skill.py <skill-name> --path <path>",
    )
    parser.add_argument("skill_name", help="Name of the skill (kebab-case)")
    parser.add_argument("--path", required=True, help="Path where the skill directory should be created")
    parser.add_argument("--capabilities", default=None,
                        help="能力位，逗号分隔（scripts,evals）。必填；传空字符串=纯提示词（只建 SKILL.md + examples/）")
    parser.add_argument("--type", choices=("heavy", "light"), default=None,
                        help="[已废弃，请用 --capabilities] light 等价于 --capabilities ''")
    args = parser.parse_args()

    skill_name = args.skill_name
    path = args.path

    # 解析能力位：--capabilities 优先；--type 兼容；都没传则拒绝——不让脚手架替判断做决定
    if args.capabilities is not None:
        caps = {x.strip() for x in args.capabilities.replace(",", " ").split() if x.strip()}
    elif args.type == "light":
        caps = set()
    elif args.type == "heavy":
        caps = {"scripts", "evals"}
    else:
        parser.error(
            "必须显式指定 --capabilities——先按 references/capability-modules.md 判断要做什么能力模块，再建目录。\n"
            "  例：--capabilities scripts,evals ｜ --capabilities scripts ｜ --capabilities \"\"（纯提示词）"
        )

    unknown = caps - {"scripts", "evals"}
    if unknown:
        parser.error(f"未知的能力位：{', '.join(sorted(unknown))}（可选：scripts, evals）")

    shown = ", ".join(c for c in ("scripts", "evals") if c in caps) or "无（纯提示词）"
    print(f"🚀 Initializing skill: {skill_name}（能力位：{shown}）")
    print(f"   Location: {path}")
    print()

    result = init_skill(skill_name, path, capabilities=caps)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
