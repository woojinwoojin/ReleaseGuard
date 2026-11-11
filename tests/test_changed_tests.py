"""Stage 1.7: 바뀐 테스트가 실제로 실행됐는지 (T03·N07), coverage 도구 확인, 원본 node id. 설계: docs/design_stage1_7.md"""

import json

import pytest
from conftest import CALC, PY

from releaseguard import runner
from releaseguard.analyze import analyze
from releaseguard.changed_tests import (
    CHANGED_TESTS_ALL_SKIPPED, HELD, MODULE_SKIPPED, NO_TEST_RESULTS, NOT_EVALUATED, PERFORMED, TEST_SUITE_REMOVED,
    check_test_changes, find_test_functions, is_collection_target, is_module_skip, read_collection_config,
)
from releaseguard.classify import load_rules
from releaseguard.decide import NOT_VERIFIED_RULES, decide
from releaseguard.report import to_markdown

RULES = load_rules()


def run(repo):
    return analyze(repo.path, "HEAD~1", "HEAD", RULES, python=PY)


def rules(result):
    return [f["rule_id"] for f in result["findings"] if f["decision"] != "NOTE"]


def notes(result):
    return [f["rule_id"] for f in result["findings"] if f["decision"] == "NOTE"]


def t03(result):
    return sorted({r["code"] for r in result["test_change_checks"]["reasons"]})


# ---------------------------------------------------------------- 순수 함수

def test_testpaths_is_supported_and_limits_targets():
    cfg = read_collection_config({"pytest.ini"}, lambda p: "[pytest]\ntestpaths = tests\npythonpath = .\n")
    assert (cfg.testpaths, cfg.unsupported) == (["tests"], [])
    assert is_collection_target("tests/test_a.py", "test", cfg)
    assert is_collection_target("tests/sub/a_test.py", "test", cfg)
    assert not is_collection_target("other/test_a.py", "test", cfg)  # testpaths 밖
    assert not is_collection_target("tests/fakes.py", "test", cfg)  # 수집 패턴 밖
    assert not is_collection_target("tests/conftest.py", "test", cfg)


@pytest.mark.parametrize("name, text, found", [
    ("pytest.ini", "[pytest]\npython_files = check_*.py\n", "pytest.ini: python_files"),
    ("pytest.ini", "[pytest]\naddopts = -q -k calc\n", "pytest.ini: addopts -k"),
    ("pytest.ini", "[pytest]\naddopts = --ignore=tests/slow\n", "pytest.ini: addopts --ignore=tests/slow"),
    ("pytest.ini", "[pytest]\ntestpaths = tests/*\n", "pytest.ini: testpaths (glob)"),
    ("pyproject.toml", '[tool.pytest.ini_options]\npython_functions = ["check_*"]\n', "pyproject.toml: python_functions"),
    ("setup.cfg", "[tool:pytest]\nnorecursedirs = tests\n", "setup.cfg: norecursedirs"),
])
def test_unsupported_collection_settings(name, text, found):
    cfg = read_collection_config({name}, lambda p: text)
    assert found in cfg.unsupported


def test_addopts_without_collection_options_is_fine():
    cfg = read_collection_config({"pytest.ini"}, lambda p: "[pytest]\naddopts = -q -ra --tb=short\n")
    assert cfg.unsupported == []


def test_conftest_collection_hooks_are_unsupported():
    files = {"tests/conftest.py": "collect_ignore = ['x.py']\n", "conftest.py": "import pytest\n"}
    cfg = read_collection_config(set(files), files.__getitem__)
    assert cfg.unsupported == ["tests/conftest.py: collect_ignore"]


def test_first_config_file_wins_like_pytest():
    files = {"pytest.ini": "[pytest]\ntestpaths = tests\n", "setup.cfg": "[tool:pytest]\npython_files = x.py\n"}
    cfg = read_collection_config(set(files), files.__getitem__)
    assert (cfg.testpaths, cfg.unsupported) == (["tests"], [])


def test_find_test_functions_follows_pytest_defaults():
    src = (
        "import pytest\n"
        "def helper():\n    pass\n"
        "@pytest.mark.parametrize('x', [1])\n"
        "def test_a(x):\n"
        "    def test_inner():\n        pass\n"
        "class TestK:\n"
        "    def test_b(self):\n        pass\n"
        "    class TestNested:\n"
        "        def test_c(self):\n            pass\n"
        "class Helper:\n"
        "    def test_not_collected(self):\n        pass\n"
    )
    found = [(f.key, f.start, f.end) for f in find_test_functions(src)]
    assert found == [("test_a", 4, 7), ("TestK.test_b", 9, 10), ("TestK.TestNested.test_c", 12, 13)]  # test_a는 데코레이터(4줄)부터
    assert find_test_functions("def test_(:\n") == []  # SyntaxError


