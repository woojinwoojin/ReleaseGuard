"""테스트 추가 실험 (docs/design_stage2_1.md 6장): 새 테스트를 원본 스냅샷과 mutant 스냅샷에서 각각 돌린다.

새 테스트 파일(docs/eval/v21/tests/)은 대상 커밋 스냅샷의 tests/ 안에 복사본으로 넣는다. Predict 저장소에는 넣지 않는다.
결과: docs/eval/v21/test_additions.json

사용: .venv/Scripts/python spikes/stage2_1/run_test_additions.py --repo ../predict-success
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mutlib import ROOT, mutations_for, run_mutant  # noqa: E402

from releaseguard.git_ops import run_git  # noqa: E402
from releaseguard.runner import find_python, snapshot  # noqa: E402

TESTS = ROOT / "docs" / "eval" / "v21" / "tests"
V20 = json.loads((ROOT / "docs" / "eval" / "v20_spike" / "mutation_result.json").read_text(encoding="utf-8"))["mutants"]
B = json.loads((ROOT / "docs" / "eval" / "v21" / "mutation_result_b.json").read_text(encoding="utf-8"))["cases"]


def from_v20(no: int) -> dict:
    m = V20[no - 1]
    return {"source": f"2.0 #{no}", "commit": m["commit"], "path": m["file"], "line": m["line"], "operator": m["operator"], "occurrence": m["occurrence"]}


def from_b(case_id: str, index: int) -> dict:
    c = next(c for c in B if c["id"] == case_id)
    m = c["mutants"][index]
    return {"source": f"B {case_id}[{index}]", "commit": c["commit"], "path": c["path"], "line": c["line"], "operator": m["operator"], "occurrence": m["occurrence"]}


# 설계 6장 규칙으로 고른 대상 (eval/mutation_review_2_1.yaml test_targets_from_a + 평가 B 결함 줄 첫 SURVIVED)
TARGETS = [
    ("T1", from_v20(2), "test_rg21_t1_zip.py"),
    ("T2", from_v20(23), "test_rg21_t2_evidence.py"),
    ("T3", from_v20(26), "test_rg21_t3_period.py"),
    ("T4", from_v20(37), "test_rg21_t4_hfs.py"),
    ("T5", from_b("D2", 0), "test_rg21_t5_section.py"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--repo", type=Path, required=True)
args = ap.parse_args()
repo = args.repo.resolve()
python = find_python(repo)
before = {"head": run_git(repo, "rev-parse", "HEAD").strip(), "status": run_git(repo, "status", "--porcelain")}

out = []
for tid, t, test_file in TARGETS:
    code = (TESTS / test_file).read_text(encoding="utf-8")
    rel = f"tests/{test_file}"
    with tempfile.TemporaryDirectory(prefix="rg_t21_") as tmp:
        tmp = Path(tmp)
        pristine = tmp / "pristine"
        pristine.mkdir()
        snapshot(repo, t["commit"], pristine)
        work = tmp / "list"
        import shutil
        shutil.copytree(pristine, work)
        found = next(m for m in mutations_for(work, t["path"], tmp) if m["operator"] == t["operator"] and m["occurrence"] == t["occurrence"])
        assert found["start_line"] == t["line"], (tid, found)
        original = run_mutant(pristine, python, t["path"], None, [rel], extra_files={rel: code})
        mutant = run_mutant(pristine, python, t["path"], found, [rel], extra_files={rel: code})
    orig_new, mut_new = original["selected"], mutant["selected"]
    if orig_new["status"] != "SURVIVED":
        outcome = "ORIGINAL_FAIL" if orig_new["status"] == "KILLED" else f"NOT_RUNNABLE ({orig_new['status']})"
    elif mut_new["status"] == "KILLED":
        outcome = "DETECTED" if mut_new["kind"] == "assertion" else f"DETECTED_BY_{(mut_new['kind'] or '?').upper()}"
    elif mut_new["status"] == "SURVIVED":
        outcome = "NOT_DETECTED"
    else:
        outcome = f"NOT_RUNNABLE ({mut_new['status']})"
    rec = {
        "id": tid, **t, "test_file": rel, "outcome": outcome,
        "original_new_test": orig_new, "mutant_new_test": mut_new,
        "original_full": original["full"]["status"], "mutant_full": mutant["full"]["status"],
        "source_before": mutant.get("source_before"), "source_after": mutant.get("source_after"),
    }
    out.append(rec)
    print(tid, t["source"], f"{t['path']}:{t['line']}", outcome, "| 원본 새 테스트", orig_new["status"], "| mutant 새 테스트", mut_new["status"], mut_new["kind"], mut_new["failed"])

after = {"head": run_git(repo, "rev-parse", "HEAD").strip(), "status": run_git(repo, "status", "--porcelain")}
(ROOT / "docs" / "eval" / "v21" / "test_additions.json").write_text(
    json.dumps({"repo_preserved": before == after, "results": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print("repo_preserved", before == after)
