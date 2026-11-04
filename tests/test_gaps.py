from releaseguard.gaps import compute, file_lines, merge_ranges
from releaseguard.runner import FileCoverage


def test_merge_ranges_bridges_non_executable_lines():
    executable = {1, 2, 3, 5, 6, 9}
    # 3과 5 사이의 4는 실행 불가(빈 줄) → 하나로, 6과 9 사이의 7·8도 실행 불가 → 하나로
    assert merge_ranges([3, 5, 6, 9], executable) == [(3, 9)]
    # 2는 실행 가능한 다른 줄이라 끊긴다
    assert merge_ranges([1, 3], executable) == [(1, 1), (3, 3)]


def test_file_lines_classifies_each_changed_line():
    cov = FileCoverage(executed={1, 2, 5}, missing={6, 7}, tests={2: ["t::a"], 5: ["t::b", "t::a"]})
    fl = file_lines("src/x.py", [1, 2, 3, 5, 6, 7], cov)
    assert fl.line_status == {1: "import_only", 2: "covered", 3: "not_executable", 5: "covered", 6: "gap", 7: "gap"}
    assert (fl.executable, fl.covered, fl.import_only, fl.gap_lines) == (5, 2, 1, 2)
    assert fl.gaps == [(6, 7)]
    assert fl.tests == ["t::a", "t::b"]


def test_fixture_only_lines_are_covered_and_counted_separately():
    cov = FileCoverage(executed={1, 2}, tests={1: ["t::a"], 2: ["t::a"]}, run_lines={2})
    fl = file_lines("src/x.py", [1, 2], cov)
    assert fl.line_status == {1: "covered", 2: "covered"}
    assert (fl.covered, fl.fixture_only, fl.import_only) == (2, 1, 0)


def test_branch_gaps_only_from_changed_executed_lines():
    cov = FileCoverage(
        executed={5, 6, 10, 11, 20},
        missing={7, 21, 30},
        tests={5: ["t::a"], 6: ["t::a"], 10: ["t::a"], 11: ["t::a"], 20: ["t::a"]},
        run_lines={5, 6, 10, 11, 20},
        executed_branches={5: [6], 10: [11, -9], 20: [-19]},
        missing_branches={5: [7], 20: [21], 30: [31, 32]},
    )
    # 5: 바뀜, 한쪽 분기 빠짐 / 10: 바뀜, 분기 다 실행 / 20: 바뀌지 않음 / 30: 바뀌었지만 줄 자체가 실행 안 됨(줄 공백)
    fl = file_lines("src/x.py", [5, 6, 10, 30], cov)
    assert fl.branch_gaps == [(5, 7)]
    assert (fl.branch_lines, fl.branches) == (2, 4)
    assert fl.gaps == [(30, 30)]  # 30은 줄 공백으로만 센다


def test_unmeasured_file_counts_every_changed_line_as_gap():
    fl = file_lines("tools/script.py", [3, 4], None)
    assert fl.measured is False and fl.gaps == [(3, 4)]


def test_compute_only_python_sources_and_ignores_blank_lines():
    files = [
        {"path": "src/x.py", "status": "M", "category": "source"},
        {"path": "tests/test_x.py", "status": "M", "category": "test"},
        {"path": "web/app.js", "status": "M", "category": "source"},
        {"path": "src/gone.py", "status": "D", "category": "source"},
    ]
    added = {"src/x.py": [(1, "x = 1"), (2, "   ")], "tests/test_x.py": [(1, "y")], "web/app.js": [(1, "z")]}
    out = compute(files, added, {"src/x.py": FileCoverage(executed={1})})
    assert [(fl.path, fl.changed) for fl in out] == [("src/x.py", 1)]
