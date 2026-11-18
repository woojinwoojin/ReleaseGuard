"""Stage 2b.1 공용 코드 (설계 docs/design_stage2b_1.md). 2b.0 artifactlib는 가져다 쓰고 고치지 않는다.

- 스냅샷: 출처(repo·commit·context)의 git archive를 core.autocrlf=false로 풀어 줄바꿈을 바꾸지 않는다(2b.0 P1 재발 방지).
  편집은 find/replace(정확히 한 번)와 create(새 파일).
- V3 (정책 재정의, 설계 3장 B): 필수 테스트의 실행 가능성과 실패 전파. FAIL에 메커니즘 코드
  REMOVED / NOT_EXECUTED / FAILURE_ALLOWED / FAILURE_MASKED.
- E1 환경 부족 규칙 (설계 3장 A, Q6 수정).

구현 중 정한 해석 (결과를 보기 전, 설계 범위 안):
- V3a 같은 계약: 2b.0처럼 주석을 지운 run 명령으로 맞추되, 실패를 숨기는 꼬리(|| true 등)는 떼고 비교한다.
  그래야 `pytest -rs || true`가 '제거'가 아니라 'FAILURE_MASKED'로 잡힌다.
- V3a INCONCLUSIVE: base의 계약이 head에서 (a) 같은 명령이 있지만 job·step의 if가 표현식이거나,
  (b) 같은 명령이 있지만 그 워크플로의 정책 이벤트가 base보다 좁아졌거나(필터 없던 이벤트에 paths·branches 필터 추가),
  (c) 같은 명령이 없지만 head에 판별하지 못하는 실행 경로(재사용 워크플로, make test·tox·nox)가 있으면 INCONCLUSIVE.
  FAIL은 확인된 제거·비활성화일 때만.
- E1: 사례·출처에 env_required가 없으면 규칙을 쓰지 않는다. 있으면
  ENV_INSUFFICIENT = (1) 선언된 변수 (2) 마지막 traceback에서 앱 코드(사이트 패키지·표준 라이브러리 밖)의 가장 안쪽 프레임이
  그 변수의 read_at(파일 끝부분·줄)과 같고, 마지막 예외 줄에 변수 이름이 있음 (3) 그 traceback에 연쇄 예외가 없고,
  그 앞에 다른 마지막 예외 줄을 가진 traceback이 없음.
  UNKNOWN_CAUSE = (2)·(3)이 확인되지 않았지만 실패 로그에 선언된 변수 이름이 단어로 나옴.
  그 밖(변수 이름이 로그에 없음)은 준비 실패 그대로 FAIL. 설계 3장 A의 "1은 맞지만 2·3이 확인되지 않으면 UNKNOWN_CAUSE"를
  "로그에 그 변수 신호가 있을 때"로 좁힌 것이다 — 그렇지 않으면 env_required가 켜진 S3의 모든 심은 결함이 UNKNOWN_CAUSE가 된다.
"""

import io
import re
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "spikes" / "stage2b_0"))
from artifactlib import NEUTRALIZED, POLICY_EVENTS, const_if, normalize, result, rm, test_steps, triggers, workflows  # noqa: E402,F401

FILTER_KEYS = ("paths", "paths-ignore", "branches", "branches-ignore")
MECH = {"if가 항상 거짓": "NOT_EXECUTED", "continue-on-error: true": "FAILURE_ALLOWED", "실패를 무시하는 명령 (|| true 등)": "FAILURE_MASKED"}


# ---------------------------------------------------------------- 스냅샷

def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), *args], capture_output=True, text=True,
                          encoding="utf-8", check=True).stdout


def source_snapshot(repo: Path, commit: str, context: str, dest: Path) -> str:
    """commit의 context 디렉터리를 dest에 그대로 푼다. 전체 커밋 해시를 돌려준다."""
    full = git(repo, "rev-parse", commit).strip()
    tree = full if context in (".", "") else f"{full}:{context}"
    data = subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo), "archive", "--format=tar", tree],
                          capture_output=True, check=True).stdout
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest, filter="data")
    return full


