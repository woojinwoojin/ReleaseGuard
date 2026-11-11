"""Stage 2.0 Mutation Feasibility Spike — 설계: docs/design_stage2_0.md

제품 기능이 아니라 독립 실험이다. releaseguard 패키지는 import만 하고 바꾸지 않는다. 판정에 넣지 않는다. API 호출 없음.

흐름 (커밋을 오래된 순으로, mutant가 상한에 찰 때까지):
  1. 커밋의 바뀐 Python 소스 줄 중 테스트가 실행한 줄(covered)을 찾는다 (ReleaseGuard runner의 coverage, 테스트 context).
  2. head를 git archive로 임시 폴더에 꺼내고, Cosmic Ray(별도 venv)로 그 파일의 mutation 목록을 만든다 (init → dump).
  3. covered 줄 + 허용 연산자만 고른다.
  4. mutant마다: 원본 보관 → cosmic-ray apply → 바뀐 줄이 지정한 줄뿐인지 확인 → (a) 그 줄을 실행한 테스트만 (b) 전체 테스트 → 원본 복구.
  5. 대상 저장소의 git 상태가 실행 전후로 같은지 확인한다.

사용 (release-guard 루트에서):
  .venv/Scripts/python spikes/stage2_0/run_spike.py --repo ../predict-success --max 40 --out out/spike/2_0
"""

import argparse
import difflib
import hashlib
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from releaseguard.classify import classify, load_rules  # noqa: E402
from releaseguard.evaluate import list_commits  # noqa: E402
from releaseguard.git_ops import collect, run_git  # noqa: E402
from releaseguard.runner import _env, find_python, run_tests, snapshot  # noqa: E402

SPIKE = Path(__file__).resolve().parent
COSMIC_RAY = SPIKE / ".venv" / "Scripts" / "cosmic-ray.exe"

# 설계 Q4: 비교(경계·부정 쌍)·불리언·상수만
COMPARISON_PAIRS = {
    "Eq_NotEq", "NotEq_Eq", "Lt_LtE", "LtE_Lt", "Gt_GtE", "GtE_Gt", "Is_IsNot", "IsNot_Is", "In_NotIn", "NotIn_In",
}
OTHER_OPERATORS = {
    "core/ReplaceAndWithOr", "core/ReplaceOrWithAnd", "core/ReplaceUnaryOperator_Not_Delete",
    "core/NumberReplacer", "core/ReplaceTrueWithFalse", "core/ReplaceFalseWithTrue",
}
TEST_TIMEOUT = 120


def clean(text: str) -> str:
    """메시지의 임시·홈 폴더 경로를 가린다 (결과 파일을 공개 저장소에 둘 수 있게)."""
    for real, mask in ((tempfile.gettempdir(), "<tmp>"), (str(Path.home()), "<home>")):
        for variant in {real, real.replace("\\", "\\\\"), real.replace("\\", "/")}:
            text = text.replace(variant, mask)
    user = Path.home().name
    return text.replace(user, "<user>") if len(user) >= 3 else text  # pytest 임시 폴더 이름(pytest-of-<user>) 등


def allowed(op: str) -> bool:
    if op.startswith("core/ReplaceComparisonOperator_"):
        return op.removeprefix("core/ReplaceComparisonOperator_") in COMPARISON_PAIRS
    return op in OTHER_OPERATORS


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_state(repo: Path) -> dict:
    return {"head": run_git(repo, "rev-parse", "HEAD").strip(), "status": run_git(repo, "status", "--porcelain")}


