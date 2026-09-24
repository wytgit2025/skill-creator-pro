"""配对 A/B 实验的编排与统计。

这个脚本只做确定性的事：展开方向语料库、盲化产物、算配对统计。
它不调用任何模型——造技能由 agent 按 SKILL.md 走，打分由 agents/grader.md 走，
盲评由 agents/comparator.md 走。

三个子命令：
    plan       把方向语料库展开成配对单元，建目录骨架和 eval_metadata.json
    blind      把两臂产物去标识并确定性随机成 A/B，供盲评使用
    aggregate  算配对差值、符号检验、盲评胜率与判分一致性

为什么不复用 aggregate_benchmark.py：它做的是全局非配对的
mean 相减（configs[0] - configs[1]），而配对设计看的是「同一个测试任务下
两臂的差值」。同一方向有多个测试任务，把 grading.json 全混在一起算均值
会产生伪重复（pseudo-replication），把方差算小、显著性算高。

用法：
    python3 -m scripts.paired_ab plan --workspace paired-ab-workspace
    python3 -m scripts.paired_ab blind --workspace paired-ab-workspace
    python3 -m scripts.paired_ab aggregate --workspace paired-ab-workspace
"""

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# 臂的定义顺序即语义：主臂在前，两个基线臂在后
ARMS = ("new_skill", "old_skill", "without_skill")

# 参与盲评的臂。without_skill 不参与：无技能产物和带技能产物形态差异明显，
# 混进盲评包等于把盲态捅破。
BLIND_ARMS = ("new_skill", "old_skill")

PRIMARY_ARM = "new_skill"

# 三组配对比较，语义是「被减 vs 减」
COMPARISONS = (
    ("new_skill", "old_skill"),
    ("new_skill", "without_skill"),
    ("old_skill", "without_skill"),
)

# 盲包里不允许出现的来源痕迹（大小写不敏感）
DEFAULT_LEAK_MARKERS = (
    "new_skill",
    "old_skill",
    "without_skill",
    "skill-creator-pro",
    "skill_creator_pro",
)

