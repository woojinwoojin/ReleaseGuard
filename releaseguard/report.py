"""분석 결과를 사람이 읽는 Markdown 보고서로 만든다 (6단계 Report)."""

_STATUS = {"A": "추가", "M": "수정", "D": "삭제", "R": "이름 변경"}
_COVERAGE = {
    "test_changed": "관련 테스트 함께 수정",
    "test_unchanged": "관련 테스트 있음, 수정 없음",
    "test_deleted": "관련 테스트 삭제",
    "no_test": "관련 테스트 없음",
}


def to_markdown(result: dict) -> str:
    s = result["summary"]
    lines = [
        f"# ReleaseGuard 보고서 — {result['decision']}",
        "",
        f"- 저장소: `{result['repo']}`",
        f"- 비교: `{result['base']}...{result['head']}` "
        f"(merge-base `{result['merge_base'][:7]}` → head `{result['head_sha'][:7]}`)",
        f"- 변경: 파일 {s['files']}개, +{s['added']} / -{s['deleted']}",
        f"- 분류: " + ", ".join(f"{k} {v}" for k, v in s["by_category"].items()),
        "",
        "## 판정 근거",
        "",
    ]
    if result["findings"]:
        lines += ["| 규칙 | 판정 | 내용 | 근거 |", "|---|---|---|---|"]
        for f in result["findings"]:
            lines.append(f"| {f['rule_id']} | {f['decision']} | {f['message']} | {'<br>'.join(f['evidence'])} |")
    else:
        lines.append("발동한 규칙이 없습니다 (SAFE).")

    lines += ["", "## 소스별 관련 테스트", ""]
    if result["coverage"]:
        lines += ["| 소스 | 상태 | 관련 테스트 (근거) |", "|---|---|---|"]
        for c in result["coverage"]:
            tests = "<br>".join(f"`{t['path']}` ({t['evidence']})" for t in c["tests"]) or "-"
            lines.append(f"| `{c['source']}` | {_COVERAGE[c['status']]} | {tests} |")
    else:
        lines.append("변경된 소스가 없습니다.")

    lines += ["", "## 변경 파일", "", "| 파일 | 상태 | 분류 | +/- |", "|---|---|---|---|"]
    for f in result["changed_files"]:
        path = f"`{f['old_path']}` → `{f['path']}`" if f["old_path"] else f"`{f['path']}`"
        delta = "바이너리" if f["added"] is None else f"+{f['added']} / -{f['deleted']}"
        lines.append(f"| {path} | {_STATUS[f['status']]} | {f['category']} | {delta} |")

    lines += ["", "## 영향 분석", "", "에이전트 영향 분석은 아직 구현되지 않았습니다 (4단계).", ""]
    return "\n".join(lines)
