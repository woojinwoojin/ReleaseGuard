"""가짜 OpenAI 클라이언트로 루프·근거 검증·판정 반영을 확인한다 (실제 API 호출 없음)."""

import json
from types import SimpleNamespace

import pytest

from releaseguard.agent import Limits, run_agent, validate_evidence
from releaseguard.agent_tools import RepoView
from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.report import to_markdown

RULES = load_rules()


def call(name, args, call_id):
    return SimpleNamespace(type="function_call", name=name, arguments=json.dumps(args), call_id=call_id)


def answer(payload):
    return SimpleNamespace(
        output=[SimpleNamespace(type="message")],
        output_text=json.dumps(payload, ensure_ascii=False),
        status="completed",
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
    )


def tool_turn(*calls):
    return SimpleNamespace(output=list(calls), status="completed", usage=SimpleNamespace(input_tokens=10, output_tokens=5))


class FakeClient:
    def __init__(self, responses):
        self.requests = []
        self._responses = iter(responses)
        self.responses = self

    def create(self, **kwargs):
        self.requests.append({**kwargs, "input": list(kwargs["input"])})
        return next(self._responses)


IMPACT = {
    "summary": "compute의 반환값이 두 배가 됩니다.",
    "impacts": [
        {
            "area": "보고서 출력",
            "files": ["src/report.py"],
            "reason": "compute를 호출합니다.",
            "evidence": ["file:src/report.py:3", "tool:#1"],
        }
    ],
    "risks": [
        {"level": "HIGH", "title": "출력값 변경", "detail": "보고서 숫자가 바뀝니다.", "evidence": ["file:src/report.py:3"]},
        {"level": "HIGH", "title": "추측", "detail": "근거 없음", "evidence": []},
        {"level": "MEDIUM", "title": "없는 줄", "detail": "", "evidence": ["file:src/report.py:99", "tool:#7"]},
    ],
    "recommended_tests": [
        {"target": "tests/test_engine.py", "kind": "run_existing", "reason": "", "evidence": ["rule:R01"]},
        {"target": "tests/test_report.py", "kind": "run_existing", "reason": "", "evidence": ["rule:R01"]},
    ],
}


@pytest.fixture
def setup(repo):
    repo.write("src/engine.py", "def compute(x):\n    return x\n")
    repo.write("src/report.py", "from src.engine import compute\n\nprint(compute(1))\n")
    repo.write("tests/test_engine.py", "from src.engine import compute\n")
    repo.commit("base")
    repo.write("src/engine.py", "def compute(x):\n    return x * 2\n")
    repo.commit("change")
    return repo


def test_loop_numbers_tool_calls_and_records_meta(setup):
    client = FakeClient([
        tool_turn(call("search_code", {"text": "compute", "path_prefix": None}, "c1"), call("read_file", {"path": "x.py", "start_line": None, "end_line": None}, "c2")),
        answer(IMPACT),
    ])
    result = analyze(setup.path, "HEAD~1", "HEAD", RULES)
    view = RepoView(setup.path, result["merge_base"], result["head_sha"])
    out = run_agent(client, "fake-model", view, result)

    assert out["output"] == IMPACT
    assert [(t["n"], t["name"], t["ok"]) for t in out["meta"]["tool_log"]] == [(1, "search_code", True), (2, "read_file", False)]
    assert out["meta"]["llm_calls"] == 2 and out["meta"]["input_tokens"] == 110
    # 두 번째 요청에는 call 번호가 붙은 도구 결과가 들어간다
    outputs = [json.loads(i["output"]) for i in client.requests[1]["input"] if isinstance(i, dict) and i.get("type") == "function_call_output"]
    assert [o["call"] for o in outputs] == ["tool:#1", "tool:#2"]
    # 첫 입력에는 규칙 결과만 있고 diff 본문은 없다
    first = client.requests[0]["input"][0]["content"]
    assert "src/engine.py" in first and "return x * 2" not in first


def test_last_step_disables_tools(setup):
    turns = [tool_turn(call("list_files", {"path_prefix": None}, f"c{i}")) for i in range(2)] + [answer(IMPACT)]
    client = FakeClient(turns)
    result = analyze(setup.path, "HEAD~1", "HEAD", RULES)
    view = RepoView(setup.path, result["merge_base"], result["head_sha"])
    run_agent(client, "m", view, result, Limits(max_steps=3))
    assert [r["tool_choice"] for r in client.requests] == ["auto", "auto", "none"]


def test_tool_call_cap(setup):
    many = tool_turn(*[call("list_files", {"path_prefix": None}, f"c{i}") for i in range(3)])
    client = FakeClient([many, answer(IMPACT)])
    result = analyze(setup.path, "HEAD~1", "HEAD", RULES)
    view = RepoView(setup.path, result["merge_base"], result["head_sha"])
    out = run_agent(client, "m", view, result, Limits(max_tool_calls=2))
    assert out["meta"]["tool_calls"] == 2
    last = json.loads(client.requests[1]["input"][-1]["output"])
    assert "상한" in last["error"]


def test_validate_evidence(setup):
    result = analyze(setup.path, "HEAD~1", "HEAD", RULES)
    view = RepoView(setup.path, result["merge_base"], result["head_sha"])
    meta = {"tool_log": [{"n": 1, "ok": True}, {"n": 2, "ok": False}]}
    checked = validate_evidence(IMPACT, meta, view, {"R01"})
    assert checked["impacts"][0]["verified"] is True
    assert [(r["title"], r["verified"]) for r in checked["risks"]] == [("출력값 변경", True), ("추측", False), ("없는 줄", False)]
    assert checked["risks"][2]["unverified"] == ["file:src/report.py:99", "tool:#7"]
    tests = checked["recommended_tests"]
    assert tests[0]["verified"] is True
    assert tests[1]["unverified"] == ["target:tests/test_report.py (head에 없음)"]


def test_only_verified_high_risk_adds_r07(setup):
    client = FakeClient([tool_turn(call("search_code", {"text": "compute", "path_prefix": None}, "c1")), answer(IMPACT)])
    runner = lambda view, result: run_agent(client, "m", view, result)  # noqa: E731
    result = analyze(setup.path, "HEAD~1", "HEAD", RULES, runner)
    r07 = [f for f in result["findings"] if f["rule_id"] == "R07"]
    assert r07 == [{
        "rule_id": "R07",
        "decision": "REVIEW REQUIRED",
        "message": "에이전트가 근거와 함께 HIGH 위험을 제시했습니다.",
        "evidence": ["출력값 변경 (file:src/report.py:3)"],
    }]
    md = to_markdown(result)
    assert "**근거 미확인**" in md and "LLM 2회" in md


def test_agent_failure_keeps_rule_result(setup):
    def broken(view, result):
        raise RuntimeError("API down")

    result = analyze(setup.path, "HEAD~1", "HEAD", RULES, broken)
    assert result["decision"] == "REVIEW REQUIRED"
    assert result["impact"] is None and result["agent_error"] == "RuntimeError: API down"
    assert "에이전트 실행 실패" in to_markdown(result)
