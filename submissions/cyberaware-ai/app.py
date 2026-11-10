
from flask import Flask, render_template, request, jsonify
from ai import get_ai_response
from quiz import get_quiz_questions, check_quiz_answer
import os

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"answer": "Please enter a question."}), 400

    if len(question) > 2000:
        return jsonify({"answer": "Please shorten your question."}), 400

    answer = get_ai_response(question)
    return jsonify({"answer": answer})


@app.route("/api/quiz", methods=["GET"])
def quiz():
    try:
        questions = get_quiz_questions()
        return jsonify({"questions": questions})
    except Exception:
        return jsonify({"error": "Quiz database is unavailable."}), 503


@app.route("/api/quiz/check", methods=["POST"])
def quiz_check():
    data = request.get_json(silent=True) or {}

    try:
        question_id = int(data.get("question_id"))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid question ID."}), 400

    selected_option = data.get("selected_option")

    if selected_option not in ("A", "B", "C"):
        return jsonify({"error": "Invalid answer option."}), 400

    try:
        result = check_quiz_answer(question_id, selected_option)
        return jsonify(result)
    except Exception:
        return jsonify({"error": "Unable to check your answer."}), 503


@app.route("/api/health")
def health():
    return jsonify({
        "status": "running",
        "application": "CyberAware AI"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
