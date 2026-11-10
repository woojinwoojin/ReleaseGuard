"""Test Suggestion Validator (S01·S02·S03). 반례는 '비슷하지만 겹치지 않는' 제안이 경고 없이 지나가는지 본다."""

from releaseguard.suggestion_checks import (
    CAUSE_CORRELATED, CAUSE_UNVERIFIED, PASS, REASON_MISSING, REASON_REPORTED, UNKNOWN, WARN,
    check_name_collision, check_suggestion, defined_tests, skip_cause,
)

TESTS = '''"""test_answer_is_marked 는 여기 문자열에만 나온다."""
import pytest

# def test_in_comment(): 주석이라 함수가 아니다


def test_unverified_evidence_is_marked():
    helper = "test_in_string"


class TestRender:
    def test_render_answer(self):
        def test_nested():  # 함수 안의 함수는 pytest가 모으지 않는다
            pass

    class TestInner:
        def test_deep(self):
            pass


class TestOther:
    def test_render_answer(self):
        pass
'''

FILES = {"app.py", "tests/test_app.py", "tests/test_api.py"}


def read(path):
    return {"tests/test_app.py": TESTS, "tests/test_api.py": "def test_x():\n    pass\n"}.get(path)


def suggest(name, file="tests/test_app.py"):
    return {"file": file, "name": name, "scenario": "-", "assertion": "-"}


def codes(checks):
    return [(w["code"], w["level"]) for w in checks["warnings"]]


# ---- S03 이름 충돌

def test_defined_tests_uses_ast_scopes():
    found = defined_tests(TESTS)
    assert found["test_unverified_evidence_is_marked"] == {""}
    assert found["test_render_answer"] == {"TestRender", "TestOther"}
    assert found["test_deep"] == {"TestRender.TestInner"}
    for name in ("test_in_comment", "test_in_string", "test_answer_is_marked", "test_nested"):
        assert name not in found


def test_module_level_duplicate_is_confirmed():
    # N3: 기존 모듈 수준 함수와 같은 이름 → 그대로 넣으면 덮어쓴다
    w, problem = check_name_collision("tests/test_app.py", "test_unverified_evidence_is_marked", TESTS)
    assert problem is None and w["code"] == "S03" and w["level"] == "warning" and w["evidence"]["confirmed"]


def test_class_scope_is_respected():
    assert check_name_collision("tests/test_app.py", "TestRender::test_render_answer", TESTS)[0]["level"] == "warning"
    assert check_name_collision("tests/test_app.py", "TestRender.TestInner.test_deep", TESTS)[0]["level"] == "warning"
    # 다른 클래스의 같은 이름은 pytest에서 다른 테스트
    assert check_name_collision("tests/test_app.py", "TestNew::test_render_answer", TESTS) == (None, None)


def test_unqualified_name_matching_only_methods_is_candidate():
    w, _ = check_name_collision("tests/test_app.py", "test_render_answer", TESTS)
    assert w["level"] == "candidate" and not w["evidence"]["confirmed"]
    assert w["evidence"]["existing_scopes"] == ["TestOther", "TestRender"]


def test_names_only_in_comments_or_strings_do_not_collide():
    for name in ("test_in_comment", "test_in_string", "test_answer_is_marked", "test_nested", "test_unverified_evidence"):
        assert check_name_collision("tests/test_app.py", name, TESTS) == (None, None)


def test_name_with_parentheses_is_normalized():
    assert check_name_collision("tests/test_app.py", "test_unverified_evidence_is_marked()", TESTS)[0] is not None


def test_unparsable_file_is_unchecked_not_passed():
    w, problem = check_name_collision("tests/test_app.py", "test_x", "def broken(:\n")
    assert w is None and problem.startswith("S03:")


# ---- S01·S02 skip

def test_skip_cause_states():
    assert skip_cause(None, FILES) == {"reason_status": REASON_MISSING, "cause_status": CAUSE_UNVERIFIED, "missing_paths": []}
    s = skip_cause("기본 데이터(data/) 없음", FILES)
    assert (s["reason_status"], s["cause_status"], s["missing_paths"]) == (REASON_REPORTED, CAUSE_CORRELATED, ["data/"])
    # 경로가 스냅샷에 있으면 상관 증거가 아니다
    assert skip_cause("app.py 확인 필요", FILES)["cause_status"] == CAUSE_UNVERIFIED
    assert skip_cause("needs tests/ folder", FILES)["cause_status"] == CAUSE_UNVERIFIED
    # 경로처럼 보이지 않는 토큰
    assert skip_cause("flaky on CI, e.g. v1.2", FILES)["cause_status"] == CAUSE_UNVERIFIED
    assert skip_cause("missing superstore.csv", FILES)["missing_paths"] == ["superstore.csv"]


