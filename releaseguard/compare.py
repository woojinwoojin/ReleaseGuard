"""base·head에서 모두 실패한 테스트가 '같은 실패'인지 판단할 근거 (실패 비교, 판정 규칙 v3.1).

PRE_EXISTING(원래 깨짐, T01)으로 낮추려면 아래가 모두 확인돼야 한다. 하나라도 확인하지 못하면 INCOMPARABLE(B03) 유지.
1. 같은 node id가 base·head 모두에서 수집되고 실패한다 (호출하는 쪽에서 확인)
2. 테스트 파일이 안 바뀌었거나, 바뀌었어도 **새 테스트 함수만 추가**됐다
   (기존 테스트·헬퍼·fixture·import 등 테스트가 아닌 부분이 모두 같음 — 처음 구현은 이 좁은 경우만 인정)
3. 공유 테스트 맥락(의존성·conftest·테스트 헬퍼 모듈·pytest 설정)이 안 바뀌었다
4. 실패 지문(runner.failure_fingerprint: 예외 종류·전체 메시지·traceback 위치)이 같다
"""

import ast
from pathlib import PurePosixPath

TEST_SETTINGS = {"pytest.ini", "setup.cfg", "tox.ini", "conftest.py"}  # pyproject.toml은 deps로 분류됨


def _is_test_def(node: ast.stmt) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name.startswith("test")
    return isinstance(node, ast.ClassDef) and node.name.startswith("Test")


def split_test_module(source: str) -> tuple[list[str], dict[str, str]] | None:
    """(테스트가 아닌 최상위 문장들, {최상위 테스트 이름: 정의}). ast.dump라 줄 번호는 비교에 들어가지 않는다.

    테스트 함수·클래스의 정의에는 데코레이터(parametrize 등)가 포함된다. 문법 오류면 None.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    others, tests = [], {}
    for node in tree.body:
        if _is_test_def(node):
            tests[node.name] = ast.dump(node)
        else:
            others.append(ast.dump(node))
    return others, tests


def top_level_test(nodeid: str) -> str:
    """tests/test_x.py::TestBox::test_m[1] → TestBox, tests/test_x.py::test_p[2-3] → test_p"""
    return nodeid.split("::")[1].split("[", 1)[0] if "::" in nodeid else ""


def file_change_evidence(base_src: str, head_src: str, nodeid: str) -> dict:
    """같은 파일이 바뀐 경우의 근거. only_new_tests_added가 True여야 2번 조건을 만족한다."""
    b, h = split_test_module(base_src), split_test_module(head_src)
    if b is None or h is None:
        return {"test_function_same": None, "only_new_tests_added": None}
    name = top_level_test(nodeid)
    function_same = name in b[1] and b[1].get(name) == h[1].get(name)
    only_new = b[0] == h[0] and all(h[1].get(n) == d for n, d in b[1].items())
    return {"test_function_same": function_same, "only_new_tests_added": only_new}


def shared_test_context_changes(files: list[dict]) -> list[str]:
    """이번 변경에서 바뀐 공유 테스트 맥락: 의존성, conftest·pytest 설정, 테스트 헬퍼(test_*.py가 아닌 테스트 폴더 모듈)."""
    out = []
    for f in files:
        name = PurePosixPath(f["path"]).name
        helper = f["category"] == "test" and not (name.startswith("test_") or name.endswith("_test.py"))
        if f["category"] == "deps" or name in TEST_SETTINGS or helper:
            out.append(f["path"])
    return sorted(set(out))
