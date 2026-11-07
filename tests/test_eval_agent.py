"""가짜 클라이언트로 eval-agent의 예산·이어 돌리기·입력 분리를 확인한다 (실제 API 호출 없음)."""

import json
from types import SimpleNamespace

import pytest
import yaml
from conftest import CALC
from test_agent import GOOD, FakeClient, answer

from releaseguard import eval_agent
from releaseguard.agent import Budget, BudgetExceeded, Limits, Meter, redact, run_loop
from releaseguard.agent_tools import RepoView
from releaseguard.classify import SecretPattern, load_rules
from releaseguard.gaps import FileLines

RULES = load_rules()
PRICE = {"input_usd_per_m": 1.0, "output_usd_per_m": 1.0}


def make_cases(tmp_path, status="fixed", cases=2, **over):
    raw = {
        "status": status, "model": "m", "pricing": PRICE,
        "limits": {"max_steps": 2, "max_tool_calls": 2, "reasoning_effort": "low", "max_output_tokens": 100},
        "budget": {"max_requests": 10, "target_usd": 1, "stop_usd": 5},
        "repeat": 2, "repos": {"r": "."},
        "cases": [{"id": f"C{i}", "type": "followup_fix", "repo": "r", "sha": f"s{i}", "path": "src/calc.py", "start": 7, "end": 7, "fix": "SECRET_FIX", "note": "SECRET_NOTE"} for i in range(cases)],
        **over,
    }
    path = tmp_path / "cases.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    return path


def prepared(raw, view):
    fl = FileLines("src/calc.py", True, 1, gaps=[(7, 7)], tests=[])
    return [{"case": c, "view": view, "ok": True, "fl": fl, "baseline": {}} for c in raw["cases"]]


@pytest.fixture
def view(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    return RepoView(pyrepo.path, "HEAD~1", "HEAD")


def go(path, state, client, view, max_runs=None):
    raw = eval_agent.load_cases(path)
    return eval_agent.run(raw, path, state, RULES, client, prepared(raw, view), max_runs)


def test_draft_cases_never_call_the_api(tmp_path, view):
    client = FakeClient([])
    with pytest.raises(ValueError, match="status: fixed"):
        go(make_cases(tmp_path, status="draft"), tmp_path / "s.json", client, view)
    assert client.requests == []


def test_unconfirmed_gap_blocks_all_runs(tmp_path, view):
    path = make_cases(tmp_path)
    raw = eval_agent.load_cases(path)
    items = prepared(raw, view)
    items[1]["ok"] = False
    client = FakeClient([])
    with pytest.raises(ValueError, match="C1"):
        eval_agent.run(raw, path, tmp_path / "s.json", RULES, client, items)
    assert client.requests == []


def test_same_commit_twice_is_rejected(tmp_path):
    path = make_cases(tmp_path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["cases"][1]["sha"] = raw["cases"][0]["sha"]
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="같은 커밋"):
        eval_agent.load_cases(path)


def test_pilot_then_resume_shares_usage_and_skips_done(tmp_path, view):
    path, state = make_cases(tmp_path), tmp_path / "s.json"
    first = go(path, state, FakeClient([answer(GOOD)] * 2), view, max_runs=2)
    assert [(r["case"], r["repeat"]) for r in first["runs"]] == [("C0", 1), ("C1", 1)]  # 서로 다른 사례부터
    second = go(path, state, FakeClient([answer(GOOD)] * 2), view)
    assert [(r["case"], r["repeat"]) for r in second["runs"]][2:] == [("C0", 2), ("C1", 2)]
    assert second["usage"]["requests"] == 4 and second["usage"]["input_tokens"] == 400
    client = FakeClient([])
    go(path, state, client, view)  # 다 돌렸으면 더 부르지 않는다
    assert client.requests == []


def test_changed_conditions_refuse_to_resume(tmp_path, view):
    path, state = make_cases(tmp_path), tmp_path / "s.json"
    go(path, state, FakeClient([answer(GOOD)]), view, max_runs=1)
    make_cases(tmp_path, model="other")
    with pytest.raises(ValueError, match="조건이 바뀌어"):
        go(path, state, FakeClient([]), view)


def test_request_limit_stops_before_sending_and_saves(tmp_path, view):
    path, state = make_cases(tmp_path, budget={"max_requests": 1, "target_usd": 1, "stop_usd": 5}), tmp_path / "s.json"
    client = FakeClient([answer(GOOD)] * 4)
    out = go(path, state, client, view)
    assert len(client.requests) == 1 and len(out["runs"]) == 1
    assert "요청 상한" in json.loads(state.read_text(encoding="utf-8"))["stopped"]


def test_usd_limit_counts_next_request_before_sending():
    budget = Budget(100, 0.0002, 1.0, 1.0)  # 토큰 200개면 닿는다
    meter = Meter(FakeClient([answer(GOOD)] * 3), budget)
    kw = {"input": [], "max_output_tokens": 50}
    meter.create(**kw)  # 150 토큰 사용
    with pytest.raises(BudgetExceeded):
        meter.create(**kw)
    assert meter.totals["requests"] == 1


def test_failed_request_is_counted_as_unknown_usage_not_zero(tmp_path, view):
    class Broken:
        responses = None

        def __init__(self):
            self.responses = self

        def create(self, **kw):
            raise RuntimeError("boom")

    out = go(make_cases(tmp_path), tmp_path / "s.json", Broken(), view, max_runs=1)
    [row] = out["runs"]
    assert row["error"] == "RuntimeError: boom"
    assert row["usage"]["requests"] == 1 and row["usage"]["failed_requests"] == 1 and row["usage"]["unknown_usage"] == 1
    assert eval_agent.summarize(eval_agent.load_cases(tmp_path / "cases.yaml"), out)["structured_output_success"] == 0


def test_partial_usage_survives_a_failure_after_a_tool_turn(view):
    turn = SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name="list_files", arguments='{"path_prefix": null}', call_id="c")],
        status="completed", usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    meter = Meter(FakeClient([turn]))  # 두 번째 요청에서 StopIteration
    with pytest.raises(Exception):
        run_loop(meter, "m", view, "입력", Limits(max_steps=2))
    assert meter.totals["input_tokens"] == 10 and meter.totals["requests"] == 2 and meter.totals["unknown_usage"] == 1


