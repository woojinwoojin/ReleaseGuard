"""5단계: 고정된 eval/mutation_confirmation_cases.yaml의 mutant를 실행한다. 설계 4장

- mutant마다 결과를 바로 저장하고, 다시 실행하면 저장된 mutant는 건너뛴다 (중단·재개).
- 실패한 mutant는 EXECUTION_ERROR로 남긴다. 빼지 않는다.
- 모든 mutant에 선택 실행과 전체 실행을 둘 다 한다 (Q2). 시간은 나눈다:
  제품 경로 = 목록(init·dump, 커밋·파일당 한 번) + 스냅샷 복사 + apply·컴파일 + 선택 실행 + 정리
  평가 비용 = 전체 실행
- 테스트 시간 상한: max(120, 기준 실행(coverage 포함) 시간 × 3)초. mutlib의 120초 고정값은 R(전체 167초)에 맞지 않는다.

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2_2_confirmation/run_mutants.py [--only R] [--limit N]
결과: docs/eval/v22c/mutation_result.json
"""

import argparse
import json
import platform
import py_compile
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import yaml

from conflib import CASES_FILE, CODEBASES, OUT, WORKSPACE, mutlib, redact
from releaseguard.git_ops import run_git
from releaseguard.runner import find_python, snapshot

RESULT_FILE = OUT / "mutation_result.json"
OWN_OUTPUTS = (":!docs/eval/v22c", ":!eval", ":!spikes", ":!out")  # R 자기 저장소: 이 실험이 쓰는 경로는 상태 비교에서 뺀다


def repo_state(repo: Path) -> dict:
    return {"head": run_git(repo, "rev-parse", "HEAD").strip(),
            "status": run_git(repo, "status", "--porcelain", "--", ".", *OWN_OUTPUTS)}


