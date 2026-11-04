"""'같은 실패' 판단 (판정 규칙 v3.1). 단위 테스트 + 임시 저장소에서 실제로 실행하는 사례.

완료 기준 (외부 검토 2026-11-04): 옛 결함이 반복 BLOCK되던 경우는 PRE_EXISTING으로 내려가고,
바뀐 테스트·헬퍼·다른 실패 같은 반례는 INCOMPARABLE(BLOCK)로 남아야 한다.
"""

from conftest import CALC, PY

from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.compare import shared_test_context_changes, split_test_module, file_change_evidence, top_level_test
from releaseguard.runner import failure_fingerprint

RULES = load_rules()

BASE_TEST = '''import os


def helper():
    return os.environ.get("RG_NO_SUCH_VAR")


def test_needs_key():
    assert helper() is not None


def test_other():
    assert True
'''


# ---------------------------------------------------------------- 단위


def test_split_ignores_line_numbers_and_keeps_decorators():
    a = "import x\n\n\n@x.mark\ndef test_a():\n    pass\n"
    b = "import x\n\n\n\n\n@x.mark\ndef test_a():\n    pass\n"  # 줄만 밀림
    assert split_test_module(a) == split_test_module(b)
    c = "import x\n\n\n@x.other\ndef test_a():\n    pass\n"  # 데코레이터만 다름
    assert split_test_module(a)[1] != split_test_module(c)[1]
    assert split_test_module("def test_a(:\n") is None


def test_only_new_tests_added():
    head = BASE_TEST + "\n\ndef test_new():\n    assert 1\n"
    assert file_change_evidence(BASE_TEST, head, "tests/test_k.py::test_needs_key") == {
        "test_function_same": True, "only_new_tests_added": True,
    }


def test_helper_or_other_test_change_is_not_only_new_tests():
    helper_changed = BASE_TEST.replace('get("RG_NO_SUCH_VAR")', 'get("RG_OTHER")')
    assert file_change_evidence(BASE_TEST, helper_changed, "tests/test_k.py::test_needs_key")["only_new_tests_added"] is False
    other_changed = BASE_TEST.replace("def test_other():\n    assert True", "def test_other():\n    assert 1 == 1")
    e = file_change_evidence(BASE_TEST, other_changed, "tests/test_k.py::test_needs_key")
    assert (e["test_function_same"], e["only_new_tests_added"]) == (True, False)
    failing_changed = BASE_TEST.replace("assert helper() is not None", "assert helper()")
    assert file_change_evidence(BASE_TEST, failing_changed, "tests/test_k.py::test_needs_key")["test_function_same"] is False


def test_top_level_test_name():
    assert top_level_test("tests/test_x.py::TestBox::test_m[1]") == "TestBox"
    assert top_level_test("tests/test_x.py::test_p[2-3]") == "test_p"


def test_shared_context_changes():
    files = [
        {"path": "tests/test_api.py", "category": "test"},
        {"path": "tests/fakes.py", "category": "test"},  # 테스트 헬퍼
        {"path": "tests/conftest.py", "category": "test"},
        {"path": "pytest.ini", "category": "config"},
        {"path": "requirements.txt", "category": "deps"},
        {"path": "src/api.py", "category": "source"},
    ]
    assert shared_test_context_changes(files) == ["pytest.ini", "requirements.txt", "tests/conftest.py", "tests/fakes.py"]


def test_fingerprint_drops_tmp_paths_addresses_and_line_numbers_but_keeps_values():
    text_a = (
        "tests\\test_api.py:110: in test_chat\n    r = http.post()\n"
        "C:\\Users\\x\\AppData\\Local\\Temp\\rg_abc\\src\\api.py:60: in get_client\n    return openai.OpenAI()\n"
        "E   openai.OpenAIError: Missing\n"
        "C:\\venv\\Lib\\site-packages\\openai\\_client.py:274: OpenAIError"
    )
    text_b = text_a.replace("rg_abc", "rg_zzz").replace(":110:", ":131:")  # 다른 임시 폴더, 줄이 밀림
    fa = failure_fingerprint("openai.OpenAIError: Missing at 0x1f3a", text_a)
    fb = failure_fingerprint("openai.OpenAIError: Missing at 0x9bc0", text_b)
    assert fa == fb
    assert "tests/test_api.py::test_chat" in fa and "api.py::get_client" in fa
    assert "C:/venv/Lib/site-packages/openai/_client.py::OpenAIError" in fa
    # 같은 함수에서 같은 종류로 실패해도 값이 다르면 다른 실패
    assert failure_fingerprint("AssertionError: assert 500 == 200", "") != failure_fingerprint("AssertionError: assert 404 == 200", "")


