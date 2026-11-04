"""대상 커밋에서 테스트를 실행하고 줄·분기 coverage를 잰다 (3단계 Run).

- 대상 커밋을 git archive로 임시 폴더에 풀어서 실행한다. 대상 저장소의 작업 폴더와 .git은 바뀌지 않는다.
- Python은 대상 저장소의 .venv를 쓰고, coverage·pytest-cov는 ReleaseGuard의 .rg/tools에서 PYTHONPATH로 넣는다.
  대상 프로젝트의 환경에는 아무것도 설치하지 않는다.
- 테스트별로 어느 줄을 실행했는지 기록한다. pytest-cov의 --cov-context=test로 context가 "node id|단계"가 되어
  테스트 본문(run)과 fixture(setup·teardown)에서 실행된 줄을 구분한다.
- branch = True로 분기(arc: 줄 A → 줄 B)도 잰다. 분기에는 테스트 context가 없다.
"""

import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .git_ops import GitError, list_files, read_file

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / ".rg" / "tools"
COVERAGE_VERSION = "7.17.0"
PYTEST_COV_VERSION = "7.1.0"
DEFAULT_TIMEOUT = 300  # 초


class RunnerError(RuntimeError):
    pass


@dataclass
class TestCase:
    nodeid: str  # pytest node id (예: tests/test_x.py::test_f[1])
    outcome: str  # passed | failed | error | skipped
    message: str = ""  # 보고서용 (300자까지). skipped면 skip 사유
    fingerprint: str = ""  # 실패 지문 (failure_fingerprint). base·head 실패가 같은 실패인지 비교할 때 쓴다


_ADDR = re.compile(r"0x[0-9a-fA-F]+")
_TMP = re.compile(r"[^\s'\"]*?rg_[^/\s]+/src/")  # 임시 스냅샷 폴더 접두사 (경로 구분자는 /로 바꾼 뒤 적용)
_FRAME = re.compile(r"^(\S+?):\d+: in (\S+)$")  # traceback 중간 프레임: 파일:줄: in 함수
_CRASH = re.compile(r"^(\S+?):\d+: (\w[\w.]*)$")  # 마지막 줄: 파일:줄: 예외 종류


def failure_fingerprint(message: str, text: str) -> str:
    """같은 실패인지 비교하는 지문: 예외 종류 + 정규화한 전체 메시지 + traceback 위치(파일·함수, 줄 번호 제외).

    - 메시지는 자르지 않는다 (보고서용 300자 메시지로 비교하면 다른 실패가 같아 보일 수 있다).
    - 임시 폴더 경로·메모리 주소만 지운다. 숫자는 남긴다 (assert 500 == 200의 500은 원인의 일부).
    - 줄 번호는 뺀다. 같은 파일에 테스트가 추가되면 줄이 밀리기 때문이다. 대신 프레임의 파일·함수 순서를 본다.
    """
    def norm(x: str) -> str:
        return _ADDR.sub("0x?", _TMP.sub("", x.replace("\\", "/"))).strip()

    frames, crash = [], ""
    for line in (text or "").splitlines():
        line = norm(line)
        if m := _FRAME.match(line):
            frames.append(f"{m.group(1)}::{m.group(2)}")
        elif m := _CRASH.match(line):
            crash = f"{m.group(1)}::{m.group(2)}"
    return "\n".join([norm(message or ""), crash, *frames])


@dataclass
class FileCoverage:
    executed: set[int] = field(default_factory=set)
    missing: set[int] = field(default_factory=set)
    tests: dict[int, list[str]] = field(default_factory=dict)  # 줄 → 그 줄을 실행한 테스트 (모든 단계, import 시점 실행은 제외)
    run_lines: set[int] = field(default_factory=set)  # 테스트 본문(run 단계)에서 실행된 줄. tests에만 있으면 fixture에서만 실행
    executed_branches: dict[int, list[int]] = field(default_factory=dict)  # 출발 줄 → 실행된 도착 줄 (음수 = 함수에서 나감)
    missing_branches: dict[int, list[int]] = field(default_factory=dict)  # 출발 줄 → 실행되지 않은 도착 줄


@dataclass
class RunResult:
    status: str  # passed | failed | error | timeout | no_tests | not_run | skipped
    reason: str | None = None
    seconds: float = 0.0
    python: str | None = None
    tests: list[TestCase] = field(default_factory=list)
    coverage: dict[str, FileCoverage] | None = None  # 저장소 기준 경로(/) → 줄 단위 coverage
    attempts: int = 1  # 시간 초과로 다시 시도했으면 2
    command: list[str] = field(default_factory=list)  # 실제 실행한 명령 (임시 폴더는 <tmp>로 바꿈)

    def counts(self) -> dict[str, int]:
        out = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for t in self.tests:
            out[t.outcome] += 1
        return out


