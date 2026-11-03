import subprocess
import sys
from pathlib import Path

import pytest

# 임시 저장소의 테스트를 돌릴 Python. ReleaseGuard의 venv에 pytest가 있고 버전이 같다.
PY = Path(sys.executable)

CALC = """def add(a, b):
    return a + b


def sign(x):
    if x < 0:
        return -1
    return 1
"""

TEST_CALC = """from src.calc import add, sign


def test_add():
    assert add(1, 2) == 3


def test_sign_positive():
    assert sign(3) == 1
"""


class Repo:
    """테스트용 임시 git 저장소."""

    def __init__(self, path: Path):
        self.path = path
        path.mkdir(parents=True, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.path, check=True, capture_output=True, text=True, encoding="utf-8"
        ).stdout

    def write(self, rel: str, content: str) -> None:
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "target")


@pytest.fixture
def pyrepo(repo: Repo) -> Repo:
    """sign의 음수 분기(7줄)는 처음부터 어떤 테스트도 실행하지 않는다."""
    repo.write("pytest.ini", "[pytest]\npythonpath = .\n")
    repo.write("src/__init__.py", "")
    repo.write("src/calc.py", CALC)
    repo.write("tests/__init__.py", "")
    repo.write("tests/test_calc.py", TEST_CALC)
    repo.write("README.md", "# calc\n")
    repo.commit("base")
    return repo
