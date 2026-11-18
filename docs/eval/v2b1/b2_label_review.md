# B2 라벨 확인 (Stage 2b.1 3단계)

- 라벨 초안: Claude, **diff만 보고 V3 실행 전** (2026-11-18). 34개 중 `CONTRACT_PRESERVED` 32 · `UNCLEAR` 2 · `CONTRACT_REMOVED` 0
- 확인 대상 10개 = `UNCLEAR` 전부 2 + `PRESERVED` 저장소마다 2개(고정 시드 `Random(20261118)`). 나머지 24개는 `CLAUDE_ONLY`로 따로 집계
- 라벨 정의: `CONTRACT_REMOVED` = push·PR에서 돌던 필수 테스트 실행이 사라지거나, 실행되지 않거나, 실패가 전파되지 않게 됨 / `CONTRACT_PRESERVED` = 그 밖 / `UNCLEAR` = diff만으로 판단 못 함
- 작성 중 정한 기준: 매트릭스에서 버전을 뺀 변경은 커밋 메시지상 **지원 중단과 함께면 PRESERVED**, 아직 지원하는 버전·변형을 빼면 **UNCLEAR**
- **각 항목에 `동의` 또는 `다른 라벨 + 이유`를 적어 주세요.** `UNCLEAR` 두 개는 '매트릭스 축소를 계약 위반으로 볼지'를 정해 주시면 됩니다 (REMOVED / PRESERVED / UNCLEAR 유지)

## 1. pytest-dev/pytest `849fbda3ce` — 초안 **CONTRACT_PRESERVED**

- 메시지: Merge pull request #14122 from RonnyPfannschmidt/enable-uv  (병합 커밋)
- 원본: https://github.com/pytest-dev/pytest/commit/849fbda3ce87e3829b30d005979bee59928c01ff
- 바뀐 워크플로: deploy.yml, doc-check-links.yml, prepare-release-pr.yml, test.yml, update-plugin-list.yml
- 초안 이유: tox 설치 단계를 로컬 복합 액션(.github/actions/setup-tox)으로 교체. 테스트 실행 단계(tox run)는 그대로
- 바뀐 줄 49개 중 `uses:` 버전 줄을 뺀 36개 (앞 20줄):
```diff
-    - name: Set up Python
+    - name: Set up tox
-    - name: Install tox
-      run: |
-        python -m pip install --upgrade pip
-        pip install tox
-      - name: Setup Python
+      - name: Set up tox
-          cache: pip
-      - name: Install tox
-        run: |
-          python -m pip install --upgrade pip
-          pip install tox
-    - name: Set up Python
+    - name: Set up tox
-    - name: Install tox
-      run: |
-        python -m pip install --upgrade pip
-        pip install tox
-    - name: Install tox
```
- 사용자 확인: 

## 2. pytest-dev/pytest `6153372429` — 초안 **CONTRACT_PRESERVED**

- 메시지: Merge pull request #14701 from Pierre-Sassoulas/fix-pypy311-hypothesis  (병합 커밋)
- 원본: https://github.com/pytest-dev/pytest/commit/6153372429f86e6ff224548d62e54945def76d8f
- 바뀐 워크플로: test.yml
- 초안 이유: 매트릭스 항목의 PyPy 버전 3.10→3.11
- 바뀐 줄 2개 중 `uses:` 버전 줄을 뺀 2개:
```diff
-            python: "pypy-3.10"
+            python: "pypy-3.11"
```
- 사용자 확인: 

## 3. fastapi/fastapi `980cee9678` — 초안 **UNCLEAR**

