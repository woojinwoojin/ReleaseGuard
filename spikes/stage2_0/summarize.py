"""Stage 2.0 spike 결과 집계: mutation_result.json → 질문 1~6에 필요한 수치와 mutant 표 (Markdown).

사용: .venv/Scripts/python spikes/stage2_0/summarize.py out/spike/2_0/mutation_result.json
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

path = Path(sys.argv[1])
d = json.loads(path.read_text(encoding="utf-8"))
ms = d["mutants"]
ran = [m for m in ms if "full" in m]


def pct(a, b):
    return f"{a}/{b}" + (f" ({a / b:.0%})" if b else "")


lines = [
    f"# Stage 2.0 spike 결과 — {d['repo']}",
    "",
    f"- Cosmic Ray: {d['setup']['cosmic_ray']} · mutant {len(ms)} (상한 {d['max']}, 커밋당 {d.get('per_commit')}) · 전체 {d['seconds']}초",
    f"- 대상 저장소 보존: {d['repo_preserved']} (HEAD·git status 전후 비교)",
    f"- 지정한 줄에만 변경: {pct(sum(m['on_target_line'] for m in ms), len(ms))}",
    f"- 원본 바이트 복구: {pct(sum(m['restored'] for m in ms), len(ms))}",
    f"- 결과(전체 실행 기준): {dict(Counter(m['result'] for m in ms))}",
    f"- KILLED 실패 종류(전체 실행): {dict(Counter(m['full']['kind'] for m in ran if m['full']['status'] == 'KILLED'))}",
    f"- 관련 테스트만 vs 전체 일치: {pct(sum(m['selected_agrees_with_full'] for m in ran), len(ran))}",
    f"- 불일치: {[(m['commit'], m['file'], m['line'], m['selected']['status'], m['full']['status']) for m in ran if not m['selected_agrees_with_full']]}",
]
sel = [m["selected"]["seconds"] for m in ran]
full = [m["full"]["seconds"] for m in ran]
if ran:
    lines += [
        f"- mutant당 시간(초): 관련 테스트만 중앙값 {statistics.median(sel):.2f} (최대 {max(sel):.2f}) · 전체 중앙값 {statistics.median(full):.2f} (최대 {max(full):.2f})",
        f"- 관련 테스트 수: 중앙값 {statistics.median(len(m['selected_tests']) for m in ran)} (최소 {min(len(m['selected_tests']) for m in ran)}, 최대 {max(len(m['selected_tests']) for m in ran)})",
    ]
lines += ["", "## 커밋", "", "| 커밋 | 기준 전체 실행 | covered 바뀐 줄 | Cosmic Ray 전체 mutation | 고른 mutant |", "|---|---|---|---|---|"]
for c in d["commits"]:
    if "files" not in c:
        lines.append(f"| `{c['sha']}` | {c.get('skipped')} | - | - | 0 |")
        continue
    n = sum(m["commit"] == c["sha"] for m in ms)
    lines.append(f"| `{c['sha']}` {c['subject'][:50]} | {c['baseline_full']} | {sum(len(v) for v in c['files'].values())} | {sum(c.get('cosmic_ray_total', {}).values())} | {n} |")
lines += ["", "## mutant", "", "| # | 커밋 | 위치 | 연산자 | 변경 | 관련만 | 전체 | 실패 종류 |", "|---|---|---|---|---|---|---|---|"]
for i, m in enumerate(ms, 1):
    sel_s = m.get("selected", {}).get("status", "-")
    full_s = m.get("full", {}).get("status", m["result"])
    change = f"`{m['source_before'][:60]}` → `{(m['source_after'] or '?')[:60]}`".replace("|", "\\|")
    lines.append(f"| {i} | `{m['commit']}` | `{m['file']}:{m['line']}` | {m['operator'].removeprefix('core/')} | {change} | {sel_s} | {full_s} | {m.get('full', {}).get('kind') or '-'} |")
out = path.with_suffix(".md")
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines[:14]))