def apply_edits(dest: Path, case: dict) -> None:
    for e in case.get("edits", []):
        f = dest / e["path"]
        if "create" in e:
            if f.exists():
                raise ValueError(f"{case['id']}: create 대상이 이미 있음 ({e['path']})")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(e["create"].encode("utf-8"))
            continue
        text = f.read_bytes().decode("utf-8")
        find, repl = e["find"], e["replace"]
        if "\r\n" in text:
            find, repl = find.replace("\n", "\r\n"), repl.replace("\n", "\r\n")
        if text.count(find) != 1:
            raise ValueError(f"{case['id']}: find가 정확히 한 번 나오지 않음 ({e['path']}, {text.count(find)}회)")
        f.write_bytes(text.replace(find, repl).encode("utf-8"))


# ---------------------------------------------------------------- V3

def _key(cmd: str) -> str:
    return NEUTRALIZED.sub("", cmd).strip()


def _filters(snap: Path) -> dict[str, dict[str, bool]]:
    """워크플로별 정책 이벤트 → 필터 있음 여부."""
    out = {}
    for path, wf in workflows(snap).items():
        trig = triggers(wf)
        out[path] = {e: bool(isinstance(trig[e], dict) and any(k in trig[e] for k in FILTER_KEYS)) for e in POLICY_EVENTS if e in trig}
    return out


def _mechs(disabled: list[str]) -> list[str]:
    return sorted({MECH[d] for d in disabled})


def _brief(s: dict) -> dict:
    return {k: s[k] for k in ("workflow", "job", "step", "command") if k in s}


def v3_policy2(snap: Path, base_snap: Path | None) -> dict:
    if not workflows(snap):
        return {"V3a": result("NOT_RUN", reason="head에 워크플로 없음"), "V3b": result("NOT_RUN", reason="head에 워크플로 없음")}
    head_steps, unsure, events = test_steps(snap)
    enabled = [s for s in head_steps if not s["disabled"]]
    filt = _filters(snap)

    # V3b 절대 — 2b.0 판단 + FAIL 메커니즘
    unfiltered = any(not f for ev in events.values() for f in ev.values())
    if any(not s["if_expression"] for s in enabled) and unfiltered:
        v3b = result("PASS", steps=[_brief(s) for s in enabled], events=events)
    elif enabled and not unfiltered:
        v3b = result("INCONCLUSIVE", reason="정책 이벤트가 모두 paths·branches 필터로 좁혀짐", events=events)
    elif enabled:
        v3b = result("INCONCLUSIVE", reason="테스트 단계의 if가 표현식이라 정적으로 참·거짓을 정하지 못함", steps=[_brief(s) for s in enabled])
    elif unsure:
        v3b = result("INCONCLUSIVE", reason="pytest 단계는 없지만 판별하지 못하는 실행 경로가 있음", unsure=unsure)
    else:
        dis = [s for s in head_steps if s["disabled"]]
        mech = sorted({m for s in dis for m in _mechs(s["disabled"])}) or ["REMOVED"]
        v3b = result("FAIL", mechanism=mech, reason="push·pull_request 워크플로에 실행되고 실패가 전파되는 pytest 단계가 없음",
                     disabled_steps=[_brief(s) | {"disabled": s["disabled"]} for s in dis], events=events)

    # V3a 상대
    if base_snap is None:
        return {"V3a": result("NOT_RUN", reason="비교 기준 없음"), "V3b": v3b}
    base_steps, _, _ = test_steps(base_snap)
    base_enabled = [s for s in base_steps if not s["disabled"]]
    if not base_enabled:
        return {"V3a": result("NOT_RUN", reason="base에 활성화된 테스트 실행 단계가 없음 (비교 대상 없음)"), "V3b": v3b}
    base_filt = _filters(base_snap)
    removed, disabled_now, unclear, moved = [], [], [], []
    for b in base_enabled:
        same = [h for h in head_steps if _key(h["command"]) == _key(b["command"])]
        live = [h for h in same if not h["disabled"]]
        if live:
            base_unf = any(v is False for v in base_filt.get(b["workflow"], {}).values())
            head_unf = any(v is False for h in live for v in filt.get(h["workflow"], {}).values())
            if all(h["if_expression"] for h in live):
                unclear.append({"base": _brief(b), "why": "같은 명령의 job·step if가 표현식"})
            elif base_unf and not head_unf:
                unclear.append({"base": _brief(b), "why": "필터 없던 정책 이벤트가 head에서 모두 paths·branches 필터로 좁혀지거나 사라짐",
                                "base_events": base_filt.get(b["workflow"]), "head_events": {h["workflow"]: filt.get(h["workflow"]) for h in live}})
            elif not any(h["job"] == b["job"] and h["step"] == b["step"] and h["command"] == b["command"] for h in live):
                moved.append(_brief(b))
            continue
        if same:
            disabled_now.append({"base": _brief(b), "head": [_brief(h) | {"disabled": h["disabled"]} for h in same],
                                 "mechanism": sorted({m for h in same for m in _mechs(h["disabled"])})})
        elif unsure:
            unclear.append({"base": _brief(b), "why": "같은 명령이 없지만 판별하지 못하는 실행 경로가 있음", "unsure": unsure})
        else:
            removed.append({"base": _brief(b)})
    if removed or disabled_now:
        mech = sorted({"REMOVED"} if removed else set()) + sorted({m for d in disabled_now for m in d["mechanism"]})
        v3a = result("FAIL", mechanism=sorted(set(mech)), removed=removed, disabled=disabled_now, unclear=unclear)
    elif unclear:
        v3a = result("INCONCLUSIVE", reason="base의 테스트 실행 계약을 head에서 정적으로 확인하지 못함", unclear=unclear)
    else:
        v3a = result("PASS", moved_or_renamed=moved)
    return {"V3a": v3a, "V3b": v3b}


