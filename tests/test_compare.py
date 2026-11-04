"""head 실패의 비교 상태(FLAKY·INCOMPARABLE·UNKNOWN), 스냅샷 예외, 실행 기록 — 임시 저장소에서 실제로 실행."""

from conftest import CALC, PY

from releaseguard.analyze import analyze
from releaseguard.classify import load_rules

RULES = load_rules()


def run(repo):
    return analyze(repo.path, "HEAD~1", "HEAD", RULES, python=PY)


def rules(result):
    return [f["rule_id"] for f in result["findings"] if f["decision"] != "NOTE"]


def test_flaky_failure_is_review_not_pass(pyrepo, tmp_path):
    # 처음 실행에서만 실패하는 테스트 (표시 파일은 스냅샷 밖에 둔다)
    marker = (tmp_path / "flaky_marker").as_posix()
    pyrepo.write(
        "tests/test_flaky.py",
        "from pathlib import Path\n\n\ndef test_flaky():\n"
        f"    p = Path({marker!r})\n"
        "    if not p.exists():\n"
        "        p.write_text('x')\n"
        "        assert False\n",
    )
    pyrepo.commit("flaky")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert f["comparison"] == "FLAKY"
    assert (result["decision"], rules(result)) == ("REVIEW REQUIRED", ["T02"])


def test_preexisting_failure_with_changed_test_file_is_incomparable(pyrepo):
    pyrepo.write("tests/test_bad.py", "def test_bad():\n    assert False\n")
    pyrepo.commit("already broken")
    pyrepo.write("tests/test_bad.py", "def test_bad():\n    assert 1 == 2\n")
    pyrepo.commit("test changed, still failing")
    result = run(pyrepo)
    assert result["test_run"]["failures"][0]["comparison"] == "INCOMPARABLE"
    assert (result["decision"], rules(result)) == ("BLOCK", ["B03"])


def test_base_run_without_result_is_unknown(pyrepo):
    # base에서는 이 테스트 파일이 문법 오류(수집 오류) → base 결과 없음
    pyrepo.write("tests/test_bad.py", "def test_bad(:\n")
    pyrepo.commit("broken test file in base")
    pyrepo.write("tests/test_bad.py", "def test_bad():\n    assert False\n")
    pyrepo.commit("now collects but fails")
    result = run(pyrepo)
    [f] = result["test_run"]["failures"]
    assert (f["comparison"], f["base_status"]) == ("UNKNOWN", "unknown")
    assert rules(result) == ["B03"]


def test_snapshot_warning_from_gitattributes(pyrepo):
    pyrepo.write(".gitattributes", "tests/fixtures/** export-ignore\n")
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return b + a"))
    pyrepo.commit("export-ignore")
    result = run(pyrepo)
    assert "E03" in rules(result)
    assert result["test_run"]["snapshot_warnings"] == [".gitattributes: export-ignore 대상은 스냅샷에서 빠짐"]


def test_record_keeps_command_and_versions(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return b + a"))
    head = pyrepo.commit("covered")
    r = run(pyrepo)["test_run"]["record"]
    assert r["head_sha"] == head and r["coverage_version"] == "7.17.0" and r["python_version"]
    assert "pytest" in r["command"] and not any("rg_" in c for c in r["command"])  # 임시 폴더 경로는 <tmp>로
