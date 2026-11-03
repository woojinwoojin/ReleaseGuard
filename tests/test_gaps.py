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