def ensure_coverage() -> Path:
    """coverage·pytest-cov를 .rg/tools에 한 번만 설치한다 (ReleaseGuard의 pip 사용, pytest는 대상 .venv의 것을 쓴다)."""
    wanted = {"coverage": f"coverage=={COVERAGE_VERSION}", "pytest_cov": f"pytest-cov=={PYTEST_COV_VERSION}"}
    missing = [spec for pkg, spec in wanted.items() if not (TOOLS_DIR / pkg / "__init__.py").exists()]
    if missing:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--target", str(TOOLS_DIR), *missing],
            check=True,
        )
    return TOOLS_DIR


def find_python(repo: Path, explicit: Path | None = None) -> Path | None:
    if explicit:
        return explicit
    for rel in (".venv/Scripts/python.exe", ".venv/bin/python"):
        if (repo / rel).exists():
            return repo / rel
    return None


def python_version(python: Path) -> str:
    out = subprocess.run([str(python), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True)
    return out.stdout.strip()


def snapshot(repo: Path, sha: str, dest: Path) -> None:
    """커밋의 파일을 dest에 푼다. git에 없는 파일(.env, 로컬 데이터)은 포함되지 않는다."""
    proc = subprocess.run(["git", "archive", "--format=tar", sha], cwd=repo, capture_output=True)
    if proc.returncode != 0:
        raise GitError(f"git archive {sha}: {proc.stderr.decode('utf-8', 'replace').strip()}")
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        tar.extractall(dest, filter="data")


def snapshot_warnings(repo: Path, sha: str) -> list[str]:
    """git archive 스냅샷이 저장소의 실제 파일과 다를 수 있는 이유. 없으면 빈 목록."""
    files = set(list_files(repo, sha))
    out = []
    if ".gitmodules" in files:
        out.append(".gitmodules: 서브모듈 내용은 스냅샷에 들어가지 않음")
    for path in sorted(f for f in files if PurePosixPath(f).name == ".gitattributes"):
        text = read_file(repo, sha, path)
        if "export-ignore" in text:
            out.append(f"{path}: export-ignore 대상은 스냅샷에서 빠짐")
        if "filter=lfs" in text:
            out.append(f"{path}: LFS 파일은 포인터만 들어감")
    return out


_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", re.I)


def host_secret_names() -> list[str]:
    """테스트에 그대로 넘어가는 호스트 환경 변수 중 자격 증명으로 보이는 이름 (값은 남기지 않는다).

    스냅샷은 git에 없는 .env를 빼지만, 호스트 환경 변수는 넘어간다. 그래서 같은 커밋이라도 이 변수가 있는
    호스트와 없는 호스트(CI)의 결과가 다를 수 있다 — 깨끗한 스냅샷이지 격리된 실행 환경은 아니다.
    """
    return sorted(k for k in os.environ if _SECRET_NAME.search(k))


def _env(tools: Path | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "VIRTUAL_ENV")}
    if tools:
        env["PYTHONPATH"] = str(tools)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _module_of(file: str) -> str:
    return ".".join(PurePosixPath(file.replace("\\", "/")).with_suffix("").parts)


def parse_junit(path: Path) -> list[TestCase]:
    """테스트 결과. junit_family=xunit1이라 file 속성이 있다."""
    if not path.exists():
        return []
    cases = []
    for tc in ET.parse(path).getroot().iter("testcase"):
        file = (tc.get("file") or "").replace("\\", "/")
        classname, name = tc.get("classname") or "", tc.get("name") or ""
        module = _module_of(file) if file else classname
        cls = classname[len(module) + 1 :] if classname.startswith(module + ".") else ""
        prefix = f"{file}::{cls + '::' if cls else ''}" if file else f"{classname}::"
        outcome, message, fingerprint = "passed", "", ""
        for tag in ("failure", "error", "skipped"):
            el = tc.find(tag)
            if el is not None:
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                message = (el.get("message") or "")[:300]
                if tag != "skipped":
                    fingerprint = failure_fingerprint(el.get("message") or "", el.text or "")
                break
        cases.append(TestCase(prefix + name, outcome, message, fingerprint))
    return cases


def parse_context(ctx: str) -> tuple[str, str]:
    """pytest-cov context "tests/x.py::test_f[1]|setup" → ("tests/x.py::test_f", "setup").

    parametrize 값은 떼어 함수 단위로 묶는다 (보고서에 같은 테스트 함수가 값마다 나오지 않게).
    """
    nodeid, sep, phase = ctx.rpartition("|")
    if not sep:
        nodeid, phase = ctx, "run"
    return re.sub(r"\[.*\]$", "", nodeid), phase


