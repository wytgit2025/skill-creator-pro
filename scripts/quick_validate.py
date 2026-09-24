#!/usr/bin/env python3
"""
技能快速校验脚本

用法（在技能创建器根目录下执行）：
    python -m scripts.quick_validate <技能目录>           # 只做语法/格式校验
    python -m scripts.quick_validate <技能目录> --deep    # 额外做内容层检查（行数、触发词、examples、evals）

退出码：0 = 通过；1 = 硬错误；deep 模式下的 warning 不阻断。
"""

import sys
import os
import re
import json
import yaml
from pathlib import Path

# frontmatter 允许出现的键，分两类：
# - Anthropic 标准：name（必填）、description（必填）、license、allowed-tools、metadata、compatibility
# - 平台扩展：WorkBuddy 需要 version/category/platforms/agent_created；企业版/依赖声明需要 requires/install/os/emoji
# 不要随便加新键——加之前确认是哪个平台要的。
ALLOWED_PROPERTIES = {
    # Anthropic 标准
    'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility',
    # WorkBuddy / QClaw
    'version', 'category', 'platforms', 'agent_created',
    # WorkBuddy 依赖声明（可选）
    'requires', 'install', 'os', 'emoji',
}

# name 里禁止出现的保留词（Anthropic 规则）
RESERVED_NAMES = {'anthropic', 'claude'}

# 动名词后缀提示（官方推荐 -ing 形式，仅作为建议）
GERUND_HINTS = ('ing-',)


def _check_frontmatter(frontmatter_text):
    """返回 (frontmatter_dict, error_message)。成功时 error_message 为 None。"""
    try:
        fm = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as e:
        # 常见原因：description 里有英文冒号
        hint = ""
        if "mapping values are not allowed" in str(e):
            hint = "（常见原因：description 里有英文冒号——换成破折号或全角冒号）"
        return None, f"前置元数据 YAML 格式错误：{e}{hint}"
    if not isinstance(fm, dict):
        return None, "前置元数据必须是 YAML 字典格式"
    return fm, None


