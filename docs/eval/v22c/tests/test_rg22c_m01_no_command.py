"""Stage 2.2 확인 평가 #1 (c910160 __main__.py:17, add_subparsers required=True → False).

기대 결과 (1차 분류 expected_test): main([])이 SystemExit(code=2)를 낸다 (AttributeError가 아님).
명세 근거 (weak): 모듈 docstring '실행: python -m releaseguard analyze --repo <경로> --base <ref> --head <ref>'.
예외를 잡아 값으로 비교한다 — mutant가 다른 예외로 죽어도 assertion 실패로 남게.
"""

from releaseguard.__main__ import main


def outcome(argv):
    try:
        return ("return", main(argv))
    except SystemExit as e:
        return ("exit", e.code)
    except Exception as e:  # noqa: BLE001
        return ("exception", type(e).__name__)


def test_no_command_is_usage_error():
    assert outcome([]) == ("exit", 2)
