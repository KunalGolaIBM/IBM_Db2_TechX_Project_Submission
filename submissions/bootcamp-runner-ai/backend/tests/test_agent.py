from backend.agent import choose_difficulty


def test_assistant_adapts_to_recent_scores():
    assert choose_difficulty([{"score": 55}]) == "easy"
    assert choose_difficulty([{"score": 85}]) == "hard"
