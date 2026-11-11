"""
Test Suite for MasteryLoop (mastree).
Covers:
1. Deterministic Mastery Calculation formula with recency decay (0.85^age) and difficulty weights.
2. 3-Factor Gate Rule validation (mastery >= 0.8, attempts >= 5, distinct difficulties >= 2).
3. Live IBM Db2 LUW Recursive CTE Prerequisite Query (skipped gracefully if Db2 is offline).
4. Transactional Attempt Recording and v_student_progress View Query.
"""

import os
import sys
import pytest

# Ensure submissions/mastree is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import (
    calculate_mastery_from_attempts,
    evaluate_gate,
    get_connection,
    close_connection,
    get_db2_server_info,
    get_or_create_student,
    get_all_concepts,
    record_attempt_and_update_mastery,
    get_current_mastery,
    find_root_cause_prereq,
    get_student_progress_view,
    set_cached_llm,
    get_cached_llm,
    save_question,
)


# ====================================================================
# 1. UNIT TESTS: MASTERY FORMULA
# ====================================================================

class TestMasteryFormula:
    """Tests for calculate_mastery_from_attempts."""

    def test_empty_attempts(self):
        score, count, diffs = calculate_mastery_from_attempts([])
        assert score == 0.0
        assert count == 0
        assert diffs == 0

    def test_single_correct_attempt(self):
        attempts = [{"attempt_id": 1, "is_correct": 1, "difficulty": "easy"}]
        score, count, diffs = calculate_mastery_from_attempts(attempts)
        assert score == 1.0
        assert count == 1
        assert diffs == 1

    def test_single_incorrect_attempt(self):
        attempts = [{"attempt_id": 1, "is_correct": 0, "difficulty": "hard"}]
        score, count, diffs = calculate_mastery_from_attempts(attempts)
        assert score == 0.0
        assert count == 1
        assert diffs == 1

    def test_recency_decay_calculation(self):
        """
        Two attempts (easy, diff_weight=1.0):
        Attempt 2 (newest, age=0): is_correct=1, weight = 1.0 * (0.85^0) = 1.0
        Attempt 1 (older,  age=1): is_correct=0, weight = 1.0 * (0.85^1) = 0.85
        Total weight = 1.85. Weighted correctness = 1.0.
        Score = 1.0 / 1.85 = 0.54054... -> rounded to 0.5405
        """
        attempts = [
            {"attempt_id": 1, "is_correct": 0, "difficulty": "easy"},
            {"attempt_id": 2, "is_correct": 1, "difficulty": "easy"},
        ]
        score, count, diffs = calculate_mastery_from_attempts(attempts)
        expected = round(1.0 / 1.85, 4)
        assert score == expected
        assert count == 2
        assert diffs == 1

    def test_difficulty_weighting(self):
        """
        Check that harder questions carry higher weight (easy: 1.0, medium: 1.5, hard: 2.0).
        """
        # Hard question correct vs Easy question incorrect
        attempts = [
            {"attempt_id": 1, "is_correct": 0, "difficulty": "easy"},   # age 1: w = 1.0 * 0.85 = 0.85
            {"attempt_id": 2, "is_correct": 1, "difficulty": "hard"},   # age 0: w = 2.0 * 1.0 = 2.0
        ]
        # Total w = 2.85, Correctness = 2.0 -> 2.0 / 2.85 = 0.7018
        score, count, diffs = calculate_mastery_from_attempts(attempts)
        assert score == round(2.0 / 2.85, 4)
        assert count == 2
        assert diffs == 2


# ====================================================================
# 2. UNIT TESTS: GATE RULE
# ====================================================================

