"""7단계 차등 검증 (docs/design_stage2_2_confirmation.md 7장, 2.1 run_test_additions.py와 같은 절차).

대상은 1차 분류의 test_targets(eval/mutation_confirmation_review.yaml)이고, 이 실행기는 테스트 결과를 보기 전에 커밋한다.
새 테스트 파일(docs/eval/v22c/tests/)은 대상 커밋 스냅샷의 tests/ 안에 복사본으로만 넣는다. 대상 저장소에는 넣지 않는다.
원본 스냅샷과 mutant 스냅샷에서 새 테스트(선택)와 전체 테스트를 각각 돌린다.
결과: docs/eval/v22c/test_additions.json (대상마다 바로 저장, 다시 실행하면 저장된 대상은 건너뜀)

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2_2_confirmation/run_test_additions.py [--only 16]
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
from conflib import OUT, ROOT, WORKSPACE, mutlib, redact  # noqa: E402

from releaseguard.git_ops import run_git  # noqa: E402
from releaseguard.runner import find_python, snapshot  # noqa: E402

TESTS = OUT / "tests"
RESULT_FILE = OUT / "test_additions.json"
REVIEW = ROOT / "eval" / "mutation_confirmation_review.yaml"
# 대상 mutant 번호 → 새 테스트 파일 (테스트 내용은 1차 분류의 expected_test를 따른다)
TEST_FILES = {
    1: "test_rg22c_m01_no_command.py",
    2: "test_rg22c_m02_repo_required.py",
    3: "test_rg22c_m03_base_required.py",
    16: "test_rg22c_m16_truncated.py",
    23: "test_rg22c_m23_single_parent.py",
}


def outcome(orig: dict, mut: dict) -> str:
    """2.1 6장 결과 해석 표."""
    if orig["status"] != "SURVIVED":  # mutlib 상태: 새 테스트가 원본에서 실패하면 KILLED로 나온다
        return "ORIGINAL_FAIL" if orig["status"] == "KILLED" else f"NOT_RUNNABLE ({orig['status']})"
    if mut["status"] == "KILLED":
        return "DETECTED" if mut["kind"] == "assertion" else f"DETECTED_BY_{(mut['kind'] or '?').upper()}"
    if mut["status"] == "SURVIVED":
        return "NOT_DETECTED"
    return f"NOT_RUNNABLE ({mut['status']})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, help="이 mutant 번호만")
    args = ap.parse_args()
    review = yaml.safe_load(REVIEW.read_text(encoding="utf-8"))
    targets = review["summary_first_pass"]["test_targets"]
    assert sorted(targets) == sorted(TEST_FILES), (targets, TEST_FILES)
    known_bug = {s["mutant"] for s in review["survivors"] if s.get("oracle_check") == "KNOWN_BUG_ORACLE"}
    mres = json.loads((OUT / "mutation_result.json").read_text(encoding="utf-8"))["mutants"]
    baseline = json.loads((OUT / "baseline.json").read_text(encoding="utf-8"))
    result = json.loads(RESULT_FILE.read_text(encoding="utf-8")) if RESULT_FILE.exists() else {"runs": [], "results": {}}
    run_info = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "repos": {}}
    result["runs"].append(run_info)

    def save():
        RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    for no in targets:
        if (args.only is not None and no != args.only) or str(no) in result["results"]:
            continue
        m = mres[str(no)]
        repo = (WORKSPACE / m["repo"]).resolve()
        python = find_python(repo)
        if m["repo"] not in run_info["repos"]:
            run_info["repos"][m["repo"]] = {"before": [run_git(repo, "rev-parse", "HEAD").strip(), run_git(repo, "status", "--porcelain")]}
        base_secs = baseline[m["codebase"]][m["repo"]]["commits"][m["commit"]]["baseline"]["seconds"]
        mutlib.TEST_TIMEOUT = max(120, int(base_secs * 3))
        test_file = TEST_FILES[no]
        code = (TESTS / test_file).read_text(encoding="utf-8")
        rel = f"tests/{test_file}"
        rec = {"no": no, "codebase": m["codebase"], "repo": m["repo"], "commit": m["commit"], "path": m["path"], "line": m["line"],
               "operator": m["operator"], "occurrence": m["occurrence"], "test_file": f"docs/eval/v22c/tests/{test_file}",
               "known_bug_oracle": no in known_bug, "timeout": mutlib.TEST_TIMEOUT}
        try:
            with tempfile.TemporaryDirectory(prefix="rg_t22c_", ignore_cleanup_errors=True) as t:
                tmp = Path(t)
                pristine = tmp / "pristine"
                pristine.mkdir()
                snapshot(repo, run_git(repo, "rev-parse", m["commit"]).strip(), pristine)
                work = tmp / "list"
                shutil.copytree(pristine, work)
                found = next(x for x in mutlib.mutations_for(work, m["path"], tmp) if x["operator"] == m["operator"] and x["occurrence"] == m["occurrence"])
                assert found["start_line"] == m["line"], (no, found)
                original = mutlib.run_mutant(pristine, python, m["path"], None, [rel], extra_files={rel: code})
                mutant = mutlib.run_mutant(pristine, python, m["path"], found, [rel], extra_files={rel: code})
            o, u = original["selected"], mutant["selected"]
            rec |= {"outcome": outcome(o, u), "original_new_test": o, "mutant_new_test": u,
                    "original_full": original["full"]["status"], "mutant_full": mutant["full"]["status"],
                    "source_before": mutant.get("source_before"), "source_after": mutant.get("source_after")}
        except Exception as e:  # noqa: BLE001 — 조용히 빼지 않고 기록한다
            rec |= {"outcome": "EXECUTION_ERROR", "error": redact(repr(e))[:300]}
        result["results"][str(no)] = json.loads(redact(json.dumps(rec, ensure_ascii=False)))
        save()
        print(f"#{no} {m['codebase']} {m['commit']} {m['path']}:{m['line']} → {rec['outcome']}"
              f" | 원본 새 테스트 {rec.get('original_new_test', {}).get('status')} | mutant 새 테스트 {rec.get('mutant_new_test', {}).get('status')}"
              f" {rec.get('mutant_new_test', {}).get('kind')} | 전체 {rec.get('original_full')}/{rec.get('mutant_full')}", flush=True)
    for rel, info in run_info["repos"].items():
        repo = (WORKSPACE / rel).resolve()
        info["after"] = [run_git(repo, "rev-parse", "HEAD").strip(), run_git(repo, "status", "--porcelain")]
        info["preserved"] = info["after"] == info["before"]
    run_info["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save()
    print("저장소 보존", {k: v["preserved"] for k, v in run_info["repos"].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
