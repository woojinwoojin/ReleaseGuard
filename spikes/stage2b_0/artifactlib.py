"""Stage 2b.0 검증기 공용 코드 (설계 docs/design_stage2b_0.md 4장).

V1 정적 진입점 검사와 V3 CI 정책 검사. 둘 다 코드를 실행하지 않는다 (AST·YAML 파싱만).
결과 값: PASS / FAIL / INCONCLUSIVE / NOT_RUN. 판정(SAFE·REVIEW·BLOCK)과 분리한다.

구현 중 정한 해석 (검증기 실행 전, 설계 4장 범위 안):
- V3b 이벤트 필터: push·pull_request 중 하나라도 paths·branches 필터 없이 테스트 단계에 닿으면 PASS.
  모든 정책 이벤트가 필터로 좁혀져 있을 때만 INCONCLUSIVE. (4주차 push는 branches: [main]이지만 pull_request는 필터 없음)
- V1: import로 묶인 이름(import … as api, from x import api)도 '정의됨'으로 보고 PASS, 근거에 defined_by: import를 남긴다.
- V3a 같은 계약: 주석을 지우고 공백을 정리한 run 명령이 같으면 같은 테스트 실행 계약으로 본다 (작업·단계 이름은 무관).
"""

import ast
import fnmatch
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from releaseguard.runner import snapshot  # noqa: E402

POLICY_EVENTS = ("push", "pull_request")
SERVERS = {"uvicorn", "gunicorn"}
APP_REF = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")
VALUE_OPTS = {"-b", "--bind", "--host", "--port", "--app-dir", "-w", "--workers", "-k", "--worker-class", "-c", "--config",
              "--timeout-keep-alive", "--log-level", "--root-path", "--env-file", "--uds", "--fd"}
PYTEST = re.compile(r"(^|[\s;&|(])(python3?\s+-m\s+)?pytest(\s|$)")
OTHER_RUNNERS = re.compile(r"(^|[\s;&|(])(make\s+test|tox|nox)(\s|$)")
NEUTRALIZED = re.compile(r"\|\|\s*(true|:)\s*$|;\s*true\s*$")


def result(status: str, **kw) -> dict:
    return {"status": status, **kw}


# ---------------------------------------------------------------- 스냅샷

def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def case_snapshot(repo: Path, base: str, case: dict, dest: Path) -> dict:
    """사례의 head 스냅샷을 dest에 만들고 {head, compare_base} 커밋을 돌려준다. seed는 base에 find/replace를 적용한다."""
    if case["kind"] == "commit":
        head = git(repo, "rev-parse", case["commit"]).strip()
        snapshot(repo, head, dest)
        parent = git(repo, "rev-parse", f"{head}^").strip()
        return {"head": head[:7], "compare_base": parent}
    head = git(repo, "rev-parse", base).strip()
    snapshot(repo, head, dest)
    for e in case.get("edits", []):
        f = dest / e["path"]
        text = f.read_bytes().decode("utf-8")
        if text.count(e["find"]) != 1:
            raise ValueError(f"{case['id']}: find가 정확히 한 번 나오지 않음 ({e['path']})")
        f.write_bytes(text.replace(e["find"], e["replace"]).encode("utf-8"))
    return {"head": f"{head[:7]}+{case['id']}", "compare_base": head}


# ---------------------------------------------------------------- V1

def dockerfile_instructions(text: str) -> list[tuple[int, str, str]]:
    """(줄 번호, 명령, 인자) 목록. 줄 끝 \\ 이어 쓰기와 주석을 처리한다."""
    out, buf, start = [], "", None
    for no, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not buf and (not s or s.startswith("#")):
            continue
        if start is None:
            start = no
        if s.endswith("\\"):
            buf += s[:-1] + " "
            continue
        buf += s
        word, _, rest = buf.partition(" ")
        out.append((start, word.upper(), rest.strip()))
        buf, start = "", None
    return out


def exec_form(arg: str) -> list[str] | None:
    try:
        v = json.loads(arg)
    except json.JSONDecodeError:
        return None
    return v if isinstance(v, list) and all(isinstance(x, str) for x in v) else None


