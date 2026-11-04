from releaseguard.classify import load_rules
from releaseguard.decide import BLOCK, COMPLETE, PARTIAL, REVIEW, SAFE, UNSUPPORTED, compute_scope, decide
from releaseguard.gaps import FileLines

SECRETS = load_rules().secrets


def run(status="passed", failures=(), coverage=True, reason=None, snapshot_warnings=()):
    return {
        "status": status, "reason": reason, "coverage": coverage, "failures": list(failures),
        "snapshot_warnings": list(snapshot_warnings),
    }


def file(path, category, status="M"):
    return {"path": path, "status": status, "category": category}


def fail(nodeid, comparison):
    return {"nodeid": nodeid, "comparison": comparison}


def ids(findings):
    return [f.rule_id for f in findings]


def judge(files, r, lines=(), added=None):
    return decide(files, r, list(lines), added or {}, SECRETS)


def test_clean_python_change_is_safe_and_complete():
    decision, findings, scope = judge([file("src/x.py", "source"), file("tests/test_x.py", "test")], run(), [FileLines("src/x.py", True, 1, 1, 1)])
    assert (decision, findings, scope.status) == (SAFE, [], COMPLETE)


def test_config_or_data_change_is_not_safe():
    # v2에서는 NOTE만 남고 SAFE였다. v3: 검증하지 못한 변경이 있으면 SAFE를 내지 않는다.
    files = [file("src/x.py", "source"), file("configs/a.yaml", "config"), file("data/a.csv", "data")]
    decision, findings, scope = judge(files, run(), [FileLines("src/x.py", True, 1, 1, 1)])
    assert decision == REVIEW and ids(findings) == ["E02"]
    assert scope.status == PARTIAL
    assert [u["path"] for u in scope.unverified] == ["configs/a.yaml", "data/a.csv"]


def test_dockerfile_only_is_unsupported():
    decision, findings, scope = judge([file("Dockerfile", "config"), file("README.md", "docs")], run("no_tests", coverage=True))
    assert (decision, ids(findings), scope.status) == (REVIEW, ["E02"], UNSUPPORTED)


def test_non_python_source_is_outside_scope():
    decision, findings, scope = judge([file("web/app.js", "source")], run())
    assert (decision, ids(findings), scope.status) == (REVIEW, ["E02"], UNSUPPORTED)
    assert "Python이 아닌 소스" in findings[0].evidence[0]


def test_docs_only_is_safe_and_complete():
    decision, findings, scope = judge([file("README.md", "docs")], run("skipped", coverage=False))
    assert (decision, findings, scope.status) == (SAFE, [], COMPLETE)


def test_deps_are_unverified_but_reported_by_r04_not_e02():
    decision, findings, scope = judge([file("requirements.txt", "deps")], run())
    assert (decision, ids(findings), scope.status) == (REVIEW, ["R04"], UNSUPPORTED)


def test_run_not_established_makes_python_changes_unverified():
    for r in (run("not_run", coverage=False, reason="no venv"), run("timeout", coverage=False)):
        decision, findings, scope = judge([file("src/x.py", "source")], r)
        assert (decision, ids(findings), scope.status) == (REVIEW, ["E01"], UNSUPPORTED)


def test_missing_coverage_is_review():
    decision, findings, _ = judge([file("src/x.py", "source")], run("passed", coverage=False))
    assert (decision, ids(findings)) == (REVIEW, ["E01"])


def test_collection_error_blocks_and_is_unsupported():
    decision, findings, scope = judge([file("src/x.py", "source")], run("error", coverage=False, reason="ImportError"))
    assert (decision, ids(findings), scope.status) == (BLOCK, ["B04"], UNSUPPORTED)


def test_gap_needs_review():
    fl = FileLines("src/x.py", True, 3, 3, 1, 0, 2, [(4, 5)])
    decision, findings, _ = judge([file("src/x.py", "source")], run(), [fl])
    assert decision == REVIEW
    assert findings[0].rule_id == "G01" and findings[0].evidence == ["src/x.py:4-5"]


def test_failures_by_comparison_state():
    failures = [
        fail("t::broken", "REGRESSION"),
        fail("t::new", "NEW_TEST_FAILING"),
        fail("t::changed", "INCOMPARABLE"),
        fail("t::unknown", "UNKNOWN"),
        fail("t::old", "PRE_EXISTING"),
        fail("t::flaky", "FLAKY"),
    ]
    decision, findings, _ = judge([], run("failed", failures))
    assert decision == BLOCK
    by = {f.rule_id: f.evidence for f in findings}
    assert by == {
        # 원래부터 실패했다고 확인되지 않으면 낮추지 않는다
        "B03": ["t::broken (REGRESSION)", "t::new (NEW_TEST_FAILING)", "t::changed (INCOMPARABLE)", "t::unknown (UNKNOWN)"],
        "T01": ["t::old (PRE_EXISTING)"],
        "T02": ["t::flaky (FLAKY)"],
    }


def test_only_preexisting_or_flaky_failure_is_review():
    for state in ("PRE_EXISTING", "FLAKY"):
        decision, _, _ = judge([], run("failed", [fail("t::x", state)]))
        assert decision == REVIEW


def test_snapshot_warning_is_review():
    decision, findings, _ = judge([], run(snapshot_warnings=[".gitmodules: 서브모듈"]))
    assert (decision, ids(findings)) == (REVIEW, ["E03"])


def test_secret_and_deps():
    key = "sk-" + "a" * 30
    decision, findings, _ = judge([file("requirements.txt", "deps")], run(), added={"a.py": [(3, f'K="{key}"')]})
    assert decision == BLOCK
    assert ids(findings) == ["B01", "R04"]
    assert findings[0].evidence == ["a.py:3 (openai_key)"]


def test_deleted_source_is_note_and_verified_by_run():
    decision, findings, scope = judge([file("src/old.py", "source", "D")], run())
    assert (decision, ids(findings), scope.status) == (SAFE, ["N06"], COMPLETE)


def test_compute_scope_ignores_docs():
    assert compute_scope([file("README.md", "docs"), file("src/x.py", "source")], "passed").status == COMPLETE
