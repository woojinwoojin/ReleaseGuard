"""2·3단계: 후보 커밋의 기준 테스트·coverage를 돌리고, 고정 규칙으로 mutant를 고른다. 설계 2장·3.2

mutant를 실행하지 않는다. Cosmic Ray는 mutation 목록(init·dump)에만 쓴다.
기준 실행은 필요한 커밋까지만 돌린다 (시간순으로 돌며 예산이 차면 멈춤). 돌린 커밋은 모두 baseline.json에 남는다.

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2_2_confirmation/select_confirmation.py [--only R]
결과: docs/eval/v22c/baseline.json (캐시 겸 기록), eval/mutation_confirmation_cases.yaml
"""

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

import yaml

from conflib import (
    CASES_FILE, CODEBASES, EXCLUDED_DIRS, FAMILY_ORDER, OUT, PER_COMMIT, BASELINE_TIMEOUT, WORKSPACE,
    family_budget, mutlib, observed_commits, redact,
)
from releaseguard.classify import classify, load_rules
from releaseguard.evaluate import list_commits
from releaseguard.gaps import file_lines
from releaseguard.git_ops import collect
from releaseguard.runner import check_coverage_tools, check_python, find_python, run_tests, snapshot

rules = load_rules()
OBSERVED = observed_commits()
BASELINE_FILE = OUT / "baseline.json"


def is_target_file(path: str, status: str) -> bool:
    return (status != "D" and path.endswith(".py") and not path.startswith(EXCLUDED_DIRS)
            and classify(path, rules)[0] == "source")


def baseline_commit(repo: Path, sha: str, subject: str, python: Path) -> dict:
    """한 커밋: 바뀐 소스 줄의 coverage 상태, 그 줄을 실행한 테스트, 줄 위의 허용 mutation 목록."""
    change = collect(repo, f"{sha}~1", sha)
    sources = [f.path for f in change.files if is_target_file(f.path, f.status)]
    rec = {"sha": sha[:7], "subject": subject, "sources": sources}
    if not sources:
        return rec | {"excluded": "소스 Python 변경 없음"}
    run = run_tests(repo, sha, python, timeout=BASELINE_TIMEOUT)
    rec["baseline"] = {"status": run.status, "reason": redact(run.reason) if run.reason else None, "seconds": run.seconds,
                       "attempts": run.attempts, "counts": run.counts()}
    if run.status != "passed" or run.coverage is None:
        return rec | {"excluded": f"기준 실행 {run.status}" + (f": {redact(run.reason)[:200]}" if run.reason else "")}
    lines, list_seconds = [], {}
    with tempfile.TemporaryDirectory(prefix="rg_sel22_", ignore_cleanup_errors=True) as t:
        tmp = Path(t)
        work = tmp / "src"
        work.mkdir()
        snapshot(repo, sha, work)
        for path in sources:
            text = dict(change.added_lines.get(path, []))
            changed = [n for n, s in change.added_lines.get(path, []) if s.strip()]
            if not changed:
                continue
            fc = run.coverage.get(path)
            fl = file_lines(path, changed, fc)
            covered = [n for n in changed if fl.line_status.get(n) == "covered"]
            muts = []
            if covered:
                started = time.perf_counter()
                try:
                    muts = mutlib.mutations_for(work, path, tmp)
                except RuntimeError as e:
                    rec.setdefault("listing_errors", {})[path] = redact(e)[:300]
                list_seconds[path] = round(time.perf_counter() - started, 2)
            gap_from = {a for a, _ in fl.branch_gaps}
            for n in changed:
                st = fl.line_status.get(n)
                item = {"path": path, "line": n, "status": st, "text": text[n].strip()[:200]}
                if st == "covered":
                    funcs = fc.tests.get(n, [])
                    item |= {
                        "fixture_only": n not in fc.run_lines,
                        "branch_gap": n in gap_from,
                        "selected_tests": sorted({r for f in funcs for r in fc.nodeids.get(f, {f})}),
                        "mutations": sorted(
                            ({"operator": m["operator"], "occurrence": m["occurrence"], "family": m["family"]}
                             for m in muts if m["family"] and m["start_line"] == n),
                            key=lambda m: (m["operator"], m["occurrence"])),
                    }
                lines.append(item)
    return rec | {"lines": lines, "listing_seconds": list_seconds}


def load_cache() -> dict:
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8")) if BASELINE_FILE.exists() else {}


