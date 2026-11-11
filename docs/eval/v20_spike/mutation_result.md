# Stage 2.0 spike 결과 — C:\Project_Folder\predict-success

- Cosmic Ray: cosmic-ray, version 8.9.0 · mutant 40 (상한 40, 커밋당 8) · 전체 175.0초
- 대상 저장소 보존: True (HEAD·git status 전후 비교)
- 지정한 줄에만 변경: 40/40 (100%)
- 원본 바이트 복구: 40/40 (100%)
- 결과(전체 실행 기준): {'KILLED': 27, 'SURVIVED': 13}
- KILLED 실패 종류(전체 실행): {'assertion': 26, 'exception': 1}
- 관련 테스트만 vs 전체 일치: 40/40 (100%)
- 불일치: []
- mutant당 시간(초): 관련 테스트만 중앙값 0.72 (최대 4.76) · 전체 중앙값 1.33 (최대 5.03)
- 관련 테스트 수: 중앙값 6.5 (최소 1, 최대 11)

## 커밋

| 커밋 | 기준 전체 실행 | covered 바뀐 줄 | Cosmic Ray 전체 mutation | 고른 mutant |
|---|---|---|---|---|
| `fc58c0e` Collect pilot filings and financial API responses  | passed | 95 | 326 | 8 |
| `99309f2` Flatten financial API responses into a per-source  | passed | 88 | 613 | 8 |
| `82e4305` Map required accounts to internal accounts and bui | passed | 53 | 779 | 8 |
| `568ea41` Reconcile required-account mismatches and add manu | passed | 48 | 1019 | 8 |
| `b67e806` Confirm balance-sheet sections by arithmetic and a | passed | 87 | 766 | 8 |

## mutant

