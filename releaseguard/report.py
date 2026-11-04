"""분석 결과를 사람이 읽는 Markdown 보고서로 만든다 (7단계 Report)."""

from .decide import NOT_VERIFIED_RULES

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
_COMPARISON = {
    "REGRESSION": "base에서는 통과 → 이번 변경 후 실패",
    "NEW_TEST_FAILING": "base에 없는 테스트",
    "PRE_EXISTING": "base에서도 같은 조건으로 실패 (원래 깨짐)",
    "INCOMPARABLE": "base에서도 실패, 하지만 같은 실패로 확인하지 못함",
    "UNKNOWN": "base 실행이 결과를 내지 못해 확인 불가",
    "FLAKY": "다시 돌리니 통과 (불안정)",
}
_SCOPE = {
    "COMPLETE": "바뀐 내용을 모두 검증 범위 안에서 확인함",
    "PARTIAL": "일부 변경은 검증하지 못함",
    "UNSUPPORTED": "변경의 핵심을 검증하지 못함",
}


def _rule_table(findings: list[dict]) -> list[str]:
    out = ["| 규칙 | 판정 | 내용 | 근거 |", "|---|---|---|---|"]
    for f in findings:
        out.append(f"| {f['rule_id']} | {f['decision']} | {f['message']} | {'<br>'.join(f'`{e}`' for e in f['evidence'])} |")
    return out


def _range(s: int, e: int) -> str:
    return f"{s}" if s == e else f"{s}-{e}"


def to_markdown(result: dict) -> str:
    s, run = result["summary"], result["test_run"]
    rules = [f for f in result["findings"] if f["decision"] != "NOTE"]
    notes = [f for f in result["findings"] if f["decision"] == "NOTE"]
    scope = result["scope"]
    not_verified = [f for f in rules if f["rule_id"] in NOT_VERIFIED_RULES]
    found = [f for f in rules if f["rule_id"] not in NOT_VERIFIED_RULES]
    lines = [
        f"# ReleaseGuard 보고서 — {result['decision']} (검증 범위: {scope['status']})",
        "",
        f"- 저장소: `{result['repo']}`",
        f"- 비교: `{result['base']}...{result['head']}` "
        f"(merge-base `{result['merge_base'][:7]}` → head `{result['head_sha'][:7]}`)",
        f"- 변경: 파일 {s['files']}개, +{s['added']} / -{s['deleted']} ("
        + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()) + ")",
        f"- 검증 범위: **{scope['status']}** — {_SCOPE[scope['status']]}",
        "",
        "> SAFE는 코드가 맞다는 보증이 아니라, ReleaseGuard의 검증 절차(테스트 실행·바뀐 줄 coverage·규칙)에서 "
        "검토 사유를 찾지 못했다는 뜻입니다.",
        "",
    ]
    if scope["unverified"]:
        lines += ["## 검증하지 못한 변경", "", "| 파일 | 분류 | 이유 |", "|---|---|---|"]
        lines += [f"| `{u['path']}` | {u['category']} | {u['reason']} |" for u in scope["unverified"]]
        lines.append("")
    lines += ["## 판정 근거", "", "### 검증이 성립하지 않은 것", ""]
    lines += _rule_table(not_verified) if not_verified else ["없음."]
    lines += ["", "### 검증해서 찾은 것", ""]
    if found:
        lines += _rule_table(found)
    elif not not_verified:
        lines.append("발동한 규칙이 없습니다: 테스트가 모두 통과했고, 바뀐 실행 줄을 모두 테스트가 실행했습니다.")
    else:
        lines.append("없음.")
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
        lines += ["", "| 실패한 테스트 | 비교 상태 | 메시지 |", "|---|---|---|"]
        for f in run["failures"]:
            msg = f["message"].replace("|", "/").splitlines()[0] if f["message"] else "-"
            lines.append(f"| `{f['nodeid']}` | {f['comparison']} — {_COMPARISON[f['comparison']]}{_evidence_note(f)} | {msg} |")
    if run.get("skipped"):
        lines += ["", f"건너뛴 테스트 {len(run['skipped'])}개 (판정에 반영하지 않음 — 이 테스트가 실행했을 줄은 검증 공백으로 보임):", "",
                  "| 테스트 | 사유 |", "|---|---|"]
        lines += [f"| `{s['nodeid']}` | {(s['reason'] or '-').replace('|', '/').splitlines()[0]} |" for s in run["skipped"]]

    lines += ["", "## 바뀐 줄의 검증 상태", ""]
    if result["lines"]:
        lines += [
            "| 파일 | 바뀐 실행 줄 | 테스트가 실행 | import 시점만 | 검증 공백 | 분기 공백 (참고) | 실행한 테스트 |",
            "|---|---|---|---|---|---|---|",
        ]
        for fl in result["lines"]:
            gaps = ", ".join(_range(s, e) for s, e in fl["gaps"]) or "-"
            measured = "" if fl["measured"] else " (coverage 밖: 전체를 공백으로 봄)"
            tests = "<br>".join(f"`{t}`" for t in fl["tests"][:8]) + (f"<br>외 {len(fl['tests']) - 8}개" if len(fl["tests"]) > 8 else "")
            covered = f"{fl['covered']}" + (f" (fixture만 {fl['fixture_only']})" if fl.get("fixture_only") else "")
            lines.append(
                f"| `{fl['path']}`{measured} | {fl['executable']} | {covered} | {fl['import_only']} | **{fl['gap_lines']}** ({gaps}) | "
                f"{_branch_cell(fl)} | {tests or '-'} |"
            )
        lines += ["", "분기 공백: 바뀐 조건문(if·while·for 등)이 실행됐지만 그중 한쪽 분기는 어떤 테스트도 지나가지 않음. "
                  "줄 공백과 따로 세며 판정에는 반영하지 않습니다."]
    elif result["estimated_tests"] is not None:
        lines.append("테스트를 실행하지 못해 이름 규칙·import로 **추정**한 관련 테스트입니다.")
        lines += ["", "| 소스 | 추정 관련 테스트 |", "|---|---|"]
        for c in result["estimated_tests"]:
            lines.append(f"| `{c['source']}` | {'<br>'.join(sorted({t['path'] for t in c['tests']})) or '-'} |")
    else:
        lines.append("검사할 Python 소스 변경이 없습니다.")

    lines += ["", "## 검증 공백 설명 (에이전트, 판정에 반영하지 않음)", ""]
    lines += _explain_lines(result)

    lines += ["", "## 실행 기록", ""]
    lines += _record_lines(run)

    lines += ["", "## 변경 파일", "", "| 파일 | 상태 | 분류 | +/- |", "|---|---|---|---|"]
    for f in result["changed_files"]:
        path = f"`{f['old_path']}` → `{f['path']}`" if f["old_path"] else f"`{f['path']}`"
        delta = "바이너리" if f["added"] is None else f"+{f['added']} / -{f['deleted']}"
        lines.append(f"| {path} | {_STATUS[f['status']]} | {f['category']} | {delta} |")
    lines.append("")
    return "\n".join(lines)


