"""가짜 OpenAI 클라이언트로 공백 설명 루프·검증을 확인한다 (실제 API 호출 없음)."""

import json
from types import SimpleNamespace

from conftest import CALC, PY

from releaseguard.agent import Limits, build_input, explain_gaps, pick_gaps, run_loop, validate
from releaseguard.agent_tools import RepoView
from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.gaps import FileLines
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


GOOD = {
    "behavior": "음수 입력이면 -2를 돌려준다.",
    "trigger": "x < 0",
    "suggested_test": {"file": "tests/test_calc.py", "name": "test_sign_negative", "scenario": "sign(-5)", "assertion": "sign(-5) == -2"},
    "evidence": ["file:src/calc.py:6-7", "tool:#1"],
}


def gap_repo(pyrepo):
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    result = analyze(pyrepo.path, "HEAD~1", "HEAD", RULES, python=PY)
    view = RepoView(pyrepo.path, result["merge_base"], result["head_sha"])
    lines = [FileLines(**{**fl, "gaps": [tuple(g) for g in fl["gaps"]]}) for fl in result["lines"]]
    return view, lines


def test_build_input_has_code_diff_and_test_hints(pyrepo):
    view, lines = gap_repo(pyrepo)
    text = build_input(view, lines[0], 7, 7)
    assert "src/calc.py 7~7줄" in text
    assert "7:         return -2" in text  # 줄 번호가 붙은 주변 코드
    assert "+        return -2" in text  # diff


def test_loop_numbers_tool_calls(pyrepo):
    view, _ = gap_repo(pyrepo)
    client = FakeClient([tool_turn(call("search_code", {"text": "sign(", "path_prefix": None}, "c1")), answer(GOOD)])
    out = run_loop(client, "m", view, "입력")
    assert out["output"] == GOOD
    assert [(t["n"], t["ok"]) for t in out["meta"]["tool_log"]] == [(1, True)]
    sent = json.loads(client.requests[1]["input"][-1]["output"])
    assert sent["call"] == "tool:#1"


def test_last_step_disables_tools(pyrepo):
    view, _ = gap_repo(pyrepo)
    turns = [tool_turn(call("list_files", {"path_prefix": None}, f"c{i}")) for i in range(2)] + [answer(GOOD)]
    client = FakeClient(turns)
    run_loop(client, "m", view, "입력", Limits(max_steps=3))
    assert [r["tool_choice"] for r in client.requests] == ["auto", "auto", "none"]


def test_validate_checks_evidence_and_test_path(pyrepo):
    view, _ = gap_repo(pyrepo)
    meta = {"tool_log": [{"n": 1, "ok": True}]}
    ok = validate(GOOD, meta, view, RULES)
    assert ok["verified"] is True and ok["new_test_file"] is False

    bad = {**GOOD, "suggested_test": {**GOOD["suggested_test"], "file": "src/calc.py"}, "evidence": ["file:src/calc.py:99", "tool:#2"]}
    out = validate(bad, meta, view, RULES)
    assert out["verified"] is False
    assert out["unverified"] == ["file:src/calc.py:99", "tool:#2", "suggested_test.file:src/calc.py (테스트 파일 경로가 아님)"]

    new = {**GOOD, "suggested_test": {**GOOD["suggested_test"], "file": "tests/test_sign.py"}}
    assert validate(new, meta, view, RULES)["new_test_file"] is True


def test_pick_gaps_largest_first_and_capped():
    a = FileLines("a.py", True, 0, gaps=[(1, 1), (10, 14)])
    b = FileLines("b.py", True, 0, gaps=[(3, 5)])
    picked = [(fl.path, s, e) for fl, s, e in pick_gaps([a, b], limit=2)]
    assert picked == [("a.py", 10, 14), ("b.py", 3, 5)]


def test_explain_gaps_end_to_end_with_report(pyrepo):
    client = FakeClient([tool_turn(call("search_code", {"text": "sign(", "path_prefix": None}, "c1")), answer(GOOD)])
    explain = lambda view, lines: explain_gaps(client, "m", view, lines, RULES)  # noqa: E731
    pyrepo.write("src/calc.py", CALC.replace("return -1", "return -2"))
    pyrepo.commit("gap")
    result = analyze(pyrepo.path, "HEAD~1", "HEAD", RULES, python=PY, explain=explain)
    [item] = result["explanations"]
    assert (item["path"], item["start"], item["end"], item["verified"]) == ("src/calc.py", 7, 7, True)
    assert result["agent"]["gaps"] == 1 and result["agent"]["llm_calls"] == 2
    assert result["decision"] == "REVIEW REQUIRED"  # 에이전트는 판정을 바꾸지 않는다
    md = to_markdown(result)
    assert "`tests/test_calc.py` → `test_sign_negative`" in md and "근거 확인됨" in md


def test_explain_gaps_keeps_going_after_one_failure(pyrepo):
    view, lines = gap_repo(pyrepo)
    two = [FileLines("src/calc.py", True, 0, gaps=[(7, 7)]), FileLines("src/calc.py", True, 0, gaps=[(2, 2)])]

    class Broken(FakeClient):
        def create(self, **kwargs):
            if not self.requests:
                self.requests.append(kwargs)
                raise RuntimeError("boom")
            return super().create(**kwargs)

    out = explain_gaps(Broken([answer(GOOD)]), "m", view, two, RULES)
    assert [i["error"] for i in out["items"]] == ["RuntimeError: boom", None]
    assert out["meta"]["errors"] == 1
