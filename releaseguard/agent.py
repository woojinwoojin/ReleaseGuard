"""검증 공백 설명 에이전트 (6단계 Explain).

공백 하나마다 좁은 질문 하나를 묻는다: "이 줄들은 어떤 동작을 바꾸고, 어떤 테스트가 그걸 확인할 수 있나?"
에이전트는 판정에 들어가지 않는다. 결과는 보고서의 설명과 테스트 제안으로만 쓴다.
프레임워크 없이 OpenAI Responses API로 tool calling 루프를 직접 돌린다.
"""

import json
import re
import sys
import time
from dataclasses import dataclass

from .agent_tools import TOOLS, RepoView, ToolError, run_tool
from .classify import RuleSet, classify
from .gaps import FileLines

DEFAULT_MODEL = "gpt-5.4-mini"
MAX_GAPS = 5  # 한 번 분석에서 설명할 공백 수 (큰 것부터)
CONTEXT_LINES = 15  # 공백 앞뒤로 입력에 넣는 줄 수


@dataclass(frozen=True)
class Limits:
    max_steps: int = 4  # LLM 호출 상한. 마지막 차례는 도구 없이 답하게 한다.
    max_tool_calls: int = 6
    reasoning_effort: str = "low"


SYSTEM_PROMPT = """당신은 테스트를 설계하는 시니어 개발자입니다.
코드 변경 중 "어떤 테스트도 실행하지 않는 줄(검증 공백)" 하나를 받습니다. 한국어로 답하세요.

할 일:
1. behavior: 이 줄들이 어떤 동작을 추가하거나 바꾸는지 1~2문장으로.
2. trigger: 어떤 입력·조건에서 이 줄들이 실행되는지.
3. suggested_test: 그 동작을 확인하는 테스트 하나. 기존 테스트 파일에 추가하는 것을 우선하세요.
   file은 저장소 기준 경로, name은 테스트 함수 이름, scenario는 준비할 입력, assertion은 확인할 결과를 실제 함수 이름과 값 형태로.

규칙:
- 코드가 맞는지 틀린지는 판단하지 마세요. 무엇이 검증되지 않았는지만 다룹니다.
- 입력에 공백 주변 코드와 diff, 같은 파일의 다른 변경을 실행하는 테스트가 있습니다. 더 필요할 때만 도구를 쓰세요
  (호출하는 쪽 찾기, 기존 테스트 형식 확인).
- evidence에는 아래 형식만 쓰세요. 다른 형식은 근거로 인정되지 않습니다.
  file:<경로>:<줄> 또는 file:<경로>:<시작줄>-<끝줄> (head 시점 줄 번호), tool:#<n> (n번째 도구 호출)"""

EXPLAIN_FORMAT = {
    "type": "json_schema",
    "name": "gap_explanation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "behavior": {"type": "string"},
            "trigger": {"type": "string"},
            "suggested_test": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "name": {"type": "string"},
                    "scenario": {"type": "string"},
                    "assertion": {"type": "string"},
                },
                "required": ["file", "name", "scenario", "assertion"],
                "additionalProperties": False,
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["behavior", "trigger", "suggested_test", "evidence"],
        "additionalProperties": False,
    },
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def build_input(view: RepoView, fl: FileLines, start: int, end: int) -> str:
    try:
        around = view.read_file(fl.path, max(1, start - CONTEXT_LINES), end + CONTEXT_LINES)["content"]
    except ToolError as e:
        around = f"(읽기 실패: {e})"
    diff = view.git_diff(fl.path)
    return "\n\n".join([
        f"검증 공백: {fl.path} {start}~{end}줄 (head 기준)",
        f"공백 주변 코드 (줄 번호 포함):\n{around}",
        f"이 파일의 diff:\n{diff['diff'][:6000]}" + ("\n(잘림)" if diff["truncated"] or len(diff["diff"]) > 6000 else ""),
        "같은 파일의 다른 변경 줄을 실행하는 테스트: " + (", ".join(fl.tests[:10]) or "없음"),
    ])


