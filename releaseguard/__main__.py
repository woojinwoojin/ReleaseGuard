"""실행: python -m releaseguard analyze --repo <경로> --base <ref> --head <ref>"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from .agent import DEFAULT_MODEL, run_agent
from .analyze import ImpactRunner, analyze
from .classify import DEFAULT_RULES, load_rules
from .git_ops import GitError
from .report import to_markdown


def openai_runner() -> ImpactRunner:
    # openai는 에이전트를 쓸 때만 필요하므로 여기서 불러온다.
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    client = OpenAI()  # .env의 OPENAI_API_KEY
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    return lambda view, result: run_agent(client, model, view, result)


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
    args = parser.parse_args(argv)

    run_impact = None if args.no_agent else openai_runner()
    try:
        result = analyze(args.repo, args.base, args.head, load_rules(args.rules), run_impact)
    except GitError as e:
        print(f"git 오류: {e}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"{date.today():%Y%m%d}_{result['head_sha'][:7]}"
    stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
    print(f"{result['decision']}  ({len(result['findings'])}개 규칙 발동)")
    if result["agent_error"]:
        print(f"에이전트 실패 (규칙 결과만 저장): {result['agent_error']}", file=sys.stderr)
    print(f"→ {stem.with_suffix('.json')}")
    print(f"→ {stem.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
