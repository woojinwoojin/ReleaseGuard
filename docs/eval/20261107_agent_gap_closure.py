"""Stage 1.6 Gap Closure 검증 (보고서 #8). 프로토콜 순서 F3 → N2 → F1 → B2, 실행 1의 제안을 사람이 코드로 옮긴다.

대상 커밋의 임시 스냅샷에서만 실행한다. 대상 저장소와 작업 폴더는 바꾸지 않는다.
- 실행 가능: 테스트가 통과한다
- Gap Closure: 대상 공백 줄을 coverage가 실행했다고 본다
- 동작 검증: 대상 줄을 바꾸면 테스트가 실패한다

쓰는 법: python docs/eval/20261107_agent_gap_closure.py <임시 폴더> <결과 json>
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path

RG = Path(__file__).resolve().parents[2]
TOOLS = RG / ".rg" / "tools"
PREDICT = RG.parent / "predict-success"
WEEK2 = RG.parent / "2026-10" / "week2-tool-calling"
WEEK3 = RG.parent / "2026-10" / "week3-fastapi-ui"

CASES = [
    {
        "id": "F3", "repo": WEEK2, "sha": "5b31f70", "path": "tools.py", "lines": [213],
        "test_file": "tests/test_tools.py", "test": "test_compare_periods_unknown_category_returns_error",
        "code": '''

def test_compare_periods_unknown_category_returns_error(df):
    result = compare_periods(df, "2024-01", "2024-01", "2024-02", "2024-02", category="C")
    assert result == {"error": "없는 카테고리: C", "available": ["A", "B"]}
''',
        "human_changes": "없음 (기존 df fixture가 제안의 A·B 데이터와 같아 그대로 씀)",
        "mutation": ("            return error\n        if \"sub_category\" not in df:", "            pass\n        if \"sub_category\" not in df:"),
    },
    {
        "id": "N2", "repo": PREDICT, "sha": "c7733b3", "path": "src/normalization/selection.py", "lines": [16, 17, 18, 19, 20, 21, 22, 24],  # 23은 22에서 시작한 문장의 이어지는 줄
        "test_file": "tests/test_dart_collector.py", "test": "test_load_published_filings_collects_only_annual_reports_from_response_json",
        "code": '''

def test_load_published_filings_collects_only_annual_reports_from_response_json(tmp_path):
    from src.normalization.selection import load_published_filings

    path = tmp_path / "01009789" / "api" / "list" / "A001" / "x" / "y" / "z" / "response.json"
    path.parent.mkdir(parents=True)
    common = {"corp_code": "01009789", "rcept_dt": "20260318"}
    path.write_text(json.dumps({"list": [
        {**common, "rcept_no": "20260318000694", "report_nm": "사업보고서 (2025.12)"},
        {**common, "rcept_no": "20250814000001", "report_nm": "반기보고서 (2025.06)"},
    ]}), encoding="utf-8")
    published = load_published_filings(tmp_path)
    assert set(published) == {"20260318000694"}
    assert published["20260318000694"]["bsns_year"] == 2025
    assert published["20260318000694"]["correction"] is None
''',
        "human_changes": "import 1줄, 제안에 없던 응답 항목의 필수 필드(corp_code·rcept_dt·rcept_no) 채움",
        "mutation": ("            if parsed:\n", "            if not parsed:\n"),
    },
    {
        "id": "F1", "repo": PREDICT, "sha": "f2d690e", "path": "src/market/run_market.py", "lines": [27, 28, 29, 30],
        "test_file": "tests/test_market.py", "test": "test_latest_raw_returns_latest_run_or_raises_when_missing",
        "code": '''

def test_latest_raw_returns_latest_run_or_raises_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(run_market, "ROOT", tmp_path)
    source = tmp_path / "raw"
    for name in ("run_a", "run_b"):
        (source / name).mkdir(parents=True)
        (source / name / "metadata.json").write_text("{}", encoding="utf-8")
    (source / "run_c").mkdir()  # metadata.json 없음 → 제외
    assert run_market.latest_raw("raw") == source / "run_b"
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        run_market.latest_raw("empty")
''',
        "human_changes": "ROOT를 monkeypatch로 바꾸는 코드 (제안은 '임시 ROOT'라고만 적음)",
        "mutation": ("    return runs[-1]\n", "    return runs[0]\n"),
    },
    {
        "id": "B2", "repo": WEEK3, "sha": "8c05dc5", "path": "api.py", "lines": [349, 350, 351],
        "test_file": "tests/test_api.py", "test": "test_chat_stream_unexpected_exception_is_generic_error_event",
        "code": '''

def test_chat_stream_unexpected_exception_is_generic_error_event(http, dataset_id, tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise ValueError("boom")

    use_fake_llm([])
    monkeypatch.setattr(api, "run_chat_agent", boom)
    events = read_sse(http, {"dataset_id": dataset_id, "question": "q"})
    assert [name for name, _ in events] == ["error"]
    assert events[-1][1]["detail"] == "서버 오류로 답변을 만들지 못했습니다."
    conn = api.db.connect(tmp_path / "app.db")
    assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
''',
        "human_changes": "use_fake_llm([]) 1줄 (제안에 없던 get_client 대체), boom 함수, db를 api.db로",
        "mutation": ('events.put(("error", {"detail": "서버 오류로 답변을 만들지 못했습니다."}))', 'events.put(("error", {"detail": "내부 오류"}))'),
    },
]


def snapshot(repo: Path, sha: str, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    data = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=BytesIO(data)) as tar:
        tar.extractall(target, filter="data")


def run(repo: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "OPENAI_API_KEY")}
    env["PYTHONPATH"] = str(TOOLS)
    env["PYTHONIOENCODING"] = "utf-8"
    python = repo / ".venv" / "Scripts" / "python.exe"
    return subprocess.run([str(python), *args], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)


def covered(repo: Path, cwd: Path, path: str) -> set[int]:
    run(repo, cwd, "-m", "coverage", "json", "-o", "cov.json", "-q")
    report = json.loads((cwd / "cov.json").read_text(encoding="utf-8"))
    return set(report["files"].get(path.replace("/", os.sep), report["files"].get(path, {})).get("executed_lines", []))


def check(case: dict, root: Path) -> dict:
    work = root / case["id"]
    snapshot(case["repo"], case["sha"], work)
    with (work / case["test_file"]).open("a", encoding="utf-8") as f:
        f.write(case["code"])
    node = f"{case['test_file']}::{case['test']}"
    first = run(case["repo"], work, "-m", "coverage", "run", "--source=.", "-m", "pytest", "-q", "-p", "no:cacheprovider", node)
    passed = first.returncode == 0
    executed = covered(case["repo"], work, case["path"])
    missing = [n for n in case["lines"] if n not in executed]

    source = work / case["path"]
    text = source.read_text(encoding="utf-8")
    old, new = case["mutation"]
    assert text.count(old) == 1, (case["id"], text.count(old))
    source.write_text(text.replace(old, new), encoding="utf-8")
    mutated = run(case["repo"], work, "-m", "pytest", "-q", "-p", "no:cacheprovider", node)
    return {
        "id": case["id"], "commit": case["sha"], "target": f"{case['path']}:{case['lines'][0]}-{case['lines'][-1]}",
        "runnable": passed, "gap_lines": len(case["lines"]), "gap_lines_executed": len(case["lines"]) - len(missing), "missing": missing,
        "behavior_checked": mutated.returncode != 0, "human_changes": case["human_changes"],
        "output": None if passed else first.stdout[-900:],
    }


def hypothesis_b1(root: Path) -> dict:
    """B1: 데이터 파일이 있으면 skip이 풀리고 공백 줄이 실행되는가."""
    out = {}
    for label, with_data in (("without_data", False), ("with_data", True)):
        work = root / f"B1_{label}"
        snapshot(WEEK3, "12b9eb3", work)
        if with_data:
            (work / "data").mkdir(exist_ok=True)
            shutil.copy(WEEK3 / "data" / "Sample - Superstore.csv", work / "data")
        done = run(WEEK3, work, "-m", "coverage", "run", "--source=.", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_app.py")
        executed = covered(WEEK3, work, "app.py")
        target = list(range(181, 207))
        out[label] = {"summary": done.stdout.strip().splitlines()[-1] if done.stdout.strip() else "", "executed_in_181_206": sorted(n for n in target if n in executed)}
    return out


def main() -> None:
    root, result = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [check(c, root) for c in CASES]
    data = {"gap_closure": rows, "b1_hypothesis": hypothesis_b1(root)}
    result.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
