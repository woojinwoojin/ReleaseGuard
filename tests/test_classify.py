import pytest

from releaseguard.classify import classify, load_rules

RULES = load_rules()


@pytest.mark.parametrize(
    "path, category",
    [
        ("requirements.txt", "deps"),
        ("app/requirements-dev.txt", "deps"),
        ("tests/test_metrics.py", "test"),
        ("tests/fixtures/sample.csv", "test"),
        ("pkg/test_util.py", "test"),
        ("configs/scoring_v2.yaml", "config"),
        (".github/workflows/ci.yml", "config"),
        ("Dockerfile", "config"),
        ("pytest.ini", "config"),
        ("README.md", "docs"),
        ("docs/decisions.md", "docs"),
        ("data/manual/market_links.csv", "data"),
        ("src/metrics/engine.py", "source"),
        ("agent.py", "source"),
        ("image.png", "other"),
    ],
)
def test_classify(path, category):
    assert classify(path, RULES)[0] == category


def test_classify_returns_rule_id():
    assert classify("src/metrics/engine.py", RULES) == ("source", "C06")
    assert classify("image.png", RULES) == ("other", None)
