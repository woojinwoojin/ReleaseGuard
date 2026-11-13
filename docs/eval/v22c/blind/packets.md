# Stage 2.2 확인 평가 — 블라인드 분류 자료

각 사례를 분류해 주세요: ACTIONABLE_GAP 후보(명세상 의미 있는 차이) / MEANINGFUL_UNVERIFIED / LOW_VALUE / EQUIVALENT_SUPPORTED(코드 보장·데이터 관측·미보장을 나눠서) / UNRESOLVED. 근거와 불확실성도 함께.

명세 근거는 **대상 커밋 시점**의 저장소 내용만 인정합니다. 문서 원문이 필요하면 경로를 알려 주세요.


---

## R-1

- 저장소: `release-guard` · 커밋 `c910160` · `releaseguard/__main__.py:34` · 함수 `main`
- 연산자: `core/NumberReplacer` (occurrence 4)
- 바뀐 줄: `stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")` → `stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent= 3), encoding="utf-8")`
- 그 줄을 실행한 테스트 (1개 선택 실행): 선택 SURVIVED (실행 1, skip 0) · 전체 SURVIVED (실행 31, skip 0)

### mutant diff

```diff
--- releaseguard/__main__.py (원본)
+++ releaseguard/__main__.py (mutant)
@@ -31,7 +31,7 @@
 
     args.out.mkdir(parents=True, exist_ok=True)
     stem = args.out / f"{date.today():%Y%m%d}_{result['head_sha'][:7]}"
-    stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
+    stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent= 3), encoding="utf-8")
     stem.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
     print(f"{result['decision']}  ({len(result['findings'])}개 규칙 발동)")
     print(f"→ {stem.with_suffix('.json')}")
```

### 원본 함수 (`c910160` 시점, 15–39줄)

```python
  15  def main(argv: list[str] | None = None) -> int:
  16      parser = argparse.ArgumentParser(prog="releaseguard")
  17      sub = parser.add_subparsers(dest="command", required=True)
  18      p = sub.add_parser("analyze", help="base...head 변경을 분석한다")
  19      p.add_argument("--repo", type=Path, required=True)
  20      p.add_argument("--base", required=True)
  21      p.add_argument("--head", default="HEAD")
  22      p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
  23      p.add_argument("--out", type=Path, default=Path("out"))
  24      args = parser.parse_args(argv)
  25  
  26      try:
  27          result = analyze(args.repo, args.base, args.head, load_rules(args.rules))
  28      except GitError as e:
  29          print(f"git 오류: {e}", file=sys.stderr)
  30          return 2
  31  
  32      args.out.mkdir(parents=True, exist_ok=True)
  33      stem = args.out / f"{date.today():%Y%m%d}_{result['head_sha'][:7]}"
  34      stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
  35      stem.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
  36      print(f"{result['decision']}  ({len(result['findings'])}개 규칙 발동)")
  37      print(f"→ {stem.with_suffix('.json')}")
  38      print(f"→ {stem.with_suffix('.md')}")
  39      return 0
```

### 모듈 docstring

```text
실행: python -m releaseguard analyze --repo <경로> --base <ref> --head <ref>
```

### 그 줄을 실행한 테스트 id

- `tests/test_analyze.py::test_cli_writes_json_and_markdown`

### 커밋 시점 문서 파일 (5개)

- `README.md`
- `docs/design.md`
- `docs/problem.md`
- `docs/proposal.md`
- `requirements.txt`

---

## R-2

- 저장소: `release-guard` · 커밋 `6fb437c` · `releaseguard/agent_tools.py:54` · 함수 `git_diff`
- 연산자: `core/ReplaceComparisonOperator_Gt_GtE` (occurrence 0)
- 바뀐 줄: `return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) > MAX_DIFF_CHARS}` → `return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) >= MAX_DIFF_CHARS}`
- 그 줄을 실행한 테스트 (1개 선택 실행): 선택 SURVIVED (실행 1, skip 0) · 전체 SURVIVED (실행 48, skip 0)

### mutant diff

```diff
--- releaseguard/agent_tools.py (원본)
+++ releaseguard/agent_tools.py (mutant)
@@ -51,7 +51,7 @@
         if path:
             args += ["--", check_path(path)]
         text = run_git(self.repo, *args)
-        return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) > MAX_DIFF_CHARS}
+        return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) >= MAX_DIFF_CHARS}
 
     def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> dict:
         path = check_path(path)
```

