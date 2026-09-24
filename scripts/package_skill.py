#!/usr/bin/env python3
"""
技能打包器 - 把技能文件夹打成可分发的 .skill 文件

用法：
    python -m scripts.package_skill <技能文件夹路径> [输出目录]

示例：
    python -m scripts.package_skill skills/public/my-skill
    python -m scripts.package_skill skills/public/my-skill ./dist

注意：在技能创建器根目录下用 -m 方式运行（本脚本依赖 scripts.quick_validate）。
"""

import fnmatch
import sys
import zipfile
from pathlib import Path
from scripts.quick_validate import validate_skill

# 打包时要排除的模式
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
# 只在技能根目录排除的目录（深层嵌套的不算）
ROOT_EXCLUDE_DIRS = {"evals", "tests"}


def should_exclude(rel_path: Path) -> bool:
    """检查一个路径要不要从打包里排除"""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    # rel_path 是相对 skill_path.parent 的，所以 parts[0] 是技能文件夹名
    # parts[1]（如果有的话）是第一个子目录
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def package_skill(skill_path, output_dir=None):
    """
    把技能文件夹打包成 .skill 文件。

    参数：
        skill_path: 技能文件夹路径
        output_dir: 可选，.skill 文件的输出目录（默认当前目录）

    返回：
        创建的 .skill 文件路径，出错就返回 None
    """
    skill_path = Path(skill_path).resolve()

    # 校验技能文件夹存在
    if not skill_path.exists():
        print(f"❌ 错误：找不到技能文件夹：{skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"❌ 错误：路径不是目录：{skill_path}")
        return None

    # 校验 SKILL.md 存在
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"❌ 错误：{skill_path} 里找不到 SKILL.md")
        return None

    # 打包前先跑校验
    print("🔍 正在校验技能...")
    valid, messages = validate_skill(skill_path)
    # validate_skill 返回的是 [(level, text), ...]，逐条渲染——直接把列表塞进 f-string 会甩出一坨 tuple
    for level, text in messages:
        print(f"{'❌' if level == 'error' else '⚠️ '} {text}")
    if not valid:
        print("   请先修复校验错误再打包。")
        return None
    print()

    # 确定输出位置
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path.cwd()

    skill_filename = output_path / f"{skill_name}.skill"

    # 创建 .skill 文件（zip 格式）
    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 遍历技能目录，排除构建产物
            for file_path in skill_path.rglob('*'):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  跳过：{arcname}")
                    continue
                zipf.write(file_path, arcname)
                print(f"  添加：{arcname}")

        print(f"\n✅ 技能打包成功：{skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"❌ 创建 .skill 文件失败：{e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("用法：python -m scripts.package_skill <技能文件夹路径> [输出目录]")
        print("\n示例：")
        print("  python -m scripts.package_skill skills/public/my-skill")
        print("  python -m scripts.package_skill skills/public/my-skill ./dist")
        sys.exit(1)

    skill_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"📦 正在打包技能：{skill_path}")
    if output_dir:
        print(f"   输出目录：{output_dir}")
    print()

    result = package_skill(skill_path, output_dir)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
