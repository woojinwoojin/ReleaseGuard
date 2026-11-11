"""바뀐 테스트가 실제로 실행됐는지 확인한다 (판정 규칙 v3.2의 T03, N07). 설계: docs/design_stage1_7.md

이미 있는 것만 쓴다: 바뀐 파일·추가된 줄, 이번 전체 실행의 JUnit 결과, head 스냅샷의 파일 내용. 테스트를 더 돌리지 않는다.
관찰한 사실만 말한다 — JUnit에 결과가 없다는 것을 "pytest가 수집하지 않았다"로 단정하지 않는다.

| 원인 코드 | 조건 |
|---|---|
| NO_TEST_RESULTS | 바뀐 수집 대상 테스트 파일에 테스트 함수가 정의돼 있는데 이번 실행의 결과가 0개 |
| CHANGED_TESTS_ALL_SKIPPED | 바뀐 테스트 함수 중 결과가 있는 것들의 결과(parametrize 값마다)가 전부 skip |
| MODULE_SKIPPED | 바뀐 테스트 함수가 있는 파일이 모듈 수준에서 skip됨 (함수별 결과 없음) |
| TEST_SUITE_REMOVED | 실행 결과가 no_tests이고 수집 대상 테스트 파일이 삭제됨 |

pytest 수집 설정을 이해하지 못하면(python_files, addopts -k 등) 앞의 세 검사는 보류하고 그 사실을 남긴다 (N07).
"""

import ast
import configparser
import re
import shlex
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

NO_TEST_RESULTS = "NO_TEST_RESULTS"
CHANGED_TESTS_ALL_SKIPPED = "CHANGED_TESTS_ALL_SKIPPED"
MODULE_SKIPPED = "MODULE_SKIPPED"
TEST_SUITE_REMOVED = "TEST_SUITE_REMOVED"
# 수집 설정을 이해하지 못할 때 보류하는 검사 (TEST_SUITE_REMOVED는 설정과 관계없는 관찰이라 계속 본다)
HELD_WHEN_UNSUPPORTED = (NO_TEST_RESULTS, CHANGED_TESTS_ALL_SKIPPED, MODULE_SKIPPED)

PERFORMED, HELD, NOT_APPLICABLE, NOT_EVALUATED = "performed", "held", "not_applicable", "not_evaluated"
EVALUATED_RUN_STATUS = ("passed", "failed", "no_tests")

_DEFAULT_FILES = re.compile(r"^(test_.*|.*_test)\.py$")
_UNSUPPORTED_KEYS = ("python_files", "python_classes", "python_functions", "norecursedirs")
_COLLECT_OPTS = ("--ignore", "--ignore-glob", "--deselect", "-k", "-m", "--pyargs")
_CONFTEST_HOOKS = re.compile(
    r"\b(collect_ignore|collect_ignore_glob|pytest_collection_modifyitems|pytest_ignore_collect|pytest_collect_file|pytest_pycollect_makeitem)\b"
)
_GLOB = re.compile(r"[*?\[]")


@dataclass
class CollectionConfig:
    testpaths: list[str] = field(default_factory=list)  # 비어 있으면 저장소 전체
    unsupported: list[str] = field(default_factory=list)  # 이해하지 못한 수집 설정 (사람이 읽는 설명)


def _ini_section(text: str, section: str) -> dict[str, str] | None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return None
    return dict(parser[section]) if parser.has_section(section) else None


