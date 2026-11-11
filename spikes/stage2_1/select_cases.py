"""평가 B 선정 규칙(docs/design_stage2_1.md 5.3)을 기계적으로 적용해 eval/mutation_cases_2_1.yaml을 만든다.

입력: docs/eval/v21/szz_candidates.json (list_szz_candidates.py), eval/szz_defect_check_2_1.yaml (수기 확인),
      docs/eval/v20_spike/mutation_result.json (2.0에서 이미 만든 mutant는 뺀다)
mutant를 실행하지 않는다. 결과 파일은 실행 전에 커밋해 고정한다.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
MAX_LINES, PER_LINE = 6, 2

cand = json.loads((ROOT / "docs/eval/v21/szz_candidates.json").read_text(encoding="utf-8"))
check = yaml.safe_load((ROOT / "eval/szz_defect_check_2_1.yaml").read_text(encoding="utf-8"))
done20 = {(m["commit"], m["file"], m["line"], m["operator"], m["occurrence"])
          for m in json.loads((ROOT / "docs/eval/v20_spike/mutation_result.json").read_text(encoding="utf-8"))["mutants"]}
status = {(c["commit"], c["path"], c["line"]): c.get("result") for c in check["lines"]}


def pick_ops(commit, path, line, ops):
    ops = sorted((tuple(o) for o in ops), key=lambda o: (o[0], o[1]))
    return [{"operator": o[0], "occurrence": o[1], "family": o[2]} for o in ops if (commit, path, line, o[0], o[1]) not in done20][:PER_LINE]


# 1) 확인된 결함 + 허용 연산자. 2) 커밋 오래된 순으로 한 바퀴에 한 줄, 이미 고른 함수는 건너뜀
eligible = {}
for c in cand["candidates"]:
    if c["allowed_ops"] and status.get((c["commit"], c["path"], c["line"])) == "confirmed_defect":
        eligible.setdefault(c["commit"], []).append(c)
for v in eligible.values():
    v.sort(key=lambda c: (c["path"], c["line"]))
chosen, used_funcs = [], set()
while len(chosen) < MAX_LINES:
    progressed = False
    for commit in cand["commits_in_order"]:
        for c in eligible.get(commit, []):
            key = (c["path"], c["definition"])
            if c in chosen or key in used_funcs:
                continue
            chosen.append(c)
            used_funcs.add(key)
            progressed = True
            break
        if len(chosen) >= MAX_LINES:
            break
    if not progressed:
        break

cases = []
for i, c in enumerate(chosen, 1):
    muts = pick_ops(c["commit"], c["path"], c["line"], c["allowed_ops"])
    cases.append({"id": f"D{i}", "group": "szz", "commit": c["commit"], "path": c["path"], "line": c["line"],
                  "definition": c["definition"], "fix": c["fix"], "text": c["text"], "mutants": muts})
    fam = muts[0]["family"]
    # 대조군: 같은 커밋 covered 바뀐 줄, 결함 줄 아님, 같은 계열 연산자 있음.
    # 같은 파일 아래 → 위 → 다른 파일(경로 순)
    ctrl = cand["controls"][c["commit"]]
    same = [x for x in ctrl.get(c["path"], []) if fam in x["families"]]
    order = ([(c["path"], x) for x in same if x["line"] > c["line"]]
             + [(c["path"], x) for x in sorted(same, key=lambda x: -x["line"]) if x["line"] < c["line"]]
             + [(p, x) for p in sorted(ctrl) if p != c["path"] for x in ctrl[p] if fam in x["families"]])
    taken = {(k["path"], k["line"]) for k in cases if k["group"] == "control"}
    pair = next(((p, x) for p, x in order if (p, x["line"]) not in taken), None)
    if pair is None:
        cases.append({"id": f"C{i}", "group": "control", "pair_of": f"D{i}", "missing": True, "reason": f"같은 커밋에 {fam} 계열 대조 줄 없음"})
        continue
    p, x = pair
    cases.append({"id": f"C{i}", "group": "control", "pair_of": f"D{i}", "commit": c["commit"], "path": p, "line": x["line"],
                  "family_matched": fam, "mutants": pick_ops(c["commit"], p, x["line"], x["ops"])})

out = {
    "note": "Stage 2.1 평가 B 사례. select_cases.py가 선정 규칙으로 만들었고, mutant 실행 전에 커밋해 고정한다. 실행 후 바꾸지 않는다.",
    "rules": {"max_defect_lines": MAX_LINES, "mutants_per_line": PER_LINE, "design": "docs/design_stage2_1.md 5.3"},
    "defect_lines_found": len(chosen),
    "cases": cases,
}
path = ROOT / "eval" / "mutation_cases_2_1.yaml"
path.write_text("# 자동 생성 — spikes/stage2_1/select_cases.py\n" + yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
for k in cases:
    print(k["id"], k.get("commit"), f"{k.get('path')}:{k.get('line')}", [m["operator"].removeprefix("core/") + f"#{m['occurrence']}" for m in k.get("mutants", [])], k.get("reason", ""))
