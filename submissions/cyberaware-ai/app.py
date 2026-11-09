from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"answer": "Please enter a question."}), 400

    answer = """
    Cybersecurity Tip:

    Never share your passwords, PINs or mobile money codes.
    Avoid clicking suspicious links.
    Verify messages before sending money.
    Use strong passwords and enable two-factor authentication.
    """

    return jsonify({"answer": answer})


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
        debug=True
    )