def run_loop(client, model: str, view: RepoView, user_input: str, limits: Limits = Limits()) -> dict:
    """{"output": 구조화된 답, "meta": 실행 기록}. 도구 결과에는 call 번호를 붙여 tool:#n 근거로 쓰게 한다."""
    history: list = [{"role": "user", "content": user_input}]
    tool_log: list[dict] = []
    input_tokens = output_tokens = 0
    started = time.perf_counter()

    for step in range(1, limits.max_steps + 1):
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=history,
            tools=TOOLS,
            tool_choice="none" if step == limits.max_steps else "auto",
            text={"format": EXPLAIN_FORMAT},
            reasoning={"effort": limits.reasoning_effort},
        )
        input_tokens += response.usage.input_tokens
        output_tokens += response.usage.output_tokens
        history.extend(response.output)

        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if response.status != "completed":
                raise RuntimeError(f"응답이 완료되지 않았습니다: {response.incomplete_details}")
            meta = {
                "model": model,
                "llm_calls": step,
                "tool_calls": len(tool_log),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "seconds": round(time.perf_counter() - started, 1),
                "tool_log": tool_log,
            }
            return {"output": json.loads(response.output_text), "meta": meta}

        for call in calls:
            # 모든 function_call에는 짝이 되는 output이 있어야 하므로 상한을 넘은 호출에도 error를 돌려준다.
            if len(tool_log) >= limits.max_tool_calls:
                output = json.dumps({"error": f"도구 호출 상한({limits.max_tool_calls}개)을 넘었습니다. 지금까지의 결과로 답하세요."}, ensure_ascii=False)
            else:
                n = len(tool_log) + 1
                body, ok = run_tool(view, call.name, call.arguments)
                tool_log.append({"n": n, "name": call.name, "arguments": call.arguments, "ok": ok})
                log(f"[tool #{n}] {call.name}({call.arguments}){'' if ok else ' → error'}")
                output = json.dumps({"call": f"tool:#{n}", "result": json.loads(body)}, ensure_ascii=False)
            history.append({"type": "function_call_output", "call_id": call.call_id, "output": output})

    raise RuntimeError(f"LLM 호출 {limits.max_steps}번 안에 답을 받지 못했습니다.")


_FILE_EVIDENCE = re.compile(r"^file:(.+):(\d+)(?:-(\d+))?$")
_TOOL_EVIDENCE = re.compile(r"^tool:#(\d+)$")


def check_evidence(evidence: str, view: RepoView, ok_calls: set[int]) -> bool:
    if m := _FILE_EVIDENCE.match(evidence):
        start, end = int(m.group(2)), int(m.group(3) or m.group(2))
        count = view.file_line_count(m.group(1))
        return count is not None and 1 <= start <= end <= count
    if m := _TOOL_EVIDENCE.match(evidence):
        return int(m.group(1)) in ok_calls
    return False


def validate(output: dict, meta: dict, view: RepoView, ruleset: RuleSet) -> dict:
    """verified = 근거가 있고 모두 확인됨 + 제안 테스트 파일이 테스트 분류 경로."""
    ok_calls = {t["n"] for t in meta["tool_log"] if t["ok"]}
    bad = [e for e in output["evidence"] if not check_evidence(e, view, ok_calls)]
    test_file = output["suggested_test"]["file"]
    if classify(test_file, ruleset)[0] != "test":
        bad.append(f"suggested_test.file:{test_file} (테스트 파일 경로가 아님)")
    return {
        **output,
        "new_test_file": view.file_line_count(test_file) is None,
        "verified": bool(output["evidence"]) and not bad,
        "unverified": bad,
    }


def pick_gaps(lines: list[FileLines], limit: int = MAX_GAPS) -> list[tuple[FileLines, int, int]]:
    """큰 공백부터 limit개. 크기가 같으면 경로·줄 순서 (실행마다 같은 순서)."""
    gaps = [(fl, s, e) for fl in lines for s, e in fl.gaps]
    return sorted(gaps, key=lambda g: (-(g[2] - g[1]), g[0].path, g[1]))[:limit]


def explain_gaps(client, model: str, view: RepoView, lines: list[FileLines], ruleset: RuleSet, limits: Limits = Limits()) -> dict:
    """{"items": 공백별 설명, "meta": 합계}. 공백 하나가 실패해도 나머지는 계속한다."""
    items, totals = [], {"model": model, "gaps": 0, "llm_calls": 0, "tool_calls": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0, "errors": 0}
    for fl, start, end in pick_gaps(lines):
        totals["gaps"] += 1
        item = {"path": fl.path, "start": start, "end": end}
        try:
            out = run_loop(client, model, view, build_input(view, fl, start, end), limits)
        except Exception as e:  # API 오류, 응답 형식 오류 등
            totals["errors"] += 1
            items.append({**item, "error": f"{type(e).__name__}: {e}"})
            continue
        meta = out["meta"]
        for k in ("llm_calls", "tool_calls", "input_tokens", "output_tokens"):
            totals[k] += meta[k]
        totals["seconds"] = round(totals["seconds"] + meta["seconds"], 1)
        items.append({**item, **validate(out["output"], meta, view, ruleset), "error": None, "tool_log": meta["tool_log"]})
        log(f"[explain] {fl.path}:{start}-{end} tools={meta['tool_calls']} input={meta['input_tokens']}")
    return {"items": items, "meta": totals}
