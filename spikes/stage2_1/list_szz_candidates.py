"""평가 B 준비: SZZ covered 결함 줄 41개에 허용 연산자 mutation이 있는지, 같은 커밋의 대조군 후보와 함께 뽑는다.

mutant는 만들지 않는다 (목록만). 결과: docs/eval/v21/szz_candidates.json
수기 결함 확인은 이 목록을 보고 eval/szz_defect_check_2_1.yaml에 적는다.

사용: .venv/Scripts/python spikes/stage2_1/list_szz_candidates.py --repo ../predict-success
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutlib import ROOT, mutations_for  # noqa: E402

from releaseguard.classify import classify, load_rules  # noqa: E402
from releaseguard.git_ops import collect, run_git  # noqa: E402
from releaseguard.runner import find_python, run_tests, snapshot  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repo", type=Path, required=True)
ap.add_argument("--szz", type=Path, default=ROOT / "out" / "eval" / "v14" / "20261107_szz.json")
ap.add_argument("--out", type=Path, default=ROOT / "docs" / "eval" / "v21" / "szz_candidates.json")
args = ap.parse_args()
repo = args.repo.resolve()
python = find_python(repo)
rules = load_rules()

szz = json.loads(args.szz.read_text(encoding="utf-8"))
all_defect = {(l["sha"][:7], l["path"], l["line"]) for r in szz["rows"] for l in r["lines"]}  # 상태와 관계없이 전부
covered = [l for r in szz["rows"] for l in r["lines"] if l["status"] == "covered"]
order = run_git(repo, "log", "--reverse", "--format=%h").split()  # 오래된 순
commits = sorted({l["sha"][:7] for l in covered}, key=lambda s: next(i for i, o in enumerate(order) if s.startswith(o) or o.startswith(s)))

out = {"commits_in_order": commits, "candidates": [], "controls": {}}
for sha in commits:
    change = collect(repo, f"{sha}~1", sha)
    run = run_tests(repo, sha, python)
    sources = [f.path for f in change.files if f.status != "D" and f.path.endswith(".py") and classify(f.path, rules)[0] == "source"]
    with tempfile.TemporaryDirectory(prefix="rg_szz21_") as t:
        tmp = Path(t)
        work = tmp / "src"
        work.mkdir()
        snapshot(repo, sha, work)
        muts = {p: mutations_for(work, p, tmp) for p in sources}
    covered_changed = {
        p: sorted(n for n, _ in change.added_lines.get(p, []) if run.coverage and run.coverage.get(p) and run.coverage[p].tests.get(n))
        for p in sources
    }
    for l in (x for x in covered if x["sha"].startswith(sha)):
        ops = [m for m in muts.get(l["path"], []) if m["start_line"] == l["line"] and m["family"]]
        out["candidates"].append({
            "commit": sha, "path": l["path"], "line": l["line"], "fix": l["fix"][:7], "text": l["text"],
            "definition": ops[0]["definition"] if ops else None,
            "allowed_ops": sorted({(m["operator"], m["occurrence"], m["family"]) for m in ops}),
        })
    # 대조군 후보: 같은 커밋의 covered 바뀐 줄 중 SZZ 결함 줄이 아니고 허용 연산자가 있는 줄
    out["controls"][sha] = {
        p: [
            {"line": n, "families": sorted({m["family"] for m in muts[p] if m["start_line"] == n and m["family"]}),
             "ops": sorted({(m["operator"], m["occurrence"], m["family"]) for m in muts[p] if m["start_line"] == n and m["family"]})}
            for n in lines if (sha, p, n) not in all_defect and any(m["start_line"] == n and m["family"] for m in muts[p])
        ]
        for p, lines in covered_changed.items()
    }
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("candidates", len(out["candidates"]), "with ops", sum(bool(c["allowed_ops"]) for c in out["candidates"]))
for c in out["candidates"]:
    print(c["commit"], c["fix"], f"{c['path']}:{c['line']}", c["definition"], [o[0].removeprefix("core/") for o in c["allowed_ops"]])
