import os
import uuid
import logging
from typing import Dict, Any, Tuple
import requests
from flask import Flask, render_template, request, jsonify, session, abort  # pyrefly: ignore[missing-import] # type: ignore

from config import Config
import analyzer
import agent_service
import database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("CodeFixAI")

def create_app() -> Flask:
    """Application factory for CodeFix AI."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # In-memory session history store for Phase 1 demonstration
    # (Replaced by IBM Db2 in Phase 4)
    app.history_store: Dict[str, Dict[str, Any]] = {}

    def persist_record(record: Dict[str, Any]):
        """Persist record to memory buffer and IBM Db2 if configured."""
        record_id = record["id"]
        app.history_store[record_id] = record
        if Config.is_db2_configured():
            saved, err = database.save_history_record(record)
            if not saved:
                logger.warning(f"Could not persist record {record_id} to IBM Db2: {err}")

    # Register Context Processors
    @app.context_processor
    def inject_globals():
        return {
            "config": Config,
            "session_id": session.get("session_id", str(uuid.uuid4()))
        }

    # =========================================================================
    # Utility & Validation Helpers
    # =========================================================================
    def get_or_create_session_id() -> str:
        """Retrieve existing session ID or assign a new secure UUID."""
        if "session_id" not in session:
            session["session_id"] = str(uuid.uuid4())
        return session["session_id"]

    def validate_request_payload(data: Dict[str, Any], required_fields: list) -> Tuple[bool, str]:
        """Validate incoming JSON payload for size, types, and required fields."""
        if not data or not isinstance(data, dict):
            return False, "Request body must be a valid JSON object."

        # Check required fields
        for field in required_fields:
            if field not in data or not str(data.get(field, "")).strip():
                return False, f"Missing required parameter: '{field}'."

        # Validate language
        language = str(data.get("language", "")).lower()
        if language and language not in Config.SUPPORTED_LANGUAGES:
            return False, f"Unsupported language '{language}'. Supported: {', '.join(Config.SUPPORTED_LANGUAGES)}."

        # Validate mode
        mode = str(data.get("mode", "")).lower()
        if mode and mode not in Config.SUPPORTED_MODES:
            return False, f"Unsupported mode '{mode}'. Supported: {', '.join(Config.SUPPORTED_MODES)}."

        # Input length guardrail to prevent DOS / resource exhaustion
        total_len = len(str(data.get("prompt", ""))) + len(str(data.get("code", ""))) + len(str(data.get("error_message", "")))
        if total_len > Config.MAX_INPUT_CHARS:
            return False, f"Input payload exceeds maximum character limit of {Config.MAX_INPUT_CHARS} characters."

        return True, ""

    # =========================================================================
    # Core Application Routes
    # =========================================================================
    @app.route("/", methods=["GET"])
    def index():
        """Render the primary CodeFix AI workspace."""
        sess_id = get_or_create_session_id()
        return render_template("index.html", session_id=sess_id)

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Check live connectivity to Ollama and IBM Db2 configuration."""
        ollama_online, status_msg, available_models = agent_service.check_ollama_status()
        db2_online, db2_msg = database.check_db2_connection()

        return jsonify({
            "status": "online",
            "ollama_online": ollama_online,
            "ollama_message": status_msg,
            "ollama_host": Config.OLLAMA_BASE_URL,
            "model": Config.OLLAMA_MODEL,
            "models_available": available_models,
            "db2_configured": Config.is_db2_configured(),
            "db2_online": db2_online,
            "db2_message": db2_msg,
            "max_input_chars": Config.MAX_INPUT_CHARS
        })

    # =========================================================================
    # Operation Endpoints (Phase 1 Baseline & Validation Layer)
    # =========================================================================
    @app.route("/generate", methods=["POST"])
    def generate_code():
        """Feature A: Write Code endpoint powered by LangChain and Ollama."""
        data = request.get_json(silent=True) or {}
        is_valid, err_msg = validate_request_payload(data, required_fields=["prompt", "language"])
        if not is_valid:
            return jsonify({"success": False, "error": err_msg}), 400

        language = data["language"].lower()
        prompt = data["prompt"].strip()
        sess_id = data.get("session_id", get_or_create_session_id())

        # Execute AI task via agent service
        result = agent_service.execute_task(
            mode="write",
            language=language,
            prompt=prompt,
            session_id=sess_id
        )

        record_id = str(uuid.uuid4())
        response_payload = {
            "id": record_id,
            "mode": result["mode"],
            "language": result["language"],
            "prompt": prompt,
            "generated_code": result["generated_code"],
            "explanation": result["explanation"],
            "diagnostics": result.get("diagnostics", []),
            "suggestions": result.get("suggestions", []),
            "model_name": result.get("model_name", Config.OLLAMA_MODEL)
        }

        persist_record({
            "id": record_id,
            "session_id": sess_id,
            "language": language,
            "mode": "write",
            "user_prompt": prompt,
            "original_code": "",
            "error_message": "",
            "generated_code": response_payload["generated_code"],
            "explanation": response_payload["explanation"],
            "model_name": response_payload["model_name"],
            "created_at": "Just now"
        })

        return jsonify(response_payload)

    @app.route("/analyze", methods=["POST"])
    def analyze_code():
        """Feature B: Debug Code endpoint with deterministic Python AST static analysis + AI fix."""
        data = request.get_json(silent=True) or {}
        is_valid, err_msg = validate_request_payload(data, required_fields=["code", "language"])
        if not is_valid:
            return jsonify({"success": False, "error": err_msg}), 400

        language = data["language"].lower()
        code = data["code"]
        prompt = data.get("prompt", "").strip()
        error_msg = data.get("error_message", "").strip()
        static_only = bool(data.get("static_only", False))
        sess_id = data.get("session_id", get_or_create_session_id())

        # Step 1: Execute deterministic AST static analysis
        analysis = analyzer.analyze_code(code, language)
        diagnostics = analysis.get("diagnostics", [])

        record_id = str(uuid.uuid4())

        if static_only:
            # Deterministic static analysis report without AI call
            explanation = (
                f"### Python AST Static Analysis Report\n"
                f"- **Syntax Valid**: {'Yes' if analysis.get('is_valid_syntax') else 'No (SyntaxError detected)'}\n"
                f"- **Static Warnings Found**: {len(analysis.get('warnings', []))}\n\n"
                f"{analysis.get('summary', '')}"
            )
            response_payload = {
                "id": record_id,
                "mode": "debug",
                "language": language,
                "prompt": prompt or "Deterministic Static AST Check",
                "generated_code": code,
                "explanation": explanation,
                "diagnostics": diagnostics,
                "suggestions": [w["suggestion"] for w in analysis.get("warnings", []) if w.get("suggestion")] or [
                    "Ensure variables are defined before usage.",
                    "Verify loop termination conditions."
                ],
                "is_valid_syntax": analysis.get("is_valid_syntax", True),
                "model_name": "Deterministic Python AST"
            }
        else:
            # Step 2: Invoke AI agent with code, error details, and static diagnostics
            ai_result = agent_service.execute_task(
                mode="debug",
                language=language,
                prompt=prompt,
                code=code,
                error_message=error_msg,
                static_diagnostics=diagnostics,
                session_id=sess_id
            )
            response_payload = {
                "id": record_id,
                "mode": "debug",
                "language": language,
                "prompt": prompt,
                "generated_code": ai_result["generated_code"],
                "explanation": ai_result["explanation"],
                "diagnostics": diagnostics,
                "suggestions": ai_result.get("suggestions", []),
                "is_valid_syntax": analysis.get("is_valid_syntax", True),
                "model_name": ai_result.get("model_name", Config.OLLAMA_MODEL)
            }

        persist_record({
            "id": record_id,
            "session_id": sess_id,
            "language": language,
            "mode": "debug",
            "user_prompt": prompt,
            "original_code": code,
            "error_message": error_msg,
            "generated_code": response_payload["generated_code"],
            "explanation": response_payload["explanation"],
            "model_name": response_payload["model_name"],
            "created_at": "Just now"
        })

        return jsonify(response_payload)

    @app.route("/improve", methods=["POST"])
    def improve_code():
        """Feature C: Improve Code endpoint powered by LangChain and Ollama."""
        data = request.get_json(silent=True) or {}
        is_valid, err_msg = validate_request_payload(data, required_fields=["code", "language"])
        if not is_valid:
            return jsonify({"success": False, "error": err_msg}), 400

        language = data["language"].lower()
        code = data["code"]
        prompt = data.get("prompt", "Improve readability, maintainability, and structure.").strip()
        sess_id = data.get("session_id", get_or_create_session_id())

        ai_result = agent_service.execute_task(
            mode="improve",
            language=language,
            prompt=prompt,
            code=code,
            session_id=sess_id
        )

        record_id = str(uuid.uuid4())
        response_payload = {
            "id": record_id,
            "mode": "improve",
            "language": language,
            "prompt": prompt,
            "generated_code": ai_result["generated_code"],
            "explanation": ai_result["explanation"],
            "diagnostics": ai_result.get("diagnostics", []),
            "suggestions": ai_result.get("suggestions", []),
            "model_name": ai_result.get("model_name", Config.OLLAMA_MODEL)
        }

        persist_record({
            "id": record_id,
            "session_id": sess_id,
            "language": language,
            "mode": "improve",
            "user_prompt": prompt,
            "original_code": code,
            "error_message": "",
            "generated_code": response_payload["generated_code"],
            "explanation": response_payload["explanation"],
            "model_name": response_payload["model_name"],
            "created_at": "Just now"
        })

        return jsonify(response_payload)

    @app.route("/explain", methods=["POST"])
    def explain_code():
        """Feature D: Explain Code endpoint powered by LangChain and Ollama."""
        data = request.get_json(silent=True) or {}
        is_valid, err_msg = validate_request_payload(data, required_fields=["code", "language"])
        if not is_valid:
            return jsonify({"success": False, "error": err_msg}), 400

        language = data["language"].lower()
        code = data["code"]
        prompt = data.get("prompt", "Provide a detailed walkthrough of this code.").strip()
        sess_id = data.get("session_id", get_or_create_session_id())

        ai_result = agent_service.execute_task(
            mode="explain",
            language=language,
            prompt=prompt,
            code=code,
            session_id=sess_id
        )

        record_id = str(uuid.uuid4())
        response_payload = {
            "id": record_id,
            "mode": "explain",
            "language": language,
            "prompt": prompt,
            "generated_code": ai_result["generated_code"],
            "explanation": ai_result["explanation"],
            "diagnostics": ai_result.get("diagnostics", []),
            "suggestions": ai_result.get("suggestions", []),
            "model_name": ai_result.get("model_name", Config.OLLAMA_MODEL)
        }

        persist_record({
            "id": record_id,
            "session_id": sess_id,
            "language": language,
            "mode": "explain",
            "user_prompt": prompt,
            "original_code": code,
            "error_message": "",
            "generated_code": response_payload["generated_code"],
            "explanation": response_payload["explanation"],
            "model_name": response_payload["model_name"],
            "created_at": "Just now"
        })

        return jsonify(response_payload)

    @app.route("/chat", methods=["POST"])
    def chat_followup():
        """Feature E: Conversational follow-up endpoint preserving session context."""
        data = request.get_json(silent=True) or {}
        message = data.get("message", "").strip()
        if not message:
            return jsonify({"success": False, "error": "Follow-up message cannot be empty."}), 400

        current_code = data.get("current_code", "")
        language = data.get("language", "python")
        history = data.get("history", [])
        sess_id = data.get("session_id", get_or_create_session_id())

        result = agent_service.process_followup(
            message=message,
            current_code=current_code,
            language=language,
            history=history,
            session_id=sess_id
        )

        return jsonify(result)

    # =========================================================================
    # History Routes (Feature F)
    # =========================================================================
    @app.route("/history", methods=["GET"])
    def history():
        """List session and database saved records."""
        if Config.is_db2_configured():
            records = database.get_history_records(limit=Config.MAX_HISTORY_PER_SESSION)
        else:
            records = list(app.history_store.values())
        return render_template("history.html", records=records)

    @app.route("/history/<record_id>", methods=["GET"])
    def view_history_record(record_id: str):
        """View a single saved history record."""
        record = None
        if Config.is_db2_configured():
            record = database.get_record_by_id(record_id)
        if not record:
            record = app.history_store.get(record_id)

        if not record:
            return render_template("error.html",
                                   status_code=404,
                                   error_title="Record Not Found",
                                   error_message=f"No saved record found with ID '{record_id}'.",
                                   suggestions=["Return to the History page to browse valid records."]), 404

        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(record)
        return render_template("result.html", record=record)

    @app.route("/history/<record_id>/delete", methods=["POST"])
    def delete_history_record(record_id: str):
        """Delete a single saved history record."""
        deleted_db = False
        if Config.is_db2_configured():
            deleted_db = database.delete_record_by_id(record_id)

        deleted_mem = False
        if record_id in app.history_store:
            del app.history_store[record_id]
            deleted_mem = True

        if deleted_db or deleted_mem:
            return jsonify({"success": True, "message": "Record deleted successfully."})
        return jsonify({"success": False, "error": "Record not found."}), 404

    # =========================================================================
    # Error Handlers
    # =========================================================================
    @app.errorhandler(400)
    def bad_request_error(e):
        if request.is_json:
            return jsonify({"success": False, "error": "Bad request", "details": str(e)}), 400
        return render_template("error.html",
                               status_code=400,
                               error_title="Invalid Request",
                               error_message="The server could not understand the request due to invalid syntax or parameters.",
                               suggestions=["Check the form fields and ensure input does not exceed character limits."]), 400

    @app.errorhandler(404)
    def not_found_error(e):
        if request.is_json:
            return jsonify({"success": False, "error": "Resource not found"}), 404
        return render_template("error.html",
                               status_code=404,
                               error_title="Page Not Found",
                               error_message="The requested URL was not found on this server.",
                               suggestions=["Double check the URL or use the navigation bar to return to the Workspace."]), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        if request.is_json:
            return jsonify({"success": False, "error": "Internal server error"}), 500
        return render_template("error.html",
                               status_code=500,
                               error_title="Internal Application Error",
                               error_message="An unexpected condition was encountered on the server.",
                               suggestions=[
                                   "Verify that the Flask application and environment variables are properly configured.",
                                   "Check server console logs for detailed diagnostic information."
                               ]), 500

    return app


# Application Entry Point
app = create_app()

if __name__ == "__main__":
    port = Config.PORT
    debug = Config.DEBUG
    logger.info(f"Starting CodeFix AI on port {port} (Debug: {debug})...")
    app.run(
    host="0.0.0.0",
    port=port,
    debug=debug,
    use_reloader=False
)