def read_collection_config(files: set[str], read: Callable[[str], str]) -> CollectionConfig:
    """head 스냅샷의 pytest 설정. pytest처럼 루트의 pytest.ini → pyproject.toml → tox.ini → setup.cfg 순으로 첫 설정을 쓴다."""
    options: dict[str, object] | None = None
    source = ""
    for name, section in (("pytest.ini", "pytest"), ("pyproject.toml", None), ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        if name not in files:
            continue
        text = read(name)
        if name == "pyproject.toml":
            try:
                found = tomllib.loads(text).get("tool", {}).get("pytest", {}).get("ini_options")
            except tomllib.TOMLDecodeError:
                found = None
        elif name == "pytest.ini":
            found = _ini_section(text, "pytest") or {}  # pytest.ini는 [pytest]가 없어도 설정 파일로 쓰인다
        else:
            found = _ini_section(text, section)
        if found is not None:
            options, source = found, name
            break

    cfg = CollectionConfig()
    for key, value in (options or {}).items():
        if key in _UNSUPPORTED_KEYS:
            cfg.unsupported.append(f"{source}: {key}")
        elif key == "testpaths":
            paths = value if isinstance(value, list) else str(value).split()
            if any(_GLOB.search(p) for p in paths):
                cfg.unsupported.append(f"{source}: testpaths (glob)")
            cfg.testpaths = [p.strip("/").removeprefix("./") for p in paths]
        elif key == "addopts":
            args = value if isinstance(value, list) else shlex.split(str(value), posix=True)
            for a in args:
                if a.split("=", 1)[0] in _COLLECT_OPTS or not a.startswith("-"):
                    cfg.unsupported.append(f"{source}: addopts {a}")
    for path in sorted(f for f in files if PurePosixPath(f).name == "conftest.py"):
        hooks = sorted(set(_CONFTEST_HOOKS.findall(read(path))))
        cfg.unsupported += [f"{path}: {h}" for h in hooks]
    return cfg


def is_collection_target(path: str, category: str, cfg: CollectionConfig) -> bool:
    if category != "test" or not _DEFAULT_FILES.match(PurePosixPath(path).name):
        return False
    if not cfg.testpaths:
        return True
    return any(p in ("", ".") or path == p or path.startswith(p + "/") for p in cfg.testpaths)


@dataclass
class DefinedTest:
    scope: str  # "" = 모듈 수준, "TestA" 또는 "TestA.TestB"
    name: str
    start: int  # 데코레이터 포함
    end: int

    @property
    def key(self) -> str:
        return f"{self.scope}.{self.name}" if self.scope else self.name


def find_test_functions(source: str) -> list[DefinedTest]:
    """pytest 기본 규칙의 테스트 함수: 모듈 수준 test*, Test* 클래스(중첩 포함) 안의 test* 메서드. SyntaxError면 빈 목록."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out = []

    def visit(body: list[ast.stmt], scope: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                start = min([d.lineno for d in node.decorator_list] + [node.lineno])
                out.append(DefinedTest(scope, node.name, start, node.end_lineno or node.lineno))
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                visit(node.body, f"{scope}.{node.name}" if scope else node.name)

    visit(tree.body, "")
    return out


def _module_of(path: str) -> str:
    return ".".join(PurePosixPath(path).with_suffix("").parts)


def _result_key(nodeid: str) -> tuple[str, str]:
    """"tests/x.py::TestA::test_f[1]" → ("tests/x.py", "TestA.test_f"). 클래스 구분자는 :: 와 . 모두 받는다."""
    file, _, rest = nodeid.partition("::")
    parts = rest.split("::")
    parts[-1] = re.sub(r"\[.*\]$", "", parts[-1])
    return file, ".".join(p for p in parts if p)


def is_module_skip(nodeid: str, outcome: str) -> bool:
    """모듈 수준 skip 기록: JUnit에 classname="" name=<모듈 경로>로 남아 parse_junit이 "파일::모듈경로"로 만든다."""
    file, _, rest = nodeid.partition("::")
    return outcome == "skipped" and rest == _module_of(file)


def check_test_changes(
    files: list[dict],
    added_lines: dict[str, list[tuple[int, str]]],
    run_status: str,
    tests: list[dict],
    full_run: bool,
    head_files: set[str],
    read_head: Callable[[str], str],
) -> dict:
    """files: {"path", "status", "category"}. tests: 이번 실행 결과 {"nodeid", "outcome", "message"}.

    결과 dict는 그대로 JSON에 저장된다 (test_change_checks). reasons가 비어 있지 않으면 T03, status가 held이면 N07.
    """
    out = {
        "status": NOT_APPLICABLE, "full_run": full_run, "run_status": run_status,
        "testpaths": [], "unsupported_config": [], "held_checks": [],
        "changed_test_files": [], "reasons": [], "unmatched_changed_tests": [],
    }
    if run_status not in EVALUATED_RUN_STATUS or not full_run:
        out["status"] = NOT_EVALUATED
        return out

    cfg = read_collection_config(head_files, read_head)
    out["testpaths"], out["unsupported_config"] = cfg.testpaths, cfg.unsupported
    changed = [
        f for f in files
        if f["status"] in ("A", "M", "R") and is_collection_target(f["path"], f["category"], cfg) and added_lines.get(f["path"])
    ]
    deleted = [f["path"] for f in files if f["status"] == "D" and is_collection_target(f["path"], f["category"], cfg)]
    out["changed_test_files"] = [f["path"] for f in changed]

    if run_status == "no_tests" and deleted:
        out["reasons"].append({"code": TEST_SUITE_REMOVED, "path": None, "deleted_test_files": deleted})
    if not changed:
        out["status"] = PERFORMED if deleted else NOT_APPLICABLE
        return out
    if cfg.unsupported:
        out["status"], out["held_checks"] = HELD, list(HELD_WHEN_UNSUPPORTED)
        return out

    out["status"] = PERFORMED
    by_file: dict[str, list[dict]] = {}
    for t in tests:
        by_file.setdefault(t["nodeid"].partition("::")[0], []).append(t)
    for f in changed:
        path = f["path"]
        funcs = find_test_functions(read_head(path))
        added = {n for n, _ in added_lines.get(path, [])}
        changed_funcs = funcs if f["status"] == "A" else [fn for fn in funcs if any(fn.start <= n <= fn.end for n in added)]
        results = by_file.get(path, [])
        module_skips = [t for t in results if is_module_skip(t["nodeid"], t["outcome"])]
        if module_skips and changed_funcs:
            out["reasons"].append({
                "code": MODULE_SKIPPED, "path": path, "message": module_skips[0]["message"],
                "changed_tests": [fn.key for fn in changed_funcs],
            })
            continue
        if not results:
            if funcs:
                out["reasons"].append({
                    "code": NO_TEST_RESULTS, "path": path, "change": f["status"], "defined_tests": len(funcs),
                })
            continue
        per_func: dict[str, list[dict]] = {}
        for t in results:
            per_func.setdefault(_result_key(t["nodeid"])[1], []).append(t)
        with_results = [fn for fn in changed_funcs if per_func.get(fn.key)]
        without = [fn.key for fn in changed_funcs if not per_func.get(fn.key)]
        if without:
            out["unmatched_changed_tests"].append({"path": path, "tests": without})
        outcomes = [t for fn in with_results for t in per_func[fn.key]]
        if with_results and all(t["outcome"] == "skipped" for t in outcomes):
            out["reasons"].append({
                "code": CHANGED_TESTS_ALL_SKIPPED, "path": path,
                "changed_tests": [fn.key for fn in with_results], "results": len(outcomes),
                "skip_reasons": sorted({t["message"] or "(사유 없음)" for t in outcomes})[:3],
                "changed_tests_without_results": without,
                "base_status_checked": False,  # 이전에도 skip이었는지는 base를 다시 돌려야 알 수 있어 확인하지 않는다
            })
    return out


def evidence_lines(checks: dict) -> list[str]:
    """T03 근거 문자열. 원인 코드로 시작한다."""
    out = []
    for r in checks["reasons"]:
        code = r["code"]
        if code == TEST_SUITE_REMOVED:
            out.append(f"{code}: 테스트 결과 0개, 삭제된 테스트 파일 {', '.join(r['deleted_test_files'])}")
        elif code == NO_TEST_RESULTS:
            out.append(f"{code}: {r['path']} — 테스트 함수 {r['defined_tests']}개 정의, 이번 실행 결과 0개")
        elif code == MODULE_SKIPPED:
            out.append(f"{code}: {r['path']} — 모듈 전체가 skip됨 ({r['message'] or '사유 없음'}), 바뀐 테스트 {', '.join(r['changed_tests'])}")
        else:
            extra = f", 결과 없는 바뀐 테스트 {', '.join(r['changed_tests_without_results'])}" if r["changed_tests_without_results"] else ""
            out.append(
                f"{code}: {r['path']} — 바뀐 테스트 {len(r['changed_tests'])}개의 결과 {r['results']}개가 모두 skip "
                f"(사유: {'; '.join(r['skip_reasons'])}; 이전에도 skip이었는지 확인 안 함){extra}"
            )
    return out
