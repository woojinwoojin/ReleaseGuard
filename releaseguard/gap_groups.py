"""검증 공백을 함수 단위로 묶고 검토 순서를 정한다 (1.4).

정보를 조직할 뿐 검증 결과를 바꾸지 않는다: 판정·G01·줄 단위 공백(`lines`)은 이 모듈을 쓰지 않는다.

- 그룹: 공백 줄을 감싸는 가장 안쪽 함수. 함수 밖은 클래스 본문(class_body)이나 모듈(module)로,
  파일을 파싱하지 못하면 unmapped로 묶는다. 어느 줄도 빠지지 않는다.
- 순서: review_priority(NORMAL → LOW), 공백 줄 수 내림차순, 파일 경로, 시작 줄, 이름.
  공백이 많은 곳을 먼저 보여줄 뿐, 결함 위험 순서가 아니다.
- LOW: rules.yaml의 review_priority.low 경로만. "안전하다"가 아니라 "뒤에 보여준다"는 뜻이다.
"""

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from .gaps import FileLines

NORMAL = "NORMAL"
LOW = "LOW"

MODULE = "<module>"
UNMAPPED = "<unmapped>"


@dataclass
class GapGroup:
    path: str
    kind: str  # function | class_body | module | unmapped
    name: str  # 함수는 Class.method처럼 감싸는 이름까지. 모듈·unmapped는 <module>·<unmapped>
    start_line: int  # 함수·클래스의 시작 줄(데코레이터 포함). 모듈·unmapped는 첫 공백 줄
    gap_lines: int = 0
    gap_ranges: list[tuple[int, int]] = field(default_factory=list)  # 줄 단위 공백 범위를 그룹 경계에서 나눈 것
    gap_line_numbers: list[int] = field(default_factory=list)  # 범위 안의 빈 줄·주석을 뺀 실제 공백 줄
    review_priority: str = NORMAL


@dataclass(frozen=True)
class _Scope:
    kind: str
    name: str
    start: int
    end: int


def _scopes(tree: ast.AST) -> list[_Scope]:
    """바깥 → 안쪽 순서의 함수·클래스 목록. 뒤에 있는 것이 더 안쪽이다."""
    out: list[_Scope] = []

    def walk(node: ast.AST, prefix: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class_body" if isinstance(child, ast.ClassDef) else "function"
                start = min([child.lineno, *(d.lineno for d in child.decorator_list)])
                names = [*prefix, child.name]
                out.append(_Scope(kind, ".".join(names), start, child.end_lineno or child.lineno))
                walk(child, names)
            else:
                walk(child, prefix)

    walk(tree, [])
    return out


def _parse(source: str | None) -> list[_Scope] | None:
    if source is None:
        return None
    try:
        return _scopes(ast.parse(source))
    except (SyntaxError, ValueError):
        return None


def _scope_of(line: int, scopes: list[_Scope] | None) -> _Scope:
    if scopes is None:
        return _Scope("unmapped", UNMAPPED, 0, 0)
    inner = [s for s in scopes if s.start <= line <= s.end]
    return inner[-1] if inner else _Scope("module", MODULE, 0, 0)


def review_priority(path: str, low_paths: tuple[str, ...]) -> str:
    return LOW if any(PurePosixPath(path).full_match(p) for p in low_paths) else NORMAL


def order_key(g: GapGroup) -> tuple:
    return (g.review_priority == LOW, -g.gap_lines, g.path, g.start_line, g.name)


def file_groups(fl: FileLines, source: str | None, low_paths: tuple[str, ...] = ()) -> list[GapGroup]:
    scopes = _parse(source)
    priority = review_priority(fl.path, low_paths)
    gap_lines = sorted(n for n, status in fl.line_status.items() if status == "gap")
    groups: dict[_Scope, GapGroup] = {}
    for first, last in fl.gaps:
        previous = None
        for n in (x for x in gap_lines if first <= x <= last):
            scope = _scope_of(n, scopes)
            g = groups.get(scope)
            if g is None:
                g = groups[scope] = GapGroup(fl.path, scope.kind, scope.name, scope.start or n, review_priority=priority)
            g.gap_lines += 1
            g.gap_line_numbers.append(n)
            if scope == previous:
                g.gap_ranges[-1] = (g.gap_ranges[-1][0], n)
            else:
                g.gap_ranges.append((n, n))
            previous = scope
    return list(groups.values())


def group_gaps(lines: list[FileLines], read: Callable[[str], str | None], low_paths: tuple[str, ...] = ()) -> list[GapGroup]:
    """공백이 있는 파일의 그룹을 검토 순서로 돌려준다. read: 경로 → head 커밋의 파일 내용."""
    groups = [g for fl in lines if fl.gaps for g in file_groups(fl, read(fl.path), low_paths)]
    return sorted(groups, key=order_key)


def preservation(lines: list[dict], groups: list[dict]) -> dict:
    """줄 단위 공백과 그룹이 같은 줄을 가리키는지. missing·extra·duplicate가 모두 0이어야 한다."""
    expected = {(fl["path"], int(n)) for fl in lines for n, status in fl["line_status"].items() if status == "gap"}
    grouped = [(g["path"], n) for g in groups for n in g["gap_line_numbers"]]
    return {
        "lines": len(expected),
        "missing": len(expected - set(grouped)),
        "extra": len(set(grouped) - expected),
        "duplicate": len(grouped) - len(set(grouped)),
    }
