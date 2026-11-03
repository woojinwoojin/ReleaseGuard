"""실행:
python -m releaseguard analyze --repo <경로> --base <ref> --head <ref> [--python <경로>] [--no-agent]
python -m releaseguard eval [--cases eval/cases.yaml] [--agent] [--repeat N]
python -m releaseguard seeds [--seeds eval/seeds_predict_success.yaml]
python -m releaseguard szz [--cases eval/cases.yaml]
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import evaluate
from .agent import DEFAULT_MODEL, explain_gaps
from .analyze import ExplainRunner, analyze
from .classify import DEFAULT_RULES, RuleSet, load_rules
from .git_ops import GitError
from .report import to_markdown
from .runner import DEFAULT_TIMEOUT

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CASES = ROOT / "eval" / "cases.yaml"
DEFAULT_SEEDS = ROOT / "eval" / "seeds_predict_success.yaml"


def openai_explainer(ruleset: RuleSet) -> ExplainRunner:
    # openai는 에이전트를 쓸 때만 필요하므로 여기서 불러온다.
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(ROOT / ".env")
    client = OpenAI()  # .env의 OPENAI_API_KEY
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    return lambda view, lines: explain_gaps(client, model, view, lines, ruleset)


def write(stem: Path, data: dict, markdown: str) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")
    print(f"→ {stem.with_suffix('.json')}")
    print(f"→ {stem.with_suffix('.md')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="releaseguard")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("analyze", help="base...head 변경을 분석한다")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--python", type=Path, help="테스트를 돌릴 Python (기본: 대상 저장소의 .venv)")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="테스트 실행 시간 상한(초)")
    p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--no-agent", action="store_true", help="검증 공백 설명(에이전트) 없이 실행")

    e = sub.add_parser("eval", help="대상 저장소의 커밋 전체로 성능을 잰다")
    e.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    e.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    e.add_argument("--out", type=Path, default=Path("out/eval"))
    e.add_argument("--agent", action="store_true", help="수기 정답이 있는 커밋의 공백 설명도 실행 (API 비용 발생)")
    e.add_argument("--repeat", type=int, default=1, help="수기 정답 커밋을 몇 번 돌릴지 (결정성 확인)")

    s = sub.add_parser("seeds", help="결함을 심은 사례로 판정을 확인한다 (임시 clone에서 실행)")
    s.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    s.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    s.add_argument("--out", type=Path, default=Path("out/eval"))

    z = sub.add_parser("szz", help="고친 커밋에서 결함을 들여온 커밋·줄을 찾고, 그 줄이 당시 검증 공백이었는지 잰다")
    z.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    z.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    z.add_argument("--out", type=Path, default=Path("out/eval"))
    args = parser.parse_args(argv)

    ruleset = load_rules(args.rules)
    today = f"{date.today():%Y%m%d}"
    if args.command == "eval":
        ev = evaluate.evaluate(args.cases, ruleset, openai_explainer(ruleset) if args.agent else None, args.repeat)
        suffix = ("_agent" if args.agent else "") + (f"_x{args.repeat}" if args.repeat > 1 else "")
        write(args.out / f"{today}_eval{suffix}", ev, evaluate.to_markdown(ev))
        return 0
    if args.command == "seeds":
        ev = evaluate.run_seeds(args.seeds, ruleset)
        write(args.out / f"{today}_seeds_{args.seeds.stem}", ev, evaluate.seeds_markdown(ev))
        return 0
    if args.command == "szz":
        ev = evaluate.run_szz(args.cases, ruleset)
        write(args.out / f"{today}_szz", ev, evaluate.szz_markdown(ev))
        return 0

    explain = None if args.no_agent else openai_explainer(ruleset)
    try:
        result = analyze(args.repo, args.base, args.head, ruleset, python=args.python, timeout=args.timeout, explain=explain)
    except GitError as e:
        print(f"git 오류: {e}", file=sys.stderr)
        return 2

    print(f"{result['decision']}  (테스트: {result['test_run']['status']}, 공백 {sum(fl['gap_lines'] for fl in result['lines'])}줄)")
    if result["agent_error"]:
        print(f"에이전트 실패 (판정·결과는 저장): {result['agent_error']}", file=sys.stderr)
    write(args.out / f"{today}_{result['head_sha'][:7]}", result, to_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
