
from flask import Flask, render_template, request, jsonify
from ai import get_ai_response
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
        return jsonify({
            "answer": "Please enter a question."
        }), 400

    if len(question) > 2000:
        return jsonify({
            "answer": "Your question is too long. Please shorten it."
        }), 400

    answer = get_ai_response(question)

    return jsonify({
        "answer": answer
    })


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