class TestGateRule:
    """Tests for evaluate_gate."""

    def test_gate_pass_exact_threshold(self):
        passed, reason = evaluate_gate(mastery_score=0.80, attempt_count=5, distinct_difficulties=2)
        assert passed is True
        assert "Passed gate" in reason

    def test_gate_pass_exceeded(self):
        passed, reason = evaluate_gate(mastery_score=0.95, attempt_count=8, distinct_difficulties=3)
        assert passed is True

    def test_gate_fail_low_score(self):
        passed, reason = evaluate_gate(mastery_score=0.79, attempt_count=6, distinct_difficulties=3)
        assert passed is False
        assert "below 0.80 threshold" in reason

    def test_gate_fail_insufficient_attempts(self):
        passed, reason = evaluate_gate(mastery_score=1.0, attempt_count=4, distinct_difficulties=2)
        assert passed is False
        assert "below required minimum of 5" in reason

    def test_gate_fail_insufficient_difficulty_span(self):
        passed, reason = evaluate_gate(mastery_score=1.0, attempt_count=6, distinct_difficulties=1)
        assert passed is False
        assert "below required minimum of 2 levels" in reason

    def test_gate_fail_all_factors(self):
        passed, reason = evaluate_gate(mastery_score=0.5, attempt_count=2, distinct_difficulties=1)
        assert passed is False
        assert "below 0.80 threshold" in reason
        assert "below required minimum of 5" in reason
        assert "below required minimum of 2 levels" in reason


# ====================================================================
# 3. INTEGRATION TESTS: LIVE IBM Db2 LUW CONNECTION
# ====================================================================

def is_db2_available() -> bool:
    """Helper to check if real Db2 instance configured in .env is reachable."""
    try:
        conn = get_connection()
        close_connection(conn)
        return True
    except Exception:
        return False


DB2_REACHABLE = is_db2_available()
skip_if_no_db2 = pytest.mark.skipif(
    not DB2_REACHABLE,
    reason="IBM Db2 connection configured in .env is unreachable"
)


@skip_if_no_db2
class TestDb2Integration:
    """Live integration tests against IBM Db2 LUW."""

    @classmethod
    def setup_class(cls):
        from src.db import table_exists
        from src.init_db import execute_ddl_idempotent, migrate_columns_idempotent, seed_concepts_and_edges, seed_notes_and_chunks
        if not table_exists("concepts"):
            execute_ddl_idempotent()
        migrate_columns_idempotent()
        if len(get_all_concepts()) < 9:
            cmap = seed_concepts_and_edges()
            seed_notes_and_chunks(cmap)

    def test_db2_server_version(self):
        info = get_db2_server_info()
        assert info is not None
        assert "dbms_ver" in info
        assert "DB2" in info.get("dbms_name", "")

    def test_student_get_or_create(self):
        student = get_or_create_student("pytest_runner_student")
        assert student is not None
        assert student["student_id"] > 0
        assert student["username"] == "pytest_runner_student"

    def test_concepts_seeded(self):
        concepts = get_all_concepts()
        assert len(concepts) >= 9
        names = [c["name"] for c in concepts]
        assert "SELECT basics" in names
        assert "JOINs" in names
        assert "Window functions" in names

    def test_recursive_cte_prerequisite_query(self):
        """
        Verify Db2 LUW Recursive CTE syntax and root-cause prerequisite detection.
        JOINs (concept 7) requires SELECT basics and WHERE.
        """
        student = get_or_create_student("pytest_runner_student")
        sid = student["student_id"]
        
        # Dynamically look up JOINs concept_id
        joins_concept = [c for c in get_all_concepts() if c["name"] == "JOINs"][0]
        root_cause, sql, rows = find_root_cause_prereq(sid, current_concept_id=joins_concept["concept_id"])
        
        # Verify CTE syntax: No RECURSIVE keyword
        assert "WITH prereq_tree" in sql
        assert "RECURSIVE" not in sql.upper()
        # Ensure comma join was used in recursive member to satisfy Db2 LUW rule
        assert "concept_prereqs cp2" in sql
        
        # Rows must contain ancestor prerequisites
        assert len(rows) >= 2
        prereq_names = [r["name"] for r in rows]
        assert "WHERE" in prereq_names or "SELECT basics" in prereq_names
        
        # Root cause must be detected if mastery is below 0.8
        if root_cause is not None:
            assert root_cause["mastery_score"] < 0.8 or root_cause["attempt_count"] == 0

    def test_transactional_attempt_and_mastery_history(self):
        """
        Verify that recording an attempt updates mastery and mastery_history
        inside an atomic transaction.
        """
        student = get_or_create_student("pytest_trans_student")
        sid = student["student_id"]
        cid = [c for c in get_all_concepts() if c["name"] == "SELECT basics"][0]["concept_id"]

        # Create a dummy question if needed
        qid = save_question(
            concept_id=cid,
            source_chunk_id=None,
            question_text="Test question for transaction verification",
            option_a="A", option_b="B", option_c="C", option_d="D",
            correct_letter="A",
            explanation="Explanation",
            difficulty="easy"
        )

        res = record_attempt_and_update_mastery(
            student_id=sid,
            concept_id=cid,
            question_id=qid,
            selected_letter="A",
            is_correct=True,
            difficulty="easy"
        )

        assert res["attempt_id"] > 0
        assert res["mastery_score"] > 0.0

        current = get_current_mastery(sid, cid)
        assert current["mastery_score"] > 0.0
        assert current["attempt_count"] >= 1

    def test_student_progress_view(self):
        """Verify analytics VIEW v_student_progress."""
        student = get_or_create_student("pytest_runner_student")
        rows = get_student_progress_view(student["student_id"])
        assert len(rows) >= 9
        first = rows[0]
        assert "concept_name" in first
        assert "current_mastery" in first
        assert "is_mastered" in first

    def test_llm_cache_storage(self):
        """Verify persistent caching table llm_cache."""
        test_key = "test_pytest_cache_key_12345"
        set_cached_llm(test_key, "pytest-model", "Test Prompt", "Cached Test Response")
        cached = get_cached_llm(test_key)
        assert cached == "Cached Test Response"


