"""분석 결과를 사람이 읽는 Markdown 보고서로 만든다 (7단계 Report)."""

_STATUS = {"A": "추가", "M": "수정", "D": "삭제", "R": "이름 변경"}
_RUN = {
    "passed": "모두 통과",
    "failed": "실패 있음",
    "error": "수집·실행 오류",
    "timeout": "시간 초과",
    "no_tests": "테스트 없음",
    "not_run": "실행하지 못함",
    "skipped": "실행 안 함",
}
_BASE = {"passed": "base에서는 통과 → 이번 변경이 깨뜨림", "failed": "base에서도 실패 (원래 깨짐)", "absent": "이번에 추가된 테스트"}


def _range(s: int, e: int) -> str:
    return f"{s}" if s == e else f"{s}-{e}"


def to_markdown(result: dict) -> str:
    s, run = result["summary"], result["test_run"]
    rules = [f for f in result["findings"] if f["decision"] != "NOTE"]
    notes = [f for f in result["findings"] if f["decision"] == "NOTE"]
    lines = [
        f"# ReleaseGuard 보고서 — {result['decision']}",
        "",
        f"- 저장소: `{result['repo']}`",
        f"- 비교: `{result['base']}...{result['head']}` "
        f"(merge-base `{result['merge_base'][:7]}` → head `{result['head_sha'][:7]}`)",
        f"- 변경: 파일 {s['files']}개, +{s['added']} / -{s['deleted']} ("
        + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()) + ")",
        "",
        "## 판정 근거",
        "",
    ]
    if rules:
        lines += ["| 규칙 | 판정 | 내용 | 근거 |", "|---|---|---|---|"]
        for f in rules:
            lines.append(f"| {f['rule_id']} | {f['decision']} | {f['message']} | {'<br>'.join(f'`{e}`' for e in f['evidence'])} |")
    else:
        lines.append("발동한 규칙이 없습니다: 테스트가 모두 통과했고, 바뀐 실행 줄을 모두 테스트가 실행했습니다.")
    if notes:
        lines += ["", "참고 (판정에 반영하지 않음):"]
        lines += [f"- {f['rule_id']} {f['message']} {', '.join(f'`{e}`' for e in f['evidence'])}" for f in notes]

    c = run["counts"]
    lines += [
        "",
        "## 테스트 실행",
        "",
        f"- 결과: **{_RUN[run['status']]}** — 통과 {c['passed']}, 실패 {c['failed']}, 오류 {c['error']}, 건너뜀 {c['skipped']} ({run['seconds']}초)",
    ]
    if run["reason"] and run["status"] != "failed":
        lines += ["", "```", run["reason"], "```"]
    if run["failures"]:
        lines += ["", "| 실패한 테스트 | base | 메시지 |", "|---|---|---|"]
        for f in run["failures"]:
            lines.append(f"| `{f['nodeid']}` | {_BASE[f['base_status']]} | {f['message'].replace('|', '/').splitlines()[0] if f['message'] else '-'} |")

    lines += ["", "## 바뀐 줄의 검증 상태", ""]
    if result["lines"]:
        lines += ["| 파일 | 바뀐 실행 줄 | 테스트가 실행 | import 시점만 | 검증 공백 | 실행한 테스트 |", "|---|---|---|---|---|---|"]
        for fl in result["lines"]:
            gaps = ", ".join(_range(s, e) for s, e in fl["gaps"]) or "-"
            measured = "" if fl["measured"] else " (coverage 밖: 전체를 공백으로 봄)"
            tests = "<br>".join(f"`{t}`" for t in fl["tests"][:8]) + (f"<br>외 {len(fl['tests']) - 8}개" if len(fl["tests"]) > 8 else "")
            lines.append(f"| `{fl['path']}`{measured} | {fl['executable']} | {fl['covered']} | {fl['import_only']} | **{fl['gap_lines']}** ({gaps}) | {tests or '-'} |")
    elif result["estimated_tests"] is not None:
        lines.append("테스트를 실행하지 못해 이름 규칙·import로 **추정**한 관련 테스트입니다.")
        lines += ["", "| 소스 | 추정 관련 테스트 |", "|---|---|"]
        for c in result["estimated_tests"]:
            lines.append(f"| `{c['source']}` | {'<br>'.join(sorted({t['path'] for t in c['tests']})) or '-'} |")
    else:
        lines.append("검사할 Python 소스 변경이 없습니다.")

    lines += ["", "## 검증 공백 설명 (에이전트, 판정에 반영하지 않음)", ""]
    lines += _explain_lines(result)

    lines += ["", "## 변경 파일", "", "| 파일 | 상태 | 분류 | +/- |", "|---|---|---|---|"]
    for f in result["changed_files"]:
        path = f"`{f['old_path']}` → `{f['path']}`" if f["old_path"] else f"`{f['path']}`"
        delta = "바이너리" if f["added"] is None else f"+{f['added']} / -{f['deleted']}"
        lines.append(f"| {path} | {_STATUS[f['status']]} | {f['category']} | {delta} |")
    lines.append("")
    return "\n".join(lines)


def _explain_lines(result: dict) -> list[str]:
    if result["agent_error"]:
        return [f"에이전트 실행 실패 (`{result['agent_error']}`)."]
    if result["explanations"] is None:
        has_gaps = any(fl["gaps"] for fl in result["lines"])
        return ["에이전트를 실행하지 않았습니다 (`--no-agent`)." if has_gaps else "설명할 공백이 없습니다."]
    out = []
    for item in result["explanations"]:
        head = f"### `{item['path']}` {_range(item['start'], item['end'])}줄"
        if item["error"]:
            out += [head, "", f"실패: `{item['error']}`", ""]
            continue
        t = item["suggested_test"]
        check = "근거 확인됨" if item["verified"] else "**근거 미확인** (" + ", ".join(item["unverified"]) + ")"
        new = " (새 파일)" if item["new_test_file"] else ""
        out += [
            head,
            "",
            f"- 바뀐 동작: {item['behavior']}",
            f"- 실행 조건: {item['trigger']}",
            f"- 제안 테스트: `{t['file']}`{new} → `{t['name']}`",
            f"  - 준비: {t['scenario']}",
            f"  - 확인: {t['assertion']}",
            f"- 근거: {', '.join(f'`{e}`' for e in item['evidence']) or '-'} — {check}",
            "",
        ]
    a = result["agent"]
    out.append(
        f"_실행 기록: {a['model']}, 공백 {a['gaps']}개, LLM {a['llm_calls']}회, 도구 {a['tool_calls']}회, "
        f"토큰 {a['input_tokens']:,} / {a['output_tokens']:,}, {a['seconds']}초_"
    )
    return out
