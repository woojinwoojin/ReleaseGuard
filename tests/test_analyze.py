"""임시 git 저장소로 1~7단계를 끝까지 실행한다 (테스트를 실제로 돌림)."""

import json
from pathlib import Path

from conftest import CALC, PY, TEST_CALC

from releaseguard.__main__ import main
from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.git_ops import collect

RULES = load_rules()


def run(repo, **kw):
    return analyze(repo.path, "HEAD~1", "HEAD", RULES, python=PY, **kw)


def rules(result):
    return [f["rule_id"] for f in result["findings"] if f["decision"] != "NOTE"]


def test_collect_status_and_lines(repo):
    repo.write("a.py", "x = 1\n")
    repo.write("README.md", "# r\n")
    repo.commit("base")
    repo.write("a.py", "x = 2\n")
    repo.git("mv", "README.md", "GUIDE.md")
    repo.commit("change")
    change = collect(repo.path, "HEAD~1", "HEAD")
    by_path = {f.path: f for f in change.files}
    assert by_path["a.py"].status == "M" and (by_path["a.py"].added, by_path["a.py"].deleted) == (1, 1)
    assert by_path["GUIDE.md"].status == "R" and by_path["GUIDE.md"].old_path == "README.md"
    assert change.added_lines["a.py"] == [(1, "x = 2")]


def test_docs_only_skips_tests(pyrepo):
    pyrepo.write("README.md", "# calc\n\nmore\n")
    pyrepo.commit("docs")
    result = run(pyrepo)
    assert result["decision"] == "SAFE"
    assert result["test_run"]["status"] == "skipped"


def test_covered_change_is_safe_and_lists_tests(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return b + a"))
    pyrepo.commit("covered")
    result = run(pyrepo)
    assert result["decision"] == "SAFE"
    [fl] = result["lines"]
    assert fl["line_status"] == {"2": "covered"} or fl["line_status"] == {2: "covered"}
    assert fl["tests"] == ["tests/test_calc.py::test_add"]


def test_untested_branch_is_gap(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    result = run(pyrepo)
    assert result["decision"] == "REVIEW REQUIRED"
    assert rules(result) == ["G01"]
    assert result["findings"][0]["evidence"] == ["src/calc.py:7"]


def test_breaking_change_blocks_with_base_check(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return a - b"))
    pyrepo.commit("break")
    result = run(pyrepo)
    assert result["decision"] == "BLOCK"
    assert result["test_run"]["failures"][0]["nodeid"] == "tests/test_calc.py::test_add"
    assert result["test_run"]["failures"][0]["base_status"] == "passed"
    assert rules(result) == ["B03"]


def test_new_failing_test_blocks(pyrepo):
    pyrepo.write("tests/test_new.py", "def test_new():\n    assert False\n")
    pyrepo.commit("new failing test")
    result = run(pyrepo)
    assert result["test_run"]["failures"][0]["base_status"] == "absent"
    assert rules(result) == ["B03"]


def test_preexisting_failure_is_review(pyrepo):
    pyrepo.write("tests/test_bad.py", "def test_bad():\n    assert False\n")
    pyrepo.commit("already broken")
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return b + a"))
    pyrepo.commit("covered change")
    result = run(pyrepo)
    assert result["decision"] == "REVIEW REQUIRED"
    assert rules(result) == ["T01"]


def test_import_error_blocks(pyrepo):
    pyrepo.write("src/calc.py", "import no_such_module\n" + CALC)
    pyrepo.commit("bad import")
    result = run(pyrepo)
    assert result["test_run"]["status"] == "error"
    assert rules(result) == ["B04"]


def test_repo_without_tests(repo):
    repo.write("a.py", "x = 1\n")
    repo.commit("base")
    repo.write("settings.example", "KEY=\n")
    repo.commit("config only")
    result = run(repo)
    assert result["test_run"]["status"] == "no_tests"
    assert result["decision"] == "SAFE"  # 바뀐 소스가 없으면 테스트가 없어도 검증할 것이 없다

    repo.write("a.py", "x = 2\n")
    repo.commit("source")
    result = run(repo)
    assert rules(result) == ["G01"]  # 테스트가 없으면 바뀐 소스 줄 전체가 공백
    assert result["lines"][0]["measured"] is False


def test_missing_python_falls_back_to_estimate(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    result = analyze(pyrepo.path, "HEAD~1", "HEAD", RULES, python=Path("no/python.exe"))
    assert result["decision"] == "REVIEW REQUIRED" and rules(result) == ["E01"]
    assert result["estimated_tests"][0]["source"] == "src/calc.py"
    assert {t["path"] for t in result["estimated_tests"][0]["tests"]} == {"tests/test_calc.py"}


def test_explain_runs_only_with_gaps_and_failure_keeps_result(pyrepo):
    calls = []

    def explain(view, lines):
        calls.append([fl.gaps for fl in lines])
        raise RuntimeError("API down")

    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return b + a"))
    pyrepo.commit("covered")
    assert run(pyrepo, explain=explain)["agent_error"] is None and calls == []

    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    result = run(pyrepo, explain=explain)
    assert calls == [[[(7, 7)]]]
    assert result["decision"] == "REVIEW REQUIRED" and result["agent_error"] == "RuntimeError: API down"


def test_cli_writes_json_and_markdown(pyrepo, tmp_path):
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    head = pyrepo.commit("gap")
    out = tmp_path / "out"
    args = ["analyze", "--repo", str(pyrepo.path), "--base", "HEAD~1", "--python", str(PY), "--out", str(out), "--no-agent"]
    assert main(args) == 0
    [json_file] = out.glob(f"*_{head[:7]}.json")
    result = json.loads(json_file.read_text(encoding="utf-8"))
    assert result["decision"] == "REVIEW REQUIRED"
    md = json_file.with_suffix(".md").read_text(encoding="utf-8")
    assert md.startswith("# ReleaseGuard 보고서 — REVIEW REQUIRED")
    assert "**1** (7)" in md


def test_unchanged_test_file_content(pyrepo):
    # 테스트 파일만 바뀌면 소스 공백 검사는 없고 테스트만 돈다
    pyrepo.write("tests/test_calc.py", TEST_CALC + "\n\ndef test_neg():\n    from src.calc import sign\n    assert sign(-1) == -1\n")
    pyrepo.commit("more tests")
    result = run(pyrepo)
    assert result["decision"] == "SAFE" and result["lines"] == []
    assert result["test_run"]["counts"]["passed"] == 3
