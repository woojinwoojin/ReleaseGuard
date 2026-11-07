"""공백 설명 에이전트 평가 (Stage 1.6). 고정된 공백 사례만 돌린다.

`eval --agent`는 라벨이 있는 커밋 전체를 돌리므로 사례와 비용을 고정할 수 없다. 여기서는:
- 사례 파일(eval/agent_cases.yaml)에 적은 공백만, 정해진 횟수만 실행한다.
- `status: fixed`가 아니면 API를 부르지 않는다. `--check`는 API 없이 사례만 확인한다.
- 진행 상태와 사용량을 파일에 남긴다. 사전 점검(--max-runs 2)과 본 실행이 같은 예산을 쓴다.
- 조건(사례·프롬프트·도구·모델·상한)이 바뀌면 이어서 돌리지 않는다.

에이전트 입력은 build_input이 만든다. 사례의 유형·라벨·후속 수정 커밋은 평가용이고 입력에 넣지 않는다.
설명이 맞는지, 제안 테스트가 공백을 메우는지는 여기서 판단하지 않는다 (docs/eval/agent_eval_protocol.md).
"""

import hashlib
import json
import time
from pathlib import Path

import yaml

from .agent import SYSTEM_PROMPT, Budget, BudgetExceeded, Limits, Meter, build_input, log, run_loop, validate
from .agent_tools import TOOLS, RepoView
from .analyze import analyze
from .classify import RuleSet
from .gaps import FileLines


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_cases(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [c["id"] for c in raw["cases"]]
    shas = [c["sha"] for c in raw["cases"]]
    if len(set(ids)) != len(ids):
        raise ValueError("사례 id가 겹칩니다.")
    if len(set(shas)) != len(shas):
        raise ValueError("같은 커밋의 공백을 두 번 고르면 안 됩니다.")
    raw["_base"] = path.resolve().parent
    return raw


def conditions(raw: dict, path: Path) -> dict:
    """이 값이 같아야 이어서 돌릴 수 있다."""
    return {
        "cases_sha256": _digest(path.read_text(encoding="utf-8")),
        "prompt_sha256": _digest(SYSTEM_PROMPT),
        "tools_sha256": _digest(json.dumps(TOOLS, sort_keys=True, ensure_ascii=False)),
        "model": raw["model"],
        "limits": raw["limits"],
        "budget": raw["budget"],
        "pricing": raw["pricing"],
        "repeat": raw["repeat"],
        "temperature": "지정 안 함 (모델 기본값)",
    }


def _group_of(result: dict, path: str, start: int, end: int) -> dict | None:
    return next(
        (g for g in result["gap_groups"] if g["path"] == path and any(start <= n <= end for n in g["gap_line_numbers"])),
        None,
    )


def rule_baseline(view: RepoView, fl: FileLines, group: dict | None, start: int, end: int) -> dict:
    """에이전트 없이 결정적 분석만으로 줄 수 있는 설명. 에이전트의 추가 가치를 재는 비교 기준이다."""
    lines = view.read_file(fl.path, start, end)["content"].splitlines()
    keywords = ("if ", "elif ", "else", "except", "raise ", "return ", "for ", "while ")
    return {
        "where": f"{fl.path}:{start}-{end}",
        "function": group["name"] if group else None,
        "conditions": [x.strip() for x in lines if x.split(":", 1)[-1].strip().startswith(keywords)],
        "tests_on_other_changes_in_file": fl.tests[:10],
    }


def prepare(raw: dict, ruleset: RuleSet) -> list[dict]:
    """사례마다 테스트를 돌려 공백이 실제로 있는지 확인한다 (API 없음)."""
    out = []
    for case in raw["cases"]:
        repo = (raw["_base"] / raw["repos"][case["repo"]]).resolve()
        result = analyze(repo, f"{case['sha']}~1", case["sha"], ruleset)
        view = RepoView(repo, result["merge_base"], result["head_sha"])
        found = next((fl for fl in result["lines"] if fl["path"] == case["path"]), None)
        span = [case["start"], case["end"]]
        ok = found is not None and span in [list(g) for g in found["gaps"]]
        item = {
            "case": case, "view": view, "ok": ok, "fl": None, "baseline": None,
            "decision": result["decision"], "skipped": result["test_run"]["skipped"],
            "gaps_in_file": [list(g) for g in found["gaps"]] if found else [],
        }
        if ok:
            fl = FileLines(**{**found, "gaps": [tuple(g) for g in found["gaps"]]})
            item["fl"] = fl
            item["baseline"] = rule_baseline(view, fl, _group_of(result, case["path"], case["start"], case["end"]), case["start"], case["end"])
        out.append(item)
    return out


def check_markdown(raw: dict, prepared: list[dict]) -> str:
    lines = [
        "# Agent Eval 사례 확인 (API 호출 없음)", "",
        f"- 상태: `{raw['status']}` · 모델 `{raw['model']}` · {len(prepared)}개 × {raw['repeat']}회", "",
        "| id | 유형 | 저장소 | 커밋 | 공백 | 함수 | 판정 | skip | 공백 확인 |", "|---|---|---|---|---|---|---|---|---|",
    ]
    for p in prepared:
        c, b = p["case"], p["baseline"] or {}
        lines.append(
            f"| {c['id']} | {c['type']} | {c['repo']} | `{c['sha']}` | `{c['path']}:{c['start']}-{c['end']}` | "
            f"`{b.get('function')}` | {p['decision']} | {len(p['skipped'])} | {'확인' if p['ok'] else '없음 ' + str(p['gaps_in_file'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_state(path: Path, cond: dict) -> dict:
    if not path.exists():
        return {"conditions": cond, "usage": {k: 0 for k in Meter.FIELDS}, "runs": []}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["conditions"] != cond:
        changed = [k for k in cond if state["conditions"].get(k) != cond[k]]
        raise ValueError(f"실행 조건이 바뀌어 이어서 돌릴 수 없습니다: {changed}. 새 출력 폴더를 쓰세요.")
    return state


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def run(raw: dict, cases_path: Path, state_path: Path, ruleset: RuleSet, client, prepared: list[dict], max_runs: int | None = None) -> dict:
    """아직 안 돌린 (회차, 사례)를 차례로 실행한다. 한 회차를 끝내고 다음 회차로 간다. 실행마다 저장한다."""
    if raw["status"] != "fixed":
        raise ValueError("사례가 고정되지 않았습니다 (status: fixed 필요). API를 호출하지 않습니다.")
    if bad := [p["case"]["id"] for p in prepared if not p["ok"]]:
        raise ValueError(f"공백이 확인되지 않은 사례가 있습니다: {bad}")
    state = _load_state(state_path, conditions(raw, cases_path))
    pricing, budget = raw["pricing"], raw["budget"]
    limits = Limits(**raw["limits"])
    meter = Meter(
        client,
        Budget(budget["max_requests"], budget["stop_usd"], pricing["input_usd_per_m"], pricing["output_usd_per_m"]),
        state["usage"],
    )
    done = {(r["case"], r["repeat"]) for r in state["runs"]}
    todo = [(rep, p) for rep in range(1, raw["repeat"] + 1) for p in prepared if (p["case"]["id"], rep) not in done]
    state["stopped"] = None
    for rep, p in todo[:max_runs]:
        case, before, started = p["case"], meter.snapshot(), time.perf_counter()
        row = {"case": case["id"], "repeat": rep, "error": None}
        try:
            out = run_loop(meter, raw["model"], p["view"], build_input(p["view"], p["fl"], case["start"], case["end"]), limits, ruleset.secrets)
            meta = out["meta"]
            row["answer"] = validate(out["output"], meta, p["view"], ruleset)
            row["tool_log"] = meta["tool_log"]
            row["response_model"] = meta["response_model"]
            row["redactions"] = meta["redactions"]
        except BudgetExceeded as e:
            state["stopped"] = str(e)
            log(f"[eval-agent] 중단: {e}")
            break
        except Exception as e:  # API 오류, 응답 형식 오류 등. 사용량은 미터에 남는다.
            row["error"] = f"{type(e).__name__}: {e}"
        used = meter.snapshot()
        row["usage"] = {k: used[k] - before[k] for k in Meter.FIELDS}
        row["seconds"] = round(time.perf_counter() - started, 1)
        state["runs"].append(row)
        state["usage"] = used
        _save(state_path, state)
        log(f"[eval-agent] {case['id']} #{rep} {row['usage']} {row['error'] or ''}")
    _save(state_path, state)
    return state


def summarize(raw: dict, state: dict) -> dict:
    runs = state["runs"]
    ok = [r for r in runs if not r["error"]]
    evidence = [e for r in ok for e in r["answer"]["evidence"]]
    invalid = sum(len(r["answer"]["invalid_references"]) for r in ok)
    tools = [t for r in ok for t in r["tool_log"]]
    u, p = state["usage"], raw["pricing"]
    cost = (u["input_tokens"] * p["input_usd_per_m"] + u["output_tokens"] * p["output_usd_per_m"]) / 1_000_000
    return {
        "planned_runs": len(raw["cases"]) * raw["repeat"],
        "runs": len(runs),
        "structured_output_success": len(ok),
        "evidence": len(evidence),
        "evidence_invalid": invalid,
        "runs_references_valid": sum(r["answer"]["references_valid"] for r in ok),
        "test_path_invalid": sum(not r["answer"]["test_path_valid"] for r in ok),
        "new_test_file": sum(r["answer"]["new_test_file"] for r in ok),
        "tool_calls": len(tools),
        "tool_errors": sum(not t["ok"] for t in tools),
        "redactions": sum(r["redactions"] for r in ok),
        "response_models": sorted({r["response_model"] for r in ok if r.get("response_model")}),
        "seconds": round(sum(r["seconds"] for r in runs), 1),
        "usage": u,
        "estimated_usd": round(cost, 4),
        "stopped": state.get("stopped"),
    }


def to_markdown(raw: dict, state: dict, prepared: list[dict]) -> str:
    s = summarize(raw, state)
    u = s["usage"]
    lines = [
        "# Agent Eval 응답", "",
        f"- 모델 `{raw['model']}` (응답 모델 {s['response_models']}) · 실행 {s['runs']}/{s['planned_runs']}",
        f"- 구조화 출력 성공 {s['structured_output_success']}/{s['runs']} · 근거 참조 오류 {s['evidence_invalid']}/{s['evidence']} "
        f"(참조 유효는 인용한 줄이 존재한다는 뜻이지 설명이 맞다는 뜻이 아님)",
        f"- 테스트 파일 경로 오류 {s['test_path_invalid']} · 새 테스트 파일 제안 {s['new_test_file']} · 도구 {s['tool_calls']}회 (오류 {s['tool_errors']}) · 가린 비밀값 {s['redactions']}",
        f"- 요청 {u['requests']}회 (실패 {u['failed_requests']}, 사용량 미확인 {u['unknown_usage']}) · 토큰 {u['input_tokens']:,} / {u['output_tokens']:,} · "
        f"추정 ${s['estimated_usd']} (캐시 할인 미반영) · {s['seconds']}초",
    ]
    if s["stopped"]:
        lines.append(f"- **중단**: {s['stopped']}")
    for p in prepared:
        c, b = p["case"], p["baseline"] or {}
        lines += [
            "", f"## {c['id']} `{c['path']}:{c['start']}-{c['end']}` (`{c['sha']}`, {c['type']})", "",
            f"규칙 기준선: 함수 `{b.get('function')}`, 조건·반환 줄 {len(b.get('conditions', []))}개, "
            f"같은 파일의 다른 변경을 실행한 테스트 {len(b.get('tests_on_other_changes_in_file', []))}개",
        ]
        for r in (x for x in state["runs"] if x["case"] == c["id"]):
            lines += ["", f"### 실행 {r['repeat']}", ""]
            if r["error"]:
                lines.append(f"실패: `{r['error']}`")
                continue
            a = r["answer"]
            t = a["suggested_test"]
            lines += [
                f"- 바뀐 동작: {a['behavior']}", f"- 실행 조건: {a['trigger']}",
                f"- 제안: `{t['file']}` → `{t['name']}`" + (" (새 파일)" if a["new_test_file"] else "") + ("" if a["test_path_valid"] else " **(테스트 경로 아님)**"),
                f"  - 준비: {t['scenario']}", f"  - 확인: {t['assertion']}",
                f"- 근거: {', '.join(f'`{e}`' for e in a['evidence']) or '-'}" + (f" — 참조 오류 {a['invalid_references']}" if a["invalid_references"] else ""),
                f"- 도구 {len(r['tool_log'])}회, 요청 {r['usage']['requests']}회, 토큰 {r['usage']['input_tokens']:,} / {r['usage']['output_tokens']:,}, {r['seconds']}초",
            ]
    lines.append("")
    return "\n".join(lines)