def top_level_bindings(tree: ast.Module) -> tuple[dict[str, str], list[str]]:
    """최상위(조건·try·with 안 포함, 함수·클래스 본문 제외)에서 묶이는 이름 → 종류. 그리고 정적 판단을 흐리는 구조 목록."""
    names, dynamic = {}, []

    def visit(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.setdefault(node.name, "def" if not isinstance(node, ast.ClassDef) else "class")
                if node.name == "__getattr__":
                    dynamic.append(f"{node.lineno}: 모듈 __getattr__")
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            names.setdefault(n.id, "assign")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for a in node.names:
                    if a.name == "*":
                        dynamic.append(f"{node.lineno}: from … import *")
                    else:
                        names.setdefault(a.asname or a.name.split(".")[0], "import")
            elif isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for field in ("body", "orelse", "finalbody"):
                    visit(getattr(node, field, []) or [])
                for h in getattr(node, "handlers", []) or []:
                    visit(h.body)
    visit(tree.body)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("exec", "globals", "setattr"):
            dynamic.append(f"{n.lineno}: {n.func.id}()")
    return names, dynamic


def copied_to_workdir(instr, snap: Path, rel_file: str) -> bool | None:
    """rel_file이 COPY로 WORKDIR 바로 아래에 들어가는가. 해석할 수 없으면 None."""
    workdir = "/"
    ignore = []
    di = snap / ".dockerignore"
    if di.exists():
        ignore = [l.strip() for l in di.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    if any(fnmatch.fnmatch(rel_file, p) for p in ignore):
        return False
    unknown = False
    for _, word, arg in instr:
        if word == "WORKDIR":
            workdir = str(PurePosixPath(workdir) / arg)
        elif word in ("COPY", "ADD"):
            parts = exec_form(arg) or shlex.split(arg)
            parts = [p for p in parts if not p.startswith("--")]
            if len(parts) < 2:
                unknown = True
                continue
            *srcs, dst = parts
            dst_abs = str(PurePosixPath(workdir) / dst) if not dst.startswith("/") else dst
            if dst_abs.rstrip("/") != workdir.rstrip("/"):
                continue
            for s in srcs:
                s = s.removeprefix("./")
                if s in (".", "") or fnmatch.fnmatch(rel_file, s) or rel_file == s:
                    return True
                if rel_file.startswith(s.rstrip("/") + "/"):
                    unknown = True  # 디렉터리째 복사: 들어가지만 WORKDIR 바로 아래가 아닐 수 있음
    return None if unknown else False


def v1_entrypoint(snap: Path) -> dict:
    df = snap / "Dockerfile"
    if not df.exists():
        return result("NOT_RUN", reason="Dockerfile 없음")
    instr = dockerfile_instructions(df.read_text(encoding="utf-8"))
    entry = next(((n, a) for n, w, a in reversed(instr) if w == "ENTRYPOINT"), None)
    cmd = next(((n, a) for n, w, a in reversed(instr) if w == "CMD"), None)
    if cmd is None and entry is None:
        return result("INCONCLUSIVE", reason="CMD·ENTRYPOINT 없음 (기본 이미지 명령)")
    argv: list[str] = []
    for item in (entry, cmd):
        if item is None:
            continue
        form = exec_form(item[1])
        if form is None:
            return result("INCONCLUSIVE", reason="셸 형식 명령", line=item[0], command=item[1])
        argv += form
    line = (cmd or entry)[0]
    ev = {"line": line, "argv": argv}
    if any("$" in a for a in argv):
        return result("INCONCLUSIVE", reason="환경 변수 치환", **ev)
    if argv[:3] in (["python", "-m", "uvicorn"], ["python3", "-m", "uvicorn"]):
        server, rest = "uvicorn", argv[3:]
    elif argv and PurePosixPath(argv[0]).name in SERVERS:
        server, rest = PurePosixPath(argv[0]).name, argv[1:]
    else:
        return result("INCONCLUSIVE", reason="해석하지 않는 서버 형식", **ev)
    if "--factory" in rest or "--app-dir" in rest:
        return result("INCONCLUSIVE", reason="--factory·--app-dir 사용", **ev)
    refs = [a for i, a in enumerate(rest) if APP_REF.match(a) and (i == 0 or rest[i - 1] not in VALUE_OPTS)]
    if len(refs) != 1:
        return result("INCONCLUSIVE", reason=f"모듈:이름 인자를 하나로 정하지 못함 ({refs})", **ev)
    module, name = refs[0].split(":")
    ev |= {"server": server, "app_ref": refs[0]}
    rel = module.replace(".", "/")
    candidates = [f"{rel}.py", f"{rel}/__init__.py"]
    found = next((c for c in candidates if (snap / c).exists()), None)
    if found is None:
        return result("FAIL", reason=f"모듈 {module}의 파일이 스냅샷에 없음 ({' / '.join(candidates)})", **ev)
    copied = copied_to_workdir(instr, snap, found)
    ev["module_file"] = found
    if copied is False:
        return result("FAIL", reason=f"{found}가 이미지 WORKDIR로 복사되지 않음 (COPY·.dockerignore)", **ev)
    if copied is None:
        return result("INCONCLUSIVE", reason="COPY 범위를 해석하지 못함", **ev)
    tree = ast.parse((snap / found).read_text(encoding="utf-8"))
    names, dynamic = top_level_bindings(tree)
    if name in names:
        return result("PASS", defined_by=names[name], **ev)
    if dynamic:
        return result("INCONCLUSIVE", reason=f"{found}에 {name} 정의가 없지만 동적 구조가 있음", dynamic=dynamic, **ev)
    near = sorted(n for n in names if not n.startswith("_"))[:20]
    return result("FAIL", reason=f"{found} 최상위에 이름 {name}이 정의되지 않음 (대입·def·class·import 모두 확인)",
                  module_top_level_names=near, **ev)


# ---------------------------------------------------------------- V3

def workflows(snap: Path) -> dict[str, dict]:
    d = snap / ".github" / "workflows"
    out = {}
    if d.is_dir():
        for f in sorted(list(d.glob("*.yml")) + list(d.glob("*.yaml"))):
            out[f".github/workflows/{f.name}"] = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return out


def triggers(wf: dict) -> dict:
    on = wf.get("on", wf.get(True))  # PyYAML은 키 on을 True로 읽는다
    if isinstance(on, str):
        return {on: {}}
    if isinstance(on, list):
        return {e: {} for e in on}
    return {k: (v or {}) for k, v in (on or {}).items()}


def const_if(expr) -> bool | None:
    """if 값이 상수면 참·거짓, 표현식이면 None. 없으면 True."""
    if expr is None:
        return True
    if isinstance(expr, bool):
        return expr
    s = str(expr).strip()
    s = s.removeprefix("${{").removesuffix("}}").strip()
    if s in ("false", "0", "''", '""'):
        return False
    if s in ("true", "1"):
        return True
    return None


def normalize(cmd: str) -> str:
    lines = []
    for line in cmd.splitlines():
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if line:
            lines.append(" ".join(line.split()))
    return " && ".join(lines)


def test_steps(snap: Path) -> tuple[list[dict], list[str], dict]:
    """정책 이벤트에서 도는 워크플로의 테스트 실행 단계 목록, 판단 불가 사유, 이벤트 정보."""
    steps, unsure, events = [], [], {}
    for path, wf in workflows(snap).items():
        trig = triggers(wf)
        pol = {e: trig[e] for e in POLICY_EVENTS if e in trig}
        if not pol:
            continue
        events[path] = {e: sorted(k for k in (v if isinstance(v, dict) else {}) if k in ("paths", "paths-ignore", "branches", "branches-ignore"))
                        for e, v in pol.items()}
        for job_id, job in (wf.get("jobs") or {}).items():
            if "uses" in job:
                unsure.append(f"{path} 작업 {job_id}: 재사용 워크플로 {job['uses']}")
                continue
            job_if = const_if(job.get("if"))
            for i, st in enumerate(job.get("steps") or []):
                run = st.get("run")
                if not isinstance(run, str):
                    continue
                cmd = normalize(run)
                if not PYTEST.search(cmd):
                    if OTHER_RUNNERS.search(cmd):
                        unsure.append(f"{path} 작업 {job_id} 단계 {st.get('name') or i}: pytest 이외의 테스트 실행기 ({cmd})")
                    continue
                step_if = const_if(st.get("if"))
                disabled = []
                if job_if is False or step_if is False:
                    disabled.append("if가 항상 거짓")
                if st.get("continue-on-error") is True or job.get("continue-on-error") is True:
                    disabled.append("continue-on-error: true")
                if NEUTRALIZED.search(cmd):
                    disabled.append("실패를 무시하는 명령 (|| true 등)")
                steps.append({"workflow": path, "job": job_id, "step": st.get("name") or f"#{i}", "command": cmd,
                              "disabled": disabled, "if_expression": job_if is None or step_if is None})
    return steps, unsure, events


def v3_policy(snap: Path, base_snap: Path | None) -> dict:
    head_steps, unsure, events = test_steps(snap)
    if not workflows(snap):
        return {"V3a": result("NOT_RUN", reason="head에 워크플로 없음"), "V3b": result("NOT_RUN", reason="head에 워크플로 없음")}
    enabled = [s for s in head_steps if not s["disabled"]]
    # V3b 절대
    unfiltered = any(not f for ev in events.values() for f in ev.values())
    if any(not s["if_expression"] for s in enabled) and unfiltered:
        v3b = result("PASS", steps=[{k: s[k] for k in ("workflow", "job", "step", "command")} for s in enabled], events=events)
    elif enabled and not unfiltered:
        v3b = result("INCONCLUSIVE", reason="정책 이벤트가 모두 paths·branches 필터로 좁혀짐", events=events)
    elif enabled:
        v3b = result("INCONCLUSIVE", reason="테스트 단계의 if가 표현식이라 정적으로 참·거짓을 정하지 못함", steps=enabled)
    elif unsure:
        v3b = result("INCONCLUSIVE", reason="pytest 단계는 없지만 판별하지 못하는 실행 경로가 있음", unsure=unsure)
    else:
        v3b = result("FAIL", reason="push·pull_request 워크플로에 활성화된 pytest 실행 단계가 없음",
                     disabled_steps=[s for s in head_steps if s["disabled"]], events=events)
    # V3a 상대
    if base_snap is None:
        v3a = result("NOT_RUN", reason="비교 기준 없음")
    else:
        base_steps, _, _ = test_steps(base_snap)
        base_enabled = [s for s in base_steps if not s["disabled"]]
        if not base_enabled:
            v3a = result("NOT_RUN", reason="base에 활성화된 테스트 실행 단계가 없음 (비교 대상 없음)")
        else:
            missing, disabled_now = [], []
            for b in base_enabled:
                same = [h for h in head_steps if h["command"] == b["command"]]
                if any(not h["disabled"] for h in same):
                    continue
                (disabled_now if same else missing).append({"base": {k: b[k] for k in ("workflow", "job", "step", "command")},
                                                            "head": [{k: h[k] for k in ("workflow", "job", "step", "disabled")} for h in same]})
            if missing or disabled_now:
                v3a = result("FAIL", reason="base의 테스트 실행 계약이 head에서 " + ("제거됨" if missing else "비활성화됨"),
                             removed=missing, disabled=disabled_now)
            else:
                moved = [b for b in base_enabled if not any(h["command"] == b["command"] and h["job"] == b["job"] and h["step"] == b["step"]
                                                           for h in enabled)]
                v3a = result("PASS", moved_or_renamed=[{k: b[k] for k in ("job", "step", "command")} for b in moved])
    return {"V3a": v3a, "V3b": v3b}


def tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="rg2b0_"))


def rm(p: Path) -> None:
    shutil.rmtree(p, ignore_errors=True)
