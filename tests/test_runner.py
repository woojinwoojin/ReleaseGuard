from pathlib import Path

from conftest import PY

from releaseguard.runner import check_python, parse_context, parse_junit, run_tests, snapshot

JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite>
<testcase classname="tests.test_x" name="test_a" file="tests\\test_x.py" line="1" time="0.1" />
<testcase classname="tests.test_x" name="test_p[2-3]" file="tests\\test_x.py" line="5" time="0.1"><failure message="assert 5 == 6">x</failure></testcase>
<testcase classname="tests.test_x.TestBox" name="test_m" file="tests\\test_x.py" line="9" time="0.1"><skipped message="later" /></testcase>
</testsuite></testsuites>"""


def test_parse_junit_builds_node_ids(tmp_path):
    path = tmp_path / "j.xml"
    path.write_text(JUNIT, encoding="utf-8")
    cases = parse_junit(path)
    assert [(c.nodeid, c.outcome) for c in cases] == [
        ("tests/test_x.py::test_a", "passed"),
        ("tests/test_x.py::test_p[2-3]", "failed"),
        ("tests/test_x.py::TestBox::test_m", "skipped"),
    ]
    assert cases[1].message == "assert 5 == 6"


def test_parse_junit_missing_file(tmp_path):
    assert parse_junit(tmp_path / "none.xml") == []


def test_parse_context_splits_phase_and_drops_parametrize_values():
    assert parse_context("tests/test_x.py::test_p[a|b]|run") == ("tests/test_x.py::test_p", "run")
    assert parse_context("tests/test_x.py::TestBox::test_m|setup") == ("tests/test_x.py::TestBox::test_m", "setup")
    assert parse_context("tests/test_x.py::test_a") == ("tests/test_x.py::test_a", "run")


def test_snapshot_has_only_committed_files(pyrepo, tmp_path):
    pyrepo.write("local_only.txt", "x")
    dest = tmp_path / "snap"
    snapshot(pyrepo.path, "HEAD", dest)
    assert (dest / "src" / "calc.py").exists()
    assert not (dest / "local_only.txt").exists()
    assert not (dest / ".git").exists()


def test_run_tests_records_which_test_ran_each_line(pyrepo):
    run = run_tests(pyrepo.path, "HEAD", PY)
    assert run.status == "passed"
    assert run.counts() == {"passed": 2, "failed": 0, "error": 0, "skipped": 0}
    cov = run.coverage["src/calc.py"]
    assert cov.tests[2] == ["tests/test_calc.py::test_add"]
    assert cov.tests[6] == ["tests/test_calc.py::test_sign_positive"]
    assert 7 in cov.missing  # 음수 분기
    assert 1 in cov.executed and 1 not in cov.tests  # def 줄은 import 시점에만 실행
    # 분기: if x < 0 (6행)에서 양수 쪽(→8)만 실행, 음수 쪽(→7)은 실행 안 됨
    assert cov.executed_branches[6] == [8] and cov.missing_branches[6] == [7]
    # 대상 저장소 작업 폴더에는 아무것도 생기지 않는다
    assert pyrepo.git("status", "--porcelain") == ""


def test_run_tests_attributes_fixture_lines_to_the_test(pyrepo):
    """fixture(setup)에서만 실행된 줄도 그 테스트가 실행한 줄로 남고, 본문(run) 실행과 구분된다 (한계 11)."""
    pyrepo.write("src/calc.py", CALC_WITH_FACTORY)
    pyrepo.write("tests/test_calc.py", TEST_WITH_FIXTURE)
    pyrepo.commit("fixture")
    cov = run_tests(pyrepo.path, "HEAD", PY).coverage["src/calc.py"]
    assert cov.tests[2] == ["tests/test_calc.py::test_uses_fixture"]  # make() 본문: fixture에서 실행
    assert 2 not in cov.run_lines
    assert cov.tests[6] == ["tests/test_calc.py::test_uses_fixture"] and 6 in cov.run_lines  # add() 본문: 테스트에서 실행


CALC_WITH_FACTORY = """def make():
    return 2


def add(a, b):
    return a + b
"""

TEST_WITH_FIXTURE = """import pytest

from src.calc import add, make


@pytest.fixture
def two():
    return make()


def test_uses_fixture(two):
    assert add(two, 1) == 3
"""


def test_run_tests_only_given_node_ids_without_coverage(pyrepo):
    run = run_tests(pyrepo.path, "HEAD", PY, with_coverage=False, nodeids=["tests/test_calc.py::test_add"])
    assert [t.nodeid for t in run.tests] == ["tests/test_calc.py::test_add"]
    assert run.coverage is None


def test_run_tests_timeout(pyrepo):
    pyrepo.write("tests/test_slow.py", "import time\n\ndef test_slow():\n    time.sleep(30)\n")
    pyrepo.commit("slow")
    run = run_tests(pyrepo.path, "HEAD", PY, timeout=3)
    assert run.status == "timeout" and run.attempts == 2  # 한 번 다시 시도한다


def test_check_python():
    assert check_python(PY) is None
    assert "Python이 없음" in check_python(Path("no/such/python.exe"))
