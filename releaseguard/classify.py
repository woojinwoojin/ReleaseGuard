"""변경 파일을 분류한다 (2단계 Classify). 규칙은 configs/rules.yaml."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "configs" / "rules.yaml"


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class SecretPattern:
    id: str
    pattern: str


@dataclass(frozen=True)
class RuleSet:
    version: int
    rules: tuple[Rule, ...]
    secrets: tuple[SecretPattern, ...]
    low_priority_paths: tuple[str, ...] = ()  # 공백을 보고서 뒤쪽에 둘 경로 (판정과 무관, gap_groups.py)


def load_rules(path: Path = DEFAULT_RULES) -> RuleSet:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RuleSet(
        version=raw["version"],
        rules=tuple(Rule(r["id"], r["category"], tuple(r["patterns"])) for r in raw["rules"]),
        secrets=tuple(SecretPattern(s["id"], s["pattern"]) for s in raw.get("secrets", [])),
        low_priority_paths=tuple((raw.get("review_priority") or {}).get("low", [])),
    )


def classify(path: str, ruleset: RuleSet) -> tuple[str, str | None]:
    """(분류, 규칙 id). 어느 규칙에도 맞지 않으면 ("other", None)."""
    p = PurePosixPath(path)
    for rule in ruleset.rules:
        if any(p.full_match(pattern) for pattern in rule.patterns):
            return rule.category, rule.id
    return "other", None