def test_skip_in_suggested_file_warns_without_claiming_it_will_not_run():
    skipped = [{"nodeid": "tests/test_app.py::test_a", "reason": "기본 데이터(data/) 없음"},
               {"nodeid": "tests/test_app.py::test_b", "reason": "기본 데이터(data/) 없음"}]
    c = check_suggestion(suggest("test_new"), skipped, FILES, read)
    assert c["status"] == WARN and codes(c) == [("S01", "warning")]
    assert c["skip_cause_status"] == CAUSE_CORRELATED
    w = c["warnings"][0]
    assert w["evidence"]["skipped_count"] == 2 and "확인하세요" in w["message"] and "실행되지 않" not in w["message"]


def test_unverified_cause_adds_s02():
    skipped = [{"nodeid": "tests/test_app.py::test_a", "reason": "data/ 없음"},
               {"nodeid": "tests/test_app.py::test_b", "reason": None}]
    c = check_suggestion(suggest("test_new"), skipped, FILES, read)
    assert codes(c) == [("S01", "warning"), ("S02", "check")]
    assert c["skip_cause_status"] == CAUSE_UNVERIFIED and c["warnings"][1]["evidence"]["reason_missing"] == 1


def test_skip_in_other_file_does_not_warn():
    skipped = [{"nodeid": "tests/test_app.py::test_a", "reason": "data/ 없음"}]
    c = check_suggestion(suggest("test_new", "tests/test_api.py"), skipped, FILES, read)
    assert c == {**c, "status": PASS, "warnings": [], "skip_cause_status": None, "unchecked": []}


def test_skip_file_prefix_is_not_a_match():
    # tests/test_app_extra.py의 skip은 tests/test_app.py와 무관
    skipped = [{"nodeid": "tests/test_app_extra.py::test_a", "reason": "x"}]
    assert check_suggestion(suggest("test_new"), skipped, FILES, read)["status"] == PASS


# ---- 상태

def test_clean_suggestion_passes():
    c = check_suggestion(suggest("test_new_behavior"), [], FILES, read)
    assert c["status"] == PASS and c["warnings"] == [] and c["unchecked"] == []


def test_new_file_has_no_collision():
    c = check_suggestion(suggest("test_unverified_evidence_is_marked", "tests/test_new.py"), [], FILES, read)
    assert c["status"] == PASS


def test_no_test_run_is_unknown():
    c = check_suggestion(suggest("test_new_behavior"), None, FILES, read)
    assert c["status"] == UNKNOWN and c["skip_cause_status"] is None and c["unchecked"]


def test_same_input_same_output():
    skipped = [{"nodeid": "tests/test_app.py::test_a", "reason": "data/ 없음"}]
    a = check_suggestion(suggest("test_unverified_evidence_is_marked"), skipped, FILES, read)
    b = check_suggestion(suggest("test_unverified_evidence_is_marked"), list(skipped), set(FILES), read)
    assert a == b and codes(a) == [("S01", "warning"), ("S03", "warning")]


def test_s01_shows_how_many_of_the_file_tests_were_skipped():
    skipped = [{"nodeid": "tests/test_app.py::test_a", "reason": "data/ 없음"}]
    partial = check_suggestion(suggest("test_new"), skipped, FILES, read, {"tests/test_app.py": 16})["warnings"][0]
    assert partial["evidence"]["collected_count"] == 16 and partial["evidence"]["all_skipped"] is False
    assert "16개 중 1개" in partial["message"]
    every = check_suggestion(suggest("test_new"), skipped, FILES, read, {"tests/test_app.py": 1})["warnings"][0]
    assert every["evidence"]["all_skipped"] is True
    unknown = check_suggestion(suggest("test_new"), skipped, FILES, read)["warnings"][0]
    assert unknown["evidence"]["all_skipped"] is None and "중 " not in unknown["message"]
