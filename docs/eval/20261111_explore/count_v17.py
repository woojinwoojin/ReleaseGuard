"""보고서 #11 2장: out/eval/v17 (규칙 v3.1, 58커밋) 재집계.

사용: python docs/eval/20261111_explore/count_v17.py   (release-guard 루트에서)
- 코드 변경 = 문서(docs) 외 분류가 하나라도 있는 커밋
- 과잉 경고 = need: no 인데 SAFE가 아님
"""
import glob
import json
import os

rows = []
for f in sorted(glob.glob("out/eval/v17/*/*_eval.json")):
    repo = os.path.basename(os.path.dirname(f))
    rows += [(repo, r) for r in json.load(open(f, encoding="utf-8"))["rows"]]


def is_code(r):
    return any(k != "docs" for k in r["by_category"])


code = [(p, r) for p, r in rows if is_code(r)]
safe = [(p, r) for p, r in rows if r["decision"] == "SAFE"]
print("커밋", len(rows), "· 코드 변경", len(code), "· 문서만", len(rows) - len(code))
print("SAFE", len(safe), "· 그중 코드 변경", sum(is_code(r) for _, r in safe), [f"{p}:{r['sha']}" for p, r in safe if is_code(r)])
print("N06 발동 커밋", sum("N06" in r["notes"] for _, r in rows))

for name, subset in (("라벨 전체", rows), ("코드 변경만", code)):
    yes = [r for _, r in subset if r["need"] == "yes"]
    no = [r for _, r in subset if r["need"] == "no"]
    under = sum(r["decision"] == "SAFE" for r in yes)
    over = [r for r in no if r["decision"] != "SAFE"]
    print(f"{name}: 과소 {under}/{len(yes)} · 과잉 {len(over)}/{len(no)}", [r["sha"] for r in over])
