"""Test Suggestion Validator — 에이전트의 테스트 제안을 결정적 규칙으로 확인한다 (LLM 호출 없음).

입력은 이미 있는 것만 쓴다: 이번 테스트 실행의 skip 목록, head 스냅샷의 파일 목록과 테스트 파일 내용.
판정(SAFE·REVIEW·BLOCK)이 끝난 뒤에 돌고, 판정에 들어가지 않는다.

| 코드 | 조건 | 수준 |
|---|---|---|
| S01 SKIPPED_TARGET_FILE | 제안한 파일에서 이번 실행에 skip된 테스트가 있음 | warning |
| S02 SKIP_CAUSE_UNVERIFIED | S01의 skip 원인을 스냅샷에서 확인하지 못함 | check (확인 필요) |
| S03 TEST_NAME_COLLISION | 제안한 이름의 테스트 함수가 같은 범위에 이미 있음 | warning (범위가 불확실하면 후보) |

status: WARN(경고 있음) / UNKNOWN(경고는 없지만 못 한 검사가 있음) / PASS.
PASS는 "구현된 정적 검사에서 경고가 없다"는 뜻이지, 제안한 테스트가 유효하거나 공백을 메운다는 뜻이 아니다.

skip 원인 상태 (S01이 있을 때만):
- 사유: REASON_REPORTED (테스트 결과에 사유가 있음) / REASON_MISSING
- 원인: CAUSE_CORRELATED (사유에 나온 경로가 head 스냅샷에 없음 — 관련 증거이지 인과 확정이 아님) / CAUSE_UNVERIFIED
"""

import ast
import re
from collections.abc import Callable

CHECKS_VERSION = "1"

PASS, WARN, UNKNOWN = "PASS", "WARN", "UNKNOWN"
REASON_REPORTED, REASON_MISSING = "REASON_REPORTED", "REASON_MISSING"
CAUSE_CORRELATED, CAUSE_UNVERIFIED = "CAUSE_CORRELATED", "CAUSE_UNVERIFIED"

# 사유 문자열 안의 경로 모양 토큰: 'data/', 'data/raw/x.csv', 'superstore.csv'.
# 슬래시가 있거나 데이터·설정 파일 확장자로 끝나야 한다 ('e.g', 'v1.2' 같은 토큰을 경로로 보지 않게).
_EXT = r"csv|tsv|jsonl|json|ya?ml|txt|xlsx?|parquet|sqlite3?|db|toml|ini|env|py|zip|pdf|html?"
_PATH_TOKEN = re.compile(rf"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]*)+|[A-Za-z0-9_\-]+\.(?:{_EXT})\b", re.I)