def test_module_skip_record():
    assert is_module_skip("tests/test_x.py::tests.test_x", "skipped")
    assert not is_module_skip("tests/test_x.py::test_a", "skipped")
    assert not is_module_skip("tests/test_x.py::tests.test_x", "passed")


TEST_FILE = "import pytest\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x):\n    pass\n\ndef test_q():\n    pass\n"


def checks(results, status="passed", file_status="A", added=None, files_extra=(), config_text="[pytest]\n"):
    files = [{"path": "tests/test_n.py", "status": file_status, "category": "test"}, *files_extra]
    contents = {"tests/test_n.py": TEST_FILE, "pytest.ini": config_text}
    added = added or {"tests/test_n.py": [(n, "") for n in range(1, 9)]}
    return check_test_changes(files, added, status, results, True, set(contents), contents.__getitem__)


def res(nodeid, outcome="passed", message=""):
    return {"nodeid": nodeid, "outcome": outcome, "message": message}


def test_parametrize_all_values_must_be_skipped():
    partial = checks([res("tests/test_n.py::test_p[1]", "skipped"), res("tests/test_n.py::test_p[2]"), res("tests/test_n.py::test_q", "skipped")])
    assert partial["reasons"] == []
    every = checks([res("tests/test_n.py::test_p[1]", "skipped", "why"), res("tests/test_n.py::test_p[2]", "skipped", "why"),
                    res("tests/test_n.py::test_q", "skipped", "why")])
    (r,) = every["reasons"]
    assert (r["code"], r["results"], r["changed_tests"], r["base_status_checked"]) == (CHANGED_TESTS_ALL_SKIPPED, 3, ["test_p", "test_q"], False)


def test_only_changed_functions_count():
    # test_q(7~8줄)만 바뀌었고 그것은 실행됨 → test_p가 전부 skip이어도 T03 아님
    added = {"tests/test_n.py": [(8, "    pass")]}
    out = checks([res("tests/test_n.py::test_p[1]", "skipped"), res("tests/test_n.py::test_p[2]", "skipped"), res("tests/test_n.py::test_q")],
                 file_status="M", added=added)
    assert out["reasons"] == []


def test_changed_function_without_results_is_recorded_not_flagged():
    added = {"tests/test_n.py": [(8, "    pass")]}  # test_q만 바뀜, 그런데 test_q 결과가 없음
    out = checks([res("tests/test_n.py::test_p[1]"), res("tests/test_n.py::test_p[2]")], file_status="M", added=added)
    assert out["reasons"] == []
    assert out["unmatched_changed_tests"] == [{"path": "tests/test_n.py", "tests": ["test_q"]}]


def test_no_results_and_module_skip():
    assert [r["code"] for r in checks([])["reasons"]] == [NO_TEST_RESULTS]
    out = checks([res("tests/test_n.py::tests.test_n", "skipped", "collection skipped")])
    assert [(r["code"], r["message"]) for r in out["reasons"]] == [(MODULE_SKIPPED, "collection skipped")]


def test_not_evaluated_without_run_evidence():
    for status in ("error", "timeout", "not_run", "skipped"):
        out = checks([], status=status)
        assert (out["status"], out["reasons"]) == (NOT_EVALUATED, [])
    files = [{"path": "tests/test_n.py", "status": "A", "category": "test"}]
    out = check_test_changes(files, {"tests/test_n.py": [(1, "")]}, "passed", [], False, {"tests/test_n.py"}, lambda p: TEST_FILE)
    assert out["status"] == NOT_EVALUATED  # 전체 실행이 아니면 "결과 없음"을 판단하지 않는다


def test_unsupported_config_holds_checks_but_not_suite_removed():
    deleted = [{"path": "tests/test_old.py", "status": "D", "category": "test"}]
    out = checks([], status="no_tests", files_extra=deleted, config_text="[pytest]\naddopts = -k calc\n")
    assert out["status"] == HELD
    assert [r["code"] for r in out["reasons"]] == [TEST_SUITE_REMOVED]  # 보류된 NO_TEST_RESULTS는 나오지 않음
    assert out["held_checks"] == [NO_TEST_RESULTS, CHANGED_TESTS_ALL_SKIPPED, MODULE_SKIPPED]


