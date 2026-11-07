"""함수별 공백 그룹: 줄 근거를 잃지 않고, 판정을 바꾸지 않으며, 순서가 안정적이어야 한다."""

from dataclasses import asdict, replace
from pathlib import Path

from conftest import PY

from releaseguard.analyze import analyze
from releaseguard.classify import load_rules
from releaseguard.evaluate import review_cost, review_order_metrics
from releaseguard.gap_groups import GapGroup, file_groups, group_gaps, order_key, preservation, review_priority
from releaseguard.gaps import FileLines
from releaseguard.report import to_markdown

SOURCE = """import os
LIMIT = int(os.environ.get("L", "1"))


class Job:
    retries = compute()

    @staticmethod
    def run(x):
        def inner():
            return x

        return inner()


def top():
    return 1
"""


def lines_of(path, gaps, status_extra=None):
    numbers = [n for s, e in gaps for n in range(s, e + 1)]
    status = {n: "gap" for n in numbers} | (status_extra or {})
    gap_count = sum(v == "gap" for v in status.values())
    return FileLines(path, True, len(status), gap_lines=gap_count, gaps=gaps, line_status=status)


def by_name(groups):
    return {g.name: g for g in groups}


def test_groups_function_method_nested_class_body_and_module():
    fl = lines_of("a.py", [(2, 2), (6, 6), (9, 9), (11, 11), (13, 13), (17, 17)])
    g = by_name(file_groups(fl, SOURCE))
    assert (g["<module>"].kind, g["<module>"].gap_line_numbers, g["<module>"].start_line) == ("module", [2], 2)
    assert (g["Job"].kind, g["Job"].gap_line_numbers) == ("class_body", [6])
    assert (g["Job.run"].kind, g["Job.run"].gap_line_numbers, g["Job.run"].start_line) == ("function", [9, 13], 8)  # 데코레이터부터
    assert g["Job.run.inner"].gap_line_numbers == [11]  # 가장 안쪽 함수
    assert g["top"].gap_line_numbers == [17]


def test_range_is_split_at_group_boundary_and_keeps_non_executable_bridge():
    # 줄 단위 범위 하나가 함수 경계를 넘으면 나뉜다 (사이 줄은 실행 불가라 lines에서는 한 범위)
    src = "def a():\n    x = 1\n\n    return x\n\n\ndef b():\n    return 2\n"
    fl = lines_of("a.py", [(2, 8)], {n: "not_executable" for n in (3, 5, 6, 7)})
    g = by_name(file_groups(fl, src))
    assert g["a"].gap_ranges == [(2, 4)] and g["a"].gap_line_numbers == [2, 4]  # 3은 빈 줄이라 범위 안, 세지는 않음
    assert g["b"].gap_ranges == [(8, 8)]


def test_outer_function_split_around_nested_function_keeps_two_ranges():
    fl = lines_of("a.py", [(9, 13)], {10: "gap", 11: "gap", 12: "not_executable", 13: "gap"})
    g = by_name(file_groups(fl, SOURCE))
    assert g["Job.run"].gap_ranges == [(9, 9), (13, 13)]
    assert g["Job.run"].gap_line_numbers == [9, 13]
    assert sorted(n for x in g.values() for n in x.gap_line_numbers) == [9, 10, 11, 13]


def test_unparsable_or_missing_source_is_kept_as_unmapped():
    fl = lines_of("a.py", [(1, 2), (5, 5)])
    for source in ("def broken(:\n", None):
        [g] = file_groups(fl, source)
        assert (g.kind, g.name, g.start_line, g.gap_lines, g.gap_ranges) == ("unmapped", "<unmapped>", 1, 3, [(1, 2), (5, 5)])


def test_order_low_last_then_size_path_start_name():
    def g(path, name, start, size, priority="NORMAL"):
        return GapGroup(path, "function", name, start, size, review_priority=priority)

    groups = [
        g("experiments/x.py", "big", 1, 100, "LOW"),
        g("b.py", "f", 1, 5),
        g("a.py", "late", 9, 5),
        g("a.py", "z", 3, 5),
        g("a.py", "y", 3, 5),
        g("c.py", "most", 1, 6),
    ]
    want = [("c.py", "most"), ("a.py", "y"), ("a.py", "z"), ("a.py", "late"), ("b.py", "f"), ("experiments/x.py", "big")]
    assert [(x.path, x.name) for x in sorted(groups, key=order_key)] == want
    assert [(x.path, x.name) for x in sorted(reversed(groups), key=order_key)] == want  # 입력 순서와 무관


