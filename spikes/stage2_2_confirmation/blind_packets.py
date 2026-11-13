"""6단계: 블라인드 독립 분류 자료. 설계 6장

코드베이스마다 SURVIVED(전체 실행 기준)를 고정 해시(conflib.blind_key) 오름차순으로 정렬해 앞의 2개.
자료는 기계적으로만 만든다 — Claude가 명세를 발췌하지 않는다. Claude의 분류·평가 초안은 넣지 않는다.

넣는 것: 대상 커밋의 원본 함수 전체(없으면 줄 앞뒤 30줄), 모듈 docstring, mutant diff,
         그 커밋 시점 저장소의 문서 파일 목록(요청하면 원문 제공), 선택·전체 테스트 결과와 그 줄을 실행한 테스트 id.
넣지 않는 것: 분류 초안, 대상 커밋 이후의 이력.

사용: .venv/Scripts/python spikes/stage2_2_confirmation/blind_packets.py
결과: docs/eval/v22c/blind/packets.md, docs/eval/v22c/blind/selection.json
"""

import ast
import difflib
import json

from conflib import CODEBASES, OUT, WORKSPACE, blind_key
from releaseguard.git_ops import run_git

DOC_SUFFIXES = (".md", ".rst", ".txt")


def enclosing(source: str, line: int) -> tuple[int, int, str]:
    """줄을 감싸는 가장 안쪽 함수 (시작, 끝, 이름). 없으면 앞뒤 30줄."""
    best = None
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= line <= node.end_lineno:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            if best is None or start >= best[0]:
                best = (start, node.end_lineno, node.name)
    return best or (max(1, line - 30), line + 30, "<module>")


def main() -> int:
    result = json.loads((OUT / "mutation_result.json").read_text(encoding="utf-8"))["mutants"]
    picked, parts = {}, ["# Stage 2.2 확인 평가 — 블라인드 분류 자료\n",
                         "각 사례를 분류해 주세요: ACTIONABLE_GAP 후보(명세상 의미 있는 차이) / MEANINGFUL_UNVERIFIED / LOW_VALUE / "
                         "EQUIVALENT_SUPPORTED(코드 보장·데이터 관측·미보장을 나눠서) / UNRESOLVED. 근거와 불확실성도 함께.\n",
                         "명세 근거는 **대상 커밋 시점**의 저장소 내용만 인정합니다. 문서 원문이 필요하면 경로를 알려 주세요.\n"]
    for name in CODEBASES:
        surv = [m for m in result.values() if m["codebase"] == name and m.get("result") == "SURVIVED"]
        surv.sort(key=lambda m: blind_key(name, m))
        picked[name] = {"survived": len(surv), "picked": [m["no"] for m in surv[:2]], "shortfall": max(0, 2 - len(surv))}
        for k, m in enumerate(surv[:2], 1):
            repo = (WORKSPACE / m["repo"]).resolve()
            sha = run_git(repo, "rev-parse", m["commit"]).strip()
            src = run_git(repo, "show", f"{sha}:{m['path']}")
            lines = src.splitlines()
            s, e, fn = enclosing(src, m["line"])
            original = lines[s - 1:e]
            mutated = list(original)
            mutated[m["line"] - s] = mutated[m["line"] - s].replace(m["source_before"], m["source_after"], 1)
            diff = "\n".join(difflib.unified_diff(original, mutated, f"{m['path']} (원본)", f"{m['path']} (mutant)", lineterm="", n=3))
            doc = ast.get_docstring(ast.parse(src)) or "(없음)"
            docs = [p for p in run_git(repo, "ls-tree", "-r", "--name-only", sha).splitlines() if p.endswith(DOC_SUFFIXES)]
            sel, full = m.get("selected") or {}, m.get("full") or {}
            parts += [
                f"\n---\n\n## {name}-{k}\n",
                f"- 저장소: `{m['repo']}` · 커밋 `{m['commit']}` · `{m['path']}:{m['line']}` · 함수 `{fn}`",
                f"- 연산자: `{m['operator']}` (occurrence {m['occurrence']})",
                f"- 바뀐 줄: `{m['source_before']}` → `{m['source_after']}`",
                f"- 그 줄을 실행한 테스트 ({len(m.get('selected_tests', []))}개 선택 실행): "
                f"선택 {sel.get('status')} (실행 {sel.get('executed')}, skip {sel.get('skipped')}) · 전체 {full.get('status')} (실행 {full.get('executed')}, skip {full.get('skipped')})",
                "\n### mutant diff\n", "```diff", diff, "```",
                f"\n### 원본 함수 (`{m['commit']}` 시점, {s}–{e}줄)\n", "```python", "\n".join(f"{s + i:>4}  {t}" for i, t in enumerate(original)), "```",
                "\n### 모듈 docstring\n", "```text", doc, "```",
                "\n### 그 줄을 실행한 테스트 id\n", *[f"- `{t}`" for t in m.get("selected_tests", [])],
                f"\n### 커밋 시점 문서 파일 ({len(docs)}개)\n", *[f"- `{p}`" for p in docs],
            ]
    out = OUT / "blind"
    out.mkdir(parents=True, exist_ok=True)
    (out / "packets.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    (out / "selection.json").write_text(json.dumps(picked, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(picked, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
