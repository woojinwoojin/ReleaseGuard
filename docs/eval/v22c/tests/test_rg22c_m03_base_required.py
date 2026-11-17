"""Stage 2.2 확인 평가 #3 (c910160 __main__.py:20, --base required=True → False).

기대 결과 (1차 분류 expected_test): main(['analyze', '--repo', '.'])가 SystemExit(code=2)를 낸다.
명세 근거 (weak): 모듈 docstring의 사용 예.
--repo는 '.' 대신 빈 tmp_path를 쓴다 (mutant가 git까지 가더라도 실제 저장소를 읽지 않게). 인자 누락 검사라는 기대 결과는 같다.
"""

from releaseguard.__main__ import main


def outcome(argv):
    try:
        return ("return", main(argv))
    except SystemExit as e:
        return ("exit", e.code)
    except Exception as e:  # noqa: BLE001
        return ("exception", type(e).__name__)


def test_missing_base_is_usage_error(tmp_path):
    assert outcome(["analyze", "--repo", str(tmp_path), "--out", str(tmp_path / "out")]) == ("exit", 2)
