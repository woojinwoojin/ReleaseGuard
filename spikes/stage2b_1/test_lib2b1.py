"""lib2b1 단위 테스트 — 사례 파일과 무관한 가짜 로그·워크플로로 규칙만 확인한다.

사용 (release-guard 루트): .venv/Scripts/python -m pytest spikes/stage2b_1/test_lib2b1.py -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib2b1 import env_rule, tracebacks, v3_policy2  # noqa: E402

ENV = [{"name": "API_TOKEN", "role": "토큰", "read_at": "svc/config.py:7"}]


def tb(frames, final, prefix=()):
    lines = list(prefix) + ["Traceback (most recent call last):"]
    for f, n in frames:
        lines += [f'  File "{f}", line {n}, in <module>', "    x = 1"]
    return lines + [final]


def test_no_env_required_means_rule_off():
    assert env_rule(tb([("/app/svc/config.py", 7)], "KeyError: 'API_TOKEN'"), []) is None


def test_env_insufficient_when_app_frame_and_name_match():
    log = tb([("/app/main.py", 2), ("/app/svc/config.py", 7), ("/usr/local/lib/python3.12/os.py", 714)], "KeyError: 'API_TOKEN'")
    r = env_rule(log, ENV)
    assert r["reason"] == "ENV_INSUFFICIENT" and r["variable"] == "API_TOKEN"


def test_wrong_line_is_unknown_cause():
    r = env_rule(tb([("/app/svc/config.py", 9)], "KeyError: 'API_TOKEN'"), ENV)
    assert r["reason"] == "UNKNOWN_CAUSE"


def test_chained_exception_is_unknown_cause():
    first = tb([("/app/svc/other.py", 3)], "ValueError: bad")
    second = tb([("/app/svc/config.py", 7)], "KeyError: 'API_TOKEN'", prefix=["", "During handling of the above exception, another exception occurred:", ""])
    assert env_rule(first + second, ENV)["reason"] == "UNKNOWN_CAUSE"


def test_earlier_different_error_is_unknown_cause():
    log = tb([("/app/a.py", 1)], "ImportError: x") + ["restarting"] + tb([("/app/svc/config.py", 7)], "KeyError: 'API_TOKEN'")
    assert env_rule(log, ENV)["reason"] == "UNKNOWN_CAUSE"


def test_repeated_same_traceback_is_fine():
    one = tb([("/app/svc/config.py", 7)], "KeyError: 'API_TOKEN'")
    assert env_rule(one + ["[ERROR] worker"] + one, ENV)["reason"] == "ENV_INSUFFICIENT"


def test_unrelated_failure_without_name_stays_fail():
    assert env_rule(tb([("/app/svc/app.py", 3)], "RuntimeError: boom"), ENV) is None


def test_name_substring_does_not_count():
    assert env_rule(["error: API_TOKENS missing"], ENV) is None


def test_tracebacks_parse_caret_lines():
    log = ["Traceback (most recent call last):", '  File "/app/x.py", line 4, in <module>', "    f()", "    ^^^", "NameError: f"]
    t = tracebacks(log)
    assert t[0]["frames"] == [("/app/x.py", 4)] and t[0]["final"] == "NameError: f"


WF = """name: T
on:
  push:
  pull_request:
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - run: {cmd}
{extra}"""


def wf(tmp_path: Path, name: str, cmd: str, extra: str = "", on=None) -> Path:
    d = tmp_path / name / ".github" / "workflows"
    d.mkdir(parents=True)
    text = WF.format(cmd=cmd, extra=extra)
    if on:
        text = text.replace("on:\n  push:\n  pull_request:\n", on)
    (d / "t.yml").write_text(text, encoding="utf-8")
    return tmp_path / name


def test_v3_masked(tmp_path):
    r = v3_policy2(wf(tmp_path, "h", "python -m pytest -q || true"), wf(tmp_path, "b", "python -m pytest -q"))
    assert r["V3a"]["status"] == "FAIL" and r["V3a"]["mechanism"] == ["FAILURE_MASKED"]
    assert r["V3b"]["mechanism"] == ["FAILURE_MASKED"]


def test_v3_removed_vs_unclear_runner(tmp_path):
    r = v3_policy2(wf(tmp_path, "h", "echo hi"), wf(tmp_path, "b", "pytest"))
    assert r["V3a"]["mechanism"] == ["REMOVED"]
    r = v3_policy2(wf(tmp_path, "h2", "nox -s tests"), wf(tmp_path, "b2", "pytest"))
    assert r["V3a"]["status"] == "INCONCLUSIVE" and r["V3b"]["status"] == "INCONCLUSIVE"


def test_v3_narrowed_events(tmp_path):
    on = "on:\n  push:\n    paths: [src/**]\n  pull_request:\n    paths: [src/**]\n"
    r = v3_policy2(wf(tmp_path, "h", "pytest", on=on), wf(tmp_path, "b", "pytest"))
    assert r["V3a"]["status"] == "INCONCLUSIVE"


def test_v3_job_continue_on_error(tmp_path):
    h = wf(tmp_path, "h", "pytest")
    p = h / ".github" / "workflows" / "t.yml"
    p.write_text(p.read_text(encoding="utf-8").replace("    runs-on: ubuntu-latest\n", "    runs-on: ubuntu-latest\n    continue-on-error: true\n"), encoding="utf-8")
    r = v3_policy2(h, wf(tmp_path, "b", "pytest"))
    assert r["V3a"]["mechanism"] == ["FAILURE_ALLOWED"]
