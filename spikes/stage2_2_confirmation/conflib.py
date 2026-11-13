"""Stage 2.2 확인 평가 공용 설정·도구. 설계: docs/design_stage2_2_confirmation.md

releaseguard는 import만 한다. Cosmic Ray·pytest 실행은 spikes/stage2_1/mutlib.py를 그대로 쓴다.
"""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
# mutlib을 파일 경로로 불러온다. stage2_1 폴더를 sys.path에 넣으면 같은 이름의 스크립트(select_cases.py 등)가 대신 import될 수 있다
_spec = importlib.util.spec_from_file_location("mutlib", HERE.parent / "stage2_1" / "mutlib.py")
mutlib = importlib.util.module_from_spec(_spec)
sys.modules["mutlib"] = mutlib
_spec.loader.exec_module(mutlib)
ROOT, clean = mutlib.ROOT, mutlib.clean

WORKSPACE = ROOT.parent
OUT = ROOT / "docs" / "eval" / "v22c"
CASES_FILE = ROOT / "eval" / "mutation_confirmation_cases.yaml"

# 설계 3.1 — 순서가 곧 W의 커밋 순서다 (week1 → week4)
CODEBASES = {
    "R": {"repos": ["release-guard"], "budget": 20, "in_go": True},
    "W": {"repos": ["2026-10/week1-csv-llm-report", "2026-10/week2-tool-calling", "2026-10/week3-fastapi-ui", "2026-10/week4-docker-aws"],
          "budget": 20, "in_go": True},
    "P": {"repos": ["predict-success"], "budget": 15, "in_go": False},
}
FAMILY_ORDER = ["comparison", "boolean", "constant"]  # 예산 배분·남은 예산을 넘기는 순서 (설계 3.2)
PER_COMMIT = 8
BLIND_SALT = "rg-2.2c-blind"
BASELINE_TIMEOUT = 900  # 초. R 전체 테스트가 coverage 없이 167초라 제품 기본값 300초로는 부족할 수 있다
EXCLUDED_DIRS = ("spikes/", "eval/")


def family_budget(total: int) -> dict[str, int]:
    """20 → 7·7·6, 15 → 5·5·5 (앞 계열부터 나머지를 하나씩)."""
    base, rest = divmod(total, len(FAMILY_ORDER))
    return {f: base + (i < rest) for i, f in enumerate(FAMILY_ORDER)}


def observed_commits() -> set[str]:
    """이미 mutation 결과를 본 커밋 (7자리). 2.0 결과 + 2.1 사례 파일 + 설계에 적은 목록."""
    out = {"fc58c0e", "99309f2", "82e4305", "568ea41", "b67e806", "c7733b3"}
    r20 = json.loads((ROOT / "docs/eval/v20_spike/mutation_result.json").read_text(encoding="utf-8"))
    out |= {m["commit"][:7] for m in r20["mutants"]}
    c21 = yaml.safe_load((ROOT / "eval/mutation_cases_2_1.yaml").read_text(encoding="utf-8"))
    out |= {c["commit"][:7] for c in c21["cases"]}
    return out


def blind_key(codebase: str, m: dict) -> str:
    raw = "|".join([BLIND_SALT, codebase, m["commit"], m["path"], str(m["line"]), m["operator"], str(m["occurrence"])])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def redact(text: str) -> str:
    """홈·임시 경로·작업 폴더를 가린다 (2.0과 같은 원칙)."""
    return clean(str(text).replace(str(WORKSPACE), "<workspace>").replace(str(WORKSPACE).replace("\\", "/"), "<workspace>"))
