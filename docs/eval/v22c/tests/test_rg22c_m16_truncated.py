"""Stage 2.2 확인 평가 #16 (6fb437c agent_tools.py:54, len(text) > MAX_DIFF_CHARS → >=).

기대 결과 (1차 분류 expected_test): 길이가 정확히 MAX_DIFF_CHARS인 diff에서 truncated is False.
명세 근거 (weak): 'truncated' 필드 이름과 같은 파일의 search_code·list_files가 같은 의미(len > 상한)로 쓰는 내부 일관성.
git 출력 길이를 정확히 맞추기 어려워 run_git을 바꿔 끼운다.
"""

from releaseguard import agent_tools


def test_diff_exactly_at_cap_is_not_truncated(monkeypatch, tmp_path):
    text = "x" * agent_tools.MAX_DIFF_CHARS
    monkeypatch.setattr(agent_tools, "run_git", lambda repo, *args: text)
    out = agent_tools.RepoView(tmp_path, "base", "head").git_diff()
    assert out["diff"] == text
    assert out["truncated"] is False


def test_diff_one_over_cap_is_truncated(monkeypatch, tmp_path):
    text = "x" * (agent_tools.MAX_DIFF_CHARS + 1)
    monkeypatch.setattr(agent_tools, "run_git", lambda repo, *args: text)
    out = agent_tools.RepoView(tmp_path, "base", "head").git_diff()
    assert len(out["diff"]) == agent_tools.MAX_DIFF_CHARS
    assert out["truncated"] is True
