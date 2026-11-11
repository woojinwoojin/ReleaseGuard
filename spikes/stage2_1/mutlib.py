"""Stage 2.1 어댑터 — 2.0(run_spike.py)에 리뷰 보완 3가지를 더했다. 설계: docs/design_stage2_1.md 2장

1. 수집 오류(pytest rc 2)는 COLLECTION_ERROR로 분리한다 (유효한 KILLED가 아님).
2. 관련 테스트만 vs 전체: 상태·실패 종류·실패한 테스트 id를 모두 비교한다.
3. mutant마다 원본 스냅샷을 새로 복사한 폴더에서 실행하고 finally로 지운다 (테스트가 만든 파일도 남지 않음).

Cosmic Ray(spikes/stage2_0/.venv)는 mutation 목록(init·dump)과 적용(apply)에만 쓴다. releaseguard는 import만 한다.
"""

import difflib
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

from releaseguard.runner import _env  # noqa: E402

COSMIC_RAY = ROOT / "spikes" / "stage2_0" / ".venv" / "Scripts" / "cosmic-ray.exe"
TEST_TIMEOUT = 120

# 2.0과 같은 허용 연산자 (설계 2.0 Q4)
COMPARISON_PAIRS = {
    "Eq_NotEq", "NotEq_Eq", "Lt_LtE", "LtE_Lt", "Gt_GtE", "GtE_Gt", "Is_IsNot", "IsNot_Is", "In_NotIn", "NotIn_In",
}
BOOLEAN = {"core/ReplaceAndWithOr", "core/ReplaceOrWithAnd", "core/ReplaceUnaryOperator_Not_Delete"}
CONSTANT = {"core/NumberReplacer", "core/ReplaceTrueWithFalse", "core/ReplaceFalseWithTrue"}


def family(op: str) -> str | None:
    """연산자 계열: comparison / boolean / constant. 허용되지 않으면 None."""
    if op.startswith("core/ReplaceComparisonOperator_"):
        return "comparison" if op.removeprefix("core/ReplaceComparisonOperator_") in COMPARISON_PAIRS else None
    if op in BOOLEAN:
        return "boolean"
    if op in CONSTANT:
        return "constant"
    return None


def clean(text: str) -> str:
    """임시·홈 폴더 경로와 계정 이름을 가린다 (결과 파일을 공개 저장소에 둘 수 있게)."""
    for real, mask in ((tempfile.gettempdir(), "<tmp>"), (str(Path.home()), "<home>")):
        for variant in {real, real.replace("\\", "\\\\"), real.replace("\\", "/")}:
            text = text.replace(variant, mask)
    user = Path.home().name
    return text.replace(user, "<user>") if len(user) >= 3 else text


