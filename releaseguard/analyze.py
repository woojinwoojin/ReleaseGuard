"""1~6단계를 순서대로 실행하고 결과를 dict로 만든다 (JSON으로 그대로 저장)."""

from dataclasses import asdict
from pathlib import Path

from . import __version__
from .classify import RuleSet, classify
from .decide import decide
from .git_ops import collect, list_files, read_file
from .related_tests import Coverage, coverage_status, find_related


def analyze(repo: Path, base: str, head: str, ruleset: RuleSet) -> dict:
    change = collect(repo, base, head)

    files = []
    for f in change.files:
        category, rule_id = classify(f.path, ruleset)
        files.append({**asdict(f), "category": category, "evidence": f"rule:{rule_id}" if rule_id else None})

    # 관련 테스트 후보: head의 테스트 파일 + 이번 변경에서 삭제된 테스트(base 쪽 내용)
    is_test = lambda p: classify(p, ruleset)[0] == "test"  # noqa: E731
    deleted_tests = {f["path"] for f in files if f["category"] == "test" and f["status"] == "D"}
    changed_tests = {f["path"] for f in files if f["category"] == "test" and f["status"] != "D"}
    tests = {
        p: read_file(change.repo, change.head_sha, p) if p.endswith(".py") else ""
        for p in list_files(change.repo, change.head_sha)
        if is_test(p)
    }
    for p in deleted_tests:
        tests[p] = read_file(change.repo, change.merge_base, p) if p.endswith(".py") else ""

    coverage = []
    for f in files:
        if f["category"] != "source" or f["status"] == "D":
            continue
        related = find_related(f["path"], tests)
        coverage.append(Coverage(f["path"], coverage_status(related, changed_tests, deleted_tests), related))

    decision, findings = decide(files, coverage, change.added_lines, ruleset.secrets)

    by_category: dict[str, int] = {}
    for f in files:
        by_category[f["category"]] = by_category.get(f["category"], 0) + 1
    return {
        "tool": "releaseguard",
        "version": __version__,
        "rules_version": ruleset.version,
        "repo": str(change.repo),
        "base": base,
        "head": head,
        "merge_base": change.merge_base,
        "head_sha": change.head_sha,
        "summary": {
            "files": len(files),
            "added": sum(f["added"] or 0 for f in files),
            "deleted": sum(f["deleted"] or 0 for f in files),
            "by_category": dict(sorted(by_category.items())),
        },
        "changed_files": files,
        "coverage": [asdict(c) for c in coverage],
        "impact": None,  # 4단계 에이전트 (미구현)
        "decision": decision,
        "findings": [asdict(f) for f in findings],
    }