# ---------------------------------------------------------------- 실제 실행


def run(repo):
    return analyze(repo.path, "HEAD~1", "HEAD", RULES, python=PY)


def rules(result):
    return [f["rule_id"] for f in result["findings"] if f["decision"] != "NOTE"]


def broken(pyrepo):
    """환경 변수가 없으면 실패하는 테스트를 들여온다 (week3 93abf12와 같은 모양)."""
    pyrepo.write("tests/test_k.py", BASE_TEST)
    pyrepo.commit("test that needs an env var")


def test_repeated_block_case_new_test_added_is_preexisting(pyrepo):
    # week3 8c05dc5·2e652ab: 실패하는 테스트는 그대로, 같은 파일 끝에 새 테스트만 추가
    broken(pyrepo)
    pyrepo.write("tests/test_k.py", BASE_TEST + "\n\ndef test_new():\n    assert 2 > 1\n")
    pyrepo.commit("add an independent test to the same file")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert f["comparison"] == "PRE_EXISTING"
    assert f["comparison_evidence"]["method"] == "matched_existing_failure_only_new_tests"
    assert (result["decision"], rules(result)) == ("REVIEW REQUIRED", ["T01"])


def test_changed_failing_test_stays_incomparable(pyrepo):
    # 반례: 실패하는 테스트 자체가 바뀌었다 (새 실패일 수 있음)
    broken(pyrepo)
    pyrepo.write("tests/test_k.py", BASE_TEST.replace("assert helper() is not None", "assert helper() == 'x'"))
    pyrepo.commit("change the failing test")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert f["comparison"] == "INCOMPARABLE" and f["comparison_evidence"]["test_function_same"] is False
    assert rules(result) == ["B03"]


def test_changed_helper_stays_incomparable(pyrepo):
    # 반례: week3 12b9eb3처럼 같은 파일의 헬퍼가 바뀜 → 같은 실패라도 낮추지 않는다
    broken(pyrepo)
    pyrepo.write("tests/test_k.py", BASE_TEST.replace('get("RG_NO_SUCH_VAR")', 'get("RG_STILL_MISSING")'))
    pyrepo.commit("change a helper in the same file")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert f["comparison"] == "INCOMPARABLE" and f["comparison_evidence"]["only_new_tests_added"] is False
    assert rules(result) == ["B03"]


def test_changed_shared_helper_module_stays_incomparable(pyrepo):
    # 반례: week3 260bafb·6c6a32e처럼 tests/fakes.py 같은 공유 헬퍼가 바뀜
    broken(pyrepo)
    pyrepo.write("tests/fakes.py", "FAKE = 1\n")
    pyrepo.commit("add a shared test helper")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert f["comparison"] == "INCOMPARABLE"
    assert f["comparison_evidence"]["shared_test_context_changes"] == ["tests/fakes.py"]


def test_different_failure_in_unchanged_test_stays_incomparable(pyrepo):
    # 반례: 테스트 파일은 그대로인데 소스 변경으로 실패 내용이 바뀜 → 원래 깨진 것과 같은 실패가 아님
    pyrepo.write("tests/test_v.py", "from src.calc import add\n\n\ndef test_add_big():\n    assert add(2, 2) == 5\n")
    pyrepo.commit("already failing: 4 != 5")
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return a + b + 10"))
    pyrepo.commit("source change makes it fail differently")
    result = run(pyrepo)
    by = {f["nodeid"]: f for f in result["test_run"]["failures"]}
    f = by["tests/test_v.py::test_add_big"]
    assert f["comparison"] == "INCOMPARABLE" and f["comparison_evidence"]["failure_fingerprint_same"] is False
    assert by["tests/test_calc.py::test_add"]["comparison"] == "REGRESSION"
    assert rules(result)[0] == "B03"


def test_skipped_tests_are_listed(pyrepo):
    pyrepo.write("tests/test_s.py", "import pytest\n\n\n@pytest.mark.skip(reason='데이터 파일 없음')\ndef test_ui():\n    pass\n")
    pyrepo.commit("skipped test")
    result = run(pyrepo)
    assert result["test_run"]["skipped"] == [{"nodeid": "tests/test_s.py::test_ui", "reason": "데이터 파일 없음"}]
    assert result["decision"] == "SAFE"  # skip은 아직 판정에 넣지 않는다 (한계로 문서화)