def test_decide_t03_is_review_with_complete_scope_and_n07_is_note():
    files = [{"path": "tests/test_n.py", "status": "A", "category": "test"}]
    run_ = {"status": "passed", "reason": None, "coverage": True, "failures": [], "snapshot_warnings": []}
    decision, findings, scope = decide(files, run_, [], {}, RULES.secrets, checks([]))
    assert (decision, [f.rule_id for f in findings], scope.status) == ("REVIEW REQUIRED", ["T03"], "COMPLETE")
    assert findings[0].evidence[0].startswith("NO_TEST_RESULTS: tests/test_n.py")
    assert "T03" in NOT_VERIFIED_RULES
    held = checks([], config_text="[pytest]\npython_files = check_*.py\n")
    decision, findings, _ = decide(files, run_, [], {}, RULES.secrets, held)
    assert (decision, [(f.rule_id, f.decision) for f in findings]) == ("SAFE", [("N07", "NOTE")])
    assert decide(files, run_, [], {}, RULES.secrets)[0] == "SAFE"  # test_checks 없으면 v3.1과 같음


# ---------------------------------------------------------------- 실제 실행: T03이 나와야 하는 사례

def test_t03_no_test_results_for_uncollectable_class(pyrepo):
    pyrepo.write("tests/test_init_cls.py", "from src.calc import add\n\n\nclass TestAdd:\n    def __init__(self):\n        self.x = 1\n\n"
                 "    def test_add(self):\n        assert add(1, 1) == 2\n")
    pyrepo.commit("test class with __init__")
    result = run(pyrepo)
    assert (result["decision"], rules(result), t03(result)) == ("REVIEW REQUIRED", ["T03"], [NO_TEST_RESULTS])
    assert result["scope"]["status"] == "COMPLETE"


def test_t03_all_new_tests_skipped(pyrepo):
    pyrepo.write("tests/test_new.py", "import pytest\n\n\n@pytest.mark.skip(reason='data/ 없음')\ndef test_a():\n    pass\n\n\n"
                 "@pytest.mark.skip(reason='data/ 없음')\ndef test_b():\n    pass\n")
    pyrepo.commit("skipped tests")
    result = run(pyrepo)
    assert (rules(result), t03(result)) == (["T03"], [CHANGED_TESTS_ALL_SKIPPED])
    assert "data/ 없음" in result["findings"][0]["evidence"][0]


def test_t03_module_level_skip(pyrepo):
    pyrepo.write("tests/test_mod.py", "import pytest\n\nnp = pytest.importorskip('no_such_module_xyz')\n\n\ndef test_a():\n    pass\n")
    pyrepo.commit("module skip")
    result = run(pyrepo)
    assert (rules(result), t03(result)) == (["T03"], [MODULE_SKIPPED])


def test_t03_test_suite_removed(pyrepo):
    pyrepo.git("rm", "-q", "tests/test_calc.py")
    pyrepo.commit("remove the only test file")
    result = run(pyrepo)
    assert result["test_run"]["status"] == "no_tests"
    assert (result["decision"], rules(result), t03(result)) == ("REVIEW REQUIRED", ["T03"], [TEST_SUITE_REMOVED])
    md = to_markdown(result)
    assert "바뀐 테스트 실행 확인 (T03)" in md and "COMPLETE와 T03이 함께 나올 수 있음" in md


def test_t03_already_skipped_file_test_modified(pyrepo):
    # X9: pytestmark로 이미 전부 skip이던 파일의 테스트를 고침 → 이전 상태를 확인하지 않고 T03
    body = "import pytest\n\npytestmark = pytest.mark.skipif(True, reason='data 없음')\n\n\ndef test_a():\n    assert {}\n"
    pyrepo.write("tests/test_ui.py", body.format("1"))
    pyrepo.commit("skipped file")
    pyrepo.write("tests/test_ui.py", body.format("2"))
    pyrepo.commit("modify skipped test")
    result = run(pyrepo)
    assert t03(result) == [CHANGED_TESTS_ALL_SKIPPED]
    assert "이전에도 skip이었는지 확인 안 함" in result["findings"][0]["evidence"][0]


# ---------------------------------------------------------------- 실제 실행: 반례 (T03이 나오면 안 됨)