def _test_file(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _norm(path: str) -> str:
    path = path.replace("\\", "/")
    return path[2:] if path.startswith("./") else path


def defined_tests(source: str) -> dict[str, set[str]]:
    """AST로 찾은 테스트 함수 이름 → 소속 범위들. 모듈 수준은 "", 클래스 메서드는 "Outer.Inner" 형식.

    주석·문자열에 나온 이름은 함수가 아니므로 세지 않는다. 함수 안에 정의된 함수는 pytest가 수집하지 않으므로 뺀다.
    SyntaxError는 호출한 쪽에서 처리한다.
    """
    out: dict[str, set[str]] = {}

    def visit(body: list[ast.stmt], scope: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out.setdefault(node.name, set()).add(scope)
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{scope}.{node.name}" if scope else node.name)

    visit(ast.parse(source).body, "")
    return out


def _split_name(name: str) -> tuple[str | None, str]:
    """제안 이름 → (소속 클래스, 함수 이름). 'TestA::test_x'·'TestA.test_x'는 클래스가 정해지고,
    'test_x'는 소속이 적혀 있지 않다 (None)."""
    name = name.strip().split("(", 1)[0]  # 'test_x()'처럼 괄호까지 쓴 경우
    parts = [p for p in re.split(r"::|\.", name) if p]
    if len(parts) <= 1:
        return None, parts[0] if parts else name
    return ".".join(parts[:-1]), parts[-1]


def check_name_collision(file: str, name: str, source: str | None) -> tuple[dict | None, str | None]:
    """(S03 경고 또는 None, 검사하지 못한 이유 또는 None)."""
    if source is None:
        return None, None  # 새 파일 제안: 겹칠 기존 함수가 없다
    try:
        defined = defined_tests(source)
    except SyntaxError as e:
        return None, f"S03: {file}를 파싱하지 못함 ({e.msg}, {e.lineno}줄)"
    scope, func = _split_name(name)
    scopes = defined.get(func, set())
    if not scopes:
        return None, None
    if scope is not None:
        if scope not in scopes:
            return None, None  # 다른 클래스의 같은 이름은 pytest에서 다른 테스트다
        confirmed, where = True, [scope]
    elif "" in scopes:
        # 소속을 안 적었고 모듈 수준에 같은 이름이 있다: 모듈 수준에 넣으면 기존 함수를 덮어쓴다
        confirmed, where = True, [""]
    else:
        # 같은 이름이 클래스 안에만 있다: 어느 범위에 넣을지 제안이 말하지 않으므로 확정하지 않는다
        confirmed, where = False, sorted(scopes)
    label = ", ".join(f"{s}.{func}" if s else f"모듈 수준 {func}" for s in where)
    message = (
        f"제안한 테스트 이름이 기존 테스트({label})와 겹칩니다. 기존 테스트를 확장할지 다른 이름을 쓸지 검토하세요."
        if confirmed else
        f"제안한 이름이 클래스 안의 기존 테스트({label})와 같습니다. 제안이 소속 클래스를 말하지 않아 충돌을 확정하지 못했습니다."
    )
    return {
        "code": "S03", "rule": "TEST_NAME_COLLISION", "level": "warning" if confirmed else "candidate",
        "message": message,
        "evidence": {"file": file, "name": func, "suggested_scope": scope, "existing_scopes": sorted(scopes), "confirmed": confirmed},
    }, None


def skip_cause(reason: str | None, snapshot_files: set[str]) -> dict:
    """skip 하나의 사유 상태와 원인 상태. 사유에 나온 경로가 head 스냅샷에 하나도 없으면 CAUSE_CORRELATED."""
    if not (reason or "").strip():
        return {"reason_status": REASON_MISSING, "cause_status": CAUSE_UNVERIFIED, "missing_paths": []}
    missing = []
    for token in dict.fromkeys(_PATH_TOKEN.findall(reason)):
        path = _norm(token)
        prefix = path if path.endswith("/") else path + "/"
        if path and path not in snapshot_files and not any(f.startswith(prefix) for f in snapshot_files):
            missing.append(token)
    return {
        "reason_status": REASON_REPORTED,
        "cause_status": CAUSE_CORRELATED if missing else CAUSE_UNVERIFIED,
        "missing_paths": missing,
    }


def check_skips(file: str, skipped: list[dict], snapshot_files: set[str], collected: int | None = None) -> tuple[list[dict], str | None]:
    """(S01·S02 경고, 파일 전체의 원인 상태 또는 None). collected는 이번 실행에서 그 파일의 테스트 수 (모르면 None)."""
    in_file = [s for s in skipped if _test_file(s["nodeid"]) == file]
    if not in_file:
        return [], None
    causes = [{"nodeid": s["nodeid"], "reason": s["reason"], **skip_cause(s["reason"], snapshot_files)} for s in in_file]
    correlated = all(c["cause_status"] == CAUSE_CORRELATED for c in causes)
    status = CAUSE_CORRELATED if correlated else CAUSE_UNVERIFIED
    reasons = sorted({c["reason"] or "(사유 없음)" for c in causes})
    warnings = [{
        "code": "S01", "rule": "SKIPPED_TARGET_FILE", "level": "warning",
        "message": (
            f"제안한 테스트 파일에서 기존 테스트 {f'{collected}개 중 ' if collected else ''}{len(in_file)}개가 이번 실행에서 건너뛰어졌습니다. "
            "새 테스트가 실행될지 확인하세요."
        ),
        "evidence": {
            "file": file, "skipped_count": len(in_file), "collected_count": collected,
            "all_skipped": collected == len(in_file) if collected else None, "reasons": reasons, "skips": causes,
        },
    }]
    if not correlated:
        missing = sum(c["reason_status"] == REASON_MISSING for c in causes)
        warnings.append({
            "code": "S02", "rule": "SKIP_CAUSE_UNVERIFIED", "level": "check",
            "message": (
                "skip 원인을 스냅샷에서 확인하지 못했습니다"
                + (f" (사유 없는 skip {missing}개)" if missing else " (사유에 스냅샷에서 빠진 경로가 보이지 않음)")
                + ". 사유 문자열은 원인의 증명이 아닙니다."
            ),
            "evidence": {"file": file, "reason_missing": missing},
        })
    return warnings, status


def check_suggestion(
    suggested_test: dict,
    skipped: list[dict] | None,
    snapshot_files: set[str],
    read_head: Callable[[str], str | None],
    tests_by_file: dict[str, int] | None = None,
) -> dict:
    """제안 하나를 확인한다. skipped가 None이면 테스트를 돌리지 않아 skip 검사를 못 한 것이다.
    read_head(path)는 head 스냅샷의 파일 내용, 없으면 None. tests_by_file은 이번 실행의 파일별 테스트 수 (근거 표시용)."""
    file = _norm(suggested_test["file"])
    warnings, unchecked = [], []
    skip_status = None
    if skipped is None:
        unchecked.append("S01·S02: 테스트를 실행하지 않아 skip 정보가 없음")
    else:
        found, skip_status = check_skips(file, skipped, snapshot_files, (tests_by_file or {}).get(file))
        warnings += found
    collision, problem = check_name_collision(file, suggested_test["name"], read_head(file) if file in snapshot_files else None)
    if collision:
        warnings.append(collision)
    if problem:
        unchecked.append(problem)
    status = WARN if warnings else UNKNOWN if unchecked else PASS
    return {"version": CHECKS_VERSION, "status": status, "warnings": warnings, "skip_cause_status": skip_status, "unchecked": unchecked}
