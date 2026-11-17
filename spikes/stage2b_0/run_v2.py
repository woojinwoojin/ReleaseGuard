"""Stage 2b.0 9장 3단계: V2 동적 준비 검사 (설계 docs/design_stage2b_0.md 4장 V2, 5장 격리).

사례마다: 스냅샷(git archive) → docker build → docker run(격리) → 준비 확인 → 정리.
- 빌드: 네트워크 허용(pip). 1회차는 --no-cache(콜드), 2·3회차는 캐시 사용. 기본 이미지 다이제스트 기록.
- 실행: --network none, --memory 512m --cpus 1 --pids-limit 256, --cap-drop ALL, no-new-privileges.
  비밀값·env 파일·볼륨·Docker 소켓 없음. Dockerfile의 USER 그대로.
- 준비 확인: 이미지 HEALTHCHECK가 있으면 healthy, 없으면 사례 파일 v2_probe.url에 컨테이너 안에서 요청(docker exec, Python urllib).
  2xx·3xx → PASS. 상한 전에 종료 → FAIL(종료 코드·로그). 응답 없이 상한 → FAIL(마지막 요청 오류).
  확인 수단이 없는데 살아 있기만 함 → STARTED_ONLY.
- 정리: docker rm -f, docker rmi. 접두어 rg2b0- 로 남은 컨테이너·이미지가 0개인지 확인. 빌드 캐시는 지우지 않고 기록만 한다.
결과: docs/eval/v2b0/v2_result.json (--precheck면 v2_precheck.json). 사례×회차마다 바로 저장, 다시 실행하면 저장된 것은 건너뜀.

사용 (release-guard 루트): .venv/Scripts/python spikes/stage2b_0/run_v2.py [--precheck]
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifactlib import ROOT, case_snapshot, git, rm, tmpdir  # noqa: E402

sys.path.insert(0, str(ROOT / "spikes" / "stage2_1"))
from mutlib import clean  # noqa: E402  홈·임시 경로·계정 이름 가림

CASES = ROOT / "eval" / "artifact_cases_2b0.yaml"
OUT = ROOT / "docs" / "eval" / "v2b0"
PREFIX = "rg2b0-"
RUN_OPTS = ["--network", "none", "--memory", "512m", "--cpus", "1", "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
BUILD_TIMEOUT = 900
ENV_HINT = re.compile(r"Temporary failure in name resolution|Could not resolve|Connection (refused|reset|timed out)|"
                      r"failed to resolve source metadata|TLS handshake timeout|no such host", re.I)


def docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def tail(text: str, n: int = 15) -> list[str]:
    return [clean(line)[:300] for line in text.strip().splitlines()[-n:]]


def leftovers() -> dict:
    c = docker("ps", "-a", "--filter", f"name={PREFIX}", "--format", "{{.Names}}").stdout.split()
    i = [x for x in docker("images", "--format", "{{.Repository}}:{{.Tag}}").stdout.split() if x.startswith(PREFIX)]
    return {"containers": c, "images": i}


def probe(name: str, url: str) -> tuple[bool, str]:
    code = ("import sys,urllib.request\n"
            f"r=urllib.request.urlopen({url!r},timeout=2)\n"
            "print(r.status)")
    p = docker("exec", name, "python", "-c", code, timeout=15)
    err = p.stderr.strip().splitlines()
    msg = p.stdout.strip() if p.returncode == 0 else (err[-1] if err else f"exit {p.returncode}")
    return p.returncode == 0, clean(msg)[:300]


def run_once(snap: Path, case_id: str, rep: int, cfg: dict) -> dict:
    tag = f"{PREFIX}{case_id.lower()}-{rep}"
    rec: dict = {"image": tag, "cold": rep == 1, "seconds": {}}
    t = time.perf_counter()
    build = docker("build", *(["--no-cache"] if rep == 1 else []), "-t", tag, str(snap), timeout=BUILD_TIMEOUT)
    rec["seconds"]["build"] = round(time.perf_counter() - t, 2)
    if build.returncode != 0:
        status = "INCONCLUSIVE" if ENV_HINT.search(build.stderr) else "FAIL"
        return rec | {"status": status, "stage": "build", "reason": "빌드 실패" + (" (환경 원인으로 보임)" if status == "INCONCLUSIVE" else ""),
                      "log_tail": tail(build.stderr)}
    hc = json.loads(docker("image", "inspect", "-f", "{{json .Config.Healthcheck}}", tag).stdout.strip() or "null")
    rec["image_healthcheck"] = hc
    url = cfg["v2_probe"]["url"]
    limit = cfg["v2_probe"]["ready_timeout_seconds"]
    if hc and hc.get("Test"):
        ns = 1e9
        limit = max(limit, (hc.get("StartPeriod", 0) + 2 * hc.get("Interval", 30 * ns)) / ns)
    rec["ready_timeout_seconds"] = limit
    t = time.perf_counter()
    run = docker("run", "-d", "--name", tag, *RUN_OPTS, tag)
    rec["seconds"]["start"] = round(time.perf_counter() - t, 2)
    if run.returncode != 0:
        return rec | {"status": "FAIL", "stage": "run", "reason": "docker run 실패", "log_tail": tail(run.stderr)}
    t0 = time.perf_counter()
    last = ""
    status = None
    while time.perf_counter() - t0 < limit:
        st = json.loads(docker("inspect", "-f", "{{json .State}}", tag).stdout)
        if not st.get("Running"):
            logs = docker("logs", tag)
            status = {"status": "FAIL", "stage": "start", "reason": f"컨테이너가 준비 전에 종료됨 (종료 코드 {st.get('ExitCode')})",
                      "exit_code": st.get("ExitCode"), "log_tail": tail(logs.stdout + "\n" + logs.stderr)}
            break
        if hc and hc.get("Test"):
            h = (st.get("Health") or {}).get("Status")
            last = f"health={h}"
            if h == "healthy":
                status = {"status": "PASS", "stage": "ready", "ready_by": "image HEALTHCHECK"}
                break
        elif url:
            ok, msg = probe(tag, url)
            last = msg
            if ok:
                status = {"status": "PASS", "stage": "ready", "ready_by": f"probe {url}", "probe_result": msg}
                break
        time.sleep(cfg["v2_probe"]["poll_seconds"])
    rec["seconds"]["ready"] = round(time.perf_counter() - t0, 2)
    if status is None:
        logs = docker("logs", tag)
        if not (hc and hc.get("Test")) and not url:
            status = {"status": "STARTED_ONLY", "stage": "ready", "reason": "준비 확인 수단 없음, 프로세스만 살아 있음"}
        else:
            status = {"status": "FAIL", "stage": "ready", "reason": f"{limit}초 안에 준비되지 않음", "last_probe": last,
                      "log_tail": tail(logs.stdout + "\n" + logs.stderr)}
    t = time.perf_counter()
    docker("rm", "-f", tag)
    docker("rmi", "-f", tag)
    rec["seconds"]["cleanup"] = round(time.perf_counter() - t, 2)
    return rec | status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--precheck", action="store_true", help="N0 1회만 (9장 3단계 사전 점검)")
    args = ap.parse_args()
    cfg = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    repo = (ROOT / cfg["repo"]).resolve()
    out_file = OUT / ("v2_precheck.json" if args.precheck else "v2_result.json")
    data = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else {"runs": [], "results": {}}
    v = docker("version", "--format", "{{.Client.Version}}|{{.Server.Version}}|{{.Server.Os}}/{{.Server.Arch}}").stdout.strip().split("|")
    info = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "docker": {"client": v[0], "server": v[1], "platform": v[-1]},
            "run_options": RUN_OPTS, "build_network": "default (pip 설치에 외부 접근)", "repo_before": [git(repo, "rev-parse", "HEAD").strip(), git(repo, "status", "--porcelain")],
            "leftovers_before": leftovers()}
    data["runs"].append(info)
    OUT.mkdir(parents=True, exist_ok=True)

    def save():
        out_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    cases = [c for c in cfg["cases"] if c["id"] == "N0"] if args.precheck else cfg["cases"]
    reps = 1 if args.precheck else cfg["v2_repeats"]
    for case in cases:
        for rep in range(1, reps + 1):
            key = f"{case['id']}#{rep}"
            if key in data["results"]:
                continue
            snap = tmpdir()
            try:
                case_snapshot(repo, cfg["base"], case, snap)
                if not (snap / "Dockerfile").exists():
                    rec = {"status": "NOT_RUN", "reason": "Dockerfile 없음"}
                else:
                    try:
                        rec = run_once(snap, case["id"], rep, cfg)
                    except Exception as e:  # noqa: BLE001 — 조용히 빼지 않는다
                        rec = {"status": "ERROR", "error": clean(repr(e))[:300]}
                        docker("rm", "-f", f"{PREFIX}{case['id'].lower()}-{rep}")
                        docker("rmi", "-f", f"{PREFIX}{case['id'].lower()}-{rep}")
            finally:
                rm(snap)
            rec["expected"] = case["expected"]["V2"]
            rec["match"] = rec["status"] == rec["expected"]
            data["results"][key] = rec
            save()
            print(f"{key:6} {rec['status']:13} 기대 {rec['expected']:8} {rec.get('stage', '')} {rec.get('reason', rec.get('ready_by', ''))}"
                  f" {rec.get('seconds', '')}", flush=True)
    base_img = docker("image", "inspect", "-f", "{{json .RepoDigests}}", "python:3.13-slim").stdout.strip()
    info |= {"base_image_digests": json.loads(base_img or "[]"), "leftovers_after": leftovers(),
             "repo_after": [git(repo, "rev-parse", "HEAD").strip(), git(repo, "status", "--porcelain")],
             "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
    info["repo_preserved"] = info["repo_after"] == info["repo_before"]
    save()
    print("잔여", info["leftovers_after"], "· 대상 저장소 보존", info["repo_preserved"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
