"""실행:
python -m releaseguard analyze --repo <경로> --base <ref> --head <ref> [--no-agent]
python -m releaseguard eval [--cases eval/cases.yaml] [--agent]
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import evaluate
from .agent import DEFAULT_MODEL, run_agent
from .analyze import ImpactRunner, analyze
from .classify import DEFAULT_RULES, load_rules
from .git_ops import GitError
from .report import to_markdown

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "eval" / "cases.yaml"


def openai_runner() -> ImpactRunner:
    # openai는 에이전트를 쓸 때만 필요하므로 여기서 불러온다.
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    client = OpenAI()  # .env의 OPENAI_API_KEY
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    return lambda view, result: run_agent(client, model, view, result)


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
    p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    p.add_argument("--out", type=Path, default=Path("out"))
    p.add_argument("--no-agent", action="store_true", help="4단계 에이전트 없이 규칙만 실행")
    e = sub.add_parser("eval", help="대상 저장소의 커밋 전체로 성능을 잰다")
    e.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    e.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    e.add_argument("--out", type=Path, default=Path("out/eval"))
    e.add_argument("--agent", action="store_true", help="수기 정답이 있는 커밋에 에이전트도 실행 (API 비용 발생)")
    args = parser.parse_args(argv)

    if args.command == "eval":
        ev = evaluate.evaluate(args.cases, load_rules(args.rules), openai_runner() if args.agent else None)
        suffix = "_agent" if args.agent else ""
        write(args.out / f"{date.today():%Y%m%d}_eval{suffix}", ev, evaluate.to_markdown(ev))
        return 0

    run_impact = None if args.no_agent else openai_runner()
    try:
        result = analyze(args.repo, args.base, args.head, load_rules(args.rules), run_impact)
    except GitError as e:
        print(f"git 오류: {e}", file=sys.stderr)
        return 2

    print(f"{result['decision']}  ({len(result['findings'])}개 규칙 발동)")
    if result["agent_error"]:
        print(f"에이전트 실패 (규칙 결과만 저장): {result['agent_error']}", file=sys.stderr)
    write(args.out / f"{date.today():%Y%m%d}_{result['head_sha'][:7]}", result, to_markdown(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
