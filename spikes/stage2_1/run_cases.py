"""평가 B 실행: eval/mutation_cases_2_1.yaml(실행 전 고정)의 mutant를 돌린다. 평가 A 대상 줄의 coverage 상태도 함께 기록한다.

줄마다 ReleaseGuard analyze(sha~1...sha)의 줄 상태와 분기 공백을 남긴다 → Incremental Detection
(그 줄이 이미 줄 공백·분기 공백으로 보였는지) 계산에 쓴다.

사용: .venv/Scripts/python spikes/stage2_1/run_cases.py --repo ../predict-success
결과: docs/eval/v21/mutation_result_b.json, docs/eval/v21/coverage_status.json
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutlib import ROOT, cosmic, mutations_for, run_mutant  # noqa: E402

from releaseguard.analyze import analyze  # noqa: E402
from releaseguard.classify import load_rules  # noqa: E402
from releaseguard.git_ops import run_git  # noqa: E402
from releaseguard.runner import find_python, run_tests, snapshot  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repo", type=Path, required=True)
ap.add_argument("--out", type=Path, default=ROOT / "docs" / "eval" / "v21")
args = ap.parse_args()
repo = args.repo.resolve()
python = find_python(repo)
rules = load_rules()
cases = yaml.safe_load((ROOT / "eval" / "mutation_cases_2_1.yaml").read_text(encoding="utf-8"))["cases"]
review = yaml.safe_load((ROOT / "eval" / "mutation_review_2_1.yaml").read_text(encoding="utf-8"))
before = {"head": run_git(repo, "rev-parse", "HEAD").strip(), "status": run_git(repo, "status", "--porcelain")}
started = time.perf_counter()

_analysis: dict[str, dict] = {}


def coverage_status(sha: str, path: str, line: int) -> dict:
    """ReleaseGuard가 이 줄을 어떻게 보였나: 줄 상태(covered·gap·…)와 이 줄에서 나가는 분기 공백 여부."""
    if sha not in _analysis:
        _analysis[sha] = analyze(repo, f"{sha}~1", sha, rules, python=python)
    res = _analysis[sha]
    fl = next((f for f in res["lines"] if f["path"] == path), None)
    if fl is None:
        return {"line_status": None, "branch_gap": None}
    st = fl["line_status"].get(str(line), fl["line_status"].get(line))
    return {"line_status": st, "branch_gap": any(a == line for a, _ in fl["branch_gaps"])}


out = {"cases": [], "coverage_a": []}
by_commit: dict[str, list[dict]] = {}
for c in cases:
    if not c.get("missing"):
        by_commit.setdefault(c["commit"], []).append(c)

for sha, group in by_commit.items():
    run = run_tests(repo, sha, python)  # coverage: 줄별 실행 테스트와 원본 node id
    with tempfile.TemporaryDirectory(prefix="rg_b21_") as t:
        tmp = Path(t)
        pristine = tmp / "pristine"
        pristine.mkdir()
        snapshot(repo, sha, pristine)
        muts_by_path = {}
        for c in group:
            fc = run.coverage.get(c["path"]) if run.coverage else None
            funcs = (fc.tests.get(c["line"]) if fc else None) or []
            selected = sorted({r for f in funcs for r in fc.nodeids.get(f, {f})}) if fc else []
            rec = {k: c[k] for k in ("id", "group", "commit", "path", "line")} | {
                "pair_of": c.get("pair_of"), "baseline_full": run.status, "selected_tests": selected,
                "coverage": coverage_status(sha, c["path"], c["line"]), "mutants": [],
            }
            if c["path"] not in muts_by_path:
                work = tmp / "list"
                shutil.rmtree(work, ignore_errors=True)
                shutil.copytree(pristine, work)
                muts_by_path[c["path"]] = mutations_for(work, c["path"], tmp)
            for m in c["mutants"]:
                found = next((x for x in muts_by_path[c["path"]] if x["operator"] == m["operator"] and x["occurrence"] == m["occurrence"]), None)
                if found is None or found["start_line"] != c["line"]:
                    rec["mutants"].append({**m, "result": "INVALID", "invalid_reason": "고정한 operator·occurrence가 이 줄에 없음"})
                    continue
                r = run_mutant(pristine, python, c["path"], found, selected)
                rec["mutants"].append({**m, **r})
            out["cases"].append(rec)

# 평가 A 대상 줄(2.0 SURVIVED 13개)의 coverage 상태
for m in review["mutants"]:
    sha, loc = m["where"].split()[:2]
    path, line = loc.rsplit(":", 1)
    out["coverage_a"].append({"no": m["no"], "commit": sha, "path": path, "line": int(line), **coverage_status(sha, path, int(line))})

out["repo_preserved"] = before == {"head": run_git(repo, "rev-parse", "HEAD").strip(), "status": run_git(repo, "status", "--porcelain")}
out["seconds"] = round(time.perf_counter() - started, 1)
out["cosmic_ray"] = cosmic("--version", cwd=ROOT).stdout.strip()
args.out.mkdir(parents=True, exist_ok=True)
(args.out / "mutation_result_b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for c in out["cases"]:
    print(c["id"], c["group"], f"{c['path']}:{c['line']}", c["coverage"], [(m["operator"].removeprefix("core/"), m["result"], (m.get("full") or {}).get("kind")) for m in c["mutants"]])
print("repo_preserved", out["repo_preserved"], out["seconds"], "s")
