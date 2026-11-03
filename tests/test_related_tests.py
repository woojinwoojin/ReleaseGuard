from releaseguard.related_tests import coverage_status, find_related, module_names, name_candidates


def test_name_candidates_use_stem_and_dirs():
    assert name_candidates("src/metrics/engine.py") == {
        "test_engine.py",
        "engine_test.py",
        "test_metrics.py",
    }
    assert name_candidates("src/market/__init__.py") == {"test_market.py"}


def test_module_names_drop_src_prefix():
    assert module_names("src/metrics/engine.py") == ["src.metrics.engine", "metrics.engine"]
    assert module_names("analysis.py") == ["analysis"]
    assert module_names("src/market/__init__.py") == ["src.market", "market"]
    assert module_names("web/app.js") == []


def test_find_related_by_name_and_import():
    tests = {
        "tests/test_metrics.py": "import pytest\nfrom src.metrics.engine import compute\n",
        "tests/test_report.py": "from src.metrics import engine, trend\n",
        "tests/test_other.py": "from src.metrics.engine_v2 import x\n",
    }
    found = find_related("src/metrics/engine.py", tests)
    assert [(t.path, t.how, t.evidence) for t in found] == [
        ("tests/test_metrics.py", "name", "name:test_metrics.py"),
        ("tests/test_metrics.py", "import", "import:tests/test_metrics.py:2"),
        ("tests/test_report.py", "import", "import:tests/test_report.py:1"),
    ]


def test_find_related_none():
    assert find_related("src/util.py", {"tests/test_metrics.py": "import os\n"}) == []


def test_coverage_status_priority():
    found = find_related("analysis.py", {"tests/test_analysis.py": "", "tests/test_x.py": "import analysis\n"})
    assert coverage_status(found, set(), set()) == "test_unchanged"
    assert coverage_status(found, {"tests/test_x.py"}, set()) == "test_changed"
    assert coverage_status(found, {"tests/test_x.py"}, {"tests/test_analysis.py"}) == "test_deleted"
    assert coverage_status([], set(), set()) == "no_test"