def save_cache(cache: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def commit_stream(name: str, cache: dict):
    """코드베이스의 후보 커밋을 시간순으로, 필요할 때 기준 실행을 하며 내준다."""
    for rel in CODEBASES[name]["repos"]:
        repo = (WORKSPACE / rel).resolve()
        python = find_python(repo)
        repo_cache = cache.setdefault(name, {}).setdefault(rel, {"commits": {}})
        if "python_check" not in repo_cache:
            problem = "no .venv" if python is None else check_python(python)
            tools = None if problem else check_coverage_tools(python)
            repo_cache["python_check"] = {"problem": problem, "coverage_ok": None if tools is None else tools["ok"]}
            save_cache(cache)
        if repo_cache["python_check"]["problem"] or not repo_cache["python_check"]["coverage_ok"]:
            continue
        for sha, subject in list_commits(repo):
            if sha[:7] in OBSERVED:
                repo_cache["commits"].setdefault(sha[:7], {"sha": sha[:7], "subject": subject, "excluded": "이미 mutation 결과를 본 커밋"})
                continue
            if sha[:7] not in repo_cache["commits"]:
                print(f"[{name}] {rel} {sha[:7]} 기준 실행 …", flush=True)
                repo_cache["commits"][sha[:7]] = baseline_commit(repo, sha, subject, python)
                save_cache(cache)
            yield rel, repo_cache["commits"][sha[:7]]


def select(name: str, cache: dict) -> dict:
    """설계 3.2. 1차: 계열 예산 안에서 시간순. 2차(예산이 남으면): 남은 수를 비교 → 불리언 → 상수 순으로."""
    budget = family_budget(CODEBASES[name]["budget"])
    total = CODEBASES[name]["budget"]
    chosen, per_commit, used_lines, seen_text, visited = [], {}, set(), set(), []

    def ordered_lines(c):
        cov = [l for l in c.get("lines", []) if l["status"] == "covered" and l["mutations"]]
        return sorted(cov, key=lambda l: (l["branch_gap"], l["path"], l["line"]))

    def take(rel, c, line, m):
        chosen.append({"codebase": name, "repo": rel, "commit": c["sha"], "path": line["path"], "line": line["line"],
                       "text": line["text"], "operator": m["operator"], "occurrence": m["occurrence"], "family": m["family"],
                       "coverage": {"line_status": "covered", "fixture_only": line["fixture_only"], "branch_gap": line["branch_gap"]},
                       "selected_tests": line["selected_tests"]})
        per_commit[(rel, c["sha"])] = per_commit.get((rel, c["sha"]), 0) + 1
        used_lines.add((rel, c["sha"], line["path"], line["line"]))
        seen_text.add((line["path"], line["text"]))

    def usable(rel, c, line):
        return ((rel, c["sha"], line["path"], line["line"]) not in used_lines
                and (line["path"], line["text"]) not in seen_text  # W: 앞 주차에서 같은 내용의 줄을 이미 골랐으면 건너뜀
                and per_commit.get((rel, c["sha"]), 0) < PER_COMMIT)

    left = dict(budget)
    for rel, c in commit_stream(name, cache):
        visited.append((rel, c))
        if "excluded" in c:
            continue
        for line in ordered_lines(c):
            if not usable(rel, c, line):
                continue
            m = next((m for m in line["mutations"] if left[m["family"]] > 0), None)
            if m:
                take(rel, c, line, m)
                left[m["family"]] -= 1
        if len(chosen) >= total:
            break
    spill = []
    if len(chosen) < total:
        for fam in FAMILY_ORDER:
            for rel, c in visited:
                if "excluded" in c:
                    continue
                for line in ordered_lines(c):
                    if len(chosen) >= total:
                        break
                    if not usable(rel, c, line):
                        continue
                    m = next((m for m in line["mutations"] if m["family"] == fam), None)
                    if m:
                        take(rel, c, line, m)
                        spill.append(fam)
    fams = {f: sum(x["family"] == f for x in chosen) for f in FAMILY_ORDER}
    return {
        "target": total, "family_budget": budget, "selected": len(chosen), "shortfall": total - len(chosen),
        "by_family": fams, "spilled_to": spill,
        "commits_visited": [{"repo": rel, "sha": c["sha"], "subject": c["subject"], "excluded": c.get("excluded"),
                             "baseline": c.get("baseline"), "picked": per_commit.get((rel, c["sha"]), 0)} for rel, c in visited],
        "mutants": chosen,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(CODEBASES))
    args = ap.parse_args()
    cache = load_cache()
    result = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))["codebases"] if CASES_FILE.exists() else {}
    for name in CODEBASES:
        if args.only and name != args.only:
            continue
        result[name] = select(name, cache)
        print(name, {k: result[name][k] for k in ("selected", "shortfall", "by_family")}, flush=True)
    n = 0
    for name in CODEBASES:
        for m in (result.get(name) or {}).get("mutants", []):
            n += 1
            m["no"] = n  # 선정 순서 = mutant 번호 (설계 7장 순환 선정에 씀)
    doc = {
        "note": "Stage 2.2 확인 평가 선정 목록 — mutant 실행 전 커밋으로 고정 (설계 docs/design_stage2_2_confirmation.md 2·3장). "
                "select_confirmation.py가 baseline.json만 보고 만든다. 손으로 고치지 않는다.",
        "observed_commits_excluded": sorted(OBSERVED),
        "per_commit": PER_COMMIT,
        "codebases": result,
    }
    CASES_FILE.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
    print("→", CASES_FILE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
