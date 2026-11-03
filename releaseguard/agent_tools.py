"""에이전트가 쓰는 읽기 전용 도구 (4단계 Impact).

모든 도구는 head 커밋의 git 객체만 읽는다. 작업 폴더를 건드리지 않고 저장소 밖으로 나갈 수 없다.
결과 크기에 상한을 둬서 Context가 한 번에 커지지 않게 한다.
"""

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .git_ops import GitError, run_git

MAX_DIFF_CHARS = 12_000
MAX_READ_LINES = 200
MAX_SEARCH_HITS = 50
MAX_LIST_FILES = 300


class ToolError(ValueError):
    """도구 인자가 잘못됨. 메시지는 LLM에게 그대로 돌려준다."""


def check_path(path: str) -> str:
    p = path.replace("\\", "/").strip()
    if not p or p.startswith("/") or ":" in p or ".." in PurePosixPath(p).parts:
        raise ToolError(f"저장소 루트 기준 상대 경로만 쓸 수 있습니다: {path!r}")
    return p.rstrip("/")


@dataclass
class RepoView:
    repo: Path
    merge_base: str
    head_sha: str

    def _lines(self, path: str) -> list[str]:
        try:
            return run_git(self.repo, "show", f"{self.head_sha}:{path}").splitlines()
        except GitError:
            raise ToolError(f"head에 없는 파일입니다: {path}") from None

    def file_line_count(self, path: str) -> int | None:
        """근거 검증용. 파일이 없으면 None."""
        try:
            return len(self._lines(check_path(path)))
        except ToolError:
            return None

    def git_diff(self, path: str | None = None) -> dict:
        args = ["diff", "--no-color", "--no-ext-diff", "-M", self.merge_base, self.head_sha]
        if path:
            args += ["--", check_path(path)]
        text = run_git(self.repo, *args)
        return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) > MAX_DIFF_CHARS}

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> dict:
        path = check_path(path)
        lines = self._lines(path)
        start = max(1, start_line or 1)
        end = min(len(lines), end_line or len(lines), start + MAX_READ_LINES - 1)
        return {
            "path": path,
            "total_lines": len(lines),
            "start_line": start,
            "end_line": end,
            "content": "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1)),
        }

    def search_code(self, text: str, path_prefix: str | None = None) -> dict:
        if not text.strip():
            raise ToolError("검색어가 비었습니다.")
        args = ["grep", "-n", "-I", "-F", "-e", text, self.head_sha]
        if path_prefix:
            args += ["--", check_path(path_prefix)]
        out = run_git(self.repo, *args, ok_codes=(0, 1))
        hits = []
        for line in out.splitlines():
            # 출력 형식: <sha>:<경로>:<줄>:<내용>
            path, lineno, content = line.removeprefix(f"{self.head_sha}:").split(":", 2)
            hits.append({"path": path, "line": int(lineno), "text": content.strip()[:200]})
        return {"text": text, "total": len(hits), "hits": hits[:MAX_SEARCH_HITS], "truncated": len(hits) > MAX_SEARCH_HITS}

    def list_files(self, path_prefix: str | None = None) -> dict:
        files = run_git(self.repo, "ls-tree", "-r", "--name-only", self.head_sha).splitlines()
        if path_prefix:
            prefix = check_path(path_prefix)
            files = [f for f in files if f == prefix or f.startswith(prefix + "/")]
        return {"total": len(files), "files": files[:MAX_LIST_FILES], "truncated": len(files) > MAX_LIST_FILES}


NULLABLE_PATH = {"type": ["string", "null"], "description": "저장소 루트 기준 경로. 제한하지 않으려면 null."}


def function_tool(name: str, description: str, properties: dict) -> dict:
    # strict 모드: 모든 속성을 required에 넣고, 선택 인자는 null을 허용한다.
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


TOOLS = [
    function_tool(
        "git_diff",
        f"이번 변경(merge-base → head)의 unified diff. 파일 하나만 보려면 path를 준다. {MAX_DIFF_CHARS}자에서 자른다.",
        {"path": NULLABLE_PATH},
    ),
    function_tool(
        "read_file",
        f"head 시점 파일 내용을 줄 번호와 함께 읽는다. 한 번에 최대 {MAX_READ_LINES}줄.",
        {
            "path": {"type": "string", "description": "저장소 루트 기준 경로"},
            "start_line": {"type": ["integer", "null"], "description": "시작 줄 (1부터). null이면 1"},
            "end_line": {"type": ["integer", "null"], "description": "끝 줄. null이면 상한까지"},
        },
    ),
    function_tool(
        "search_code",
        f"head 시점 저장소에서 고정 문자열을 찾는다 (정규식 아님). 함수·모듈 이름의 사용처를 찾을 때 쓴다. 최대 {MAX_SEARCH_HITS}건.",
        {
            "text": {"type": "string", "description": "찾을 문자열 (예: compute_metrics, from src.metrics)"},
            "path_prefix": NULLABLE_PATH,
        },
    ),
    function_tool(
        "list_files",
        f"head 시점 파일 목록. 최대 {MAX_LIST_FILES}개.",
        {"path_prefix": NULLABLE_PATH},
    ),
]


def run_tool(view: RepoView, name: str, arguments: str) -> tuple[str, bool]:
    """(LLM에게 돌려줄 JSON 문자열, 성공 여부). 잘못된 인자는 예외 대신 error로 돌려준다."""
    handlers = {
        "git_diff": view.git_diff,
        "read_file": view.read_file,
        "search_code": view.search_code,
        "list_files": view.list_files,
    }
    try:
        if name not in handlers:
            raise ToolError(f"없는 도구입니다: {name}")
        result, ok = handlers[name](**json.loads(arguments)), True
    except (ToolError, GitError, TypeError, json.JSONDecodeError) as e:
        result, ok = {"error": str(e)}, False
    return json.dumps(result, ensure_ascii=False), ok
