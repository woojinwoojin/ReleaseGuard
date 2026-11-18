"""Stage 2b.1 V2 동적 준비 검사 (설계 docs/design_stage2b_1.md 3장 A, 5장 격리). 일회용 EC2에서 돌린다(Q8).

2b.0 run_v2와 같은 흐름(스냅샷 → build → 격리 run → 준비 확인 → 정리)에 다음을 더한다.
- 출처별 context·build_target (`docker build --target`), 줄바꿈 변환 없는 스냅샷
- 빌드 전 정적 확인 기록: 대상 단계까지의 FROM·RUN·COPY --from 줄, requirements 파일 내용
- 빌드 로그(--progress=plain)에서 이미지 다이제스트(sha256) 전부, 1회차에 설치 패키지(pip freeze, 격리 실행)
- 이미지 설정(Entrypoint·Cmd·Env·User·ExposedPorts) 기록 — A0 '필요한 환경 변수와 실행 명령'
- 시작 로그 앞 50줄·마지막 40줄 따로 저장, factory 경고 여부(H-F, 결과 값에 안 씀)
- 준비 실패에 E1 환경 부족 규칙(lib2b1.env_rule) → INCONCLUSIVE(ENV_INSUFFICIENT | UNKNOWN_CAUSE)

결과: docs/eval/v2b1/v2_result.json (--a0이면 a0_result.json). 사례×회차마다 바로 저장, 다시 실행하면 저장된 것은 건너뜀.
사용 (release-guard 루트): python spikes/stage2b_1/run_v2.py [--a0] [--only ID ...]
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib2b1 import ROOT, apply_edits, env_rule, git, rm, source_snapshot  # noqa: E402

sys.path.insert(0, str(ROOT / "spikes" / "stage2b_0"))
from artifactlib import dockerfile_instructions  # noqa: E402

sys.path.insert(0, str(ROOT / "spikes" / "stage2_1"))
from mutlib import clean  # noqa: E402  홈·임시 경로·계정 이름 가림

CASES = ROOT / "eval" / "artifact_cases_2b1.yaml"
OUT = ROOT / "docs" / "eval" / "v2b1"
PREFIX = "rg2b1-"
ISOLATION = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
RUN_OPTS = [*ISOLATION, "--memory", "512m", "--cpus", "1", "--pids-limit", "256"]
BUILD_TIMEOUT = 900
ENV_HINT = re.compile(r"Temporary failure in name resolution|Could not resolve|Connection (refused|reset|timed out)|"
                      r"failed to resolve source metadata|TLS handshake timeout|no such host", re.I)
DIGEST = re.compile(r"([\w./:-]+@sha256:[0-9a-f]{64})")
FACTORY = "ASGI app factory detected"


def docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def cut(lines: list[str]) -> list[str]:
    return [clean(x)[:300] for x in lines]


def leftovers() -> dict:
    c = docker("ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}").stdout.split()
    i = [x for x in docker("images", "--format", "{{.Repository}}:{{.Tag}}").stdout.split() if x.startswith(PREFIX)]
    n = [x for x in docker("network", "ls", "--format", "{{.Name}}").stdout.split() if x.startswith(PREFIX)]
    return {"containers": c, "images": i, "networks": n}


def prebuild_review(snap: Path, target: str | None) -> dict:
    """대상 단계까지의 FROM·RUN·COPY --from 줄과 requirements 내용 (설계 5장 '빌드 전 정적 확인')."""
    df = snap / "Dockerfile"
    lines, stage_done = [], False
    for no, ins, arg in dockerfile_instructions(df.read_text(encoding="utf-8")):
        if ins == "FROM" and stage_done:
            break
        if ins == "FROM" and target and re.search(rf"\bAS\s+{re.escape(target)}\b", arg, re.I):
            stage_done = True
        if ins in ("FROM", "RUN") or (ins == "COPY" and "--from" in arg):
            lines.append(f"{no}: {ins} {arg}"[:300])
    reqs = {p.name: p.read_text(encoding="utf-8").splitlines() for p in snap.glob("requirements*.txt")}
    return {"instructions": lines, "requirements": reqs}


def probe(name: str, url: str) -> tuple[bool, str]:
    code = f"import urllib.request\nr=urllib.request.urlopen({url!r},timeout=2)\nprint(r.status)"
    p = docker("exec", name, "python", "-c", code, timeout=15)
    err = p.stderr.strip().splitlines()
    return p.returncode == 0, clean(p.stdout.strip() if p.returncode == 0 else (err[-1] if err else f"exit {p.returncode}"))[:300]


def logs_of(tag: str) -> list[str]:
    lg = docker("logs", tag)
    return (lg.stdout + "\n" + lg.stderr).strip().splitlines()


def run_once(snap: Path, case: dict, src: dict, rep: int, cfg: dict) -> dict:
    tag = f"{PREFIX}{case['id'].lower()}-{rep}"
    rec: dict = {"image": tag, "cold": rep == 1, "seconds": {}}
    target = src.get("build_target")
    t = time.perf_counter()
    build = docker("build", "--progress=plain", *(["--no-cache"] if rep == 1 else []), *(["--target", target] if target else []),
                   "-t", tag, str(snap), timeout=BUILD_TIMEOUT)
    rec["seconds"]["build"] = round(time.perf_counter() - t, 2)
    blog = build.stdout + "\n" + build.stderr
    rec["build_digests"] = sorted(set(DIGEST.findall(blog)))
    if build.returncode != 0:
        status = "INCONCLUSIVE" if ENV_HINT.search(blog) else "FAIL"
        return rec | {"status": status, "stage": "build", "reason": "빌드 실패" + (" (환경 원인으로 보임)" if status == "INCONCLUSIVE" else ""),
                      "log_tail": cut(blog.strip().splitlines()[-20:])}
    conf = json.loads(docker("image", "inspect", "-f", "{{json .Config}}", tag).stdout.strip() or "{}")
    rec["image_config"] = {k: conf.get(k) for k in ("Entrypoint", "Cmd", "Env", "User", "ExposedPorts", "WorkingDir")}
    hc = conf.get("Healthcheck")
    rec["image_healthcheck"] = hc
    if rep == 1:
        fr = docker("run", "--rm", *ISOLATION, "--entrypoint", "python", tag, "-m", "pip", "freeze", timeout=60)
        rec["pip_freeze"] = fr.stdout.split() if fr.returncode == 0 else {"error": cut(fr.stderr.strip().splitlines()[-3:])}
    url = src["probe"]
    limit = cfg["v2_ready_timeout_seconds"]
    if hc and hc.get("Test"):
        ns = 1e9
        limit = max(limit, (hc.get("StartPeriod", 0) + 2 * hc.get("Interval", 30 * ns)) / ns)
    rec["ready_timeout_seconds"] = limit
    t = time.perf_counter()
    run = docker("run", "-d", "--name", tag, *RUN_OPTS, tag)
    rec["seconds"]["start"] = round(time.perf_counter() - t, 2)
    if run.returncode != 0:
        docker("rm", "-f", tag)
        docker("rmi", "-f", tag)
        return rec | {"status": "FAIL", "stage": "run", "reason": "docker run 실패", "log_tail": cut(run.stderr.strip().splitlines()[-15:])}
    t0 = time.perf_counter()
    last, status = "", None
    while time.perf_counter() - t0 < limit:
        st = json.loads(docker("inspect", "-f", "{{json .State}}", tag).stdout)
        if not st.get("Running"):
            status = {"status": "FAIL", "stage": "start", "reason": f"컨테이너가 준비 전에 종료됨 (종료 코드 {st.get('ExitCode')})",
                      "exit_code": st.get("ExitCode")}
            break
        if hc and hc.get("Test"):
            h = (st.get("Health") or {}).get("Status")
            last = f"health={h}"
            if h == "healthy":
                status = {"status": "PASS", "stage": "ready", "ready_by": "image HEALTHCHECK"}
                break
        else:
            ok, msg = probe(tag, url)
            last = msg
            if ok:
                status = {"status": "PASS", "stage": "ready", "ready_by": f"probe {url}", "probe_result": msg}
                break
        time.sleep(cfg["v2_poll_seconds"])
    rec["seconds"]["ready"] = round(time.perf_counter() - t0, 2)
    if status is None:
        status = {"status": "FAIL", "stage": "ready", "reason": f"{limit}초 안에 준비되지 않음", "last_probe": last}
    lines = logs_of(tag)
    sl = cfg["startup_log"]
    rec["log_head"] = cut(lines[:sl["head_lines"]])
    rec["log_tail"] = cut(lines[-sl["tail_lines"]:]) if len(lines) > sl["head_lines"] else []
    rec["log_lines"] = len(lines)
    rec["factory_warning"] = any(FACTORY in x for x in lines)
    if status["status"] == "FAIL":
        env = (src.get("env_required") or []) + (case.get("env_required") or [])
        er = env_rule(lines, env)
        status["env_rule"] = er
        if er:
            status = status | {"status": "INCONCLUSIVE", "inconclusive_reason": er["reason"], "fail_evidence_kept": status["reason"]}
    t = time.perf_counter()
    docker("rm", "-f", tag)
    docker("rmi", "-f", tag)
    rec["seconds"]["cleanup"] = round(time.perf_counter() - t, 2)
    return rec | status


def repo_state(repos: set[Path]) -> dict:
    return {str(r.relative_to(ROOT.parent)) if r.is_relative_to(ROOT.parent) else r.name:
            [git(r, "rev-parse", "HEAD").strip(), git(r, "status", "--porcelain")] for r in sorted(repos)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a0", action="store_true", help="A0 표본 적합성 사전 검사: baseline 사례 1회(콜드)")
    ap.add_argument("--only", nargs="*", help="이 사례 ID만")
    args = ap.parse_args()
    cfg = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    cases = [c for c in cfg["v2_cases"] if (not args.a0 or c["kind"] == "baseline") and (not args.only or c["id"] in args.only)]
    repos = {(ROOT / cfg["sources"][c["source"]]["repo"]).resolve() for c in cases}
    out_file = OUT / ("a0_result.json" if args.a0 else "v2_result.json")
    data = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else {"runs": [], "prebuild_review": {}, "results": {}}
    v = docker("version", "--format", "{{.Client.Version}}|{{.Server.Version}}|{{.Server.Os}}/{{.Server.Arch}}").stdout.strip().split("|")
    info = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "docker": {"client": v[0], "server": v[1] if len(v) > 1 else None, "platform": v[-1]},
            "run_options": RUN_OPTS, "build_network": "default (기본 이미지 레지스트리·PyPI 접근, 빌드 로그에 다이제스트 기록)",
            "repos_before": repo_state(repos), "leftovers_before": leftovers()}
    data["runs"].append(info)
    OUT.mkdir(parents=True, exist_ok=True)

    def save():
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    reps = 1 if args.a0 else cfg["v2_repeats"]
    for case in cases:
        src = cfg["sources"][case["source"]]
        repo = (ROOT / src["repo"]).resolve()
        for rep in range(1, reps + 1):
            key = f"{case['id']}#{rep}"
            if key in data["results"]:
                continue
            snap = Path(tempfile.mkdtemp(prefix="rg2b1_"))
            try:
                full = source_snapshot(repo, src["commit"], src["context"], snap)
                apply_edits(snap, case)
                if case["id"] not in data["prebuild_review"]:
                    data["prebuild_review"][case["id"]] = prebuild_review(snap, src.get("build_target"))
                try:
                    rec = run_once(snap, case, src, rep, cfg)
                except Exception as e:  # noqa: BLE001 — 조용히 빼지 않는다
                    rec = {"status": "ERROR", "error": clean(repr(e))[:300]}
                    docker("rm", "-f", f"{PREFIX}{case['id'].lower()}-{rep}")
                    docker("rmi", "-f", f"{PREFIX}{case['id'].lower()}-{rep}")
            finally:
                rm(snap)
            rec["source_commit"] = full[:12]
            rec["expected"] = case["expected"]
            rec["expected_reason"] = case.get("expected_reason")
            rec["match"] = rec["status"] == case["expected"] and (not case.get("expected_reason") or rec.get("inconclusive_reason") == case["expected_reason"])
            data["results"][key] = rec
            save()
            print(f"{key:10} {rec['status']:13} {rec.get('inconclusive_reason') or '':16} 기대 {case['expected']:12} "
                  f"{rec.get('stage', '')} {rec.get('reason', rec.get('ready_by', ''))} factory={rec.get('factory_warning')} {rec.get('seconds', '')}",
                  flush=True)
    info |= {"leftovers_after": leftovers(), "repos_after": repo_state(repos), "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
    info["repos_preserved"] = info["repos_after"] == info["repos_before"]
    save()
    print("잔여", info["leftovers_after"], "· 대상 저장소 보존", info["repos_preserved"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
