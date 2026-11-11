from backend.agent import choose_difficulty


def test_assistant_adapts_to_recent_scores():
    assert choose_difficulty([{"score": 55}]) == "easy"
    assert choose_difficulty([{"score": 850}]) == "medium"
    assert choose_difficulty([{"score": 1850}]) == "hard"
