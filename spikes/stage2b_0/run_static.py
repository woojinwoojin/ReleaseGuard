"""Stage 2b.0 9장 2단계: V1·V3 실행 (Docker 불필요, 코드 실행 없음).

사례: eval/artifact_cases_2b0.yaml (실행 전 고정 9dc0ba3). 결과: docs/eval/v2b0/static_result.json
결과는 대상 저장소 밖에 쓰고, 대상 저장소 HEAD·작업 트리가 그대로인지 확인한다.

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2b_0/run_static.py
"""

import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifactlib import ROOT, case_snapshot, git, rm, tmpdir, v1_entrypoint, v3_policy  # noqa: E402
from releaseguard.runner import snapshot  # noqa: E402

CASES = ROOT / "eval" / "artifact_cases_2b0.yaml"
OUT = ROOT / "docs" / "eval" / "v2b0"


def main() -> int:
    cfg = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    repo = (ROOT / cfg["repo"]).resolve()
    before = [git(repo, "rev-parse", "HEAD").strip(), git(repo, "status", "--porcelain")]
    out = {"cases_file": "eval/artifact_cases_2b0.yaml", "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": {}}
    for case in cfg["cases"]:
        head_dir, base_dir = tmpdir(), tmpdir()
        try:
            t0 = time.perf_counter()
            info = case_snapshot(repo, cfg["base"], case, head_dir)
            snapshot(repo, info["compare_base"], base_dir)
            t1 = time.perf_counter()
            v1 = v1_entrypoint(head_dir)
            t2 = time.perf_counter()
            v3 = v3_policy(head_dir, base_dir)
            t3 = time.perf_counter()
        finally:
            rm(head_dir)
            rm(base_dir)
        got = {"V1": v1["status"], "V3a": v3["V3a"]["status"], "V3b": v3["V3b"]["status"]}
        exp = {k: case["expected"][k] for k in got}
        rec = {"id": case["id"], "head": info["head"], "compare_base": info["compare_base"][:7], "V1": v1, **v3,
               "V2": {"status": "NOT_RUN", "reason": "9장 3단계 (Docker 데몬 필요)"},
               "expected": exp, "match": {k: got[k] == exp[k] for k in got},
               "seconds": {"snapshot": round(t1 - t0, 3), "V1": round(t2 - t1, 4), "V3": round(t3 - t2, 4)}}
        out["results"][case["id"]] = rec
        flag = "" if all(rec["match"].values()) else "   ← 기대와 다름 " + str({k: exp[k] for k, m in rec["match"].items() if not m})
        print(f"{case['id']:4} V1 {got['V1']:12} V3a {got['V3a']:12} V3b {got['V3b']:12}{flag}")
    after = [git(repo, "rev-parse", "HEAD").strip(), git(repo, "status", "--porcelain")]
    out["repo_preserved"] = before == after
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "static_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    total = sum(len(r["match"]) for r in out["results"].values())
    ok = sum(sum(r["match"].values()) for r in out["results"].values())
    print(f"기대 일치 {ok}/{total} · 대상 저장소 보존 {out['repo_preserved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
