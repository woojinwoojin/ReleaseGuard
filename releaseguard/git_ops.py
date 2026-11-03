"""대상 저장소에서 변경 정보를 읽는다 (1단계 Collect).

읽기 전용 git 명령만 쓰고, 파일 내용은 작업 폴더가 아니라 커밋에서 읽는다.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class GitError(RuntimeError):
    pass


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


@dataclass
class ChangedFile:
    path: str  # 삭제된 파일은 base 쪽 경로
    status: str  # A, M, D, R (복사·타입 변경은 M으로 취급)
    old_path: str | None = None  # 이름 변경(R)일 때만
    added: int | None = 0  # 바이너리 파일은 None
    deleted: int | None = 0


@dataclass
class Change:
    repo: Path
    base: str
    head: str
    merge_base: str
    head_sha: str
    files: list[ChangedFile]
    # 파일별 (줄 번호, 내용). 비밀값 검사용이라 결과 JSON에는 넣지 않는다.
    added_lines: dict[str, list[tuple[int, str]]] = field(default_factory=dict, repr=False)


def resolve(repo: Path, ref: str) -> str:
    return run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def list_files(repo: Path, sha: str) -> list[str]:
    return run_git(repo, "ls-tree", "-r", "--name-only", sha).splitlines()


def read_file(repo: Path, sha: str, path: str) -> str:
    return run_git(repo, "show", f"{sha}:{path}")


def _name_status(repo: Path, a: str, b: str) -> list[ChangedFile]:
    files = []
    for line in run_git(repo, "diff", "--name-status", "-M", a, b).splitlines():
        parts = line.split("\t")
        code = parts[0][0]
        if code == "R":
            files.append(ChangedFile(path=parts[2], status="R", old_path=parts[1]))
        elif code in "AD":
            files.append(ChangedFile(path=parts[1], status=code))
        else:
            files.append(ChangedFile(path=parts[-1], status="M"))
    return files


def _numstat(repo: Path, a: str, b: str) -> dict[str, tuple[int | None, int | None]]:
    # -z 출력: 일반은 "추가\t삭제\t경로\0", 이름 변경은 "추가\t삭제\t\0이전\0이후\0"
    tokens = run_git(repo, "diff", "--numstat", "-M", "-z", a, b).split("\0")
    stats: dict[str, tuple[int | None, int | None]] = {}
    i = 0
    while i < len(tokens) and tokens[i]:
        added, deleted, path = tokens[i].split("\t", 2)
        if not path:
            path = tokens[i + 2]
            i += 2
        stats[path] = (None if added == "-" else int(added), None if deleted == "-" else int(deleted))
        i += 1
    return stats


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _added_lines(repo: Path, a: str, b: str) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    path, lineno, in_header = None, 0, False
    for line in run_git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "-M", a, b).splitlines():
        if line.startswith("diff --git "):
            path, in_header = None, True
        elif in_header and line.startswith("+++ "):
            target = line[4:]
            path = target[2:] if target.startswith("b/") else None  # /dev/null = 삭제
        elif line.startswith("@@"):
            in_header = False
            m = _HUNK.match(line)
            lineno = int(m.group(1)) if m else 0
        elif not in_header and path and line.startswith("+"):
            out.setdefault(path, []).append((lineno, line[1:]))
            lineno += 1
    return out


def collect(repo: Path, base: str, head: str) -> Change:
    repo = repo.resolve()
    head_sha = resolve(repo, head)
    merge_base = run_git(repo, "merge-base", resolve(repo, base), head_sha).strip()
    files = _name_status(repo, merge_base, head_sha)
    stats = _numstat(repo, merge_base, head_sha)
    for f in files:
        f.added, f.deleted = stats.get(f.path, (0, 0))
    return Change(
        repo=repo,
        base=base,
        head=head,
        merge_base=merge_base,
        head_sha=head_sha,
        files=files,
        added_lines=_added_lines(repo, merge_base, head_sha),
    )
