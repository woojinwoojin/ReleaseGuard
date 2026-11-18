"""Stage 2b.1 V3 실행 (코드 실행 없음, Docker 불필요).

- 기본: B1 seed (eval/artifact_cases_2b1.yaml v3_cases) → docs/eval/v2b1/v3_b1_result.json
- --regression: 2b.0 사례(eval/artifact_cases_2b0.yaml)에 새 V3를 돌려 2b.0 static_result.json의 V3a·V3b와 비교 (메커니즘 코드는 새로 생긴 필드)
- --b2 FILE: B2 고정 목록(JSON, 3단계 산출물) → docs/eval/v2b1/v3_b2_result.json

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2b_1/run_v3.py [--regression | --b2 FILE]
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib2b1 import ROOT, apply_edits, git, rm, source_snapshot, v3_policy2  # noqa: E402

OUT = ROOT / "docs" / "eval" / "v2b1"


def tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="rg2b1_"))


def run_pair(repo: Path, base: str, head: str | None, context: str, case: dict | None) -> dict:
    h, b = tmp(), tmp()
    try:
        if head is None:  # seed: base에 편집
            source_snapshot(repo, base, context, h)
            apply_edits(h, case)
        else:
            source_snapshot(repo, head, context, h)
        source_snapshot(repo, base, context, b)
        t = time.perf_counter()
        r = v3_policy2(h, b)
        r["seconds"] = round(time.perf_counter() - t, 4)
        return r
    finally:
        rm(h)
        rm(b)


def short(r: dict) -> str:
    return r["status"] + (f"({','.join(r['mechanism'])})" if r.get("mechanism") else "")


def b1() -> int:
    cfg = yaml.safe_load((ROOT / "eval" / "artifact_cases_2b1.yaml").read_text(encoding="utf-8"))
    out = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": {}}
    ok = total = 0
    for case in cfg["v3_cases"]:
        src = cfg["sources"][case["source"]]
        repo = (ROOT / src["repo"]).resolve()
        r = run_pair(repo, src["commit"], None, src["context"], case)
        exp = case["expected"]
        got = [r["V3a"]["status"], r["V3b"]["status"]]
        match = {"V3a": got[0] == exp[0], "V3b": got[1] == exp[1]}
        if case.get("mechanism"):
            match["mechanism"] = all(case["mechanism"] in r[k].get("mechanism", []) for k in ("V3a", "V3b"))
        out["results"][case["id"]] = r | {"expected": exp, "expected_mechanism": case.get("mechanism"), "match": match}
        ok += sum(match.values())
        total += len(match)
        flag = "" if all(match.values()) else "   ← 기대와 다름"
        print(f"{case['id']:7} V3a {short(r['V3a']):32} V3b {short(r['V3b']):32} 기대 {exp} {case.get('mechanism') or ''}{flag}")
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v3_b1_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기대 일치 {ok}/{total}")
    return 0


def regression() -> int:
    cfg = yaml.safe_load((ROOT / "eval" / "artifact_cases_2b0.yaml").read_text(encoding="utf-8"))
    old = json.loads((ROOT / "docs" / "eval" / "v2b0" / "static_result.json").read_text(encoding="utf-8"))["results"]
    repo = (ROOT / cfg["repo"]).resolve()
    same = 0
    rows = {}
    for case in cfg["cases"]:
        if case["kind"] == "commit":
            head = git(repo, "rev-parse", case["commit"]).strip()
            try:
                base = git(repo, "rev-parse", f"{head}^").strip()
            except Exception:  # noqa: BLE001
                base = None
            r = run_pair(repo, base, head, ".", None) if base else None
        else:
            r = run_pair(repo, cfg["base"], None, ".", case)
        got = [r["V3a"]["status"], r["V3b"]["status"]]
        was = [old[case["id"]]["V3a"]["status"], old[case["id"]]["V3b"]["status"]]
        rows[case["id"]] = {"new": got, "old": was, "mechanism": [r["V3a"].get("mechanism"), r["V3b"].get("mechanism")]}
        same += got == was
        print(f"{case['id']:4} 2b.0 {was} → 2b.1 {got} {rows[case['id']]['mechanism']}{'' if got == was else '   ← 다름'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v3_regression_2b0.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"2b.0과 같음 {same}/{len(cfg['cases'])}")
    return 0


def b2(path: Path) -> int:
    items = json.loads(path.read_text(encoding="utf-8"))
    out = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "source_list": str(path.relative_to(ROOT)), "results": {}}
    for it in items["commits"]:
        repo = (ROOT / items["clones"][it["repo"]]).resolve()
        r = run_pair(repo, it["base_sha"], it["head_sha"], ".", None)
        out["results"][f"{it['repo']}@{it['head_sha'][:10]}"] = r | {"label": it.get("label"), "label_status": it.get("label_status")}
        print(f"{it['repo']:20} {it['head_sha'][:10]} V3a {short(r['V3a']):28} V3b {short(r['V3b']):28} 라벨 {it.get('label')}")
    out["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v3_b2_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--regression", action="store_true")
    ap.add_argument("--b2", type=Path)
    a = ap.parse_args()
    raise SystemExit(regression() if a.regression else b2(a.b2) if a.b2 else b1())
