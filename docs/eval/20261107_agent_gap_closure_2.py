"""실험 2의 추가 검증 (사전 계획에 없음). F2 실행 1이 guideline_section 직접 호출로 바뀌어서 실제로 공백을 메우는지 본다.

쓰는 법: python docs/eval/20261107_agent_gap_closure_2.py <임시 폴더> <결과 json>
"""

import importlib.util
import json
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("gap_closure", Path(__file__).with_name("20261107_agent_gap_closure.py"))
gc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gc)

CASE = {
    "id": "F2", "repo": gc.PREDICT, "sha": "adb2f5b", "path": "src/market/run_market.py", "lines": list(range(238, 255)),
    "test_file": "tests/test_market.py", "test": "test_guideline_section_formats_tables_and_notes",
    "code": '''

def test_guideline_section_formats_tables_and_notes():
    judgments = pd.DataFrame([{
        "judgment_id": "J1", "question": "Q3 연속성 확인", "applies_years": "2021~2025", "status": "연속성 확인",
        "confirmed": "...", "remaining_uncertainty": "...", "consequence": "...", "evidence": "F1;F2",
    }])
    facts = pd.DataFrame([{
        "fact_id": "F1", "question": "Q1 가격 확인", "topic": "가격", "applies_years": "2021~2025", "evidence_level": "명시적 확인",
        "doc_id": "D1", "doc_version": "1판", "location": "p.1", "interpretation": "...",
    }])
    out = []
    run_market.guideline_section(out.append, facts, judgments)
    text = "\\n".join(out)
    assert "| J1 | Q3 연속성 확인 | 2021~2025 | **연속성 확인** |" in text
    assert "| F1 | Q1 가격 확인 | 가격 | 2021~2025 | 명시적 확인 | D1 (1판; p.1) |" in text
    assert "F1, F2" in text
    assert "근거 수준:" in text and "게시판 공지는 같은 주소에서 본문이 갱신된다" in text
''',
    "human_changes": "DataFrame 생성과 출력 수집 코드 (값은 제안 그대로)",
    "mutation": ("{j.consequence} | {j.evidence.replace(';', ', ')} |", "{j.consequence} | {j.evidence} |"),
}


def main() -> None:
    root, result = Path(sys.argv[1]), Path(sys.argv[2])
    row = gc.check(CASE, root)
    result.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(row, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
