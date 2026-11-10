from backend.agent import analyze_topic_performance, recommend_difficulty


def test_tools_analyze_and_recommend():
    result = analyze_topic_performance([{"topic": "Python", "score": 55}], "python")
    assert result["average_score"] == 55
    assert recommend_difficulty(result["average_score"]) == "easy"
