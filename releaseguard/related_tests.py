"""변경된 소스와 관련된 테스트를 찾는다 (3단계 Related tests).

두 가지 근거를 쓴다.
- 이름 규칙: src/metrics/engine.py → test_engine.py, test_metrics.py
- import 검색: 테스트 파일에서 해당 모듈을 import하는 줄
"""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

# 폴더 이름으로 테스트 이름을 만들 때 건너뛰는 일반적인 최상위 폴더
_GENERIC_DIRS = {"src", "lib"}


@dataclass
class RelatedTest:
    path: str
    how: str  # "name" | "import"
    evidence: str


@dataclass
class Coverage:
    source: str
    status: str  # "test_changed" | "test_unchanged" | "test_deleted" | "no_test"
    tests: list[RelatedTest] = field(default_factory=list)


def name_candidates(source: str) -> set[str]:
    p = PurePosixPath(source)
    names = set()
    if p.stem != "__init__":
        names |= {f"test_{p.stem}{p.suffix}", f"{p.stem}_test{p.suffix}"}
    for d in p.parent.parts:
        if d not in _GENERIC_DIRS:
            names.add(f"test_{d}{p.suffix}")
    return names


def module_names(source: str) -> list[str]:
    """import 경로 후보. src 레이아웃이면 'src.'를 뗀 이름도 넣는다."""
    p = PurePosixPath(source)
    if p.suffix != ".py":
        return []
    parts = list(p.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts:
        return []
    names = [".".join(parts)]
    if parts[0] == "src" and len(parts) > 1:
        names.append(".".join(parts[1:]))
    return names


def _import_patterns(module: str) -> list[re.Pattern]:
    patterns = [re.compile(rf"^\s*(?:from|import)\s+{re.escape(module)}(?:\s|,|$)")]
    if "." in module:
        parent, name = module.rsplit(".", 1)
        patterns.append(re.compile(rf"^\s*from\s+{re.escape(parent)}\s+import\s+.*\b{re.escape(name)}\b"))
    return patterns


def find_related(source: str, tests: dict[str, str]) -> list[RelatedTest]:
    """tests: {테스트 경로: 내용}. 같은 테스트가 두 근거로 잡히면 둘 다 남긴다."""
    found = []
    names = name_candidates(source)
    for path in sorted(tests):
        if PurePosixPath(path).name in names:
            found.append(RelatedTest(path, "name", f"name:{PurePosixPath(path).name}"))
    patterns = [pat for m in module_names(source) for pat in _import_patterns(m)]
    if patterns:
        for path in sorted(tests):
            if not path.endswith(".py"):
                continue
            for lineno, line in enumerate(tests[path].splitlines(), 1):
                if any(pat.search(line) for pat in patterns):
                    found.append(RelatedTest(path, "import", f"import:{path}:{lineno}"))
                    break
    return found


def coverage_status(related: list[RelatedTest], changed_tests: set[str], deleted_tests: set[str]) -> str:
    paths = {t.path for t in related}
    if paths & deleted_tests:
        return "test_deleted"
    if paths & changed_tests:
        return "test_changed"
    if paths:
        return "test_unchanged"
    return "no_test"