def test_x1_helper_change_in_running_test_file(pyrepo):
    text = (pyrepo.path / "tests/test_calc.py").read_text(encoding="utf-8")
    pyrepo.write("tests/test_calc.py", text + "\n\ndef _two():\n    return 2\n")
    pyrepo.commit("helper only")
    result = run(pyrepo)
    assert (result["decision"], t03(result)) == ("SAFE", [])


@pytest.mark.parametrize("path, content", [
    ("tests/fakes.py", "def fake():\n    return 1\n"),  # X2
    ("tests/conftest.py", "import pytest\n\n\n@pytest.fixture\ndef one():\n    return 1\n"),  # X3
    ("tests/test_helpers.py", "def make_input():\n    return 1\n"),  # X11: 이름은 패턴에 맞지만 테스트 함수가 없음
])
def test_non_test_files_do_not_trigger(pyrepo, path, content):
    pyrepo.write(path, content)
    pyrepo.commit("helper file")
    result = run(pyrepo)
    assert (result["decision"], t03(result)) == ("SAFE", [])


@pytest.mark.parametrize("content", [
    # X4: 새 테스트 2개 중 1개만 skip
    "import pytest\n\n\ndef test_a():\n    pass\n\n\n@pytest.mark.skip(reason='later')\ndef test_b():\n    pass\n",
    # X4p: parametrize 값 하나만 skip
    "import pytest\n\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x):\n    if x == 2:\n        pytest.skip('two')\n",
])
def test_partial_skip_does_not_trigger(pyrepo, content):
    pyrepo.write("tests/test_new.py", content)
    pyrepo.commit("partial skip")
    result = run(pyrepo)
    assert (result["decision"], t03(result)) == ("SAFE", [])
    assert result["test_run"]["skipped"]  # skip 표에는 나온다


def test_x7_rename_only(pyrepo):
    pyrepo.git("mv", "tests/test_calc.py", "tests/test_calc2.py")
    pyrepo.commit("rename test file")
    result = run(pyrepo)
    assert [f["status"] for f in result["changed_files"]] == ["R"]
    assert (result["decision"], t03(result)) == ("SAFE", [])


def test_x8_delete_one_test_file_others_run(pyrepo):
    pyrepo.write("tests/test_extra.py", "def test_x():\n    pass\n")
    pyrepo.commit("extra")
    pyrepo.git("rm", "-q", "tests/test_extra.py")
    pyrepo.commit("remove extra")
    result = run(pyrepo)
    assert (result["decision"], t03(result)) == ("SAFE", [])


def test_x10_collection_error_is_b04_only(pyrepo):
    pyrepo.write("tests/test_bad.py", "import no_such_module_xyz\n\n\ndef test_a():\n    pass\n")
    pyrepo.commit("bad test import")
    result = run(pyrepo)
    assert rules(result) == ["B04"]
    assert result["test_change_checks"]["status"] == NOT_EVALUATED


def test_x12_unsupported_config_holds_and_reports(pyrepo):
    pyrepo.write("pytest.ini", "[pytest]\npythonpath = .\naddopts = -k calc\n")
    pyrepo.commit("deselect by default")
    pyrepo.write("tests/test_new.py", "def test_other():\n    pass\n")  # -k calc로 선택되지 않아 결과가 없음
    pyrepo.commit("new test")
    result = run(pyrepo)
    assert (result["decision"], t03(result), notes(result)) == ("SAFE", [], ["N07"])
    assert result["test_change_checks"]["status"] == HELD
    assert "하지 않은 검사" in to_markdown(result)


# ---------------------------------------------------------------- 소스 삭제 (N06, 판정 그대로)

def test_d1_unreferenced_module_deleted(pyrepo):
    pyrepo.write("src/legacy.py", "def old():\n    return 1\n")
    pyrepo.commit("legacy")
    pyrepo.git("rm", "-q", "src/legacy.py")
    pyrepo.commit("delete legacy")
    result = run(pyrepo)
    assert (result["decision"], notes(result)) == ("SAFE", ["N06"])
    assert "삭제 영향 미검증" in result["findings"][0]["message"]


def test_d2_imported_module_deleted_blocks(pyrepo):
    pyrepo.write("src/helper.py", "def one():\n    return 1\n")
    pyrepo.write("src/uses.py", "from src.helper import one\n")
    pyrepo.write("tests/test_uses.py", "import src.uses\n\n\ndef test_u():\n    assert src.uses.one() == 1\n")
    pyrepo.commit("helper")
    pyrepo.git("rm", "-q", "src/helper.py")
    pyrepo.commit("delete helper")
    assert rules(run(pyrepo)) == ["B04"]


