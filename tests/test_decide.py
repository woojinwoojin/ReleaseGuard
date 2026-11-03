from releaseguard.classify import load_rules
from releaseguard.decide import BLOCK, REVIEW, SAFE, decide
from releaseguard.gaps import FileLines

SECRETS = load_rules().secrets


def run(status="passed", failures=(), coverage=True, reason=None):
    return {"status": status, "reason": reason, "coverage": coverage, "failures": list(failures)}


def file(path, category, status="M"):
    return {"path": path, "status": status, "category": category}


def ids(findings):
    return [f.rule_id for f in findings]


def test_clean_change_is_safe_and_config_data_are_notes_only():
    files = [file("src/x.py", "source"), file("configs/a.yaml", "config"), file("data/a.csv", "data")]
    decision, findings = decide(files, run(), [FileLines("src/x.py", True, 1, 1, 1)], {}, SECRETS)
    assert decision == SAFE
    assert ids(findings) == ["N03", "N05"]


def test_gap_needs_review():
    fl = FileLines("src/x.py", True, 3, 3, 1, 0, 2, [(4, 5)])
    decision, findings = decide([file("src/x.py", "source")], run(), [fl], {}, SECRETS)
    assert decision == REVIEW
    assert findings[0].rule_id == "G01" and findings[0].evidence == ["src/x.py:4-5"]


def test_failures_split_by_base_status():
    failures = [
        {"nodeid": "t::broken", "base_status": "passed"},
        {"nodeid": "t::new", "base_status": "absent"},
        {"nodeid": "t::old", "base_status": "failed"},
    ]
    decision, findings = decide([], run("failed", failures), [], {}, SECRETS)
    assert decision == BLOCK
    by = {f.rule_id: f.evidence for f in findings}
    assert by == {"B03": ["t::broken", "t::new"], "T01": ["t::old"]}


def test_only_preexisting_failure_is_review():
    decision, _ = decide([], run("failed", [{"nodeid": "t::old", "base_status": "failed"}]), [], {}, SECRETS)
    assert decision == REVIEW


def test_collection_error_blocks():
    decision, findings = decide([], run("error", coverage=False, reason="ImportError"), [], {}, SECRETS)
    assert decision == BLOCK and ids(findings) == ["B04"]


def test_not_run_timeout_or_missing_coverage_is_review():
    for r in (run("not_run", coverage=False, reason="no venv"), run("timeout", coverage=False), run("passed", coverage=False)):
        decision, findings = decide([file("src/x.py", "source")], r, [], {}, SECRETS)
        assert (decision, ids(findings)) == (REVIEW, ["E01"])


def test_skipped_docs_only_is_safe():
    decision, findings = decide([file("README.md", "docs")], run("skipped", coverage=False), [], {}, SECRETS)
    assert (decision, findings) == (SAFE, [])


def test_secret_and_deps():
    key = "sk-" + "a" * 30
    decision, findings = decide([file("requirements.txt", "deps")], run(), [], {"a.py": [(3, f'K="{key}"')]}, SECRETS)
    assert decision == BLOCK
    assert ids(findings) == ["B01", "R04"]
    assert findings[0].evidence == ["a.py:3 (openai_key)"]
