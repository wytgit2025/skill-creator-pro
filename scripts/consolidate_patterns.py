#!/usr/bin/env python3
"""
consolidate_patterns.py — 运行期经验沉淀（skill-creator-pro 母版脚本）

读 <skill-root>/runtime/trace.jsonl，把反复出现的失败/批评模式沉淀成
<skill-root>/runtime/patterns/<slug>.md。这是 WikiSkill 思想的在线版：
信号每次重算会丢历史，pattern 文件让跨轮经验累积、不回滚。

纯标准库，可复制进任意技能的 scripts/ 后独立运行：

    python3 scripts/consolidate_patterns.py --skill-root <技能根目录>

设计约束：
- 脚本只做机械聚类和计数；根因/解法段留空，由巡检 agent 或用户填写，脚本不猜。
- 已存在的 pattern 只更新"出现次数/首见/末见"三行，绝不覆盖人手填的根因和解法。
- 样本不足（跨不同 request < min-requests）时不建新 pattern，避免个例膨胀。
- 失败安全：任何异常只警告退出，不阻断巡检主流程。
"""

import argparse
import json
import re
import sys
from pathlib import Path

NEG_RULES = [
    ("怎么还是", "问题反复"), ("重做", "问题反复"), ("又", "问题反复"),
    ("不对", "结果不对"), ("错误", "结果不对"), ("错了", "结果不对"), ("错", "结果不对"),
    ("太慢", "太慢"), ("变慢", "太慢"), ("慢", "太慢"),
    ("别再", "不希望的动作"), ("别", "不希望的动作"),
    ("不能用", "质量差"), ("没用", "质量差"), ("失败", "质量差"),
]


def reason_key(error):
    e = (str(error) if error else "unknown-error").strip().splitlines()[0].strip()
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Timeout))\b", e)
    if m:
        return m.group(1)
    if ":" in e:
        head = e.split(":", 1)[0].strip()
        if re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", head):
            return head
    return e[:40]


def request_token(rec):
    if rec.get("request_id"):
        return str(rec["request_id"])
    return "h:" + str(rec.get("input_summary") or "")[:80]


def classify_criticism(feedback):
    text = str(feedback)
    for word, theme in NEG_RULES:
        if word in text:
            return theme
    return None


def slugify(text, prefix):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return f"{prefix}-{s}"[:60]


def load_trace(skill_root):
    path = skill_root / "runtime" / "trace.jsonl"
    records = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def bucketize(records):
    """返回 {slug: {kind, title, count, requests:set, first, last, example}}"""
    buckets = {}
    for rec in records:
        ts = rec.get("ts")
        token = request_token(rec)
        is_fail = rec.get("status") == "failure" or bool(rec.get("error"))
        if is_fail:
            rk = reason_key(rec.get("error"))
            slug = slugify(rk, "fail")
            b = buckets.setdefault(slug, {"kind": "failure", "title": rk,
                                          "count": 0, "requests": set(),
                                          "first": None, "last": None, "example": None})
            b["count"] += 1
            b["requests"].add(token)
            if b["example"] is None:
                b["example"] = (rec.get("error") or rec.get("input_summary") or "")[:160]
            if ts:
                if b["first"] is None or str(ts) < b["first"]:
                    b["first"] = str(ts)
                if b["last"] is None or str(ts) > b["last"]:
                    b["last"] = str(ts)
        fb = rec.get("feedback")
        if fb:
            theme = classify_criticism(fb)
            if theme:
                slug = slugify(theme, "critic")
                b = buckets.setdefault(slug, {"kind": "criticism", "title": theme,
                                              "count": 0, "requests": set(),
                                              "first": None, "last": None, "example": None})
                b["count"] += 1
                b["requests"].add(token)
                if b["example"] is None:
                    b["example"] = str(fb)[:160]
                if ts:
                    if b["first"] is None or str(ts) < b["first"]:
                        b["first"] = str(ts)
                    if b["last"] is None or str(ts) > b["last"]:
                        b["last"] = str(ts)
    return buckets


def render_new(slug, b):
    return f"""# {b['title']}

- 状态: open
- 类别: {b['kind']}
- 现象: {b['example'] or ''}
- 出现次数: {b['count']}；首见 {b['first'] or '-'}；末见 {b['last'] or '-'}
- 影响 request: {len(b['requests'])} 个
- 根因:
- 解法/处置:
- 促成改动:
"""


def update_existing(path, b):
    """只更新计数三行，保留根因/解法。返回是否写了文件。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    new_count_line = (f"- 出现次数: {b['count']}；首见 {b['first'] or '-'}；"
                      f"末见 {b['last'] or '-'}")
    new_req_line = f"- 影响 request: {len(b['requests'])} 个"
    for i, ln in enumerate(lines):
        if ln.startswith("- 出现次数:") and lines[i] != new_count_line:
            lines[i] = new_count_line
            changed = True
        elif ln.startswith("- 影响 request:") and lines[i] != new_req_line:
            lines[i] = new_req_line
            changed = True
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return changed


def main():
    ap = argparse.ArgumentParser(description="把反复出现的失败/批评沉淀为 runtime/patterns/*.md")
    ap.add_argument("--skill-root", required=True)
    ap.add_argument("--min-requests", type=int, default=3,
                    help="跨不同 request 数达到才建/更新 pattern，默认 3")
    args = ap.parse_args()

    try:
        skill_root = Path(args.skill_root).resolve()
        records = load_trace(skill_root)
        patterns_dir = skill_root / "runtime" / "patterns"
        patterns_dir.mkdir(parents=True, exist_ok=True)

        buckets = bucketize(records)
        created, updated, skipped = [], [], []
        for slug, b in sorted(buckets.items(), key=lambda kv: kv[1]["count"], reverse=True):
            if len(b["requests"]) < args.min_requests:
                skipped.append(slug)
                continue
            p = patterns_dir / f"{slug}.md"
            if p.exists():
                if update_existing(p, b):
                    updated.append(slug)
            else:
                p.write_text(render_new(slug, b), encoding="utf-8")
                created.append(slug)

        open_items = [p.stem for p in sorted(patterns_dir.glob("*.md"))
                      if p.name != "README.md"]
        print(f"[consolidate] trace {len(records)} 条；buckets {len(buckets)}；"
              f"新建 {len(created)}，更新 {len(updated)}，样本不足跳过 {len(skipped)}")
        if created:
            print("  新建: " + ", ".join(created))
        if updated:
            print("  更新: " + ", ".join(updated))
        print(f"  当前 open pattern: {len(open_items)} 个 → 巡检时逐个补根因和解法")
    except Exception as exc:
        print(f"[consolidate] warning: 沉淀失败（已忽略）：{exc}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
