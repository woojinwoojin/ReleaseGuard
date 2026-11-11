#!/usr/bin/env bash
# 보고서 #11 3장: SAFE 경계 사례 4개를 임시 저장소에서 재현한다 (판정 규칙 v3.1, 코드 변경 없음).
# 사용: bash docs/eval/20261111_explore/boundary_cases.sh <작업 폴더>   (release-guard 루트에서 실행)
# 결과: 사례별 decision · scope · test_status · rules · notes · counts
set -euo pipefail
WORK="${1:?작업 폴더를 지정하세요}"
RG="$(pwd)"
PY="$RG/.venv/Scripts/python.exe"; [ -x "$PY" ] || PY="$RG/.venv/bin/python"
rm -rf "$WORK"; mkdir -p "$WORK/repo"; cd "$WORK/repo"
git init -q -b main; git config user.email t@t; git config user.name t; git config core.autocrlf false

mkdir -p pkg tests
printf 'def add(a, b):\n    return a + b\n' > pkg/core.py
printf 'def old():\n    return 1\n' > pkg/legacy.py
touch pkg/__init__.py
printf 'from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n' > tests/test_core.py
git add -A; git commit -qm base

# C1: 테스트 파일 추가, test_ 함수 없음 (v3.2에서는 X11 — 테스트 함수가 없으므로 T03 아님, SAFE)
git checkout -qb c1; printf 'def helper_check():\n    assert True\n' > tests/test_new.py; git add -A; git commit -qm c1; git checkout -q main
# C2 (v3.2 T03 CHANGED_TESTS_ALL_SKIPPED): 추가한 테스트가 전부 skip
git checkout -qb c2
printf 'import pytest\nfrom pkg.core import add\n\n@pytest.mark.skip(reason="data/ 없음")\ndef test_add_big():\n    assert add(10, 20) == 30\n' > tests/test_skip.py
git add -A; git commit -qm c2; git checkout -q main
# C3 소스 삭제 (참조 없음, 남은 테스트 통과)
git checkout -qb c3; git rm -q pkg/legacy.py; git commit -qm c3; git checkout -q main
# C4 (v3.2 T03 TEST_SUITE_REMOVED): 유일한 테스트 파일 삭제 → no_tests
git checkout -qb c4; git rm -q tests/test_core.py; git commit -qm c4; git checkout -q main

cd "$RG"
for b in c1 c2 c3 c4; do
  "$PY" -m releaseguard analyze --repo "$WORK/repo" --base main --head "$b" --python "$PY" --out "$WORK/out/$b" --no-agent > /dev/null
  "$PY" - "$b" "$WORK/out/$b" <<'EOF'
import glob, json, sys
d = json.load(open(glob.glob(sys.argv[2] + "/*.json")[0], encoding="utf-8"))
f = d["findings"]
print(sys.argv[1], d["decision"], d["scope"]["status"], d["test_run"]["status"],
      [x["rule_id"] for x in f if x["decision"] != "NOTE"], [x["rule_id"] for x in f if x["decision"] == "NOTE"], d["test_run"]["counts"])
EOF
done
