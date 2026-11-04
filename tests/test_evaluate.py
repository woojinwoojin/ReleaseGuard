from conftest import CALC, PY

from releaseguard.classify import load_rules
from releaseguard.evaluate import evaluate, run_seeds, run_szz, seeds_markdown, szz_markdown, to_markdown

RULES = load_rules()


def cases_file(tmp_path, body):
    path = tmp_path / "cases.yaml"
    path.write_text(f"repo: target\npython: {PY.as_posix()}\n{body}", encoding="utf-8")
    return path


def test_evaluate_commits_and_determinism(pyrepo, tmp_path):
    pyrepo.write("README.md", "# x\n")
    docs = pyrepo.commit("docs")
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.write("tests/test_calc.py", (pyrepo.path / "tests/test_calc.py").read_text() + "\n")
    gap = pyrepo.commit("gap + test touch")
    cases = cases_file(
        tmp_path,
        f"cases:\n  - sha: {docs[:7]}\n    need: no\n    expected_scope: COMPLETE\n"
        f"  - sha: {gap[:7]}\n    need: no\n    expected_scope: PARTIAL\n",
    )

    ev = evaluate(cases, RULES, repeat=2)
    m = ev["metrics"]
    assert m["commits"] == 2  # 첫 커밋은 제외
    assert m["decisions"] == {"REVIEW REQUIRED": 1, "SAFE": 1}
    lb = m["labels"]
    assert lb["need_no"] == 2 and lb["under_warning"]["count"] == 0
    # 반복 2회 × 공백 커밋 1개 → 과잉 경고 2회, 원인은 G01
    assert (lb["over_warning"]["count"], lb["over_warning"]["of"], lb["over_warning"]["by_cause"]) == (2, 4, {"G01": 2})
    assert lb["scope_agreement"]["agree"] == 1 and lb["scope_agreement"]["mismatch"] == [f"{gap[:7]} (PARTIAL → COMPLETE)"]
    assert m["determinism"] == {"commits": 2, "identical": 2}
    assert m["gaps"] == {"commits_with_gap": 1, "gap_lines": 1, "executable_lines": 1}
    # 공백 줄(7)은 아무 테스트도 실행하지 않으므로 실행한 테스트가 없다 → 정답(바뀐 테스트)과 겹치지 않음
    assert m["changed_test_retrieval"] == {"commits": 1, "precision": None, "recall": 0.0}
    assert "| `" + gap[:7] + "` |" in to_markdown(ev)


def test_seeds_run_in_a_clone(pyrepo, tmp_path):
    seeds = tmp_path / "seeds.yaml"
    seeds.write_text(
        f"repo: target\npython: {PY.as_posix()}\nseeds:\n"
        "  - id: S1\n    description: 테스트 없는 분기 수정\n    expected: REVIEW REQUIRED\n    expect_rules: [G01]\n"
        "    edits:\n      - path: src/calc.py\n        find: 'return -1'\n        replace: 'return -2'\n"
        "  - id: S2\n    description: 덧셈을 깨뜨림\n    expected: BLOCK\n    expect_rules: [B03]\n"
        "    edits:\n      - path: src/calc.py\n        find: 'return a + b'\n        replace: 'return a - b'\n"
        "  - id: S3\n    description: 테스트 파일 삭제\n    expected: REVIEW REQUIRED\n    expect_rules: [G01]\n"
        "    edits:\n      - path: tests/test_calc.py\n        delete: true\n      - path: src/calc.py\n        find: 'return a + b'\n        replace: 'return b + a'\n",
        encoding="utf-8",
    )
    ev = run_seeds(seeds, RULES)
    assert [(r["id"], r["decision"], r["pass"]) for r in ev["rows"]] == [
        ("S1", "REVIEW REQUIRED", True),
        ("S2", "BLOCK", True),
        ("S3", "REVIEW REQUIRED", True),
    ]
    assert pyrepo.git("log", "--oneline").count("\n") == 1  # 원래 저장소에는 커밋이 생기지 않는다
    assert "(3/3 통과)" in seeds_markdown(ev)


def test_szz_traces_defect_lines_to_their_status(pyrepo, tmp_path):
    # 결함을 들여온 커밋: 테스트된 줄 하나(add), 테스트 안 된 줄 하나(sign 음수 분기)
    pyrepo.write("src/calc.py", CALC.replace("return a + b", "return a + b + 0").replace("return -1", "return -1 * 1"))
    intro = pyrepo.commit("introduce")
    pyrepo.write("src/calc.py", CALC)
    fix = pyrepo.commit("fix")
    cases = cases_file(tmp_path, f"fix_commits: [{fix[:7]}]\n")

    ev = run_szz(cases, RULES)
    assert ev["introducing_commits"] == 1 and ev["rows"][0]["sha"] == intro[:7]
    assert sorted((ln["line"], ln["status"]) for ln in ev["rows"][0]["lines"]) == [(2, "covered"), (7, "gap")]
    assert ev["gap_ratio"] == 0.5
    assert "공백 비율 0.5" in szz_markdown(ev)


def test_over_warning_cause_and_yaml_booleans():
    from releaseguard.evaluate import _need, over_warning_cause

    assert over_warning_cause(["E02"]) == "scope_only"
    assert over_warning_cause(["G01", "E02"]) == "G01"
    assert over_warning_cause(["R04"]) == "other"
    assert over_warning_cause(["B03", "G01"]) == "B03"
    assert (_need(True), _need(False), _need("yes"), _need(None)) == ("yes", "no", "yes", None)


def test_under_warning_split_by_reason_and_scope_skips_broken_runs():
    from releaseguard.evaluate import label_metrics

    def row(sha, need, reason, decision, scope="COMPLETE", expected_scope="COMPLETE", status="passed"):
        return {"sha": sha, "need": need, "need_reason": reason, "decisions": [decision], "rules": [],
                "scope": scope, "expected_scope": expected_scope, "test_status": status}

    m = label_metrics([
        row("a", "yes", "untested", "REVIEW REQUIRED"),
        row("b", "yes", "risky_area", "SAFE"),
        row("c", "yes", "risky_area", "SAFE"),
        row("d", "no", "none", "SAFE", scope="UNSUPPORTED", status="timeout"),  # 실행 실패 → 범위 비교에서 뺀다
    ])
    assert m["under_warning"] == {"count": 2, "of": 3, "commits": ["b", "c"]}
    assert m["under_warning_by_reason"]["untested"]["count"] == 0
    assert m["under_warning_by_reason"]["risky_area"] == {"count": 2, "of": 2, "commits": ["b", "c"]}
    assert m["scope_agreement"]["of"] == 3