# ====================================================================
# 4. UNIT TESTS: CHUNKING & WIKIPEDIA MOCKED RESPONSES
# ====================================================================

from unittest.mock import MagicMock, patch
from src.init_db import chunk_text
from src.wiki import search_wikipedia, fetch_wikipedia_extract
from src.video_lecture import _build_fallback_video_lecture


class TestChunking:
    """Tests for text chunking algorithm (~120 words)."""

    def test_chunk_text_splits_long_passages(self):
        # 300-word passage
        sample = ("Word " * 20 + ". ") * 15
        chunks = chunk_text(sample, target_words=120)
        assert len(chunks) >= 2
        for chk in chunks:
            assert len(chk.split()) <= 160

    def test_chunk_text_preserves_sentence_integrity(self):
        text = "First sentence here. Second sentence follows. Third sentence concludes."
        chunks = chunk_text(text, target_words=5)
        # Verify sentences aren't split across arbitrary word boundaries
        for chk in chunks:
            assert chk.endswith(".")


class TestWikipediaIntegration:
    """Tests for MediaWiki API search and extract parsing with mocked responses."""

    @patch("requests.get")
    def test_search_wikipedia_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "query": {
                "search": [
                    {"title": "Database transaction", "snippet": "A <span>transaction</span> symbolizes a unit of work.", "pageid": 123},
                    {"title": "Relational database", "snippet": "A database based on relations.", "pageid": 456}
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = search_wikipedia("Database transaction", limit=2)
        assert len(results) == 2
        assert results[0]["title"] == "Database transaction"
        assert "<span>" not in results[0]["snippet"]
        assert "transaction" in results[0]["snippet"]

    @patch("requests.get")
    def test_fetch_wikipedia_extract_mocked(self, mock_get):
        mock_resp = MagicMock()
        sample_words = " ".join([f"token{i}" for i in range(100)])
        mock_resp.json.return_value = {
            "query": {
                "pages": [
                    {
                        "pageid": 123,
                        "title": "ACID Properties",
                        "extract": f"ACID represents atomicity consistency isolation and durability. {sample_words}"
                    }
                ]
            }
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text, url = fetch_wikipedia_extract("ACID Properties", max_words=5000)
        assert "ACID represents atomicity" in text
        assert "https://en.wikipedia.org/wiki/ACID_Properties" in url


class TestVideoLecture:
    """Tests for Video Lecture scene synthesis and structure."""

    def test_video_lecture_fallback_structure(self):
        dummy_chunks = [
            {"chunk_id": 1, "content": "Database transactions enforce ACID guarantees across tables."},
            {"chunk_id": 2, "content": "Commit and rollback commands manage transaction state in Db2."}
        ]
        lecture = _build_fallback_video_lecture("ACID", dummy_chunks, style="clear overview")
        scenes = lecture.get("scenes", [])
        assert len(scenes) >= 5
        for sc in scenes:
            assert "title" in sc
            assert "bullets" in sc
            assert len(sc["bullets"]) <= 4
            assert "narration" in sc
            assert len(sc["narration"].split()) <= 45
            assert "key_term" in sc
            assert "citations" in sc


# ====================================================================
# 5. UNIT TESTS: SCENE-JSON VALIDATION & VISUAL SCHEMAS
# ====================================================================

from src.ai import validate_visual, validate_scene, generate_scenes_lesson


class TestSceneValidation:
    """Tests for strict visual schema enforcement and scene bounds."""

    def test_validate_visual_flow(self):
        visual = {"type": "flow", "steps": ["Input", "Process", "Output"]}
        res = validate_visual(visual)
        assert res["type"] == "flow"
        assert res["steps"] == ["Input", "Process", "Output"]

    def test_validate_visual_compare(self):
        visual = {
            "type": "compare",
            "left": {"title": "WHERE", "points": ["Row filter", "Pre-grouping"]},
            "right": {"title": "HAVING", "points": ["Group filter", "Post-aggregation"]}
        }
        res = validate_visual(visual)
        assert res["type"] == "compare"
        assert res["left"]["title"] == "WHERE"
        assert len(res["right"]["points"]) == 2

    def test_validate_visual_concept_map(self):
        visual = {
            "type": "concept_map",
            "nodes": ["Query", "Optimizer", "Catalog"],
            "edges": [{"from": "Query", "to": "Optimizer"}, {"from": "Optimizer", "to": "Catalog"}]
        }
        res = validate_visual(visual)
        assert res["type"] == "concept_map"
        assert len(res["nodes"]) == 3
        assert len(res["edges"]) == 2

    def test_validate_visual_timeline(self):
        visual = {
            "type": "timeline",
            "events": [{"label": "Phase 1", "detail": "FROM"}, {"label": "Phase 2", "detail": "WHERE"}]
        }
        res = validate_visual(visual)
        assert res["type"] == "timeline"
        assert len(res["events"]) == 2

    def test_validate_visual_equation(self):
        visual = {
            "type": "equation",
            "latex": "SELECT * FROM tab",
            "explanation": "Projection syntax"
        }
        res = validate_visual(visual)
        assert res["type"] == "equation"
        assert res["latex"] == "SELECT * FROM tab"

    def test_validate_visual_invalid_falls_back_to_bullets(self):
        # SVG or raw HTML injection must fall back to bullets
        visual = {"type": "svg_diagram", "svg": "<svg><rect/></svg>"}
        res = validate_visual(visual)
        assert res["type"] == "bullets"

        # None or invalid type falls back to bullets
        assert validate_visual(None)["type"] == "bullets"
        assert validate_visual("invalid")["type"] == "bullets"

    def test_validate_scene_enforces_bounds(self):
        # 50-word narration should be capped at 45
        long_narration = " ".join(["word"] * 50)
        raw_scene = {
            "title": "Scene 1",
            "narration": long_narration,
            "bullets": ["Bullet 1", "Bullet 2", "Bullet 3", "Bullet 4", "Bullet 5"],
            "key_term": "Relational",
            "citations": [1, 2, 999],
            "visual": {"type": "flow", "steps": ["A", "B"]}
        }
        sc = validate_scene(raw_scene, valid_chunk_ids=[1, 2])
        assert sc is not None
        assert len(sc["narration"].split()) <= 45
        assert len(sc["bullets"]) <= 4
        assert sc["citations"] == [1, 2] # 999 filtered out


# ====================================================================
# 6. INTEGRATION TESTS: FASTAPI SMOKE TESTS WITH TESTCLIENT
# ====================================================================

from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


class TestFastAPISmoke:
    """Smoke tests for FastAPI endpoints."""

    @classmethod
    def setup_class(cls):
        from src.db import table_exists
        from src.init_db import execute_ddl_idempotent, migrate_columns_idempotent, seed_concepts_and_edges, seed_notes_and_chunks
        if not table_exists("concepts"):
            execute_ddl_idempotent()
        migrate_columns_idempotent()
        if len(get_all_concepts()) < 9:
            cmap = seed_concepts_and_edges()
            seed_notes_and_chunks(cmap)

    def test_login_endpoint_success(self):
        resp = client.post("/api/login", json={"username": "smoke_test_user"})
        assert resp.status_code == 200
        data = resp.json()
        assert "student_id" in data
        assert data["username"] == "smoke_test_user"

    def test_login_endpoint_empty_username_error(self):
        resp = client.post("/api/login", json={"username": "   "})
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert "detail" in data

    def test_courses_endpoint(self):
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert "courses" in data
        assert len(data["courses"]) >= 9

    @patch("src.api.search_internet")
    def test_search_endpoint_mocked(self, mock_search):
        mock_search.return_value = [
            {"id": "abc", "title": "Python Decorators - Real Python", "snippet": "A decorator wraps a function.", "source": "realpython.com", "url": "https://realpython.com/primer"}
        ]
        resp = client.post("/api/search", json={"query": "Python decorators", "include_web": True, "include_wikipedia": False})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["source"] == "realpython.com"
        mock_search.assert_called_once_with("Python decorators", limit=5, exclude_wikipedia=True)

    @patch("requests.get")
    def test_fetch_webpage_text_strips_boilerplate(self, mock_get):
        from src.web_search import fetch_webpage_text
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://example.org/decorators"
        mock_resp.encoding = "utf-8"
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.text = """
        <html><body>
          <nav><a href="/">Home Login</a></nav>
          <script>var secret = 1;</script>
          <article>
            <h1>Python Decorators</h1>
            <p>Decorators allow wrapping functions cleanly without modifying source definitions.</p>
            <p>Higher order functions accept callables as arguments and return new functions with augmented behavior.</p>
          </article>
          <footer>Copyright footer line should not dominate.</footer>
        </body></html>
        """
        # Pad words inside <article> to meet 40-word minimum for clean article extraction
        mock_resp.text = mock_resp.text.replace(
            "</article>",
            "<p>Using functools.wraps preserves function metadata such as docstrings and original function names across multiple decorator layers in Python programs cleanly.</p></article>"
        )
        # Re-pad slightly more
        mock_resp.text = mock_resp.text.replace(
            "</article>",
            "<p>Common applications include logging, caching, timing, authentication checks, and enforcing preconditions reliably.</p></article>"
        )
        mock_get.return_value = mock_resp
        txt, final_url = fetch_webpage_text("https://example.org/decorators", max_words=500)
        assert final_url == "https://example.org/decorators"
        assert "var secret" not in txt
        assert "Decorators allow wrapping functions" in txt

    def test_fallback_quiz_has_distinct_options_across_questions(self):
        from src.ai import _build_fallback_quiz
        chunks = [
            {"chunk_id": 10, "content": "Decorators wrap a callable object and return a modified callable object cleanly."},
            {"chunk_id": 11, "content": "The at-symbol syntax applies a decorator at function definition time cleanly."}
        ]
        qs = _build_fallback_quiz(99, "Python Decorators", chunks, loop_index=1)
        assert len(qs) == 5
        distractor_sets = set()
        for q in qs:
            correct = q["correct_letter"].lower()
            wrong_opts = tuple(sorted(q[f"option_{l}"] for l in ("a", "b", "c", "d") if l != correct))
            assert len(set([q["option_a"], q["option_b"], q["option_c"], q["option_d"]])) == 4
            distractor_sets.add(wrong_opts)
        # Distractor sets must NOT be identical across all 5 questions
        assert len(distractor_sets) >= 4

    def test_progress_endpoint(self):
        # Create student first
        login_resp = client.post("/api/login", json={"username": "progress_smoke_user"})
        student_id = login_resp.json()["student_id"]

        resp = client.get(f"/api/progress/{student_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "progress" in data
        assert "history" in data
        assert "latest_event_id" in data

    @patch("src.api.batch_embed_texts", return_value=[None, None])
    @patch("src.ai.is_demo_mode", return_value=True)
    def test_custom_upload_lesson_quiz_gate_end_to_end(self, _mock_demo, _mock_embed):
        """
        Regression test for custom topic ingestion -> lesson -> quiz -> answer -> gate.
        Verifies create_custom_concept works inside ingestion transaction and static HTML serves.
        """
        import time

        # Static index served at root with clean state (no hardcoded demo strings)
        home = client.get("/")
        assert home.status_code == 200
        assert "alex_chen" not in home.text
        assert "B-Tree Fanout" not in home.text

        login = client.post("/api/login", json={"username": "e2e_custom_user"})
        assert login.status_code == 200
        sid = login.json()["student_id"]

        sample_notes = (
            "Photosynthesis converts light energy into chemical energy inside chloroplasts. "
            "Chlorophyll pigments absorb red and blue wavelengths during light-dependent reactions. "
            "ATP and NADPH generated in thylakoid membranes power the Calvin cycle in the stroma. "
            "Carbon dioxide fixation produces three-carbon sugar phosphates for plant growth."
        )
        upload = client.post(
            "/api/ingest/upload",
            data={"topic_name": "E2E Photosynthesis", "text": sample_notes, "student_id": str(sid)},
        )
        assert upload.status_code == 200
        job_id = upload.json()["job_id"]

        status = None
        for _ in range(150):
            st = client.get(f"/api/ingest/{job_id}")
            assert st.status_code == 200
            status = st.json()
            if status["status"] in ("completed", "failed"):
                break
            time.sleep(0.1)

        assert status is not None
        assert status["status"] == "completed", f"Ingest failed: {status.get('error')}"
        cid = status["concept_id"]
        assert cid > 0
        assert status["chunk_count"] >= 1
        assert isinstance(status["chunks_preview"][0], dict)
        assert "text" in status["chunks_preview"][0]

        # Stored concept appears with chunk_count > 0
        courses = client.get("/api/courses").json()["courses"]
        match = [c for c in courses if c["concept_id"] == cid]
        assert match and match[0]["chunk_count"] >= 1

        # Lesson should not contain hardcoded SQL disclaimers for non-SQL topic
        lesson = client.post(
            "/api/lesson",
            json={"student_id": sid, "concept_id": cid, "format": "board", "style": "overview", "loop_count": 1},
        )
        assert lesson.status_code == 200
        scenes = lesson.json()["scenes"]
        assert len(scenes) >= 4
        assert "SQL queries" not in scenes[1]["narration"]

        # Quiz + answer + gate
        quiz = client.post("/api/quiz/generate", json={"student_id": sid, "concept_id": cid, "loop_index": 1})
        assert quiz.status_code == 200
        qs = quiz.json()["questions"]
        assert len(qs) == 5

        ans = client.post(
            "/api/quiz/answer",
            json={
                "student_id": sid,
                "concept_id": cid,
                "answers": [{"question_id": q["question_id"], "selected_letter": "A"} for q in qs],
            },
        )
        assert ans.status_code == 200
        assert "citation_chunk_id" in ans.json()["results"][0]

        gate = client.post("/api/gate", json={"student_id": sid, "concept_id": cid, "loop_count": 1})
        assert gate.status_code == 200
        assert "event_id" in gate.json()