### 원본 함수 (`6fb437c` 시점, 49–54줄)

```python
  49      def git_diff(self, path: str | None = None) -> dict:
  50          args = ["diff", "--no-color", "--no-ext-diff", "-M", self.merge_base, self.head_sha]
  51          if path:
  52              args += ["--", check_path(path)]
  53          text = run_git(self.repo, *args)
  54          return {"path": path, "diff": text[:MAX_DIFF_CHARS], "truncated": len(text) > MAX_DIFF_CHARS}
```

### 모듈 docstring

```text
에이전트가 쓰는 읽기 전용 도구 (4단계 Impact).

모든 도구는 head 커밋의 git 객체만 읽는다. 작업 폴더를 건드리지 않고 저장소 밖으로 나갈 수 없다.
결과 크기에 상한을 둬서 Context가 한 번에 커지지 않게 한다.
```

### 그 줄을 실행한 테스트 id

- `tests/test_agent_tools.py::test_git_diff_single_file`

### 커밋 시점 문서 파일 (5개)

- `README.md`
- `docs/design.md`
- `docs/problem.md`
- `docs/proposal.md`
- `requirements.txt`

---

## W-1

- 저장소: `2026-10/week2-tool-calling` · 커밋 `5b31f70` · `tools.py:56` · 함수 `check_category`
- 연산자: `core/NumberReplacer` (occurrence 22)
- 바뀐 줄: `error["hint"] = f"{category}는 {parent.iloc[0]}의 하위 카테고리입니다."` → `error["hint"] = f"{category}는 {parent.iloc[ 1]}의 하위 카테고리입니다."`
- 그 줄을 실행한 테스트 (1개 선택 실행): 선택 SURVIVED (실행 1, skip 0) · 전체 SURVIVED (실행 35, skip 0)

### mutant diff

```diff
--- tools.py (원본)
+++ tools.py (mutant)
@@ -53,7 +53,7 @@
     if "sub_category" in df:
         parent = df.loc[df["sub_category"] == category, "category"]
         if not parent.empty:
-            error["hint"] = f"{category}는 {parent.iloc[0]}의 하위 카테고리입니다."
+            error["hint"] = f"{category}는 {parent.iloc[ 1]}의 하위 카테고리입니다."
     return error
 
 
```

### 원본 함수 (`5b31f70` 시점, 47–57줄)

```python
  47  def check_category(df: pd.DataFrame, category: str) -> dict | None:
  48      """없는 카테고리면 LLM이 인자를 고칠 수 있는 error dict를, 있으면 None을 돌려준다."""
  49      categories = sorted(df["category"].unique())
  50      if category in categories:
  51          return None
  52      error = {"error": f"없는 카테고리: {category}", "available": categories}
  53      if "sub_category" in df:
  54          parent = df.loc[df["sub_category"] == category, "category"]
  55          if not parent.empty:
  56              error["hint"] = f"{category}는 {parent.iloc[0]}의 하위 카테고리입니다."
  57      return error
```

### 모듈 docstring

```text
LLM이 호출할 수 있는 분석 도구(tool)와 그 스키마.

각 도구는 역할 이름 컬럼(date, sales, ...)의 df를 받아 JSON으로 바꿀 수 있는 dict를 돌려준다.
LLM에는 원본 행이 아니라 이 요약 결과만 전달된다.
잘못된 인자는 예외 대신 {"error": ...}로 돌려줘서, LLM이 결과를 보고 인자를 고쳐 다시 호출할 수 있게 한다.
```

### 그 줄을 실행한 테스트 id

- `tests/test_tools.py::test_unknown_category_hints_sub_category`

### 커밋 시점 문서 파일 (2개)

- `README.md`
- `requirements.txt`

---

## P-1

- 저장소: `predict-success` · 커밋 `3db2f31` · `src/metrics/engine.py:57` · 함수 `combine`
- 연산자: `core/NumberReplacer` (occurrence 6)
- 바뀐 줄: `result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[:60]}")` → `result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[: 61]}")`
- 그 줄을 실행한 테스트 (1개 선택 실행): 선택 SURVIVED (실행 1, skip 0) · 전체 SURVIVED (실행 76, skip 0)

### mutant diff

```diff
--- src/metrics/engine.py (원본)
+++ src/metrics/engine.py (mutant)
@@ -54,7 +54,7 @@
     result.calc_status = worst
     for i in inputs:
         if i.calc_status == "reference":
-            result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[:60]}")
+            result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[: 61]}")
         elif i.calc_status == "not_computed":
             result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[:60]}")
     if worst != "normal":
```

