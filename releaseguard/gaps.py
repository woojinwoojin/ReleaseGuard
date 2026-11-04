"""바뀐 줄과 coverage를 대조해 검증 공백을 찾는다 (4단계 Gaps).

바뀐 줄 하나는 넷 중 하나다.
- covered: 어떤 테스트가 실행함 (테스트 목록이 남는다). 테스트 본문이 아니라 fixture(setup·teardown)에서만
  실행됐으면 fixture_only로도 센다.
- import_only: 모듈을 불러올 때만 실행됨 (def·클래스·상수 줄). 공백으로 보지 않는다.
- gap: 실행 가능한 줄인데 어떤 테스트도 실행하지 않음 → 검증 공백 (G01)
- 실행 불가: 빈 줄·주석·docstring 등 (세지 않음)

분기 공백은 줄 공백과 따로 센다 (1.5, 판정에는 넣지 않음).
- 대상: 출발 줄이 바뀐 줄이고 그 줄은 실행됐는데, 거기서 나가는 분기 중 실행되지 않은 것.
- 출발 줄 자체가 실행되지 않았으면 이미 줄 공백이므로 분기 공백으로 다시 세지 않는다.
"""

from dataclasses import dataclass, field

from .runner import FileCoverage


@dataclass
class FileLines:
    path: str
    measured: bool  # coverage 데이터에 파일이 있는가
    changed: int  # 추가·수정된 줄 수
    executable: int = 0  # 그중 실행 가능한 줄
    covered: int = 0
    import_only: int = 0
    gap_lines: int = 0
    gaps: list[tuple[int, int]] = field(default_factory=list)  # (시작줄, 끝줄)
    tests: list[str] = field(default_factory=list)  # 바뀐 줄을 실행한 테스트
    line_status: dict[int, str] = field(default_factory=dict)  # 바뀐 줄 → covered | import_only | gap | not_executable
    fixture_only: int = 0  # covered 중 fixture(setup·teardown)에서만 실행된 줄
    branch_lines: int = 0  # 바뀐 줄 중 실행된 분기 줄 (if·while·for 등)
    branches: int = 0  # 그 줄들에서 나가는 분기 수
    branch_gaps: list[tuple[int, int]] = field(default_factory=list)  # 실행되지 않은 분기 (출발줄, 도착줄). 도착 음수 = 함수에서 나감


def merge_ranges(gap: list[int], executable: set[int]) -> list[tuple[int, int]]:
    """연속된 공백 줄을 묶는다. 사이에 실행 불가 줄(빈 줄·주석)만 있으면 하나로 본다."""
    ranges: list[tuple[int, int]] = []
    for n in sorted(gap):
        if ranges and not any(m in executable for m in range(ranges[-1][1] + 1, n)):
            ranges[-1] = (ranges[-1][0], n)
        else:
            ranges.append((n, n))
    return ranges


def file_lines(path: str, changed: list[int], cov: FileCoverage | None) -> FileLines:
    if cov is None:
        # coverage가 이 파일을 보지 못함 (패키지 밖 스크립트 등). 실행 가능 여부를 알 수 없어 바뀐 줄 전체를 공백으로 본다.
        return FileLines(
            path, False, len(changed), len(changed), 0, 0, len(changed), merge_ranges(changed, set(changed)),
            line_status={n: "gap" for n in changed},
        )
    executable = cov.executed | cov.missing
    out = FileLines(path, True, len(changed))
    gap, tests = [], set()
    for n in changed:
        if n not in executable:
            out.line_status[n] = "not_executable"
            continue
        out.executable += 1
        if n in cov.missing:
            gap.append(n)
            out.line_status[n] = "gap"
        elif n in cov.tests:
            out.covered += 1
            out.fixture_only += n not in cov.run_lines
            tests.update(cov.tests[n])
            out.line_status[n] = "covered"
        else:
            out.import_only += 1
            out.line_status[n] = "import_only"
        if n in cov.executed:
            missed = cov.missing_branches.get(n, [])
            total = len(cov.executed_branches.get(n, [])) + len(missed)
            if total:
                out.branch_lines += 1
                out.branches += total
                out.branch_gaps += [(n, to) for to in sorted(missed)]
    out.gap_lines = len(gap)
    out.gaps = merge_ranges(gap, executable)
    out.tests = sorted(tests)
    return out


def compute(files: list[dict], added_lines: dict[str, list[tuple[int, str]]], coverage: dict[str, FileCoverage]) -> list[FileLines]:
    """files: 분류된 변경 파일. Python 소스(테스트 제외)만 본다."""
    out = []
    for f in files:
        if f["category"] != "source" or not f["path"].endswith(".py") or f["status"] == "D":
            continue
        changed = [n for n, text in added_lines.get(f["path"], []) if text.strip()]
        if changed:
            out.append(file_lines(f["path"], changed, coverage.get(f["path"])))
    return out
