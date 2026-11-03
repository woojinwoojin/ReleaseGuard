"""임시 git 저장소로 1~6단계를 끝까지 실행한다."""

import json

import pytest

from releaseguard.__main__ import main
from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.git_ops import GitError, collect
from releaseguard.report import to_markdown

RULES = load_rules()


@pytest.fixture
def base(repo):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x\n")
    repo.write("tests/test_metrics.py", "from src.metrics.engine import compute\n\ndef test_compute():\n    assert compute(1) == 1\n")
    repo.write("README.md", "# demo\n")
    return repo.commit("base")


def run(repo):
    return analyze(repo.path, "HEAD~1", "HEAD", RULES)


def test_collect_status_and_lines(repo, base):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x * 2\n")
    repo.git("mv", "README.md", "GUIDE.md")
    repo.write("new.py", "a = 1\n")
    repo.commit("change")
    change = collect(repo.path, "HEAD~1", "HEAD")
    by_path = {f.path: f for f in change.files}
    assert by_path["src/metrics/engine.py"].status == "M"
    assert (by_path["src/metrics/engine.py"].added, by_path["src/metrics/engine.py"].deleted) == (1, 1)
    assert by_path["GUIDE.md"].status == "R" and by_path["GUIDE.md"].old_path == "README.md"
    assert by_path["new.py"].status == "A"
    assert change.added_lines["src/metrics/engine.py"] == [(2, "    return x * 2")]


def test_docs_only_is_safe(repo, base):
    repo.write("README.md", "# demo\n\nmore\n")
    repo.commit("docs")
    result = run(repo)
    assert result["decision"] == "SAFE"
    assert result["findings"] == []


def test_source_with_test_change_is_safe(repo, base):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x * 2\n")
    repo.write("tests/test_metrics.py", "from src.metrics.engine import compute\n\ndef test_compute():\n    assert compute(1) == 2\n")
    repo.commit("both")
    result = run(repo)
    assert result["decision"] == "SAFE"
    assert result["coverage"][0]["status"] == "test_changed"


def test_source_without_test_change_needs_review(repo, base):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x * 2\n")
    repo.write("src/util.py", "def f():\n    pass\n")
    repo.commit("src only")
    result = run(repo)
    assert result["decision"] == "REVIEW REQUIRED"
    rules = {f["rule_id"]: f["evidence"] for f in result["findings"]}
    assert rules == {"R01": ["src/metrics/engine.py"], "R02": ["src/util.py"]}


def test_deleted_related_test_blocks(repo, base):
    repo.write("src/metrics/engine.py", "def compute(x):\n    return x * 2\n")
    repo.git("rm", "-q", "tests/test_metrics.py")
    repo.commit("drop test")
    result = run(repo)
    assert result["decision"] == "BLOCK"
    assert [f["rule_id"] for f in result["findings"]] == ["B02"]


def test_secret_blocks_without_leaking_value(repo, base):
    key = "sk-" + "a" * 30
    repo.write("settings.py", f'KEY = "{key}"\n')
    repo.commit("oops")
    result = run(repo)
    assert result["decision"] == "BLOCK"
    assert result["findings"][0] == {
        "rule_id": "B01",
        "decision": "BLOCK",
        "message": "추가된 줄에 비밀값 패턴이 있습니다.",
        "evidence": ["settings.py:1 (openai_key)"],
    }
    assert key not in json.dumps(result)


def test_config_deps_data_need_review(repo, base):
    repo.write("configs/a.yaml", "x: 1\n")
    repo.write("requirements.txt", "pyyaml\n")
    repo.write("data/manual/x.csv", "a,b\n")
    repo.commit("misc")
    result = run(repo)
    assert [f["rule_id"] for f in result["findings"]] == ["R03", "R04", "R05"]


def test_three_dot_uses_merge_base(repo, base):
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("src/util.py", "x = 1\n")
    repo.commit("feature work")
    repo.git("checkout", "-q", "main")
    repo.write("README.md", "# changed on main\n")
    repo.commit("main work")
    result = analyze(repo.path, "main", "feature", RULES)
    assert [f["path"] for f in result["changed_files"]] == ["src/util.py"]
    assert result["merge_base"] == base


def test_bad_ref_raises(repo, base):
    with pytest.raises(GitError):
        analyze(repo.path, "nope", "HEAD", RULES)


def test_cli_writes_json_and_markdown(repo, base, tmp_path):
    repo.write("src/util.py", "x = 1\n")
    head = repo.commit("add util")
    out = tmp_path / "out"
    assert main(["analyze", "--repo", str(repo.path), "--base", "HEAD~1", "--out", str(out)]) == 0
    [json_file] = out.glob(f"*_{head[:7]}.json")
    result = json.loads(json_file.read_text(encoding="utf-8"))
    assert result["decision"] == "REVIEW REQUIRED"
    md = json_file.with_suffix(".md").read_text(encoding="utf-8")
    assert md.startswith("# ReleaseGuard 보고서 — REVIEW REQUIRED")
    assert to_markdown(result) == md