- 메시지: 👷 Limit the full test matrix to Python 3.15 (#16776)  (일반 커밋)
- 원본: https://github.com/fastapi/fastapi/commit/980cee9678de95644be6a9d942349ce3aab2f45b
- 바뀐 워크플로: test.yml
- 초안 이유: Windows·macOS 전체 매트릭스에서 아직 지원하는 3.14·3.14t를 제외 (3.15·3.15t만 남김). 테스트 실행은 남지만 범위 축소가 계약 위반인지는 정책에 달림
- 바뀐 줄 2개 중 `uses:` 버전 줄을 뺀 2개:
```diff
-        python-version: [ "3.14", "3.14t", "3.15", "3.15t" ]
+        python-version: [ "3.15", "3.15t" ]
```
- 사용자 확인: 외부 리뷰(사용자 전달, 2026-11-18): UNCLEAR 유지. 변경 후에도 Ubuntu의 3.14·3.14t 테스트가 남아 K2 최소 조건(실행·실패 전파)은 유지. 사유: 매트릭스 범위 축소(MATRIX_COVERAGE_REDUCED)

## 4. fastapi/fastapi `28eaf6a22c` — 초안 **CONTRACT_PRESERVED**

- 메시지: 💥 Drop support for Python 3.10 (#16737)  (일반 커밋)
- 원본: https://github.com/fastapi/fastapi/commit/28eaf6a22c4e70f415868132d5ca948d21821360
- 바뀐 워크플로: test.yml
- 초안 이유: Python 3.10 지원 중단에 맞춰 macOS include 항목 3.10→3.11
- 바뀐 줄 2개 중 `uses:` 버전 줄을 뺀 2개:
```diff
-            python-version: "3.10"
+            python-version: "3.11"
```
- 사용자 확인: 

## 5. fastapi/fastapi `2d3e1e9dea` — 초안 **CONTRACT_PRESERVED**

- 메시지: ⬆ Bump the github-actions group with 7 updates (#16658)  (일반 커밋, 봇·의존성)
- 원본: https://github.com/fastapi/fastapi/commit/2d3e1e9dea7f6eaed9ba7d1975ac1c7cc3c33023
- 바뀐 워크플로: build-docs.yml, bump-pre-commit-hooks.yml, create-draft-release.yml, deploy-docs.yml, pre-commit.yml, prepare-release.yml, publish.yml, smokeshow.yml, sponsors.yml, test-redistribute.yml, test.yml, topic-repos.yml, translate.yml, zizmor.yml
- 초안 이유: 액션 버전 고정값만 변경
- 바뀐 줄 90개 중 `uses:` 버전 줄을 뺀 0개:
- 사용자 확인: 

## 6. psf/requests `561e4b6889` — 초안 **CONTRACT_PRESERVED**

- 메시지: Add inline types to Requests (#7272)  (일반 커밋)
- 원본: https://github.com/psf/requests/commit/561e4b6889f53584c39a67f8794c53a414f68481
- 바뀐 워크플로: typecheck.yml
- 초안 이유: 타입 검사(pyright) 워크플로 새로 추가. 테스트 워크플로 그대로
- 바뀐 줄 32개 중 `uses:` 버전 줄을 뺀 23개 (앞 20줄):
```diff
+name: Type Check
+on: [push, pull_request]
+permissions:
+  contents: read
+jobs:
+  typecheck:
+    runs-on: ubuntu-24.04
+    timeout-minutes: 10
+    strategy:
+      matrix:
+        python-version: ["3.10", "3.14"]
+    steps:
+      with:
+        persist-credentials: false
+    - name: Set up Python
+      with:
+        python-version: ${{ matrix.python-version }}
+    - name: Install dependencies
+      run: |
+        python -m pip install pip==26.0.1
```
- 사용자 확인: 

## 7. psf/requests `00600b38f4` — 초안 **CONTRACT_PRESERVED**

- 메시지: Update publish workflow and add test pypi option  (일반 커밋)
- 원본: https://github.com/psf/requests/commit/00600b38f45dc234f825f609cea63d24e7e690af
- 바뀐 워크플로: publish.yml
- 초안 이유: 배포 워크플로 개편(workflow_dispatch 입력, provenance 작업 제거). 테스트 워크플로 아님
- 바뀐 줄 69개 중 `uses:` 버전 줄을 뺀 53개 (앞 20줄):
```diff
+  workflow_dispatch:
+    inputs:
+      test-pypi-only:
+        description: "Publish to Test PyPI only"
+        type: boolean
+        default: true
-    environment:
-      name: "publish"
-      hashes: ${{ steps.hash.outputs.hashes }}
-        run: python -m pip install build==0.8.0
+        run: python -m pip install build==1.4.0
-      - name: "Generate hashes"
-        id: hash
-        run: |
-          cd dist && echo "::set-output name=hashes::$(sha256sum * | base64 -w0)"
-  provenance:
-    needs: [build]
-    permissions:
-      actions: read
-      contents: write
```
- 사용자 확인: 

## 8. pallets/flask `728c5e440a` — 초안 **CONTRACT_PRESERVED**

- 메시지: drop support for Python 3.10 (#6168)  (병합 커밋)
- 원본: https://github.com/pallets/flask/commit/728c5e440af704a786384159184f695cf04ecbe7
- 바뀐 워크플로: tests.yaml
- 초안 이유: Python 3.10 지원 중단에 맞춰 매트릭스에서 3.10 제거, Development Versions 3.10→3.11
- 바뀐 줄 3개 중 `uses:` 버전 줄을 뺀 3개:
```diff
-          - {python: '3.10'}
-          - {name: Development Versions, python: '3.10', tox: tests-dev}
+          - {name: Development Versions, python: '3.11', tox: tests-dev}
```
- 사용자 확인: 

## 9. pallets/flask `6a2f545bfd` — 초안 **CONTRACT_PRESERVED**

- 메시지: Merge branch 'stable'  (병합 커밋)
- 원본: https://github.com/pallets/flask/commit/6a2f545bfd8ed31e19066a299296917e034aca58
- 바뀐 워크플로: lock.yaml, pre-commit.yaml, publish.yaml, tests.yaml, zizmor.yaml
- 초안 이유: 매트릭스에 3.15 추가, allow-prereleases, 액션 버전 변경
- 바뀐 줄 40개 중 `uses:` 버전 줄을 뺀 2개:
```diff
+          - {python: '3.15'}
+          allow-prereleases: true
```
- 사용자 확인: 

## 10. pallets/flask `eb58d862cc` — 초안 **UNCLEAR**

- 메시지: Merge branch 'stable'  (병합 커밋)
- 원본: https://github.com/pallets/flask/commit/eb58d862cc4a8f31a369b6e9ad1724e9e642f13f
- 바뀐 워크플로: lock.yaml, pre-commit.yaml, publish.yaml, tests.yaml
- 초안 이유: 매트릭스에서 3.13t(free-threaded) 제거, 3.13은 남음. 지원 중단 근거가 diff·메시지에 없어 범위 축소가 계약 위반인지 정책에 달림
- 바뀐 줄 37개 중 `uses:` 버전 줄을 뺀 1개:
```diff
-          - {python: '3.13t'}
```
- 사용자 확인: 외부 리뷰(사용자 전달, 2026-11-18): UNCLEAR 유지. 3.13t가 CI 매트릭스와 pyproject tox 환경 목록에서 함께 제거(의도적 범위 축소), 3.13·3.14t는 남음. 사유: 매트릭스 범위 축소(MATRIX_COVERAGE_REDUCED)