def cosmic(*args: str, cwd: Path, out_file: Path | None = None) -> subprocess.CompletedProcess:
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            return subprocess.run([str(COSMIC_RAY), *args], cwd=cwd, stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    return subprocess.run([str(COSMIC_RAY), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def mutations_for(work: Path, module: str, tmp: Path) -> list[dict]:
    """Cosmic Ray가 이 모듈에 만드는 mutation 전체 (operator, occurrence, 줄)."""
    cfg = tmp / "cr.toml"
    cfg.write_text(
        f'[cosmic-ray]\nmodule-path = "{module}"\ntimeout = 60.0\nexcluded-modules = []\ntest-command = "python -m pytest"\n\n'
        '[cosmic-ray.distributor]\nname = "local"\n',
        encoding="utf-8",
    )
    session = tmp / "session.sqlite"
    session.unlink(missing_ok=True)
    init = cosmic("init", str(cfg), str(session), cwd=work)
    if init.returncode != 0:
        raise RuntimeError(f"cosmic-ray init 실패: {init.stderr[-500:]}")
    dump_file = tmp / "dump.jsonl"
    dump = cosmic("dump", str(session), cwd=work, out_file=dump_file)
    if dump.returncode != 0:
        raise RuntimeError(f"cosmic-ray dump 실패: {dump.stderr[-500:]}")
    out = []
    for line in dump_file.read_text(encoding="utf-8").splitlines():
        item, _ = json.loads(line)
        for m in item["mutations"]:
            out.append({
                "operator": m["operator_name"], "occurrence": m["occurrence"],
                "start_line": m["start_pos"][0], "end_line": m["end_pos"][0], "definition": m.get("definition_name"),
            })
    return out


def run_pytest(python: Path, work: Path, nodeids: list[str], tmp: Path, tag: str) -> dict:
    junit = tmp / f"junit_{tag}.xml"
    junit.unlink(missing_ok=True)
    cmd = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "junit_family=xunit1", f"--junitxml={junit}", *nodeids]
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=work, env=_env(None), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "kind": None, "seconds": round(time.perf_counter() - started, 2), "tests": len(nodeids) or None}
    seconds = round(time.perf_counter() - started, 2)
    failures = _junit_failures(junit)
    rc = proc.returncode
    if rc == 0:
        status, kind = "SURVIVED", None
    elif rc == 1:
        status, kind = "KILLED", _kill_kind(failures)
    elif rc == 2:
        status, kind = "KILLED", "collection"  # 수집 중 오류(import 시점 예외 등)도 동작 변화를 드러낸 것
    elif rc == 5:
        status, kind = "NO_RELEVANT_TEST", None
    else:
        status, kind = "RUN_ERROR", f"pytest rc={rc}"
    return {"status": status, "kind": kind, "seconds": seconds, "tests": len(nodeids) or None,
            "failed": [f["nodeid"] for f in failures][:10], "messages": [clean(f["message"])[:160] for f in failures][:3]}


def _junit_failures(junit: Path) -> list[dict]:
    if not junit.exists():
        return []
    out = []
    for tc in ET.parse(junit).getroot().iter("testcase"):
        for tag in ("failure", "error"):
            el = tc.find(tag)
            if el is not None:
                out.append({"nodeid": f"{tc.get('file')}::{tc.get('name')}", "tag": tag, "message": el.get("message") or ""})
    return out


def _kill_kind(failures: list[dict]) -> str:
    """실패 종류: assertion(assert가 잡음) / exception(테스트 중 다른 예외) / error(setup·teardown 오류)."""
    kinds = set()
    for f in failures:
        if f["tag"] == "error":
            kinds.add("error")
        elif f["message"].startswith(("assert ", "AssertionError")):
            kinds.add("assertion")
        else:
            kinds.add("exception")
    for k in ("assertion", "exception", "error"):
        if k in kinds:
            return k
    return "unknown"


def changed_lines(before: str, after: str) -> list[int]:
    """원본 기준으로 바뀐 줄 번호."""
    out = []
    sm = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines(), autojunk=False)
    for op, a1, a2, _, _ in sm.get_opcodes():
        if op != "equal":
            out += list(range(a1 + 1, a2 + 1)) or [a1 + 1]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--max", type=int, default=40)
    # 커밋당 상한과 한 줄에 하나: 첫 커밋 한 파일에 후보 줄이 95개라 상한 40이 한 커밋에 몰리는 것을 막는다.
    # mutant 결과를 보기 전에 후보 줄 수만 보고 정했다 (3개짜리 도구 확인 실행 뒤, 본 실행 전).
    ap.add_argument("--per-commit", type=int, default=8)
    ap.add_argument("--out", type=Path, default=ROOT / "out" / "spike" / "2_0")
    args = ap.parse_args()
    repo = args.repo.resolve()
    python = find_python(repo)
    rules = load_rules()
    before = repo_state(repo)
    started = time.perf_counter()

    mutants, commits_seen, setup = [], [], {"cosmic_ray": cosmic("--version", cwd=SPIKE).stdout.strip(), "python": str(python)}
    for sha, subject in list_commits(repo):
        if len(mutants) >= args.max:
            break
        change = collect(repo, f"{sha}~1", sha)
        sources = [f.path for f in change.files if f.status != "D" and f.path.endswith(".py") and classify(f.path, rules)[0] == "source"]
        if not sources:
            continue
        run = run_tests(repo, sha, python)  # 전체 실행 + coverage (테스트 context)
        if run.coverage is None:
            commits_seen.append({"sha": sha[:7], "skipped": f"coverage 없음 ({run.status})"})
            continue
        targets = {}
        for path in sources:
            fc = run.coverage.get(path)
            if not fc:
                continue
            covered = sorted(n for n, _ in change.added_lines.get(path, []) if fc.tests.get(n))
            if covered:
                targets[path] = (covered, fc)
        if not targets:
            continue
        commit = {"sha": sha[:7], "subject": subject, "baseline_full": run.status, "files": {p: v[0] for p, v in targets.items()}}
        commits_seen.append(commit)

        with tempfile.TemporaryDirectory(prefix="rg_mut_", ignore_cleanup_errors=True) as t:
            tmp = Path(t)
            work = tmp / "src"
            work.mkdir()
            snapshot(repo, sha, work)
            for path, (covered, fc) in targets.items():
                if len(mutants) >= args.max:
                    break
                candidates = mutations_for(work, path, tmp)
                commit.setdefault("cosmic_ray_total", {})[path] = len(candidates)
                ordered = sorted(
                    (m for m in candidates if allowed(m["operator"]) and m["start_line"] in covered),
                    key=lambda m: (m["start_line"], m["operator"], m["occurrence"]),
                )
                chosen, used_lines = [], set()
                for m in ordered:  # 한 줄에 하나 (연산자 이름 순으로 첫 번째)
                    if m["start_line"] not in used_lines:
                        chosen.append(m)
                        used_lines.add(m["start_line"])
                target = work / path
                original_bytes = target.read_bytes()
                original_text = original_bytes.decode("utf-8")
                original_hash = sha256(target)
                for m in chosen:
                    if len(mutants) >= args.max or sum(x["commit"] == sha[:7] for x in mutants) >= args.per_commit:
                        break
                    line = m["start_line"]
                    funcs = fc.tests[line]
                    raw = sorted({r for f in funcs for r in fc.nodeids.get(f, {f})})
                    rec = {"commit": sha[:7], "file": path, "line": line, **m, "selected_tests": raw}
                    applied = cosmic("apply", path, m["operator"], str(m["occurrence"]), cwd=work)
                    mutated = target.read_bytes().decode("utf-8")
                    rec["source_before"] = original_text.splitlines()[line - 1].strip()[:160]
                    rec["changed_lines"] = changed_lines(original_text, mutated)
                    rec["on_target_line"] = rec["changed_lines"] == [line]
                    rec["source_after"] = mutated.splitlines()[line - 1].strip()[:160] if rec["on_target_line"] else None
                    try:
                        if applied.returncode != 0 or mutated == original_text:
                            raise ValueError(applied.stderr[-300:] or "apply가 파일을 바꾸지 않음")
                        py_compile.compile(str(target), doraise=True, cfile=str(tmp / "check.pyc"))
                    except (ValueError, py_compile.PyCompileError) as e:
                        rec["result"] = "INVALID"
                        rec["invalid_reason"] = clean(str(e))[:300]
                    else:
                        if run.status != "passed":
                            rec["result"] = "INCOMPARABLE"  # 기준 실행(mutant 없음)이 통과하지 않음
                        rec["selected"] = run_pytest(python, work, raw, tmp, "sel")
                        rec["full"] = run_pytest(python, work, [], tmp, "full")
                        rec.setdefault("result", rec["full"]["status"])
                        rec["selected_agrees_with_full"] = rec["selected"]["status"] == rec["full"]["status"]
                    target.write_bytes(original_bytes)
                    rec["restored"] = sha256(target) == original_hash
                    mutants.append(rec)

    after = repo_state(repo)
    result = {
        "spike": "stage2_0", "repo": str(repo), "max": args.max, "per_commit": args.per_commit, "setup": setup,
        "operators": {"comparison_pairs": sorted(COMPARISON_PAIRS), "other": sorted(OTHER_OPERATORS)},
        "repo_preserved": before == after, "repo_state_before": before, "repo_state_after": after,
        "seconds": round(time.perf_counter() - started, 1), "commits": commits_seen, "mutants": mutants,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "mutation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"mutants {len(mutants)} · repo_preserved {result['repo_preserved']} · {result['seconds']}s → {args.out / 'mutation_result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