def cosmic(*args: str, cwd: Path, out_file: Path | None = None) -> subprocess.CompletedProcess:
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            return subprocess.run([str(COSMIC_RAY), *args], cwd=cwd, stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    return subprocess.run([str(COSMIC_RAY), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def mutations_for(work: Path, module: str, tmp: Path) -> list[dict]:
    """Cosmic Ray가 이 모듈에 만드는 mutation 전체 (operator, occurrence, 줄). 허용 계열만 family가 붙는다."""
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
        raise RuntimeError(f"cosmic-ray init 실패: {clean(init.stderr[-500:])}")
    dump_file = tmp / "dump.jsonl"
    dump = cosmic("dump", str(session), cwd=work, out_file=dump_file)
    if dump.returncode != 0:
        raise RuntimeError(f"cosmic-ray dump 실패: {clean(dump.stderr[-500:])}")
    out = []
    for line in dump_file.read_text(encoding="utf-8").splitlines():
        item, _ = json.loads(line)
        for m in item["mutations"]:
            out.append({
                "operator": m["operator_name"], "occurrence": m["occurrence"], "family": family(m["operator_name"]),
                "start_line": m["start_pos"][0], "end_line": m["end_pos"][0], "definition": m.get("definition_name"),
            })
    return out


def junit_results(junit: Path) -> list[dict]:
    if not junit.exists():
        return []
    out = []
    for tc in ET.parse(junit).getroot().iter("testcase"):
        outcome, message = "passed", ""
        for tag in ("failure", "error", "skipped"):
            el = tc.find(tag)
            if el is not None:
                outcome, message = tag, el.get("message") or ""
                break
        file = (tc.get("file") or "").replace("\\", "/")
        out.append({"nodeid": f"{file}::{tc.get('name')}", "outcome": outcome, "message": message})
    return out


def failure_kind(r: dict) -> str:
    if r["outcome"] == "error":
        return "error"  # setup·teardown 오류
    return "assertion" if r["message"].startswith(("assert ", "AssertionError")) else "exception"


def run_pytest(python: Path, work: Path, nodeids: list[str], tag: str) -> dict:
    junit = work.parent / f"junit_{tag}.xml"
    junit.unlink(missing_ok=True)
    cmd = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "junit_family=xunit1", f"--junitxml={junit}", *nodeids]
    started = time.perf_counter()
    try:
        proc = subprocess.run(cmd, cwd=work, env=_env(None), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "kind": None, "seconds": round(time.perf_counter() - started, 2), "failed": [], "kinds": {}}
    seconds = round(time.perf_counter() - started, 2)
    results = junit_results(junit)
    failed = sorted(r["nodeid"] for r in results if r["outcome"] in ("failure", "error"))
    kinds = {r["nodeid"]: failure_kind(r) for r in results if r["outcome"] in ("failure", "error")}
    rc = proc.returncode
    if rc == 0:
        status = "SURVIVED"
    elif rc == 1:
        status = "KILLED"
    elif rc == 2:
        status = "COLLECTION_ERROR"  # 보완 1: 유효한 KILLED가 아니다
    elif rc == 5:
        status = "NO_RELEVANT_TEST"
    else:
        status = "EXECUTION_ERROR"
    kind = None
    if status == "KILLED":
        found = set(kinds.values())
        kind = next((k for k in ("assertion", "exception", "error") if k in found), "unknown")
    msgs = [clean(r["message"])[:160] for r in results if r["outcome"] in ("failure", "error")][:3]
    tail = clean(proc.stdout[-400:]) if status in ("COLLECTION_ERROR", "EXECUTION_ERROR") else None
    return {"status": status, "kind": kind, "seconds": seconds, "failed": failed, "kinds": kinds, "messages": msgs, "tail": tail}


def compare(selected: dict, full: dict, selected_ids: list[str]) -> dict:
    """보완 2: 상태·실패 종류·실패한 테스트 id. 선택 실행의 실패 id는 전체의 실패 id ∩ 선택 테스트와 같아야 완전 일치."""
    def in_selection(nodeid: str) -> bool:
        return any(nodeid == s or nodeid.startswith(s + "[") for s in selected_ids)

    expected = sorted(n for n in full["failed"] if in_selection(n))
    out = {
        "status_same": selected["status"] == full["status"],
        "kind_same": selected.get("kind") == full.get("kind"),
        "failed_ids_same": selected["failed"] == expected,
        "full_failures_outside_selection": sorted(n for n in full["failed"] if not in_selection(n)),
    }
    out["exact"] = out["status_same"] and out["kind_same"] and out["failed_ids_same"]
    return out


def changed_lines(before: str, after: str) -> list[int]:
    out = []
    sm = difflib.SequenceMatcher(a=before.splitlines(), b=after.splitlines(), autojunk=False)
    for op, a1, a2, _, _ in sm.get_opcodes():
        if op != "equal":
            out += list(range(a1 + 1, a2 + 1)) or [a1 + 1]
    return out


def run_mutant(pristine: Path, python: Path, path: str, mutation: dict, selected_ids: list[str], extra_files: dict[str, str] | None = None) -> dict:
    """보완 3: 원본 스냅샷을 새로 복사한 폴더에서 mutant 하나를 적용·실행하고, finally로 지운다.

    extra_files: {상대 경로: 내용} — 테스트 추가 실험에서 새 테스트 파일을 넣을 때 쓴다.
    mutation이 None이면 원본(변형 없음)으로 실행한다.
    """
    base = Path(tempfile.mkdtemp(prefix="rg_mut21_"))
    work = base / "src"
    rec: dict = {}
    try:
        shutil.copytree(pristine, work)
        for rel, text in (extra_files or {}).items():
            (work / rel).parent.mkdir(parents=True, exist_ok=True)
            (work / rel).write_text(text, encoding="utf-8", newline="\n")
        target = work / path
        before = target.read_bytes().decode("utf-8")
        if mutation is not None:
            applied = cosmic("apply", path, mutation["operator"], str(mutation["occurrence"]), cwd=work)
            after = target.read_bytes().decode("utf-8")
            line = mutation["start_line"]
            rec["changed_lines"] = changed_lines(before, after)
            rec["on_target_line"] = rec["changed_lines"] == [line]
            rec["source_before"] = before.splitlines()[line - 1].strip()[:200]
            rec["source_after"] = after.splitlines()[line - 1].strip()[:200] if rec["on_target_line"] else None
            try:
                if applied.returncode != 0 or after == before:
                    raise ValueError(clean(applied.stderr[-300:]) or "apply가 파일을 바꾸지 않음")
                py_compile.compile(str(target), doraise=True, cfile=str(base / "check.pyc"))
            except (ValueError, py_compile.PyCompileError) as e:
                rec["result"] = "INVALID"
                rec["invalid_reason"] = clean(str(e))[:300]
                return rec
        rec["selected"] = run_pytest(python, work, selected_ids, "sel") if selected_ids else None
        rec["full"] = run_pytest(python, work, [], "full")
        rec["result"] = rec["full"]["status"]
        if rec["selected"] is not None:
            rec["agreement"] = compare(rec["selected"], rec["full"], selected_ids)
        return rec
    finally:
        shutil.rmtree(base, ignore_errors=True)
