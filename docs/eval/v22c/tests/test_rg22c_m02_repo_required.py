"""Stage 2.2 확인 평가 #2 (c910160 __main__.py:19, --repo required=True → False).

기대 결과 (1차 분류 expected_test): main(['analyze', '--base', 'x'])가 SystemExit(code=2)를 낸다.
명세 근거 (weak): 모듈 docstring의 사용 예 (--repo <경로>는 기본값 없는 인자).
--out은 tmp_path로 둬서 mutant가 분석까지 가더라도 저장소에 쓰지 않게 한다.
"""

from releaseguard.__main__ import main


def outcome(argv):
    try:
        return ("return", main(argv))
    except SystemExit as e:
        return ("exit", e.code)
    except Exception as e:  # noqa: BLE001
        return ("exception", type(e).__name__)


def test_missing_repo_is_usage_error(tmp_path):
    assert outcome(["analyze", "--base", "x", "--out", str(tmp_path / "out")]) == ("exit", 2)
