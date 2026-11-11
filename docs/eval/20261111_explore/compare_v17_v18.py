"""보고서 #12: 판정 규칙 v3.1(out/eval/v17) ↔ v3.2(out/eval/v18), 58커밋 비교.

사용: python docs/eval/20261111_explore/compare_v17_v18.py   (release-guard 루트에서)
- 판정·규칙·NOTE·scope·줄 공백이 바뀐 커밋을 모두 나열
- T03·N07이 나온 커밋과 검사 상태(performed·held·not_applicable·not_evaluated) 분포
- 과소·과잉 경고 (라벨 전체, 코드 변경만) — 관찰 지표
"""
import glob
import json
import os
from collections import Counter


def load(version):
    out = {}
    for f in sorted(glob.glob(f"out/eval/{version}/*/*_eval.json")):
        repo = os.path.basename(os.path.dirname(f))
        for r in json.load(open(f, encoding="utf-8"))["rows"]:
            out[(repo, r["sha"])] = r
    return out


old, new = load("v17"), load("v18")
assert old.keys() == new.keys(), (len(old), len(new))
print("커밋", len(new))

changed = []
for key, n in new.items():
    o = n_ = None
    o = old[key]
    diff = {k: (o[k], n[k]) for k in ("decision", "rules", "notes", "scope", "gaps") if o[k] != n[k]}
    if diff:
        changed.append((key, diff, n.get("t03"), n["need"]))
print("바뀐 커밋", len(changed))
for (repo, sha), diff, t03, need in changed:
    print(f"  {repo}:{sha} need={need} t03={t03}", {k: f"{a} -> {b}" for k, (a, b) in diff.items()})

print("T03 검사 상태", dict(Counter(r["t03_status"] for r in new.values())))
print("T03 발동", [(f"{p}:{s}", r["t03"]) for (p, s), r in new.items() if r["t03"]])
print("N07 발동", [f"{p}:{s}" for (p, s), r in new.items() if "N07" in r["notes"]])


def is_code(r):
    return any(k != "docs" for k in r["by_category"])


for name, rows in (("v17", old), ("v18", new)):
    for label, subset in (("라벨 전체", list(rows.values())), ("코드 변경만", [r for r in rows.values() if is_code(r)])):
        yes = [r for r in subset if r["need"] == "yes"]
        no = [r for r in subset if r["need"] == "no"]
        over = [r["sha"] for r in no if r["decision"] != "SAFE"]
        print(f"{name} {label}: 과소 {sum(r['decision'] == 'SAFE' for r in yes)}/{len(yes)} · 과잉 {len(over)}/{len(no)}")
safe_code = [f"{p}:{s}" for (p, s), r in new.items() if r["decision"] == "SAFE" and is_code(r)]
print("v18 코드 변경 SAFE", len(safe_code), safe_code)