def test_low_only_for_declared_paths():
    low = ("experiments/**",)
    assert review_priority("experiments/a/b.py", low) == "LOW"
    assert review_priority("src/experiments/b.py", low) == "NORMAL"  # 폴더 이름만 보고 추측하지 않는다
    assert review_priority("experiments/b.py", ()) == "NORMAL"
    assert load_rules().low_priority_paths == low


def test_group_gaps_skips_files_without_gaps_and_preservation_counts():
    clean = FileLines("clean.py", True, 1, line_status={1: "covered"})
    fl = lines_of("a.py", [(2, 2), (17, 17)])
    groups = [asdict(g) for g in group_gaps([clean, fl], lambda p: SOURCE)]
    as_json = [{"path": fl.path, "line_status": {str(k): v for k, v in fl.line_status.items()}}]
    assert preservation(as_json, groups) == {"lines": 2, "missing": 0, "extra": 0, "duplicate": 0}
    broken = [{**groups[0], "gap_line_numbers": []}, groups[1], groups[1]]
    result = preservation(as_json, broken)
    assert (result["missing"], result["duplicate"]) == (1, 1)


def test_low_priority_does_not_change_decision_or_line_gaps(pyrepo):
    """같은 커밋을 LOW 선언 유무로 돌려 판정·규칙·줄 공백이 같고 review_priority만 달라야 한다."""
    pyrepo.write("experiments/run.py", "def go():\n    return 1\n")
    pyrepo.commit("add experiment")
    rules = load_rules()
    declared = analyze(pyrepo.path, "HEAD~1", "HEAD", rules, python=PY)
    undeclared = analyze(pyrepo.path, "HEAD~1", "HEAD", replace(rules, low_priority_paths=()), python=PY)
    for key in ("decision", "scope", "findings", "lines"):
        assert declared[key] == undeclared[key]
    assert "G01" in [f["rule_id"] for f in declared["findings"]]
    assert {g["review_priority"] for g in declared["gap_groups"]} == {"LOW"}
    assert {g["review_priority"] for g in undeclared["gap_groups"]} == {"NORMAL"}


def test_report_lists_groups_and_says_priority_is_not_risk(pyrepo):
    pyrepo.write("experiments/run.py", "def go():\n    return 1\n")
    pyrepo.commit("add experiment")
    text = to_markdown(analyze(pyrepo.path, "HEAD~1", "HEAD", load_rules(), python=PY))
    assert "## 검증 공백 — 함수별 검토 순서" in text
    assert "| 1 | `experiments/run.py` | `go` |" in text
    assert "결함 위험 순서가 아닙니다" in text and "안전하다는 뜻이 아니며" in text


def test_review_cost_counts_lines_until_first_defect_group():
    groups = [
        {"path": "b.py", "gap_lines": 10, "gap_line_numbers": list(range(1, 11))},
        {"path": "a.py", "gap_lines": 3, "gap_line_numbers": [1, 2, 3]},
        {"path": "c.py", "gap_lines": 1, "gap_line_numbers": [7]},
    ]
    cost = review_cost(groups, {("c.py", 7)})
    assert (cost["rank"], cost["lines_read"], cost["source_rank"], cost["source_lines_read"]) == (3, 14, 3, 14)
    cost = review_cost(groups, {("b.py", 4)})
    assert (cost["rank"], cost["lines_read"], cost["source_rank"], cost["source_lines_read"]) == (1, 10, 2, 13)
    assert (cost["lines_to_defect"], cost["source_lines_to_defect"]) == (4, 7)  # 결함 줄까지만 읽으면
    assert review_cost(groups, {("z.py", 1)}) is None  # 결함 줄이 공백이 아니면 재지 않는다
    m = review_order_metrics([cost])
    assert (m["by_gap_size"]["top1"], m["by_gap_size"]["mrr"], m["source_order"]["mrr"]) == (1, 1.0, 0.5)
    assert review_order_metrics([]) is None