TEXT_SUFFIXES = (
    ".md", ".txt", ".json", ".yaml", ".yml", ".py", ".csv",
    ".html", ".sh", ".toml", ".ini", ".cfg",
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# 语料库加载与校验
# --------------------------------------------------------------------------


def load_directions(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"错误：找不到方向语料库 {path}")
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SystemExit(f"错误：{path} 不是合法 JSON：{e}")
    if not isinstance(data, dict):
        raise SystemExit(f"错误：{path} 顶层必须是对象")
    return data


def validate_directions(data: dict, min_variants: int) -> list[str]:
    """校验语料库结构。

    严格是刻意的：漏写 expectations 的用例会被聚合静默跳过，报告显示空值，
    实验看着跑完了其实是白跑。
    """
    errors: list[str] = []

    layer_ids = set()
    for layer in data.get("layers", []):
        lid = layer.get("id")
        if not lid:
            errors.append("layers[] 里有条目缺 id")
            continue
        if lid in layer_ids:
            errors.append(f"layer id 重复：{lid}")
        layer_ids.add(lid)
    if not layer_ids:
        errors.append("没有定义任何 layer")

    directions = data.get("directions", [])
    if not directions:
        errors.append("没有定义任何 direction")

    seen_dirs: set[str] = set()
    covered: set[str] = set()

    for direction in directions:
        did = direction.get("id", "<缺 id>")
        if did in seen_dirs:
            errors.append(f"direction id 重复：{did}")
        seen_dirs.add(did)

        layer = direction.get("layer")
        if layer not in layer_ids:
            errors.append(f"{did}: layer '{layer}' 不在 layers 列表里")
        else:
            covered.add(layer)

        if not str(direction.get("brief", "")).strip():
            errors.append(f"{did}: 缺 brief（A/B 两组要收到同一份 brief）")

        variants = direction.get("variants", [])
        if len(variants) < min_variants:
            errors.append(
                f"{did}: 只有 {len(variants)} 个变体，低于要求的 {min_variants} 个"
                "（同方向多变体是压住方向间异质性的关键）"
            )

        seen_variants: set[str] = set()
        for variant in variants:
            vid = variant.get("id", "<缺 id>")
            if vid in seen_variants:
                errors.append(f"{did}: variant id 重复：{vid}")
            seen_variants.add(vid)

            evals = variant.get("evals", [])
            if not evals:
                errors.append(f"{did}/{vid}: 没有 evals")
            for ev in evals:
                tag = f"{did}/{vid}/e{ev.get('id', '?')}"
                if not isinstance(ev.get("id"), int):
                    errors.append(f"{tag}: evals[].id 必须是整数")
                if not str(ev.get("prompt", "")).strip():
                    errors.append(f"{tag}: 缺 prompt")
                expectations = ev.get("expectations")
                if not isinstance(expectations, list) or not expectations:
                    errors.append(f"{tag}: expectations 必须是非空数组")
                elif not all(isinstance(x, str) and x.strip() for x in expectations):
                    errors.append(f"{tag}: expectations 必须是非空字符串数组")

    uncovered = layer_ids - covered
    if uncovered:
        errors.append(f"这些 layer 没有任何方向覆盖：{sorted(uncovered)}")
    return errors


def expand_units(data: dict) -> list[dict]:
    """把语料库展开成配对单元（一个单元 = 一个测试任务 = 一个 eval 目录）。"""
    units = []
    eval_id = 0
    for direction in data["directions"]:
        for variant in direction["variants"]:
            for ev in variant["evals"]:
                eval_id += 1
                units.append({
                    "eval_id": eval_id,
                    "layer": direction["layer"],
                    "direction": direction["id"],
                    "direction_title": direction.get("title", direction["id"]),
                    "variant": variant["id"],
                    "variant_label": variant.get("label", variant["id"]),
                    "eval_no": ev["id"],
                    "eval_dir": f"{direction['id']}__{variant['id']}__e{ev['id']}",
                    "prompt": ev["prompt"],
                    "expected_output": ev.get("expected_output", ""),
                    "expectations": ev["expectations"],
                })
    return units


def cmd_plan(args) -> int:
    data = load_directions(Path(args.directions))
    errors = validate_directions(data, args.min_variants)
    if errors:
        print("方向语料库校验未通过：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    units = expand_units(data)
    workspace = Path(args.workspace)
    layers = {l["id"]: l.get("label", l["id"]) for l in data["layers"]}
    by_layer: dict[str, list[str]] = {}
    for direction in data["directions"]:
        by_layer.setdefault(direction["layer"], []).append(direction["id"])

    if not args.dry_run:
        workspace.mkdir(parents=True, exist_ok=True)

    for unit in units:
        eval_dir = workspace / unit["eval_dir"]
        if not args.dry_run:
            eval_dir.mkdir(parents=True, exist_ok=True)
            for arm in ARMS:
                (eval_dir / arm).mkdir(exist_ok=True)

            metadata = {
                "eval_id": unit["eval_id"],
                "eval_name": f"{unit['direction']}-{unit['variant']}-e{unit['eval_no']}",
                "prompt": unit["prompt"],
                "expectations": unit["expectations"],
                # 额外字段。schemas.md 列的四个键是查看器和 aggregate_benchmark
                # 读的；pairing 块它们不认识但会忽略，配对统计靠它还原方向归属。
                "pairing": {
                    "layer": unit["layer"],
                    "direction": unit["direction"],
                    "variant": unit["variant"],
                    "eval_no": unit["eval_no"],
                    "arms": list(ARMS),
                },
            }
            (eval_dir / "eval_metadata.json").write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"
            )

    plan = {
        "generated_at": _now(),
        "directions_file": str(Path(args.directions).resolve()),
        "workspace": str(workspace.resolve()),
        "arms": {arm: data.get("arms", {}).get(arm, "") for arm in ARMS},
        "layers": layers,
        "directions_by_layer": by_layer,
        "units": [
            {k: v for k, v in unit.items() if k != "expectations"}
            | {"expectations_count": len(unit["expectations"])}
            for unit in units
        ],
    }
    if not args.dry_run:
        (workspace / "plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False) + "\n"
        )

    print(f"方向数：{len(data['directions'])}，配对单元：{len(units)} 个")
    print(f"每单元 {len(ARMS)} 个臂（{' / '.join(ARMS)}），合计待跑 {len(units) * len(ARMS)} 次")
    for layer_id, label in layers.items():
        print(f"  {label}：{len(by_layer.get(layer_id, []))} 个方向")
    if args.dry_run:
        print("（--dry-run，未写盘）")
    else:
        print(f"骨架已建：{workspace.resolve()}")
        print("下一步：对每个方向各造两套技能（old_skill 用官方原版 / new_skill 用 Pro），")
        print("        产物落到对应臂目录，再用 agents/grader.md 打分出 grading.json。")
    return 0


# --------------------------------------------------------------------------
# blind
# --------------------------------------------------------------------------


def _leak_scan(pack_dir: Path, markers: tuple[str, ...]) -> list[str]:
    """检查盲包里是否残留来源痕迹。

    盲评的前提是判分者看不出哪个是哪个。光靠「约定不猜」守不住——
    产物里只要出现 skill-creator-pro 或臂目录名，盲态就已经破了。
    """
    findings = []
    lowered = tuple(m.lower() for m in markers if m)
    for path in sorted(pack_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            if any(marker in low for marker in lowered):
                findings.append(f"{path.relative_to(pack_dir)}:{lineno}")
    return findings


def cmd_blind(args) -> int:
    workspace = Path(args.workspace)
    plan_path = workspace / "plan.json"
    if not plan_path.exists():
        raise SystemExit(f"错误：找不到 {plan_path}，先跑 plan")
    plan = json.loads(plan_path.read_text())

    blind_root = Path(args.blind_root) if args.blind_root else Path(f"{workspace}-blind")
    keys_dir = blind_root / ".keys"
    blind_root.mkdir(parents=True, exist_ok=True)
    keys_dir.mkdir(parents=True, exist_ok=True)

    pairs, skipped = [], []
    for unit in plan["units"]:
        eval_dir_name = unit["eval_dir"]
        eval_dir = workspace / eval_dir_name
        available = [
            arm for arm in BLIND_ARMS
            if (eval_dir / arm).is_dir() and any((eval_dir / arm).iterdir())
        ]
        if len(available) < 2:
            skipped.append((eval_dir_name, available))
        else:
            pairs.append((eval_dir_name, unit, available))

    if not pairs:
        print("没有任何单元两侧都齐了，没法盲化。", file=sys.stderr)
        print("每个臂目录下要先有产物（outputs/、transcript 之类）。", file=sys.stderr)
        return 1

    leak_reports = []
    for eval_dir_name, unit, available in pairs:
        pack_dir = blind_root / eval_dir_name
        if pack_dir.exists():
            shutil.rmtree(pack_dir)
        pack_dir.mkdir(parents=True)

        # 确定性随机：同一个单元无论跑多少次 A/B 分配都一致，方便复核；
        # 种子取自单元名，所以不同单元的分配互不相同。
        seed = int(hashlib.sha256(eval_dir_name.encode()).hexdigest()[:12], 16)
        shuffled = list(available)
        random.Random(seed).shuffle(shuffled)
        slots = dict(zip(("A", "B"), shuffled))

        for slot, arm in slots.items():
            shutil.copytree(workspace / eval_dir_name / arm, pack_dir / slot)

        (pack_dir / "prompt.txt").write_text(unit["prompt"] + "\n")
        (pack_dir / "expectations.json").write_text(
            json.dumps(
                {"expected_output": unit.get("expected_output", ""),
                 "expectations": unit.get("expectations", [])},
                indent=2, ensure_ascii=False,
            ) + "\n"
        )

        # 密钥不能放进盲包——判分者读得到的目录里不许有它
        (keys_dir / f"{eval_dir_name}.json").write_text(
            json.dumps(
                {"eval_dir": eval_dir_name, "direction": unit["direction"],
                 "variant": unit["variant"], "seed": seed, "slots": slots},
                indent=2, ensure_ascii=False,
            ) + "\n"
        )

        findings = _leak_scan(
            pack_dir,
            DEFAULT_LEAK_MARKERS + (unit["direction"], unit.get("direction_title", "")),
        )
        if findings:
            leak_reports.append((eval_dir_name, findings))

    print(f"已生成 {len(pairs)} 个盲评包：{blind_root.resolve()}")
    print(f"密钥单独放在：{keys_dir.resolve()}（不要给判分者）")
    if skipped:
        print(f"跳过的单元（某侧还没产物）：{len(skipped)}")
        for name, available in skipped[:5]:
            print(f"  {name}: 只有 {available or '无'}")
    if leak_reports:
        print()
        print(f"⚠️ {len(leak_reports)} 个盲包发现来源痕迹，盲态已破：")
        for name, findings in leak_reports[:5]:
            print(f"  {name}：{len(findings)} 处，例如 {findings[:3]}")
        if args.strict:
            print("（--strict：按失败退出）", file=sys.stderr)
            return 1
    return 0


# --------------------------------------------------------------------------
# aggregate
# --------------------------------------------------------------------------


def _read_pass_rate(grading_path: Path) -> float | None:
    """从 grading.json 读通过率，优先用 summary.pass_rate。"""
    try:
        data = json.loads(grading_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    summary = data.get("summary") or {}
    rate = summary.get("pass_rate")
    if isinstance(rate, (int, float)):
        return float(rate)
    passed, total = summary.get("passed"), summary.get("total")
    if isinstance(passed, int) and isinstance(total, int) and total > 0:
        return passed / total
    expectations = data.get("expectations")
    if isinstance(expectations, list) and expectations:
        return sum(1 for e in expectations if isinstance(e, dict) and e.get("passed")) / len(expectations)
    return None


def arm_pass_rate(eval_dir: Path, arm: str) -> float | None:
    """取一个臂在某个单元下的通过率。

    支持 <arm>/grading.json（跑一次）和 <arm>/run-N/grading.json（跑多次）。
    跑多次时取均值——配对比较用的是单元级的一个数，不是把次数全铺开。
    """
    arm_dir = eval_dir / arm
    if not arm_dir.is_dir():
        return None
    rates = []
    flat = arm_dir / "grading.json"
    if flat.exists():
        rate = _read_pass_rate(flat)
        if rate is not None:
            rates.append(rate)
    for run_dir in sorted(arm_dir.glob("run-*")):
        grading = run_dir / "grading.json"
        if grading.exists():
            rate = _read_pass_rate(grading)
            if rate is not None:
                rates.append(rate)
    return sum(rates) / len(rates) if rates else None


def sign_test_p(k: int, n: int) -> float:
    """双侧精确符号检验（Binom(n, 0.5)）。

    不引 scipy——requirements.txt 只有 requests 和 PyYAML。n 很小时正态近似
    会失真，所以用精确算法：把概率不超过观测点概率的项全加起来。
    """
    if n <= 0:
        return 1.0
    k = max(0, min(k, n))
    pmf = [math.comb(n, i) / (2 ** n) for i in range(n + 1)]
    observed = pmf[k]
    return min(1.0, sum(p for p in pmf if p <= observed + 1e-12))


def sign_test_critical(n: int, alpha: float = 0.05) -> int | None:
    """达到显著性所需的最少「胜」次数。

    这个数是给实验设计用的：如果 n 个方向里连这么多次都赢不了，
    那这个规模下无论真实效应多大都测不出显著性，得加样本或改指标。
    """
    # 从中间往上找，第一个显著的 k 就是门槛。
    # 反着找（从 n 往下）会立刻命中 k=n 并返回 n，等于没算。
    for k in range(n // 2, n + 1):
        if sign_test_p(k, n) <= alpha:
            return k
    return None


def discover_units(workspace: Path) -> list[dict]:
    """扫描 workspace 还原配对单元。比读 plan.json 稳，plan.json 删了也能跑。"""
    units = []
    for eval_dir in sorted(p for p in workspace.iterdir() if p.is_dir()):
        meta_path = eval_dir / "eval_metadata.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            continue
        pairing = meta.get("pairing")
        if not isinstance(pairing, dict):
            continue
        units.append({
            "eval_dir": eval_dir.name,
            "path": eval_dir,
            "eval_id": meta.get("eval_id"),
            "direction": pairing.get("direction"),
            "layer": pairing.get("layer"),
            "variant": pairing.get("variant"),
        })
    return units


def _decode_blind(blind_root: Path) -> dict:
    """反解盲评结果。A/B 是随机分配的，不查密钥就会把胜率算反。"""
    keys_dir = blind_root / ".keys"
    result = {"pairs": 0, "wins": {}, "ties": 0, "unresolved": [],
              "comparable": 0, "agreements": 0, "inconsistent": []}
    if not keys_dir.is_dir():
        return result

    for key_path in sorted(keys_dir.glob("*.json")):
        try:
            key = json.loads(key_path.read_text())
        except json.JSONDecodeError:
            continue
        slots = key.get("slots", {})
        pack = blind_root / key.get("eval_dir", key_path.stem)
        comparisons = sorted(pack.glob("comparison*.json")) if pack.is_dir() else []
        if not comparisons:
            continue
        result["pairs"] += 1

        winners = []
        for comparison_path in comparisons:
            try:
                data = json.loads(comparison_path.read_text())
            except json.JSONDecodeError:
                continue
            winner = str(data.get("winner", "")).strip()
            if winner in ("A", "B", "平局", "tie", "Tie"):
                winners.append(winner)
        if not winners:
            result["unresolved"].append(key.get("eval_dir"))
            continue

        # 同一对产物评了多次：先看判分者自己稳不稳
        if len(winners) > 1:
            result["comparable"] += 1
            majority = max(set(winners), key=winners.count)
            if winners.count(majority) == len(winners):
                result["agreements"] += 1
            else:
                result["inconsistent"].append({
                    "eval_dir": key.get("eval_dir"), "winners": winners,
                })

        winner = winners[0]
        if winner in ("平局", "tie", "Tie"):
            result["ties"] += 1
            continue
        arm = slots.get(winner)
        if arm:
            result["wins"][arm] = result["wins"].get(arm, 0) + 1
    return result


def _paired_stats(deltas: list[float]) -> dict:
    n = len(deltas)
    wins = sum(1 for d in deltas if d > 0)
    losses = sum(1 for d in deltas if d < 0)
    ties = n - wins - losses
    effective = wins + losses
    return {
        "n": n,
        "effective_n": effective,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "mean_delta": round(sum(deltas) / n, 4) if n else None,
        "median_delta": round(sorted(deltas)[n // 2], 4) if n else None,
        "sign_test_p": round(sign_test_p(wins, effective), 4) if effective else None,
        "critical_wins": sign_test_critical(effective) if effective else None,
        "significant": (sign_test_p(wins, effective) <= 0.05) if effective else False,
    }


def cmd_aggregate(args) -> int:
    workspace = Path(args.workspace)
    if not workspace.is_dir():
        raise SystemExit(f"错误：找不到工作区 {workspace}")

    units = discover_units(workspace)
    if not units:
        raise SystemExit(f"错误：{workspace} 下没有找到任何配对单元（缺 eval_metadata.json 的 pairing 块）")

    # 单元级：每个臂的通过率 + 配对差值
    unit_rows, incomplete = [], []
    for unit in units:
        rates = {arm: arm_pass_rate(unit["path"], arm) for arm in ARMS}
        missing = [arm for arm, rate in rates.items() if rate is None]
        if len(missing) == len(ARMS):
            incomplete.append({"eval_dir": unit["eval_dir"], "missing": missing})
            continue
        row = {
            "eval_dir": unit["eval_dir"],
            "direction": unit["direction"],
            "layer": unit["layer"],
            "variant": unit["variant"],
            "rates": {arm: (round(r, 4) if r is not None else None) for arm, r in rates.items()},
            "deltas": {},
        }
        for high, low in COMPARISONS:
            if rates[high] is not None and rates[low] is not None:
                row["deltas"][f"{high}_vs_{low}"] = round(rates[high] - rates[low], 4)
        if missing:
            incomplete.append({"eval_dir": unit["eval_dir"], "missing": missing})
        unit_rows.append(row)

    # 方向级：同方向的多个单元先平均，避免多用例的方向在层均值里权重翻倍
    directions: dict[str, dict] = {}
    for row in unit_rows:
        entry = directions.setdefault(row["direction"], {
            "layer": row["layer"],
            "deltas": {f"{h}_vs_{l}": [] for h, l in COMPARISONS},
        })
        for key, value in row["deltas"].items():
            entry["deltas"][key].append(value)

    direction_stats = {}
    for name, entry in sorted(directions.items()):
        direction_stats[name] = {
            "layer": entry["layer"],
            "units": max((len(v) for v in entry["deltas"].values()), default=0),
            "comparisons": {
                key: _paired_stats(values)
                for key, values in entry["deltas"].items() if values
            },
        }

    # 层聚合：对方向的均值再求均值，不是把所有单元堆起来
    layer_stats = {}
    for name, stats in direction_stats.items():
        layer = stats["layer"]
        bucket = layer_stats.setdefault(layer, {f"{h}_vs_{l}": [] for h, l in COMPARISONS})
        for key, comp in stats["comparisons"].items():
            if comp["mean_delta"] is not None:
                bucket[key].append(comp["mean_delta"])
    layer_summary = {
        layer: {key: _paired_stats(values) for key, values in bucket.items() if values}
        for layer, bucket in sorted(layer_stats.items())
    }

    # 全局：按方向均值再算一次，报告的主数字用这个
    overall = {}
    for key in (f"{h}_vs_{l}" for h, l in COMPARISONS):
        values = [
            stats["comparisons"][key]["mean_delta"]
            for stats in direction_stats.values() if key in stats["comparisons"]
        ]
        if values:
            overall[key] = _paired_stats(values)

    blind_root = Path(args.blind_root) if args.blind_root else Path(f"{workspace}-blind")
    blind = _decode_blind(blind_root)

    n_directions = len(direction_stats)
    critical = sign_test_critical(n_directions)
    caveats = []
    if n_directions and critical:
        caveats.append(
            f"方向数 {n_directions}：符号检验要 {critical}/{n_directions} 个方向同向才算显著（α=0.05）。"
            f"在这个规模下，中等效应很容易测不出来——别把「不显著」读成「没效果」。"
        )
    if blind["comparable"] and blind["agreements"] < blind["comparable"]:
        caveats.append(
            f"判分者重复评同一对产物时一致性 {blind['agreements']}/{blind['comparable']}，"
            f"不一致的单元说明 judge 噪声和效应量可能同量级。"
        )
    if incomplete:
        caveats.append(f"{len(incomplete)} 个单元缺臂，未计入配对统计（缺臂不是零分）。")

    report = {
        "generated_at": _now(),
        "workspace": str(workspace.resolve()),
        "blind_root": str(blind_root.resolve()),
        "counts": {
            "planned_units": len(units),
            "usable_units": len(unit_rows),
            "directions": n_directions,
            "incomplete": len(incomplete),
        },
        "overall": overall,
        "by_layer": layer_summary,
        "by_direction": direction_stats,
        "units": unit_rows,
        "incomplete_units": incomplete,
        "blind": blind,
        "caveats": caveats,
    }

    json_path = Path(args.json) if args.json else workspace / "paired_ab_report.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    md_path = Path(args.md) if args.md else workspace / "paired_ab_report.md"
    md_path.write_text(_render_markdown(report))

    print(f"配对单元：{report['counts']['usable_units']}/{len(units)} 可用，涉及 {n_directions} 个方向")
    for key, stats in overall.items():
        print(f"  {key}: 平均差 {stats['mean_delta']:+.4f}，"
              f"{stats['wins']} 胜 / {stats['losses']} 负 / {stats['ties']} 平，"
              f"p={stats['sign_test_p']}")
    if blind["pairs"]:
        wins = blind["wins"]
        print(f"  盲评 {blind['pairs']} 对：new_skill 胜 {wins.get('new_skill', 0)}，"
              f"old_skill 胜 {wins.get('old_skill', 0)}，平 {blind['ties']}")
    for caveat in caveats:
        print(f"⚠️ {caveat}")
    print(f"报告：{json_path.resolve()}")
    print(f"     {md_path.resolve()}")
    return 0


def _render_markdown(report: dict) -> str:
    lines = ["# 配对 A/B 实验报告", "",
             f"生成时间：{report['generated_at']}", ""]
    counts = report["counts"]
    lines += [
        f"- 配对单元：{counts['usable_units']}/{counts['planned_units']} 可用",
        f"- 方向数：{counts['directions']}",
        f"- 缺臂单元：{counts['incomplete']}",
        "",
        "## 总体（按方向均值）", "",
        "| 比较 | 方向数 | 平均差 | 胜/负/平 | 符号检验 p | 显著 |",
        "|---|---|---|---|---|---|",
    ]
    for key, stats in report["overall"].items():
        lines.append(
            f"| {key} | {stats['n']} | {stats['mean_delta']:+.4f} | "
            f"{stats['wins']}/{stats['losses']}/{stats['ties']} | "
            f"{stats['sign_test_p']} | {'是' if stats['significant'] else '否'} |"
        )

    lines += ["", "## 分层", "", "| 层 | 比较 | 方向数 | 平均差 | p |", "|---|---|---|---|---|"]
    for layer, comparisons in report["by_layer"].items():
        for key, stats in comparisons.items():
            lines.append(
                f"| {layer} | {key} | {stats['n']} | {stats['mean_delta']:+.4f} | {stats['sign_test_p']} |"
            )

    lines += ["", "## 盲评", ""]
    blind = report["blind"]
    if blind["pairs"]:
        wins = blind["wins"]
        lines += [
            f"- 参与盲评：{blind['pairs']} 对",
            f"- new_skill 胜：{wins.get('new_skill', 0)}",
            f"- old_skill 胜：{wins.get('old_skill', 0)}",
            f"- 平局：{blind['ties']}",
            f"- 判分者重复一致：{blind['agreements']}/{blind['comparable']}",
            "",
        ]
    else:
        lines += ["（没有找到盲评结果；先跑 blind 并把 comparison*.json 放进盲包）", ""]

    if report["caveats"]:
        lines += ["## 注意", ""]
        lines += [f"- {c}" for c in report["caveats"]]
        lines.append("")

    lines += ["## 单元明细", "", "| 单元 | 层 | new | old | without | new-old |", "|---|---|---|---|---|---|"]
    for row in report["units"]:
        rates = row["rates"]
        fmt = lambda v: "—" if v is None else f"{v:.2f}"  # noqa: E731
        lines.append(
            f"| {row['eval_dir']} | {row['layer']} | {fmt(rates.get('new_skill'))} | "
            f"{fmt(rates.get('old_skill'))} | {fmt(rates.get('without_skill'))} | "
            f"{row['deltas'].get('new_skill_vs_old_skill', '—')} |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="配对 A/B 实验编排：展开方向语料库、盲化产物、算配对统计"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="展开方向语料库，建目录骨架")
    p_plan.add_argument("--workspace", required=True, help="实验工作区目录")
    p_plan.add_argument("--directions", default="evals/paired_ab/directions.json",
                        help="方向语料库 JSON 路径")
    p_plan.add_argument("--min-variants", type=int, default=3,
                        help="每个方向至少要几个变体（默认 3）")
    p_plan.add_argument("--dry-run", action="store_true", help="只校验和打印，不写盘")
    p_plan.set_defaults(func=cmd_plan)

    p_blind = sub.add_parser("blind", help="生成盲评包（A/B 去标识 + 确定性随机）")
    p_blind.add_argument("--workspace", required=True, help="实验工作区目录")
    p_blind.add_argument("--blind-root", default=None, help="盲包输出目录（默认 <workspace>-blind）")
    p_blind.add_argument("--strict", action="store_true", help="发现来源痕迹就按失败退出")
    p_blind.set_defaults(func=cmd_blind)

    p_agg = sub.add_parser("aggregate", help="算配对差值与盲评胜率")
    p_agg.add_argument("--workspace", required=True, help="实验工作区目录")
    p_agg.add_argument("--blind-root", default=None, help="盲包目录（默认 <workspace>-blind）")
    p_agg.add_argument("--json", default=None, help="报告 JSON 输出路径")
    p_agg.add_argument("--md", default=None, help="报告 Markdown 输出路径")
    p_agg.set_defaults(func=cmd_aggregate)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()

