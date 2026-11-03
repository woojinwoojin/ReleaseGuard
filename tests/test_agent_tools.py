import json

import pytest

from releaseguard.agent_tools import MAX_READ_LINES, RepoView, ToolError, check_path, run_tool
from releaseguard.git_ops import collect


@pytest.fixture
def view(repo):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x\n")
    repo.write("src/report.py", "from src.metrics.engine import compute\n\nprint(compute(1))\n")
    repo.write("big.txt", "".join(f"line {i}\n" for i in range(1, 501)))
    repo.commit("base")
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x * 2\n")
    repo.write("notes.txt", "")
    repo.commit("change")
    repo.write("working_only.py", "compute\n")  # 커밋하지 않은 파일은 도구에 보이면 안 된다
    change = collect(repo.path, "HEAD~1", "HEAD")
    return RepoView(change.repo, change.merge_base, change.head_sha)


@pytest.mark.parametrize("bad", ["", "/etc/passwd", "C:/Windows", "../secret", "src/../../x"])
def test_check_path_rejects_outside(bad):
    with pytest.raises(ToolError):
        check_path(bad)


def test_check_path_normalizes():
    assert check_path("src\\metrics\\") == "src/metrics"


def test_git_diff_single_file(view):
    out = view.git_diff("src/metrics/engine.py")
    assert "+    return x * 2" in out["diff"]
    assert out["truncated"] is False


def test_read_file_numbers_and_caps(view):
    out = view.read_file("big.txt", None, None)
    assert out["total_lines"] == 500
    assert (out["start_line"], out["end_line"]) == (1, MAX_READ_LINES)
    assert out["content"].splitlines()[0] == "1: line 1"
    assert view.read_file("big.txt", 499, 900)["content"] == "499: line 499\n500: line 500"


def test_search_code_reads_head_not_working_tree(view):
    out = view.search_code("compute", None)
    assert {(h["path"], h["line"]) for h in out["hits"]} == {
        ("src/metrics/engine.py", 1),
        ("src/report.py", 1),
        ("src/report.py", 3),
    }
    assert view.search_code("nothing_matches_this", None)["total"] == 0
    assert view.search_code("compute", "src/metrics")["total"] == 1


def test_list_files_prefix(view):
    assert view.list_files("src")["files"] == ["src/metrics/engine.py", "src/report.py"]


def test_run_tool_returns_errors_as_json(view):
    body, ok = run_tool(view, "read_file", json.dumps({"path": "nope.py", "start_line": None, "end_line": None}))
    assert not ok and "head에 없는 파일" in json.loads(body)["error"]
    body, ok = run_tool(view, "rm_rf", "{}")
    assert not ok
    body, ok = run_tool(view, "list_files", "not json")
    assert not ok
    body, ok = run_tool(view, "list_files", json.dumps({"path_prefix": None}))
    assert ok and json.loads(body)["total"] == 4