def _arcs(pairs: list[list[int]]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for a, b in pairs:
        out.setdefault(a, []).append(b)
    return out


def parse_coverage(path: Path) -> dict[str, FileCoverage]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for name, f in data["files"].items():
        tests, run_lines = {}, set()
        for line, ctxs in f.get("contexts", {}).items():
            parsed = [parse_context(c) for c in ctxs if c]  # 빈 context = 테스트 밖(수집·import)에서 실행
            if parsed:
                tests[int(line)] = sorted({n for n, _ in parsed})
                if any(ph == "run" for _, ph in parsed):
                    run_lines.add(int(line))
        out[name.replace("\\", "/")] = FileCoverage(
            set(f["executed_lines"]), set(f["missing_lines"]), tests, run_lines,
            _arcs(f.get("executed_branches", [])), _arcs(f.get("missing_branches", [])),
        )
    return out


def _tail(text: str, n: int = 15) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def run_tests(
    repo: Path,
    sha: str,
    python: Path,
    *,
    with_coverage: bool = True,
    nodeids: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> RunResult:
    """sha 시점의 테스트를 실행한다. nodeids(node id 또는 테스트 파일 경로)를 주면 그것만 (coverage 없이 쓰는 재실행용).

    시간 초과는 한 번 다시 시도한다. 같은 테스트가 1초에 끝나는 커밋에서도 실행 환경 때문에 멈춘 적이 있다
    (Eval v2, da30a78). 두 번 모두 넘기면 timeout으로 남긴다.
    """
    result = _run_once(repo, sha, python, with_coverage, nodeids, timeout)
    if result.status == "timeout":
        retry = _run_once(repo, sha, python, with_coverage, nodeids, timeout)
        retry.attempts = 2
        retry.seconds = round(result.seconds + retry.seconds, 1)
        return retry
    return result


def _run_once(repo: Path, sha: str, python: Path, with_coverage: bool, nodeids: list[str] | None, timeout: int) -> RunResult:
    tools = ensure_coverage() if with_coverage else None
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="rg_", ignore_cleanup_errors=True) as tmp:
        tmp = Path(tmp)
        work = tmp / "src"
        work.mkdir()
        snapshot(repo, sha, work)
        junit = tmp / "junit.xml"
        pytest_args = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "junit_family=xunit1", f"--junitxml={junit}", *(nodeids or [])]
        if with_coverage:
            rc = tmp / "rg.rc"
            rc.write_text(
                f"[run]\nbranch = True\nrelative_files = True\nsource = .\ndata_file = {tmp / 'rg.cov'}\n",
                encoding="utf-8",
            )
            # -p pytest_cov: 플러그인 자동 로드가 꺼져 있어도 불러온다. --cov-report=: 보고서는 아래 coverage json으로 따로 만든다
            cov_args = ["-p", "pytest_cov", "--cov", f"--cov-config={rc}", "--cov-context=test", "--cov-report="]
            cmd = [str(python), *pytest_args, *cov_args]
        else:
            cmd = [str(python), *pytest_args]
        # 출력은 파이프가 아니라 파일로 받는다. 파이프로 받으면 시간 초과 후에도 자식 프로세스가 파이프를 쥐고 있어
        # 기다림이 끝나지 않을 수 있다 (Windows).
        log_path = tmp / "pytest.log"
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                proc = subprocess.run(cmd, cwd=work, env=_env(tools), stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired:
            return RunResult("timeout", f"{timeout}초 안에 끝나지 않음", round(time.perf_counter() - started, 1), str(python), command=_shown(cmd, tmp))
        output = log_path.read_text(encoding="utf-8", errors="replace")

        tests = parse_junit(junit)
        # pytest 종료 코드: 0 통과, 1 실패, 5 테스트 없음, 그 밖은 수집 오류·사용 오류
        status = {0: "passed", 1: "failed", 5: "no_tests"}.get(proc.returncode, "error")
        reason = None if status in ("passed", "no_tests") else _tail(output)
        coverage = None
        if with_coverage and status == "no_tests":
            coverage = {}  # 테스트가 없으면 coverage 데이터도 없다. 바뀐 소스 줄은 모두 측정 밖(공백)으로 본다.
        elif with_coverage and status in ("passed", "failed"):
            report = tmp / "coverage.json"
            cov = subprocess.run(
                [str(python), "-m", "coverage", "json", f"--rcfile={rc}", "--show-contexts", "-q", "-o", str(report)],
                cwd=work, env=_env(tools), capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if cov.returncode == 0:
                coverage = parse_coverage(report)
            else:
                reason = f"coverage 보고서 생성 실패: {_tail(cov.stdout + cov.stderr, 5)}"
        return RunResult(status, reason, round(time.perf_counter() - started, 1), str(python), tests, coverage, command=_shown(cmd, tmp))


def _shown(cmd: list[str], tmp: Path) -> list[str]:
    return [c.replace(str(tmp), "<tmp>") for c in cmd]


def check_python(python: Path) -> str | None:
    """coverage(.rg/tools)와 대상 Python의 버전이 맞지 않으면 사유를 돌려준다."""
    if not python.exists():
        return f"Python이 없음: {python}"
    target = python_version(python)
    own = "%d.%d" % sys.version_info[:2]
    if not target:
        return f"Python을 실행할 수 없음: {python}"
    if target != own:
        return f"대상 Python {target}과 coverage 설치 버전 {own}이 다름"
    return None