def test_d3_lazy_reference_not_executed_is_known_limit(pyrepo):
    # 알려진 한계: 테스트가 지나가지 않는 경로의 참조는 보지 않는다 → SAFE + N06 (메시지에 미검증 명시)
    pyrepo.write("src/helper.py", "def one():\n    return 1\n")
    pyrepo.write("src/lazy.py", "def later():\n    from src.helper import one\n    return one()\n")
    pyrepo.write("tests/test_lazy.py", "import src.lazy\n\n\ndef test_imports():\n    assert src.lazy\n")
    pyrepo.commit("lazy")
    pyrepo.git("rm", "-q", "src/helper.py")
    pyrepo.commit("delete helper")
    result = run(pyrepo)
    assert (result["decision"], notes(result)) == ("SAFE", ["N06"])


# ---------------------------------------------------------------- coverage 도구 확인

GOOD = {"coverage": {"version": runner.COVERAGE_VERSION, "in_tools": True}, "pytest_cov": {"version": runner.PYTEST_COV_VERSION, "in_tools": True}}


@pytest.mark.parametrize("first, second, ok, reinstalled", [
    (GOOD, None, True, False),
    ({**GOOD, "coverage": {"version": "7.0.0", "in_tools": True}}, GOOD, True, True),  # 버전 불일치 → 재설치로 해결
    ({**GOOD, "pytest_cov": {"version": runner.PYTEST_COV_VERSION, "in_tools": False}}, None, False, True),  # 호스트 패키지 → 재설치 후에도
    ({"error": "ModuleNotFoundError"}, None, False, True),  # 읽기 실패
])
def test_check_coverage_tools(monkeypatch, tmp_path, first, second, ok, reinstalled):
    probes = iter([first, second or first])
    monkeypatch.setattr(runner, "_probe_tools", lambda python, tools: next(probes))
    calls = []
    out = runner.check_coverage_tools(PY, tmp_path, reinstall=lambda: calls.append(1))
    assert (out["ok"], out["reinstalled"], len(calls)) == (ok, reinstalled, int(reinstalled))


def test_probe_reads_real_tools():
    out = runner.check_coverage_tools(PY)
    assert out["ok"] and not out["reinstalled"]
    assert out["loaded"]["coverage"] == {"version": runner.COVERAGE_VERSION, "in_tools": True}


def test_failed_tool_check_means_not_run(pyrepo, monkeypatch):
    import releaseguard.analyze as an
    monkeypatch.setattr(an, "check_coverage_tools", lambda py: {"ok": False, "loaded": {"error": "x"}, "reinstalled": True, "required": {}})
    pyrepo.write("src/calc.py", CALC + "\n\ndef three():\n    return 3\n")
    pyrepo.commit("change")
    result = run(pyrepo)
    assert (result["test_run"]["status"], rules(result)) == ("not_run", ["E01"])


# ---------------------------------------------------------------- 원본 node id

def test_parse_coverage_keeps_raw_parametrized_ids(tmp_path):
    data = {"files": {"src/calc.py": {
        "executed_lines": [1, 2], "missing_lines": [],
        "contexts": {"2": ["tests/t.py::test_add[1-2]|run", "tests/t.py::test_add[3-4]|run", "tests/t.py::test_x|setup", ""]},
    }}}
    path = tmp_path / "cov.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    fc = runner.parse_coverage(path)["src/calc.py"]
    assert fc.tests[2] == ["tests/t.py::test_add", "tests/t.py::test_x"]  # 함수 단위 요약은 그대로
    assert fc.nodeids == {
        "tests/t.py::test_add": {"tests/t.py::test_add[1-2]", "tests/t.py::test_add[3-4]"},
        "tests/t.py::test_x": {"tests/t.py::test_x"},
    }


def test_nodeid_map_in_result(pyrepo):
    pyrepo.write("tests/test_param.py", "import pytest\nfrom src.calc import add\n\n\n@pytest.mark.parametrize('a, b', [(1, 2), (3, 4)])\n"
                 "def test_add_many(a, b):\n    assert add(a, b) == a + b\n")
    pyrepo.commit("parametrized")
    result = run(pyrepo)
    assert result["test_run"]["nodeid_map"]["tests/test_param.py::test_add_many"] == [
        "tests/test_param.py::test_add_many[1-2]", "tests/test_param.py::test_add_many[3-4]",
    ]
    assert result["test_run"]["record"]["coverage_runtime"]["ok"] is True
