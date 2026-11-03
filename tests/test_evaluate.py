from itertools import count

from releaseguard.classify import load_rules
from releaseguard.evaluate import evaluate, metrics, to_markdown


def make_repo(repo):
    repo.write("src/engine.py", "def f():\n    return 1\n")
    repo.write("tests/test_engine.py", "from src.engine import f\n")
    repo.commit("base")
    repo.write("README.md", "# x\n")
    docs = repo.commit("docs")
    repo.write("src/engine.py", "def f():\n    return 2\n")
    repo.write("tests/test_engine.py", "from src.engine import f\n\ndef test_f():\n    assert f() == 2\n")
    src = repo.commit("src+test")
    return docs, src


def test_evaluate_rules_only(repo, tmp_path):
    docs, _ = make_repo(repo)
    cases = tmp_path / "cases.yaml"
    cases.write_text(f"repo: target\ncases:\n  - sha: {docs[:7]}\n    expected: REVIEW REQUIRED\n", encoding="utf-8")

    ev = evaluate(cases, load_rules())
    m = ev["metrics"]
    assert m["commits"] == 2  # 첫 커밋은 제외
    assert m["test_retrieval"] == {"commits": 1, "precision": 1.0, "recall": 1.0}
    assert m["decision"]["labeled"] == 1 and m["decision"]["under_warning"] == 1
    assert m["agent"] is None


def test_evaluate_repeat_measures_consistency(repo, tmp_path):
    docs, src = make_repo(repo)
    cases = tmp_path / "cases.yaml"
    cases.write_text(
        f"repo: target\ncases:\n"
        f"  - sha: {docs[:7]}\n    expected: SAFE\n"
        f"  - sha: {src[:7]}\n    expected: REVIEW REQUIRED\n    followup_fix: [later]\n",
        encoding="utf-8",
    )
    calls = count()

    def runner(view, result):
        n = next(calls)
        # src 커밋에서만 실행마다 HIGH가 나왔다 안 나왔다 한다 (docs 3회 → src 3회 순서)
        high = n >= 3 and n % 2 == 1
        risk = {"level": "HIGH", "title": "t", "detail": "", "evidence": ["file:src/engine.py:1"]}
        output = {"summary": "s", "impacts": [], "risks": [risk] if high else [], "recommended_tests": []}
        return {"output": output, "meta": {"model": "m", "llm_calls": 1, "tool_calls": 0, "input_tokens": 1, "output_tokens": 1, "seconds": 0.1, "tool_log": []}}

    ev = evaluate(cases, load_rules(), runner, repeat=3)
    a = ev["metrics"]["agent"]
    assert a["runs"] == 6
    assert a["high_on_followup"] == {"commits": 1, "run_rate": 0.667, "any_run": 1, "every_run": 0}
    assert a["high_on_safe"]["any_run"] == 0
    assert a["consistency"]["commits"] == 2 and a["consistency"]["high_same"] == 1
    # src 커밋은 HIGH가 나온 실행에서만 R07 → 판정이 갈린다
    src_row = next(r for r in ev["rows"] if r["sha"] == src[:7])
    assert src_row["decisions"] == ["REVIEW REQUIRED", "SAFE", "REVIEW REQUIRED"]
    assert ev["metrics"]["decision"]["judgments"] == 6
    assert "실행 1 · HIGH: t" in to_markdown(ev)


def row(decision, expected=None, predicted=(), actual=(), rules=()):
    return {
        "decision": decision,
        "decisions": [decision],
        "expected": expected,
        "followup_fix": None,
        "predicted_tests": list(predicted),
        "actual_tests": list(actual),
        "rules": list(rules),
        "has_source": True,
        "agent_runs": [],
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
