"""변경 영향 분석 에이전트 (4단계 Impact).

프레임워크 없이 OpenAI Responses API로 tool calling 루프를 직접 돌린다.
에이전트는 판정하지 않는다. 영향·위험·추천 테스트를 근거와 함께 내고,
근거는 validate_evidence가 코드로 확인한다.
"""

import json
import re
import sys
import time
from dataclasses import dataclass

from .agent_tools import TOOLS, RepoView, run_tool

DEFAULT_MODEL = "gpt-5.4-mini"


@dataclass(frozen=True)
class Limits:
    max_steps: int = 8  # LLM 호출 상한. 마지막 차례는 도구 없이 답하게 한다.
    max_tool_calls: int = 20
    reasoning_effort: str = "low"


SYSTEM_PROMPT = """당신은 코드 변경의 영향을 분석하는 시니어 개발자입니다.
규칙 단계의 결과(변경 파일, 관련 테스트, 발동한 판정 규칙)를 받아서, 도구로 실제 코드를 확인한 뒤
이 변경이 어디에 영향을 주고 무엇을 검증해야 하는지 한국어로 답하세요.

작업 순서:
1. 소스·설정 변경은 git_diff로 무엇이 바뀌었는지 먼저 봅니다.
2. 바뀐 함수·클래스·설정 키를 search_code로 찾아 사용처(호출하는 쪽)를 확인합니다.
3. 필요한 부분만 read_file로 읽습니다. 파일 전체를 읽지 마세요.

규칙:
- 도구 결과로 확인한 내용만 주장하세요. 확인하지 못한 추측은 쓰지 마세요.
- 모든 항목의 evidence에는 아래 형식만 쓰세요. 다른 형식은 근거로 인정되지 않습니다.
  - file:<경로>:<줄> 또는 file:<경로>:<시작줄>-<끝줄>  (head 시점 줄 번호. read_file·search_code 결과에서 확인한 것)
  - tool:#<n>  (n번째 도구 호출. 도구 결과의 call 번호)
  - rule:<규칙 id>  (입력에 있는 발동 규칙)
- risks의 level: HIGH = 배포 후 잘못된 결과·장애가 날 가능성이 근거로 확인됨, MEDIUM = 검증이 필요함, LOW = 참고.
  근거가 약하면 HIGH를 쓰지 마세요.
- recommended_tests: 이미 있는 테스트를 돌리라면 kind=run_existing, target=테스트 파일 경로.
  새로 만들어야 하면 kind=add_new, target=만들 테스트의 위치나 이름.
- 문서만 바뀐 변경처럼 영향이 없으면 빈 배열로 두세요."""

EVIDENCE = {"type": "array", "items": {"type": "string"}, "description": "file:<경로>:<줄>, tool:#<n>, rule:<id>"}

IMPACT_FORMAT = {
    "type": "json_schema",
    "name": "impact_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "변경 요약 2~3문장"},
            "impacts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "area": {"type": "string", "description": "영향받는 기능·모듈"},
                        "files": {"type": "array", "items": {"type": "string"}},
                        "reason": {"type": "string"},
                        "evidence": EVIDENCE,
                    },
                    "required": ["area", "files", "reason", "evidence"],
                    "additionalProperties": False,
                },
            },
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "title": {"type": "string"},
                        "detail": {"type": "string"},
                        "evidence": EVIDENCE,
                    },
                    "required": ["level", "title", "detail", "evidence"],
                    "additionalProperties": False,
                },
            },
            "recommended_tests": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string"},
                        "kind": {"type": "string", "enum": ["run_existing", "add_new"]},
                        "reason": {"type": "string"},
                        "evidence": EVIDENCE,
                    },
                    "required": ["target", "kind", "reason", "evidence"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "impacts", "risks", "recommended_tests"],
        "additionalProperties": False,
    },
}


def build_input(result: dict) -> str:
    """규칙 단계 결과 중 에이전트에게 필요한 것만 추린다. diff 본문은 넣지 않는다."""
    context = {
        "changed_files": [
            {k: f[k] for k in ("path", "status", "old_path", "category", "added", "deleted")}
            for f in result["changed_files"]
        ],
        "coverage": [
            {"source": c["source"], "status": c["status"], "tests": sorted({t["path"] for t in c["tests"]})}
            for c in result["coverage"]
        ],
        "fired_rules": [
            {"rule_id": f["rule_id"], "decision": f["decision"], "message": f["message"], "evidence": f["evidence"]}
            for f in result["findings"]
        ],
    }
    return "규칙 단계 결과:\n" + json.dumps(context, ensure_ascii=False, indent=1)


def log(message: str) -> None:
    print(message, file=sys.stderr)


def run_agent(client, model: str, view: RepoView, result: dict, limits: Limits = Limits()) -> dict:
    """{"output": 구조화된 답, "meta": 실행 기록}. 도구 결과에는 call 번호를 붙여 tool:#n 근거로 쓰게 한다."""
    history: list = [{"role": "user", "content": build_input(result)}]
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
            text={"format": IMPACT_FORMAT},
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
            log(f"[agent] steps={step} tools={len(tool_log)} input={input_tokens} output={output_tokens} time={meta['seconds']}s")
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


def check_evidence(evidence: str, view: RepoView, ok_calls: set[int], fired_rules: set[str]) -> bool:
    if m := _FILE_EVIDENCE.match(evidence):
        start, end = int(m.group(2)), int(m.group(3) or m.group(2))
        count = view.file_line_count(m.group(1))
        return count is not None and 1 <= start <= end <= count
    if m := _TOOL_EVIDENCE.match(evidence):
        return int(m.group(1)) in ok_calls
    if evidence.startswith("rule:"):
        return evidence[5:] in fired_rules
    return False


def validate_evidence(output: dict, meta: dict, view: RepoView, fired_rules: set[str]) -> dict:
    """항목마다 verified(근거가 있고 모두 확인됨)와 unverified(확인 안 된 근거)를 붙인다."""
    ok_calls = {t["n"] for t in meta["tool_log"] if t["ok"]}
    checked = {"summary": output["summary"]}
    for key in ("impacts", "risks", "recommended_tests"):
        items = []
        for item in output[key]:
            bad = [e for e in item["evidence"] if not check_evidence(e, view, ok_calls, fired_rules)]
            if key == "recommended_tests" and item["kind"] == "run_existing" and view.file_line_count(item["target"]) is None:
                bad.append(f"target:{item['target']} (head에 없음)")
            items.append({**item, "verified": bool(item["evidence"]) and not bad, "unverified": bad})
        checked[key] = items
    return checked
