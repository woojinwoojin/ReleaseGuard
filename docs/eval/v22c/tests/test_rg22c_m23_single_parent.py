"""Stage 2.2 확인 평가 #23 (week2 5b31f70 tools.py:56, parent.iloc[0] → parent.iloc[1]).

기대 결과 (1차 분류 expected_test): sub_category 행이 하나인 df에서 check_category(df, '<하위>')가
예외 없이 hint에 상위 카테고리를 담은 dict를 돌려준다.
명세 근거 (strong): 모듈 docstring '잘못된 인자는 예외 대신 {"error": ...}로 돌려줘서, LLM이 결과를 보고 인자를 고쳐 다시 호출할 수 있게 한다',
check_category docstring '없는 카테고리면 LLM이 인자를 고칠 수 있는 error dict를'.
예외를 잡아 값으로 비교한다 — mutant의 IndexError도 assertion 실패로 남게.
"""

import pandas as pd

from tools import check_category


def test_sub_category_with_single_row_hints_parent():
    df = pd.DataFrame({"category": ["A", "B"], "sub_category": ["A1", "B1"]})
    try:
        result = check_category(df, "B1")
    except Exception as e:  # noqa: BLE001
        result = {"exception": type(e).__name__}
    assert result.get("error") == "없는 카테고리: B1"
    assert result.get("hint") == "B1는 B의 하위 카테고리입니다."