def tool_versions(python: Path) -> dict:
    def ver(*cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        return (p.stdout or p.stderr).strip()[:120]
    return {"python": ver(str(python), "--version"), "pytest": ver(str(python), "-m", "pytest", "--version"),
            "cosmic_ray": mutlib.cosmic("--version", cwd=Path.cwd()).stdout.strip(), "cosmic_ray_expected": mutlib.COSMIC_RAY_VERSION,
            "host": platform.platform()}


def run_one(pristine: Path, python: Path, m: dict, found: dict) -> dict:
    """mutant 하나. mutlib.run_mutant와 같은 절차이고, 단계별 시간을 나눠 잰다."""
    t0 = time.perf_counter()
    base = Path(tempfile.mkdtemp(prefix="rg_mut22_"))
    work = base / "src"
    rec, times = {}, {}
    try:
        shutil.copytree(pristine, work)
        times["copy"] = time.perf_counter() - t0
        t = time.perf_counter()
        target = work / m["path"]
        before = target.read_bytes().decode("utf-8")
        applied = mutlib.cosmic("apply", m["path"], m["operator"], str(m["occurrence"]), cwd=work)
        after = target.read_bytes().decode("utf-8")
        line = m["line"]
        rec["changed_lines"] = mutlib.changed_lines(before, after)
        rec["on_target_line"] = rec["changed_lines"] == [line]
        rec["source_before"] = before.splitlines()[line - 1].strip()[:200]
        rec["source_after"] = after.splitlines()[line - 1].strip()[:200] if rec["on_target_line"] else None
        try:
            if applied.returncode != 0 or after == before:
                raise ValueError(mutlib.clean(applied.stderr[-300:]) or "apply가 파일을 바꾸지 않음")
            py_compile.compile(str(target), doraise=True, cfile=str(base / "check.pyc"))
        except (ValueError, py_compile.PyCompileError) as e:
            times["apply"] = time.perf_counter() - t
            return rec | {"result": "INVALID", "invalid_reason": redact(e)[:300]}
        times["apply"] = time.perf_counter() - t
        t = time.perf_counter()
        sel_ids = m["selected_tests"]
        rec["selected"] = mutlib.run_pytest(python, work, sel_ids, "sel") if sel_ids else None
        times["selected"] = time.perf_counter() - t
        t = time.perf_counter()
        rec["full"] = mutlib.run_pytest(python, work, [], "full")
        times["full"] = time.perf_counter() - t
        rec["result"] = rec["full"]["status"]  # 2.1과 같은 의미: 분류 대상(SURVIVED)은 전체 실행 기준
        rec["result_selected"] = rec["selected"]["status"] if rec["selected"] else "NO_RELEVANT_TEST"  # 제품 경로 결과
        if rec["selected"] is not None:
            rec["agreement"] = mutlib.compare(rec["selected"], rec["full"], sel_ids)
        return rec
    finally:
        t = time.perf_counter()
        shutil.rmtree(base, ignore_errors=True)
        times["cleanup"] = time.perf_counter() - t
        rec["seconds"] = {k: round(v, 2) for k, v in times.items()}
        rec["seconds"]["product_path"] = round(sum(times.get(k, 0) for k in ("copy", "apply", "selected", "cleanup")), 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(CODEBASES))
    ap.add_argument("--limit", type=int, help="이번 실행에서 돌릴 최대 mutant 수 (사전 점검용)")
    args = ap.parse_args()
    cases = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    baseline = json.loads((OUT / "baseline.json").read_text(encoding="utf-8"))
    result = json.loads(RESULT_FILE.read_text(encoding="utf-8")) if RESULT_FILE.exists() else {
        "cases_file": "eval/mutation_confirmation_cases.yaml", "runs": [], "listing": {}, "mutants": {}}
    run_info = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "repos": {}, "versions": {}}
    result["runs"].append(run_info)

    def save():
        RESULT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    done = 0
    for name, cb in cases["codebases"].items():
        if args.only and name != args.only:
            continue
        groups: dict[tuple[str, str], list[dict]] = {}
        for m in cb["mutants"]:
            groups.setdefault((m["repo"], m["commit"]), []).append(m)
        for (rel, sha), muts in groups.items():
            todo = [m for m in muts if str(m["no"]) not in result["mutants"]]
            if not todo or (args.limit is not None and done >= args.limit):
                continue
            repo = (WORKSPACE / rel).resolve()
            python = find_python(repo)
            if rel not in run_info["repos"]:
                run_info["repos"][rel] = {"before": repo_state(repo)}
                run_info["versions"][rel] = tool_versions(python)
            base_secs = baseline[name][rel]["commits"][sha]["baseline"]["seconds"]
            mutlib.TEST_TIMEOUT = max(120, int(base_secs * 3))
            with tempfile.TemporaryDirectory(prefix="rg_run22_", ignore_cleanup_errors=True) as t:
                tmp = Path(t)
                pristine = tmp / "pristine"
                pristine.mkdir()
                snapshot(repo, run_git(repo, "rev-parse", sha).strip(), pristine)
                listed: dict[str, list[dict]] = {}
                for m in todo:
                    if args.limit is not None and done >= args.limit:
                        break
                    key = f"{name}|{rel}|{sha}|{m['path']}"
                    if m["path"] not in listed:
                        work = tmp / "list"
                        shutil.rmtree(work, ignore_errors=True)
                        shutil.copytree(pristine, work)
                        started = time.perf_counter()
                        try:
                            listed[m["path"]] = mutlib.mutations_for(work, m["path"], tmp)
                        except RuntimeError as e:
                            listed[m["path"]] = []
                            result["listing"][key] = {"error": redact(e)[:300]}
                        result["listing"].setdefault(key, {})["seconds"] = round(time.perf_counter() - started, 2)
                    found = next((x for x in listed[m["path"]] if x["operator"] == m["operator"] and x["occurrence"] == m["occurrence"]), None)
                    rec = {"no": m["no"], "codebase": name, "repo": rel, "commit": sha, "path": m["path"], "line": m["line"],
                           "operator": m["operator"], "occurrence": m["occurrence"], "family": m["family"], "timeout": mutlib.TEST_TIMEOUT,
                           "selected_tests": m["selected_tests"], "coverage": m["coverage"]}
                    try:
                        if found is None or found["start_line"] != m["line"]:
                            rec |= {"result": "INVALID", "invalid_reason": "고정한 operator·occurrence가 이 줄에 없음"}
                        else:
                            rec |= run_one(pristine, python, m, found)
                    except Exception as e:  # noqa: BLE001 — 조용히 빼지 않고 기록한다
                        rec |= {"result": "EXECUTION_ERROR", "error": redact(repr(e))[:300]}
                    result["mutants"][str(m["no"])] = rec
                    save()
                    done += 1
                    print(f"#{m['no']} {name} {sha} {m['path']}:{m['line']} {m['operator'].removeprefix('core/')} → {rec['result']}"
                          f" (selected {rec.get('result_selected')},{rec.get('seconds', {}).get('product_path')}s)", flush=True)
    for rel, info in run_info["repos"].items():
        info["after"] = repo_state((WORKSPACE / rel).resolve())
        info["preserved"] = info["after"] == info["before"]
    run_info["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save()
    total = sum(len(cb["mutants"]) for cb in cases["codebases"].values())
    print(f"저장된 결과 {len(result['mutants'])}/{total} · 저장소 보존 {[i['preserved'] for i in run_info['repos'].values()]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