def _branch_cell(fl: dict) -> str:
    """분기 공백 n/전체 (출발→도착, …). 도착이 음수면 함수에서 나가는 분기."""
    if "branch_gaps" not in fl:  # 1.5 이전 결과
        return "-"
    if not fl["branches"]:
        return "분기 없음"
    arcs = ", ".join(f"{a}→{'나감' if b < 0 else b}" for a, b in fl["branch_gaps"][:6]) + (" …" if len(fl["branch_gaps"]) > 6 else "")
    return f"{len(fl['branch_gaps'])}/{fl['branches']}" + (f" ({arcs})" if arcs else "")


def _record_lines(run: dict) -> list[str]:
    r = run.get("record")
    if not r or not r["command"]:
        return ["테스트를 실행하지 않았습니다."]
    out = [
        f"- head `{r['head_sha'][:12]}` · merge-base `{r['merge_base'][:12]}`",
        f"- Python {r['python_version'] or '?'} (`{r['python']}`) · coverage {r['coverage_version']}{' + pytest-cov ' + r['pytest_cov_version'] + ' (분기 포함)' if r.get('pytest_cov_version') else ''} · 시간 상한 {r['timeout']}초 · 시도 {r['attempts']}회",
        f"- 명령: `{' '.join(r['command'])}`",
        "- 실행 위치: `git archive`로 푼 임시 폴더 (대상 작업 폴더는 건드리지 않음, 샌드박스는 아님)",
    ]
    for x in r["reruns"]:
        out.append(f"- {x['purpose']}: `{x['sha'][:7]}` → {x['status']} ({x['seconds']}초)")
    if run.get("snapshot_warnings"):
        out += [f"- 스냅샷 주의: {w}" for w in run["snapshot_warnings"]]
    if r.get("host_secret_env"):
        out.append(
            "- 테스트에 그대로 넘어간 자격 증명류 호스트 환경 변수 (이름만): "
            + ", ".join(f"`{n}`" for n in r["host_secret_env"])
            + " — 이 변수가 없는 환경(CI)에서는 결과가 다를 수 있음"
        )
    return out


def _evidence_note(f: dict) -> str:
    """base·head 모두 실패한 경우, 같은 실패로 본(또는 못 본) 근거를 짧게."""
    e = f.get("comparison_evidence")
    if not e:
        return ""
    if e["method"]:
        how = "새 테스트만 추가됨" if e["test_file_changed"] else "테스트 파일 안 바뀜"
        return f" <br>근거: 같은 실패 지문, {how}, 공유 맥락 그대로"
    why = []
    if e["test_function_same"] is not True:
        why.append("테스트 정의가 바뀜" if e["test_function_same"] is False else "테스트 정의를 비교하지 못함")
    elif e["test_file_changed"] and e["only_new_tests_added"] is not True:
        why.append("같은 파일의 기존 코드(헬퍼·다른 테스트·import)가 바뀜")
    if not e["shared_test_context_unchanged"]:
        why.append("공유 맥락 변경: " + ", ".join(e["shared_test_context_changes"]))
    if not e["failure_fingerprint_same"]:
        why.append("실패 지문이 다름")
    return " <br>같은 실패로 확인 못 함: " + "; ".join(why)


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