### 원본 함수 (`3db2f31` 시점, 50–62줄)

```python
  50  def combine(result: Result, inputs: list[Input]) -> Result:
  51      """입력 중 가장 나쁜 상태를 따른다. 보류 사유를 모은다."""
  52      result.inputs = inputs
  53      worst = max((i.calc_status for i in inputs), key=STATUS_RANK.get, default="normal")
  54      result.calc_status = worst
  55      for i in inputs:
  56          if i.calc_status == "reference":
  57              result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[:60]}")
  58          elif i.calc_status == "not_computed":
  59              result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[:60]}")
  60      if worst != "normal":
  61          result.score_eligible = "보류"
  62      return result
```

### 모듈 docstring

```text
2025 지표 계산 (README 6.1~6.3, docs/decisions.md D9). 점수(0~100 변환)는 아직 하지 않는다.

입력 상태 → 계산 상태:
  mapped                → normal     (정상 계산)
  candidate             → reference  (참고 계산 — 후보 이자비용, 산술로만 판정된 매각예정 조정 등. 점수 반영 보류)
  그 밖(확인 필요 등)    → not_computed (계산하지 않음, 보류 사유)
비교군 기준 지표는 파일럿 비교군(평가기업 제외 3개사)이라 '검증용'으로만 표시한다.
```

### 그 줄을 실행한 테스트 id

- `tests/test_metrics.py::test_candidate_input_gives_reference_calculation_and_holds_score`

### 커밋 시점 문서 파일 (5개)

- `README.md`
- `docs/decisions.md`
- `docs/problem.md`
- `docs/progress.md`
- `requirements.txt`

---

## P-2

- 저장소: `predict-success` · 커밋 `3db2f31` · `src/metrics/engine.py:59` · 함수 `combine`
- 연산자: `core/NumberReplacer` (occurrence 8)
- 바뀐 줄: `result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[:60]}")` → `result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[: 61]}")`
- 그 줄을 실행한 테스트 (1개 선택 실행): 선택 SURVIVED (실행 1, skip 0) · 전체 SURVIVED (실행 76, skip 0)

### mutant diff

```diff
--- src/metrics/engine.py (원본)
+++ src/metrics/engine.py (mutant)
@@ -56,7 +56,7 @@
         if i.calc_status == "reference":
             result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[:60]}")
         elif i.calc_status == "not_computed":
-            result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[:60]}")
+            result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[: 61]}")
     if worst != "normal":
         result.score_eligible = "보류"
     return result
```

### 원본 함수 (`3db2f31` 시점, 50–62줄)

```python
  50  def combine(result: Result, inputs: list[Input]) -> Result:
  51      """입력 중 가장 나쁜 상태를 따른다. 보류 사유를 모은다."""
  52      result.inputs = inputs
  53      worst = max((i.calc_status for i in inputs), key=STATUS_RANK.get, default="normal")
  54      result.calc_status = worst
  55      for i in inputs:
  56          if i.calc_status == "reference":
  57              result.hold_reasons.append(f"{i.label} {i.year}: 후보값 — {i.note[:60]}")
  58          elif i.calc_status == "not_computed":
  59              result.hold_reasons.append(f"{i.label} {i.year}: {i.status} — {i.note[:60]}")
  60      if worst != "normal":
  61          result.score_eligible = "보류"
  62      return result
```

### 모듈 docstring

```text
2025 지표 계산 (README 6.1~6.3, docs/decisions.md D9). 점수(0~100 변환)는 아직 하지 않는다.

입력 상태 → 계산 상태:
  mapped                → normal     (정상 계산)
  candidate             → reference  (참고 계산 — 후보 이자비용, 산술로만 판정된 매각예정 조정 등. 점수 반영 보류)
  그 밖(확인 필요 등)    → not_computed (계산하지 않음, 보류 사유)
비교군 기준 지표는 파일럿 비교군(평가기업 제외 3개사)이라 '검증용'으로만 표시한다.
```

### 그 줄을 실행한 테스트 id

- `tests/test_metrics.py::test_unconfirmed_input_is_not_computed_with_reason`

### 커밋 시점 문서 파일 (5개)

- `README.md`
- `docs/decisions.md`
- `docs/problem.md`
- `docs/progress.md`
- `requirements.txt`
