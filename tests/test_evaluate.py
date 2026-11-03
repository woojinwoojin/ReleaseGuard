from releaseguard.classify import load_rules
from releaseguard.evaluate import evaluate, metrics


def test_evaluate_on_temp_repo(repo, tmp_path):
    repo.write("src/engine.py", "def f():\n    return 1\n")
    repo.write("tests/test_engine.py", "from src.engine import f\n")
    repo.commit("base")
    repo.write("README.md", "# x\n")
    docs = repo.commit("docs")
    repo.write("src/engine.py", "def f():\n    return 2\n")
    repo.write("tests/test_engine.py", "from src.engine import f\n\ndef test_f():\n    assert f() == 2\n")
    repo.commit("src+test")
    cases = tmp_path / "cases.yaml"
    cases.write_text(f"repo: target\ncases:\n  - sha: {docs[:7]}\n    expected: REVIEW REQUIRED\n", encoding="utf-8")

    ev = evaluate(cases, load_rules())
    m = ev["metrics"]
    assert m["commits"] == 2  # 첫 커밋은 제외
    assert m["test_retrieval"] == {"commits": 1, "precision": 1.0, "recall": 1.0}
    assert m["decision"]["labeled"] == 1 and m["decision"]["under_warning"] == 1
    assert m["agent"] is None


def row(decision, expected=None, predicted=(), actual=(), rules=()):
    return {
        "decision": decision,
        "expected": expected,
        "predicted_tests": list(predicted),
        "actual_tests": list(actual),
        "rules": list(rules),
        "has_source": True,
        "agent": None,
    }


def test_metrics_retrieval_skips_unknown_and_counts_warnings():
    m = metrics([
        row("SAFE", "SAFE", predicted=["a", "b"], actual=["a"]),
        row("REVIEW REQUIRED", "SAFE", predicted=["c"], actual=[], rules=["R03"]),
        row("SAFE", "BLOCK"),
    ])
    assert m["test_retrieval"] == {"commits": 1, "precision": 0.5, "recall": 1.0}
    assert m["decision"]["accuracy"] == 0.333
    assert (m["decision"]["over_warning"], m["decision"]["under_warning"]) == (1, 1)
    assert m["rule_fire_rate"] == {"R03": 0.333}