def validate_skill(skill_path, deep=False):
    """校验一个技能。返回 (ok, messages)，messages 是 [(level, text), ...]，level ∈ {error, warning}。"""
    skill_path = Path(skill_path)
    messages = []

    # 1. SKILL.md 存在
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, [('error', '找不到 SKILL.md 文件')]

    content = skill_md.read_text()
    if not content.startswith('---'):
        return False, [('error', '找不到 YAML 前置元数据（开头没有 ---）')]

    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, [('error', '前置元数据格式无效')]

    fm, err = _check_frontmatter(match.group(1))
    if err:
        return False, [('error', err)]

    # 2. 未识别的键
    unexpected = set(fm.keys()) - ALLOWED_PROPERTIES
    if unexpected:
        return False, [('error',
            f"SKILL.md 前置元数据里有不认识的键：{', '.join(sorted(unexpected))}。"
            f"允许的属性有：{', '.join(sorted(ALLOWED_PROPERTIES))}")]

    # 3. 必填字段
    if 'name' not in fm:
        return False, [('error', "前置元数据里缺少 'name' 字段")]
    if 'description' not in fm:
        return False, [('error', "前置元数据里缺少 'description' 字段")]

    # 4. name 规则
    name = fm.get('name', '')
    if not isinstance(name, str):
        return False, [('error', f"name 必须是字符串，实际是 {type(name).__name__}")]
    name = name.strip()
    if name:
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, [('error', f"name '{name}' 应该用 kebab-case 格式（只能小写字母、数字、连字符）")]
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, [('error', f"name '{name}' 不能以连字符开头/结尾，也不能有连续的连字符")]
        if len(name) > 64:
            return False, [('error', f"name 太长了（{len(name)} 个字符）。最多 64 个字符。")]
        if name.lower() in RESERVED_NAMES:
            return False, [('error', f"name '{name}' 是保留词，不能用")]
        # 模糊名提示
        if name in {'helper', 'utils', 'tools', 'skill'}:
            messages.append(('warning',
                f"name '{name}' 太模糊，换成能说明具体做什么的名字（如 processing-pdfs）"))

    # 5. description 规则
    description = fm.get('description', '')
    if not isinstance(description, str):
        return False, [('error', f"description 必须是字符串，实际是 {type(description).__name__}")]
    description = description.strip()
    if description:
        if '<' in description or '>' in description:
            return False, [('error', "description 不能包含尖括号（< 或 >）")]
        if len(description) > 1024:
            return False, [('error', f"description 太长了（{len(description)} 个字符）。最多 1024 个字符。")]

    # 6. compatibility
    compatibility = fm.get('compatibility', '')
    if compatibility:
        if not isinstance(compatibility, str):
            return False, [('error', f"compatibility 必须是字符串，实际是 {type(compatibility).__name__}")]
        if len(compatibility) > 500:
            return False, [('error', f"compatibility 太长了（{len(compatibility)} 个字符）。最多 500 个字符。")]

    # 7. WorkBuddy 必填联动：如果出现 agent_created=true，要求配套字段
    if fm.get('agent_created') is True:
        for required in ('version', 'category', 'platforms'):
            if required not in fm:
                messages.append(('warning',
                    f"WorkBuddy 技能标了 agent_created: true，建议同时提供 {required} 字段"))

    # ------ deep 模式：内容层检查 ------
    if deep:
        body = content[match.end():].strip('\n')
        body_lines = body.count('\n') + 1
        if body_lines > 500:
            messages.append(('warning',
                f"SKILL.md 正文 {body_lines} 行，超过官方建议的 500 行——把细节拆到 references/ 下"))

        # description 触发词线索：太短、或没提"什么时候用"
        if len(description) < 30:
            messages.append(('warning',
                "description 太短——官方要求同时写清'做什么'和'什么时候触发'，"
                "建议加上 Use when / 用于 / 当...时 这类触发短语"))
        else:
            has_trigger_hint = re.search(
                r'(use when|when user|use it when|when the user|when to use|用于|当.*时|触发)',
                description, re.IGNORECASE)
            if not has_trigger_hint:
                messages.append(('warning',
                    "description 里没看到明确的触发场景短语（Use when / 用于 / 当...时），"
                    "模型可能不知道什么时候该调用这个技能"))

        # description 里有英文冒号会导致 YAML 解析失败
        if re.search(r'[\u4e00-\u9fff]:', description) or re.search(r'\w:', description):
            messages.append(('warning',
                "description 里有英文冒号——YAML 会解析失败，建议换成破折号（-）或全角冒号（：）"))

        # examples
        examples_dir = skill_path / 'examples'
        if not examples_dir.exists() and 'examples/' not in content:
            messages.append(('warning',
                "没看到 examples/ 目录或正文里的示例 input/output 对——"
                "官方要求 examples 必须具体，不能抽象"))
        else:
            # 检查 examples 里是不是还留着模板占位符
            for ex_file in examples_dir.glob('*.md') if examples_dir.exists() else []:
                ex_text = ex_file.read_text()
                if 'TODO' in ex_text or '删掉这一段' in ex_text or '（一句真实用户' in ex_text:
                    messages.append(('warning',
                        f"examples/{ex_file.name} 里还有模板占位符——"
                        "换成真实的 input/output 对，别留 TODO"))

        # evals
        evals_path = skill_path / 'evals' / 'evals.json'
        if not evals_path.exists() and not (skill_path / 'evals.json').exists() and 'evals/evals.json' not in content:
            messages.append(('warning',
                "没看到 evals/evals.json——官方建议至少写 3 个测试用例再开始迭代"))
        elif evals_path.exists():
            try:
                evals_data = json.loads(evals_path.read_text())
                for ev in evals_data.get('evals', []):
                    p = ev.get('prompt', '')
                    if '用户真实会说' in p or '边界情况' in p or '不该触发' in p:
                        messages.append(('warning',
                            f"evals/evals.json 第 {ev.get('id', '?')} 条还是模板——换成真实用户会说的话"))
                        break
            except Exception:
                pass

        # scripts 存在性
        if not (skill_path / 'scripts').exists():
            messages.append(('warning',
                "没有 scripts/ 目录——如果这个技能里有每次都要重复做的确定性操作"
                "（格式转换、解析、校验），应该写成脚本，不要让模型每次临场写"))
        else:
            # 合规扫描：scripts/ 里的 .py 有没有往外发数据 / 读敏感文件
            import re as _re
            network_patterns = [
                r'requests\.(post|put|get|patch|delete)\s*\(',
                r'urllib\.request\.urlopen',
                r'httpx\.(post|put|get)',
                r'urlopen\s*\(',
                r'socket\.connect',
            ]
            secret_patterns = [
                r'\.env',
                r'os\.environ\[',
                r'os\.getenv\s*\(',
                r'api_key',
                r'token',
                r'password',
                r'secret',
            ]
            for py_file in (skill_path / 'scripts').rglob('*.py'):
                try:
                    py_text = py_file.read_text()
                    hits_net = []
                    for pat in network_patterns:
                        if _re.search(pat, py_text):
                            hits_net.append(pat)
                    if hits_net:
                        messages.append(('warning',
                            f"scripts/{py_file.name} 里有网络调用（{', '.join(hits_net[:2])}）——"
                            "确认数据是否会发到境外/第三方，国内合规要求数据不出境"))
                    hits_sec = []
                    for pat in secret_patterns:
                        if _re.search(pat, py_text, _re.IGNORECASE):
                            hits_sec.append(pat)
                    if hits_sec:
                        messages.append(('warning',
                            f"scripts/{py_file.name} 里读敏感信息（{', '.join(hits_sec[:3])}）——"
                            "确认不要硬编码凭据，从环境变量读，且不要把用户数据写日志"))
                except Exception:
                    pass

        # 引用嵌套深度（粗查：正文里链接到的 .md 是否还指向别的 .md）
        ref_links = re.findall(r'\[[^\]]+\]\(([^)]+\.md)\)', body)
        nested = []
        for link in ref_links:
            if link.startswith('http'):
                continue
            target = (skill_path / link).resolve()
            if not target.exists():
                continue
            try:
                sub = target.read_text()
                sub_links = re.findall(r'\[[^\]]+\]\(([^)]+\.md)\)', sub)
                sub_links = [l for l in sub_links if not l.startswith('http')]
                if sub_links:
                    nested.append(f"{link} -> {', '.join(sub_links)}")
            except Exception:
                pass
        if nested:
            messages.append(('warning',
                "发现引用嵌套超过一层：" + '; '.join(nested)
                + "——官方要求引用只一层深，否则模型可能只读半份文件"))

    has_error = any(level == 'error' for level, _ in messages)
    return (not has_error), messages


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    deep = '--deep' in sys.argv
    target = None
    for arg in sys.argv[1:]:
        if arg != '--deep':
            target = arg
    if not target:
        print(__doc__)
        sys.exit(1)

    ok, messages = validate_skill(target, deep=deep)
    for level, text in messages:
        mark = '❌' if level == 'error' else '⚠️ '
        print(f"{mark} {text}")
    if ok:
        print("✅ 技能校验通过！" + ("（deep 模式下的 warning 不阻断）" if deep else ""))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