| # | 커밋 | 위치 | 연산자 | 변경 | 관련만 | 전체 | 실패 종류 |
|---|---|---|---|---|---|---|---|
| 1 | `fc58c0e` | `src/collectors/dart.py:53` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 2 | `fc58c0e` | `src/collectors/dart.py:56` | ReplaceAndWithOr | `return bool(z.namelist()) and z.testzip() is None` → `return bool(z.namelist()) or z.testzip() is None` | SURVIVED | SURVIVED | - |
| 3 | `fc58c0e` | `src/collectors/dart.py:58` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 4 | `fc58c0e` | `src/collectors/dart.py:66` | ReplaceOrWithAnd | `self.session = session or requests.Session()` → `self.session = session and requests.Session()` | KILLED | KILLED | assertion |
| 5 | `fc58c0e` | `src/collectors/dart.py:74` | NumberReplacer | `r = self.session.get(f"{BASE_URL}/{endpoint}", params={**par` → `r = self.session.get(f"{BASE_URL}/{endpoint}", params={**par` | SURVIVED | SURVIVED | - |
| 6 | `fc58c0e` | `src/collectors/dart.py:102` | ReplaceTrueWithFalse | `directory.mkdir(parents=True, exist_ok=True)` → `directory.mkdir(parents=False, exist_ok=True)` | KILLED | KILLED | exception |
| 7 | `fc58c0e` | `src/collectors/dart.py:109` | NumberReplacer | `return json.dumps(obj, ensure_ascii=False, indent=2).encode(` → `return json.dumps(obj, ensure_ascii=False, indent= 3).encode` | SURVIVED | SURVIVED | - |
| 8 | `fc58c0e` | `src/collectors/dart.py:114` | NumberReplacer | `bgn_de = f"{min(years) + 1}0101"  # 2022 사업보고서는 2023년에 접수된다` → `bgn_de = f"{min(years) + 2}0101"  # 2022 사업보고서는 2023년에 접수된다` | SURVIVED | SURVIVED | - |
| 9 | `99309f2` | `src/normalization/build_facts.py:22` | ReplaceAndWithOr | `if f["link"] == "stored" and f.get("corp_code") == corp_code` → `if f["link"] == "stored" or f.get("corp_code") == corp_code ` | KILLED | KILLED | assertion |
| 10 | `99309f2` | `src/normalization/build_facts.py:23` | ReplaceAndWithOr | `and f["rcept_dt"] <= as_of and f.get("correction") not in NO` → `or f["rcept_dt"] <= as_of and f.get("correction") not in NON` | KILLED | KILLED | assertion |
| 11 | `99309f2` | `src/normalization/dart_facts.py:38` | ReplaceComparisonOperator_Is_IsNot | `if raw is None or str(raw).strip() in ("", "-"):` → `if raw is not None or str(raw).strip() in ("", "-"):` | KILLED | KILLED | assertion |
| 12 | `99309f2` | `src/normalization/dart_facts.py:56` | NumberReplacer | `one_year_later = s.replace(year=s.year + 1)` → `one_year_later = s.replace(year=s.year + 2)` | KILLED | KILLED | assertion |
| 13 | `99309f2` | `src/normalization/dart_facts.py:59` | ReplaceComparisonOperator_LtE_Lt | `return s <= e < one_year_later` → `return s < e < one_year_later` | SURVIVED | SURVIVED | - |
| 14 | `99309f2` | `src/normalization/dart_facts.py:73` | NumberReplacer | `period = (_iso(m[2], m[3], m[4]), _iso(m[5], m[6], m[7]))` → `period = (_iso(m[ 3], m[3], m[4]), _iso(m[5], m[6], m[7]))` | KILLED | KILLED | assertion |
| 15 | `99309f2` | `src/normalization/dart_facts.py:78` | NumberReplacer | `found.setdefault(int(m[1]), set()).add(period)` → `found.setdefault(int(m[ 2]), set()).add(period)` | KILLED | KILLED | assertion |
| 16 | `99309f2` | `src/normalization/dart_facts.py:79` | NumberReplacer | `return {term: (next(iter(periods)) if len(periods) == 1 else` → `return {term: (next(iter(periods)) if len(periods) == 2 else` | KILLED | KILLED | assertion |
| 17 | `82e4305` | `src/normalization/account_map.py:18` | ReplaceComparisonOperator_NotEq_Eq | `return account_id in (config["nonstandard_account_id"], "", ` → `return account_id in (config["nonstandard_account_id"], "", ` | KILLED | KILLED | assertion |
| 18 | `82e4305` | `src/normalization/account_map.py:23` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 19 | `82e4305` | `src/normalization/account_map.py:24` | ReplaceAndWithOr | `if "account_detail" in rule and row["account_detail"] != rul` → `if "account_detail" in rule or row["account_detail"] != rule` | KILLED | KILLED | assertion |
| 20 | `82e4305` | `src/normalization/account_map.py:25` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 21 | `82e4305` | `src/normalization/account_map.py:27` | ReplaceComparisonOperator_Eq_NotEq | `return row["account_id"] == rule["account_id"]` → `return row["account_id"] != rule["account_id"]` | KILLED | KILLED | assertion |
| 22 | `82e4305` | `src/normalization/account_map.py:29` | ReplaceAndWithOr | `return is_nonstandard(row["account_id"], config) and str(row` → `return is_nonstandard(row["account_id"], config) or str(row[` | KILLED | KILLED | assertion |
| 23 | `82e4305` | `src/normalization/account_map.py:40` | ReplaceOrWithAnd | `"rule": rule.get("account_id") or f"name:{rule.get('nonstand` → `"rule": rule.get("account_id") and f"name:{rule.get('nonstan` | SURVIVED | SURVIVED | - |
| 24 | `82e4305` | `src/normalization/account_map.py:65` | ReplaceComparisonOperator_NotEq_Eq | `if any(r["value_status"] != "parsed" for r, _ in found):` → `if any(r["value_status"] == "parsed" for r, _ in found):` | KILLED | KILLED | assertion |
| 25 | `568ea41` | `src/normalization/account_map.py:60` | ReplaceAndWithOr | `overlapping = [(total, parts) for total, parts in spec.get("` → `overlapping = [(total, parts) for total, parts in spec.get("` | KILLED | KILLED | assertion |
| 26 | `568ea41` | `src/normalization/dart_facts.py:57` | NumberReplacer | `return (date.fromisoformat(end) - date.fromisoformat(start))` → `return (date.fromisoformat(end) - date.fromisoformat(start))` | SURVIVED | SURVIVED | - |
| 27 | `568ea41` | `src/normalization/dart_facts.py:62` | ReplaceComparisonOperator_Lt_LtE | `return date.fromisoformat(end) < date.fromisoformat(start)` → `return date.fromisoformat(end) <= date.fromisoformat(start)` | SURVIVED | SURVIVED | - |
| 28 | `568ea41` | `src/normalization/dart_facts.py:67` | ReplaceComparisonOperator_Gt_GtE | `return period_days(start, end) > MAX_REGULAR_DAYS` → `return period_days(start, end) >= MAX_REGULAR_DAYS` | SURVIVED | SURVIVED | - |
| 29 | `568ea41` | `src/normalization/dart_facts.py:73` | ReplaceComparisonOperator_NotEq_Eq | `if reprt_code != ANNUAL_REPORT_CODE:` → `if reprt_code == ANNUAL_REPORT_CODE:` | KILLED | KILLED | assertion |
| 30 | `568ea41` | `src/normalization/dart_facts.py:74` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 31 | `568ea41` | `src/normalization/dart_facts.py:77` | NumberReplacer | `twelve_months = e == s.replace(year=s.year + 1) - timedelta(` → `twelve_months = e == s.replace(year=s.year + 2) - timedelta(` | SURVIVED | SURVIVED | - |
| 32 | `568ea41` | `src/normalization/dart_facts.py:80` | NumberReplacer | `return twelve_months or 364 <= period_days(start, end) <= MA` → `return twelve_months or 365 <= period_days(start, end) <= MA` | KILLED | KILLED | assertion |
| 33 | `b67e806` | `src/normalization/account_map.py:28` | ReplaceComparisonOperator_Eq_NotEq | `if rule["section"] == "unconfirmed":` → `if rule["section"] != "unconfirmed":` | KILLED | KILLED | assertion |
| 34 | `b67e806` | `src/normalization/account_map.py:30` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 35 | `b67e806` | `src/normalization/account_map.py:31` | ReplaceAndWithOr | `elif not (row.get("bs_section") == rule["section"] and row.g` → `elif not (row.get("bs_section") == rule["section"] or row.ge` | KILLED | KILLED | assertion |
| 36 | `b67e806` | `src/normalization/account_map.py:32` | ReplaceFalseWithTrue | `return False` → `return True` | KILLED | KILLED | assertion |
| 37 | `b67e806` | `src/normalization/bs_sections.py:23` | ReplaceOrWithAnd | `return row["account_id"] in HFS_ASSET_IDS \| HFS_LIABILITY_ID` → `return row["account_id"] in HFS_ASSET_IDS \| HFS_LIABILITY_ID` | SURVIVED | SURVIVED | - |
| 38 | `b67e806` | `src/normalization/bs_sections.py:27` | NumberReplacer | `return Decimal(row["value"]) if row["value_status"] == "pars` → `return Decimal(row["value"]) if row["value_status"] == "pars` | SURVIVED | SURVIVED | - |
| 39 | `b67e806` | `src/normalization/bs_sections.py:35` | ReplaceFalseWithTrue | `r.setdefault("bs_section_confirmed", False)` → `r.setdefault("bs_section_confirmed", True)` | SURVIVED | SURVIVED | - |
| 40 | `b67e806` | `src/normalization/bs_sections.py:36` | ReplaceComparisonOperator_Eq_NotEq | `if r["sj_div"] == "BS":` → `if r["sj_div"] != "BS":` | KILLED | KILLED | assertion |
