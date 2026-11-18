"""Stage 2b.1 3단계: B2 실제 CI 변경 이력 목록 추출 (규칙 eval/b2_selection_2b1.yaml, 실행 전 커밋 a8a3b3c).

V3 판단 코드를 쓰지 않는다. 트리거(on 키)만 YAML로 읽는다.
저장소는 .rg/external/<owner>_<name> 에 부분 clone(--filter=blob:none)해 둔다. 기본 브랜치 HEAD를 기록한다.
결과: docs/eval/v2b1/b2_candidates.json (라벨 칸은 비어 있음)

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2b_1/select_b2.py
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib2b1 import ROOT, triggers  # noqa: E402

RULE = yaml.safe_load((ROOT / "eval" / "b2_selection_2b1.yaml").read_text(encoding="utf-8"))
OUT = ROOT / "docs" / "eval" / "v2b1" / "b2_candidates.json"
WF = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
BUMP = re.compile(r"^(Bump|bump|chore\(deps\)|build\(deps\))")


def git(repo: Path, *a: str, check: bool = True) -> str:
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), *a], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=check).stdout


def blob(repo: Path, sha: str, path: str) -> str | None:
    p = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{path}"], capture_output=True)
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def policy(text: str | None) -> bool | None:
    """push·pull_request 트리거가 있으면 True, 없으면 False, 파싱 실패면 None. 파일 없음은 False."""
    if text is None:
        return False
    try:
        wf = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(wf, dict):
        return None
    return any(e in triggers(wf) for e in ("push", "pull_request"))


def main(include_merges: bool = False, out_path: Path = OUT) -> int:
    since = datetime.fromisoformat(RULE["period"]["since"].replace("Z", "+00:00"))
    until = datetime.fromisoformat(RULE["period"]["until"].replace("Z", "+00:00"))
    out = {"rule_file": "eval/b2_selection_2b1.yaml", "extracted": datetime.now().isoformat(timespec="seconds"), "clones": {}, "repo_heads": {},
           "commits": [], "skipped": []}
    for name in RULE["repos"]:
        rel = f".rg/external/{name.replace('/', '_')}"
        repo = ROOT / rel
        out["clones"][name] = rel
        branch = git(repo, "symbolic-ref", "--short", "HEAD").strip()
        out["repo_heads"][name] = {"branch": branch, "head": git(repo, "rev-parse", branch).strip()}
        log = git(repo, "log", "--first-parent", "--format=%H%x09%P%x09%cI%x09%an%x09%s", branch, "--", ".github/workflows")
        picked, bots, seen_patch = [], 0, set()
        for line in log.splitlines():
            sha, parents, cdate, author, subject = line.split("\t", 4)
            when = datetime.fromisoformat(cdate)
            if when >= until:
                continue
            if when < since or len(picked) >= RULE["cap"]["per_repo"]:
                break
            ps = parents.split()
            if len(ps) > 2 or (len(ps) == 2 and not include_merges):
                out["skipped"].append({"repo": name, "sha": sha, "why": "부모 3개 이상인 병합" if len(ps) > 2 else "병합 커밋"})
                continue
            files = [f for f in git(repo, "diff", "--name-only", ps[0], sha).splitlines() if WF.match(f)]
            if not files:
                continue
            diff = git(repo, "diff", ps[0], sha, "--", *files)
            pid = subprocess.run(["git", "-C", str(repo), "patch-id", "--stable"], input=diff.encode("utf-8"), capture_output=True).stdout.decode().split()
            pid = pid[0] if pid else None
            if pid and pid in seen_patch:
                out["skipped"].append({"repo": name, "sha": sha, "why": "같은 patch-id 재적용"})
                continue
            pol = [(f, policy(blob(repo, ps[0], f)), policy(blob(repo, sha, f))) for f in files]
            if all(b is None and h is None for _, b, h in pol):
                out["skipped"].append({"repo": name, "sha": sha, "why": "워크플로 YAML이 base·head 모두 파싱 안 됨"})
                continue
            if not any(b or h for _, b, h in pol):
                continue  # 정책 이벤트 없는 워크플로만 바뀜 (기록하지 않는 일반 비대상)
            changed = [ln for ln in diff.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
            uses_only = bool(changed) and all(re.match(r"^[+-]\s*(-\s*)?uses:", ln) or not ln[1:].strip() for ln in changed)
            is_bot = author.endswith("[bot]") or bool(BUMP.match(subject)) or uses_only
            if is_bot and bots >= RULE["cap"]["bot_or_dependency_per_repo"]:
                out["skipped"].append({"repo": name, "sha": sha, "why": "봇·의존성 상한"})
                continue
            if pid:
                seen_patch.add(pid)
            bots += is_bot
            picked.append({"repo": name, "head_sha": sha, "base_sha": ps[0], "committed_at": cdate, "author_is_bot_or_dep": is_bot,
                           "changed_workflows": files, "message_first_line": subject[:200],
                           "is_merge": len(ps) == 2, "selected_reason": "규칙 include 충족" + (" (봇·의존성)" if is_bot else ""),
                           "label": None, "label_reason": None, "label_status": None})
        out["commits"] += picked
        print(f"{name:20} {len(picked):2}개 (봇·의존성 {bots}) {out['repo_heads'][name]['head'][:10]}")
    out["include_merges"] = include_merges
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("총", len(out["commits"]), "· 건너뜀", len(out["skipped"]))
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--original-rule", action="store_true", help="P1 이전 규칙(병합 제외)으로 추출 — 비교용")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    raise SystemExit(main(not a.original_rule and RULE["merge_policy"]["include_merges"], a.out))
