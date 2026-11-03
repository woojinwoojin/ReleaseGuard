from pathlib import Path

from conftest import PY

from releaseguard.runner import check_python, parse_junit, run_tests, snapshot

JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite>
<testcase classname="tests.test_x" name="test_a" file="tests\\test_x.py" line="1" time="0.1" />
<testcase classname="tests.test_x" name="test_p[2-3]" file="tests\\test_x.py" line="5" time="0.1"><failure message="assert 5 == 6">x</failure></testcase>
<testcase classname="tests.test_x.TestBox" name="test_m" file="tests\\test_x.py" line="9" time="0.1"><skipped message="later" /></testcase>
</testsuite></testsuites>"""


def test_parse_junit_builds_node_ids_and_context_map(tmp_path):
    path = tmp_path / "j.xml"
    path.write_text(JUNIT, encoding="utf-8")
    cases, ctx = parse_junit(path)
    assert [(c.nodeid, c.outcome) for c in cases] == [
        ("tests/test_x.py::test_a", "passed"),
        ("tests/test_x.py::test_p[2-3]", "failed"),
        ("tests/test_x.py::TestBox::test_m", "skipped"),
    ]
    assert cases[1].message == "assert 5 == 6"
    # coverage context(모듈.함수)는 parametrize 값 없이 함수 단위로 묶인다
    assert ctx == {
        "tests.test_x.test_a": "tests/test_x.py::test_a",
        "tests.test_x.test_p": "tests/test_x.py::test_p",
        "tests.test_x.TestBox.test_m": "tests/test_x.py::TestBox::test_m",
    }


def test_parse_junit_missing_file(tmp_path):
    assert parse_junit(tmp_path / "none.xml") == ([], {})


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
    # 대상 저장소 작업 폴더에는 아무것도 생기지 않는다
    assert pyrepo.git("status", "--porcelain") == ""


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
