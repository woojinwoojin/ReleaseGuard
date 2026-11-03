"""실행: python -m releaseguard analyze --repo <경로> --base <ref> --head <ref>"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .analyze import analyze
from .classify import DEFAULT_RULES, load_rules
from .git_ops import GitError
from .report import to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="releaseguard")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("analyze", help="base...head 변경을 분석한다")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--base", required=True)
    p.add_argument("--head", default="HEAD")
    p.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    p.add_argument("--out", type=Path, default=Path("out"))
    args = parser.parse_args(argv)

    try:
        result = analyze(args.repo, args.base, args.head, load_rules(args.rules))
    except GitError as e:
        print(f"git 오류: {e}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"{date.today():%Y%m%d}_{result['head_sha'][:7]}"
    stem.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    stem.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
    print(f"{result['decision']}  ({len(result['findings'])}개 규칙 발동)")
    print(f"→ {stem.with_suffix('.json')}")
    print(f"→ {stem.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