def test_labels_and_followup_are_not_in_model_input(tmp_path, view):
    path = make_cases(tmp_path)
    client = FakeClient([answer(GOOD)])
    go(path, tmp_path / "s.json", client, view, max_runs=1)
    sent = json.dumps(client.requests[0], ensure_ascii=False, default=str)
    for hidden in ("SECRET_FIX", "SECRET_NOTE", "followup_fix"):
        assert hidden not in sent


def test_secrets_are_masked_in_input_and_tool_results(pyrepo):
    key = "sk-" + "a" * 24
    pyrepo.write("src/calc.py", CALC + f'\nKEY = "{key}"\n')
    pyrepo.commit("key")
    view = RepoView(pyrepo.path, "HEAD~1", "HEAD")
    turn = SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name="read_file", arguments=json.dumps({"path": "src/calc.py", "start_line": None, "end_line": None}), call_id="c")],
        status="completed", usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    client = FakeClient([turn, answer(GOOD)])
    out = run_loop(client, "m", view, f"입력 {key}", Limits(max_steps=2), RULES.secrets)
    sent = json.dumps(client.requests, ensure_ascii=False, default=str)
    assert key not in sent and "[REDACTED:openai_key]" in sent
    assert out["meta"]["redactions"] == 2
    assert redact("x", (SecretPattern("a", "y"),)) == ("x", 0)


def test_reference_valid_is_not_called_verified_and_summary_counts(tmp_path, view):
    wrong = {**GOOD, "behavior": "사용자가 삭제되면 DB를 초기화한다.", "evidence": ["file:src/calc.py:1"]}
    path = make_cases(tmp_path, cases=1)
    out = go(path, tmp_path / "s.json", FakeClient([answer(wrong)]), view, max_runs=1)
    # 설명이 코드와 무관해도 참조는 유효하다: 코드로는 내용까지 확인하지 못한다는 것을 고정해 둔다.
    assert out["runs"][0]["answer"]["references_valid"] is True
    s = eval_agent.summarize(eval_agent.load_cases(path), out)
    assert (s["runs"], s["evidence"], s["evidence_invalid"], s["estimated_usd"]) == (1, 1, 0, 0.0001)
    assert "설명이 맞다는 뜻이 아님" in eval_agent.to_markdown(eval_agent.load_cases(path), out, prepared(eval_agent.load_cases(path), view))