# ---------------------------------------------------------------- E1 환경 부족 규칙

TB_START = "Traceback (most recent call last):"
FRAME = re.compile(r'^\s*File "([^"]+)", line (\d+)')
CHAIN = ("During handling of the above exception", "The above exception was the direct cause")
LIB_PATH = re.compile(r"site-packages|dist-packages|/usr/(local/)?lib/python\d|<frozen ")


def tracebacks(lines: list[str]) -> list[dict]:
    """로그에서 traceback 블록들: frames, final(마지막 예외 줄), chained(블록 바로 앞에 연쇄 문구)."""
    out = []
    i = 0
    while i < len(lines):
        if lines[i].strip().endswith(TB_START):
            frames, j = [], i + 1
            while j < len(lines):
                m = FRAME.match(lines[j])
                if m:
                    frames.append((m.group(1), int(m.group(2))))
                    j += 1
                elif lines[j].startswith((" ", "\t")) or not lines[j].strip():
                    j += 1
                else:
                    break
            final = lines[j].strip() if j < len(lines) else ""
            prev = "\n".join(lines[max(0, i - 3):i])
            out.append({"frames": frames, "final": final, "chained": any(c in prev for c in CHAIN)})
            i = j
        else:
            i += 1
    return out


def env_rule(log_lines: list[str], env_required: list[dict]) -> dict | None:
    """준비 실패 로그에 E1 규칙을 적용. None이면 규칙 미적용(FAIL 유지)."""
    if not env_required:
        return None
    tbs = tracebacks(log_lines)
    names = [v["name"] for v in env_required]
    if tbs:
        last = tbs[-1]
        app = [f for f in last["frames"] if not LIB_PATH.search(f[0])]
        inner = app[-1] if app else None
        others = {t["final"] for t in tbs[:-1]} - {last["final"]}
        for v in env_required:
            file, line = v["read_at"].rsplit(":", 1)
            at = inner is not None and inner[0].replace("\\", "/").endswith("/" + file) and inner[1] == int(line)
            named = re.search(rf"\b{re.escape(v['name'])}\b", last["final"]) is not None
            if at and named and not last["chained"] and not others:
                return {"reason": "ENV_INSUFFICIENT", "variable": v["name"], "read_at": v["read_at"], "final_exception": last["final"],
                        "app_frame": f"{PurePosixPath(inner[0]).name}:{inner[1]}"}
    text = "\n".join(log_lines)
    seen = [n for n in names if re.search(rf"\b{re.escape(n)}\b", text)]
    if seen:
        return {"reason": "UNKNOWN_CAUSE", "variables_in_log": seen,
                "final_exception": tbs[-1]["final"] if tbs else None, "tracebacks": len(tbs)}
    return None
