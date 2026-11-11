"""
FastAPI Backend for MasteryLoop (mastree).
Provides REST endpoints for:
- Student authentication and course curriculum
- Wikipedia & Google Search grounding topic discovery
- Asynchronous background knowledge ingestion into IBM Db2 LUW
- Grounded multi-format lesson synthesis (Board & Video Lecture scenes)
- 5-MCQ generation, deterministic grading, and Bloom mastery updates
- 3-factor gate evaluation and recursive CTE prerequisite root cause analysis
- Analytics progress view and 'Why this?' SQL inspection
"""

import os
import sys
import io
import json
import uuid
import logging
import threading
import traceback
from typing import Any, Dict, List, Optional

# Add project root and src directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Internal module imports (supports running both from root and from src/)
try:
    from src.db import (
        get_or_create_student,
        get_student_by_id,
        get_all_concepts,
        get_concept_by_id,
        get_concept_prereqs,
        get_all_concept_prereqs_map,
        find_root_cause_prereq,
        create_custom_concept,
        insert_document,
        insert_chunk,
        get_chunks_for_concept,
        save_lesson,
        get_latest_lesson,
        save_question,
        get_unanswered_questions,
        get_all_questions_for_concept,
        get_question_by_id,
        record_attempt_and_update_mastery,
        get_current_mastery,
        evaluate_gate,
        log_loop_event,
        get_loop_event_by_id,
        get_student_progress_view,
        get_mastery_history_series,
        save_lesson_image,
        get_lesson_image,
        transaction,
        execute_query,
        execute_non_query
    )
    from src.wiki import search_wikipedia, fetch_wikipedia_extract
    from src.web_search import search_internet, fetch_webpage_text
    from src.ai import (
        batch_embed_texts,
        retrieve_top_chunks,
        chunk_text,
        synthesize_ai_knowledge,
        generate_scenes_lesson,
        generate_and_verify_quiz,
        search_with_gemini_grounding,
        generate_illustration,
        validate_visual,
        AIError
    )
except ImportError:
    from db import (
        get_or_create_student,
        get_student_by_id,
        get_all_concepts,
        get_concept_by_id,
        get_concept_prereqs,
        get_all_concept_prereqs_map,
        find_root_cause_prereq,
        create_custom_concept,
        insert_document,
        insert_chunk,
        get_chunks_for_concept,
        save_lesson,
        get_latest_lesson,
        save_question,
        get_unanswered_questions,
        get_all_questions_for_concept,
        get_question_by_id,
        record_attempt_and_update_mastery,
        get_current_mastery,
        evaluate_gate,
        log_loop_event,
        get_loop_event_by_id,
        get_student_progress_view,
        get_mastery_history_series,
        save_lesson_image,
        get_lesson_image,
        transaction,
        execute_query,
        execute_non_query
    )
    from wiki import search_wikipedia, fetch_wikipedia_extract
    from web_search import search_internet, fetch_webpage_text
    from ai import (
        batch_embed_texts,
        retrieve_top_chunks,
        chunk_text,
        synthesize_ai_knowledge,
        generate_scenes_lesson,
        generate_and_verify_quiz,
        search_with_gemini_grounding,
        generate_illustration,
        validate_visual,
        AIError
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mastree.api")

app = FastAPI(
    title="MasteryLoop API",
    description="Adaptive learning engine with IBM Db2 LUW recursive graph analytics and Bloom mastery loop.",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory background ingestion registry
# Format: job_id -> {job_id, status, step, progress, message, concept_id, chunk_count, source_label, chunks_preview, error}
INGESTION_JOBS: Dict[str, Dict[str, Any]] = {}


# ====================================================================
# ERROR HANDLING
# ====================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Return errors in strict {error, detail} format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "HTTPException", "detail": exc.detail}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Log full tracebacks to terminal while returning clean JSON error responses."""
    logger.error("Unhandled API Exception:")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)}
    )


# ====================================================================
# PYDANTIC REQUEST / RESPONSE MODELS
# ====================================================================

class LoginRequest(BaseModel):
    username: str

class SearchRequest(BaseModel):
    query: str
    include_web: bool = True
    include_wikipedia: bool = False

class IngestRequest(BaseModel):
    source_type: str = "web" # web | url | ai_kb | wikipedia | course | paste
    topic_name: str
    student_id: Optional[int] = None
    url: Optional[str] = None
    text: Optional[str] = None
    focus: Optional[str] = None
    replace_existing: bool = True
    prereq_ids: Optional[List[int]] = None

class LessonRequest(BaseModel):
    student_id: int
    concept_id: int
    format: str = "board" # board | video
    style: Optional[str] = None # overview | worked example | analogy | step-by-step
    loop_count: int = 1

class QuizGenerateRequest(BaseModel):
    concept_id: int
    student_id: int
    loop_index: int = 1

class AnswerItem(BaseModel):
    question_id: int
    selected_letter: str

class QuizAnswerRequest(BaseModel):
    student_id: int
    concept_id: int
    answers: List[AnswerItem]

class GateRequest(BaseModel):
    student_id: int
    concept_id: int
    loop_count: int = 1


# ====================================================================
# BACKGROUND INGESTION WORKER
# ====================================================================

def _run_ingest_job(
    job_id: str,
    source_type: str,
    topic_name: str,
    student_id: Optional[int],
    url: Optional[str],
    text_content: Optional[str],
    prereq_ids: Optional[List[int]],
    focus: Optional[str] = None,
    replace_existing: bool = True
):
    """
    Background worker for knowledge ingestion into IBM Db2 LUW.
    Steps: fetch (web URL / internet / AI KB / upload) -> chunk (~120 words) ->
    embed in ONE batched call -> Db2 transaction.
    Caps content at 3000 words / 25 chunks.
    """
    job = INGESTION_JOBS.get(job_id)
    if not job:
        return

    try:
        job["status"] = "running"
        job["step"] = "Fetching content"
        job["progress"] = 20
        job["message"] = f"Fetching source material for '{topic_name}'..."

        raw_text = ""
        source_url = url or ""
        source_label = f"{source_type.title()}: {topic_name}"

        if source_type in ("web", "url"):
            if text_content and len(text_content.split()) >= 80:
                raw_text = text_content.strip()
                source_label = f"Web: {topic_name}"
            elif source_url and source_url.startswith(("http://", "https://")):
                if "wikipedia.org" in source_url.lower():
                    raw_text, source_url = fetch_wikipedia_extract(topic_name, max_words=3000)
                    source_label = f"Wikipedia: {topic_name}"
                else:
                    raw_text, source_url = fetch_webpage_text(source_url, max_words=3000)
                    from urllib.parse import urlparse
                    dom = urlparse(source_url).netloc.replace("www.", "")
                    source_label = f"Web ({dom}): {topic_name}"
            else:
                web_hits = search_internet(topic_name, limit=5, exclude_wikipedia=True)
                for hit in web_hits:
                    try:
                        raw_text, source_url = fetch_webpage_text(hit["url"], max_words=3000)
                        source_label = f"Web ({hit['source']}): {topic_name}"
                        break
                    except Exception:
                        continue
                if not raw_text:
                    raise ValueError(
                        f"Could not extract a full web article for '{topic_name}'. "
                        "Try 'Generate from AI Knowledge Base' or paste a specific URL."
                    )
        elif source_type == "ai_kb":
            job["message"] = f"Synthesizing study guide for '{topic_name}' via Gemini Knowledge Base..."
            raw_text = synthesize_ai_knowledge(topic_name, focus=focus or "")
            source_url = f"gemini://knowledge-base/{topic_name.strip().replace(' ', '_')[:80]}"
            source_label = f"Gemini KB: {topic_name}"
        elif source_type == "wikipedia":
            raw_text, source_url = fetch_wikipedia_extract(topic_name, max_words=3000)
            source_label = f"Wikipedia: {topic_name}"
        elif source_type == "course":
            # Seed course lookup
            notes_path = os.path.join(os.path.dirname(__file__), "data", "sql_notes.md")
            if os.path.exists(notes_path):
                with open(notes_path, "r", encoding="utf-8") as f:
                    full_notes = f.read()
                import re
                sections = re.split(r'\n##\s+', full_notes)
                for sec in sections:
                    lines = sec.strip().split("\n", 1)
                    if lines and lines[0].strip().lower() == topic_name.strip().lower() and len(lines) > 1:
                        raw_text = lines[1].strip()
                        break
            if not raw_text:
                raw_text = f"Curriculum reference material for {topic_name}."
            source_url = "curriculum://sql"
            source_label = f"Course (SQL): {topic_name}"
        elif source_type in ("upload", "paste"):
            raw_text = (text_content or "").strip()
            source_url = url or f"{source_type}://local"
            source_label = f"{source_type.title()}: {topic_name}"

        words = raw_text.split()
        if len(words) > 3000:
            raw_text = " ".join(words[:3000])

        if not raw_text:
            raise ValueError(f"No textual content could be obtained for '{topic_name}'.")

        # Step 2: Chunking
        job["step"] = "Chunking text"
        job["progress"] = 45
        job["message"] = "Partitioning text into ~120-word educational chunks..."

        chunks_text = chunk_text(raw_text, target_words=120)
        chunks_text = chunks_text[:25] # Cap at 25 chunks max

        if not chunks_text:
            raise ValueError("Text passage resulted in zero valid chunks.")

        job["chunks_preview"] = [
            {
                "chunk_index": idx + 1,
                "text": c[:130] + ("..." if len(c) > 130 else ""),
                "word_count": len(c.split()),
            }
            for idx, c in enumerate(chunks_text[:5])
        ]

        # Step 3: Batch Embedding in ONE call
        job["step"] = "Embedding chunks"
        job["progress"] = 70
        job["message"] = f"Embedding {len(chunks_text)} chunks in a single batched call..."

        embeddings = batch_embed_texts(chunks_text)

        # Step 4: Atomic Db2 Transaction
        job["step"] = "Persisting to Db2"
        job["progress"] = 85
        job["message"] = "Writing concept, document, and chunks to IBM Db2 LUW..."

        valid_creator = student_id if (student_id and get_student_by_id(student_id)) else None
        clean_topic = topic_name.strip()[:100]
        concept_id = None
        with transaction() as conn:
            # Check if concept already exists
            existing_c = execute_query(
                "SELECT concept_id FROM concepts WHERE name = ? FETCH FIRST 1 ROWS ONLY",
                (clean_topic,),
                conn=conn
            )
            if existing_c:
                concept_id = existing_c[0]["concept_id"]
                if replace_existing and source_type in ("web", "url", "ai_kb", "wikipedia"):
                    # Clear previous chunks/questions/docs so fresh source cleanly replaces stale material
                    execute_non_query("DELETE FROM questions WHERE concept_id = ?", (concept_id,), conn=conn)
                    execute_non_query("DELETE FROM chunks WHERE concept_id = ?", (concept_id,), conn=conn)
                    execute_non_query("DELETE FROM documents WHERE concept_id = ?", (concept_id,), conn=conn)
                    execute_non_query(
                        "UPDATE concepts SET description = ? WHERE concept_id = ?",
                        (f"{source_label} knowledge module"[:500], concept_id),
                        conn=conn
                    )
            else:
                is_custom = 0 if source_type == "course" else 1
                seq_query = execute_query("SELECT COALESCE(MAX(seq_order), 0) + 1 AS next_seq FROM concepts", conn=conn)
                next_seq = int(seq_query[0]["next_seq"]) if seq_query else 10

                concept_id = create_custom_concept(
                    name=clean_topic,
                    description=f"{source_label} knowledge module",
                    seq_order=next_seq,
                    created_by=valid_creator,
                    is_custom=is_custom,
                    prereq_ids=prereq_ids or [],
                    conn=conn
                )

            # Insert document
            doc_id = insert_document(
                concept_id=concept_id,
                title=topic_name,
                source=source_label[:50],
                content=raw_text,
                source_type=source_type[:20],
                source_url=source_url[:500],
                conn=conn
            )

            # Insert chunks
            for idx, c_text in enumerate(chunks_text):
                emb = embeddings[idx] if idx < len(embeddings) else None
                emb_json = json.dumps(emb) if emb else None
                insert_chunk(
                    doc_id=doc_id,
                    concept_id=concept_id,
                    chunk_index=idx,
                    content=c_text,
                    embedding_json=emb_json,
                    conn=conn
                )

        # Step 5: Completed
        job["status"] = "completed"
        job["step"] = "Completed"
        job["progress"] = 100
        job["concept_id"] = concept_id
        job["chunk_count"] = len(chunks_text)
        job["source_label"] = source_label
        job["message"] = f"Stored {len(chunks_text)} chunks in Db2"
        logger.info(f"Ingestion job {job_id} completed successfully for '{topic_name}' ({len(chunks_text)} chunks).")

    except Exception as e:
        logger.error(f"Ingestion job {job_id} failed: {e}")
        job["status"] = "failed"
        job["step"] = "Failed"
        job["error"] = str(e)
        job["message"] = f"Ingestion error: {e}"


# ====================================================================
# API ENDPOINTS
# ====================================================================

@app.post("/api/login")
def login_student(payload: LoginRequest):
    """
    Authenticate or provision student by username.
    Passwordless flow: creates student record if new.
    """
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty.")
    student = get_or_create_student(username)
    return {
        "student_id": student["student_id"],
        "username": student["username"],
        "created_at": str(student.get("created_at", ""))
    }


@app.get("/api/courses")
def get_courses():
    """
    Return all available concepts and their prerequisite graph relationships.
    """
    concepts = get_all_concepts()
    prereqs_map = get_all_concept_prereqs_map()
    courses = []
    for c in concepts:
        cid = int(c["concept_id"])
        courses.append({
            "concept_id": cid,
            "name": c["name"],
            "description": c.get("description", ""),
            "seq_order": c.get("seq_order", 0),
            "is_custom": c.get("is_custom", 0),
            "created_by": c.get("created_by"),
            "chunk_count": c.get("chunk_count", 0),
            "prereqs": prereqs_map.get(cid, [])
        })
    return {"courses": courses}


@app.post("/api/search")
def search_topics(payload: SearchRequest):
    """
    Search diverse internet sources (tutorials, docs, articles) via DuckDuckGo / OpenAlex.
    Excludes Wikipedia unless include_wikipedia=True.
    """
    query = payload.query.strip()
    if not query:
        return {"results": [], "web_search_unavailable": False, "note": None}

    results = []
    web_unavailable = False
    note = None

    try:
        results = search_internet(query, limit=5, exclude_wikipedia=not payload.include_wikipedia)
    except Exception as e:
        logger.warning(f"Internet search error: {e}")
        web_unavailable = True
        note = "web_search_unavailable"

    if payload.include_wikipedia and len(results) < 5:
        try:
            wiki_results = search_wikipedia(query, limit=2)
            results.extend(wiki_results)
        except Exception as e:
            logger.warning(f"Optional Wikipedia search error: {e}")

    return {
        "results": results,
        "web_search_unavailable": web_unavailable,
        "note": note
    }


@app.post("/api/ingest")
def start_ingest(payload: IngestRequest):
    """
    Queue background ingestion from web search, direct URL, AI knowledge base, course, or pasted text.
    Returns {job_id} immediately for non-blocking UI polling.
    """
    topic = payload.topic_name.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic name is required.")

    job_id = uuid.uuid4().hex[:12]
    INGESTION_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "step": "Initializing",
        "progress": 5,
        "message": f"Queued ingestion for '{topic}'...",
        "concept_id": None,
        "chunk_count": 0,
        "source_label": f"{payload.source_type.title()}: {topic}",
        "chunks_preview": [],
        "error": None
    }

    thread = threading.Thread(
        target=_run_ingest_job,
        args=(
            job_id,
            payload.source_type,
            topic,
            payload.student_id,
            payload.url,
            payload.text,
            payload.prereq_ids,
            payload.focus,
            payload.replace_existing,
        ),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id}


@app.post("/api/ingest/upload")
async def start_upload_ingest(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    topic_name: str = Form(...),
    student_id: Optional[int] = Form(None),
    prereq_ids: Optional[str] = Form(None)
):
    """
    Queue background ingestion for uploaded notes (.txt, .md, .pdf) or pasted text.
    Returns {job_id} immediately.
    """
    topic = topic_name.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic name is required.")

    extracted_text = ""
    source_type = "paste"
    source_url = "upload://local"

    if file and file.filename:
        filename = file.filename.lower()
        source_type = "upload"
        source_url = f"file://{file.filename}"
        content_bytes = await file.read()

        if filename.endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(content_bytes))
                pages_text = []
                for p in reader.pages:
                    ptxt = p.extract_text()
                    if ptxt:
                        pages_text.append(ptxt)
                extracted_text = "\n\n".join(pages_text)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to parse PDF file: {e}")
        else: # .txt or .md
            extracted_text = content_bytes.decode("utf-8", errors="replace")
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="No readable text could be extracted from the uploaded file.")
    elif text and text.strip():
        extracted_text = text.strip()
        source_type = "paste"
        source_url = "paste://user"
    else:
        raise HTTPException(status_code=400, detail="Please upload a file or paste text content.")

    # Parse prerequisite IDs if provided
    parsed_prereqs = []
    if prereq_ids:
        try:
            if prereq_ids.strip().startswith("["):
                parsed_prereqs = [int(x) for x in json.loads(prereq_ids)]
            else:
                parsed_prereqs = [int(x.strip()) for x in prereq_ids.split(",") if x.strip()]
        except Exception:
            parsed_prereqs = []

    job_id = uuid.uuid4().hex[:12]
    INGESTION_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "step": "Initializing",
        "progress": 5,
        "message": f"Queued file ingestion for '{topic}'...",
        "concept_id": None,
        "chunk_count": 0,
        "source_label": f"{source_type.title()}: {topic}",
        "chunks_preview": [],
        "error": None
    }

    thread = threading.Thread(
        target=_run_ingest_job,
        args=(
            job_id,
            source_type,
            topic,
            student_id,
            source_url,
            extracted_text,
            parsed_prereqs
        ),
        daemon=True
    )
    thread.start()

    return {"job_id": job_id}


@app.get("/api/ingest/{job_id}")
def get_ingest_status(job_id: str):
    """
    Poll status of background ingestion job.
    Returns {status, step, progress, message, concept_id, chunk_count, source_label, chunks_preview}.
    """
    job = INGESTION_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job '{job_id}' not found.")
    return job


@app.post("/api/lesson")
def get_or_generate_lesson(payload: LessonRequest):
    """
    Generate or retrieve 5-6 scenes instructional lesson for a concept.
    ONE Gemini call (cached in Db2 llm_cache) built ONLY from retrieved chunks.
    Visual schemas: flow, cycle, hierarchy, compare, timeline, concept_map, equation, bullets.
    """
    if not get_student_by_id(payload.student_id):
        raise HTTPException(status_code=404, detail="Student session expired or invalid. Please log in again.")

    concept = get_concept_by_id(payload.concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found.")

    chunks = get_chunks_for_concept(payload.concept_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found in Db2 for this concept.")

    # Retrieve top chunks strictly scoped to concept_id, avoiding repeating prior lesson chunks on reteach
    query_hint = f"Explain core concepts, mechanisms, and worked examples for {concept['name']}"
    candidate_chunks = chunks
    if payload.loop_count > 1 and len(chunks) > 5:
        latest = get_latest_lesson(payload.student_id, payload.concept_id)
        prior_cids = set()
        if latest and latest.get("steps_json"):
            try:
                for sc in json.loads(latest["steps_json"]):
                    prior_cids.update(int(cid) for cid in (sc.get("citations") or []))
            except Exception:
                pass
        unseen = [c for c in chunks if int(c["chunk_id"]) not in prior_cids]
        if len(unseen) >= 3:
            candidate_chunks = unseen
        else:
            offset = ((payload.loop_count - 1) * 3) % len(chunks)
            candidate_chunks = chunks[offset:] + chunks[:offset]

    top_chunks = retrieve_top_chunks(candidate_chunks, query_hint, top_k=5)

    # Generate 5-6 scenes with validated visual schemas
    lesson_data = generate_scenes_lesson(
        concept_name=concept["name"],
        chunks=top_chunks,
        style=payload.style,
        loop_count=payload.loop_count
    )

    # Persist lesson in Db2
    lesson_id = save_lesson(
        student_id=payload.student_id,
        concept_id=payload.concept_id,
        loop_count=payload.loop_count,
        style=lesson_data["style"],
        steps_json=json.dumps(lesson_data["scenes"])
    )

    # Optional image illustration if GEMINI_IMAGE_MODEL is configured
    illustration_url = None
    try:
        key_term = lesson_data["scenes"][0].get("key_term", "") if lesson_data["scenes"] else ""
        img_bytes = generate_illustration(concept["name"], key_term)
        if img_bytes:
            save_lesson_image(lesson_id, payload.concept_id, img_bytes)
            illustration_url = f"/api/illustration/{lesson_id}"
    except Exception as e:
        logger.debug(f"Optional illustration skipped: {e}")

    return {
        "lesson_id": lesson_id,
        "concept_id": payload.concept_id,
        "concept_name": concept["name"],
        "style": lesson_data["style"],
        "format": payload.format,
        "scenes": lesson_data["scenes"],
        "illustration_url": illustration_url,
        "used_fallback": bool(lesson_data.get("used_fallback", False)),
        "fallback_reason": lesson_data.get("fallback_reason"),
    }


@app.post("/api/quiz/generate")
def generate_quiz(payload: QuizGenerateRequest):
    """
    Fetch or synthesize 5 verified MCQs for concept assessment.
    Prioritizes previously untested chunks and passes prior question stems to prevent repetition.
    """
    if not get_student_by_id(payload.student_id):
        raise HTTPException(status_code=404, detail="Student session expired or invalid. Please log in again.")

    concept = get_concept_by_id(payload.concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail="Concept not found.")

    # Retrieve all chunks for concept
    all_chunks = get_chunks_for_concept(payload.concept_id)
    if not all_chunks:
        raise HTTPException(status_code=404, detail="No chunks found to generate quiz.")

    unanswered = get_unanswered_questions(payload.student_id, payload.concept_id, limit=5)
    needs_generation = len(unanswered) < 5 or payload.loop_index > 1
    quiz_meta: Dict[str, Any] = {"used_fallback": False, "fallback_reason": None}

    if needs_generation:
        prior_questions = get_all_questions_for_concept(payload.concept_id)
        used_chunk_ids = {int(q["source_chunk_id"]) for q in prior_questions if q.get("source_chunk_id")}
        excluded_texts = [q["question_text"] for q in prior_questions[-10:] if q.get("question_text")]

        # Prioritize untested chunks across the document before wrapping around
        unseen_chunks = [c for c in all_chunks if int(c["chunk_id"]) not in used_chunk_ids]
        if len(unseen_chunks) >= min(5, len(all_chunks)):
            active_chunks = unseen_chunks[:5]
        elif unseen_chunks:
            seen_chunks = [c for c in all_chunks if int(c["chunk_id"]) in used_chunk_ids]
            active_chunks = (unseen_chunks + seen_chunks)[:min(5, len(all_chunks))]
        else:
            chunk_offset = ((payload.loop_index - 1) * 4) % len(all_chunks)
            doubled_chunks = all_chunks + all_chunks
            active_chunks = doubled_chunks[chunk_offset:chunk_offset + min(5, len(all_chunks))]

        verified_qs = generate_and_verify_quiz(
            concept_id=payload.concept_id,
            concept_name=concept["name"],
            chunks=active_chunks,
            loop_index=payload.loop_index,
            excluded_questions=excluded_texts,
            meta_out=quiz_meta,
        )
        for q in verified_qs:
            save_question(
                concept_id=payload.concept_id,
                source_chunk_id=q.get("source_chunk_id"),
                question_text=q["question_text"],
                option_a=q["option_a"],
                option_b=q["option_b"],
                option_c=q["option_c"],
                option_d=q["option_d"],
                correct_letter=q["correct_letter"],
                explanation=q["explanation"],
                difficulty=q["difficulty"],
                loop_index=payload.loop_index
            )
        unanswered = get_unanswered_questions(payload.student_id, payload.concept_id, limit=5)

    # Return questions with answer keys hidden
    sanitized_questions = []
    for q in unanswered[:5]:
        sanitized_questions.append({
            "question_id": q["question_id"],
            "question_text": q["question_text"],
            "option_a": q["option_a"],
            "option_b": q["option_b"],
            "option_c": q["option_c"],
            "option_d": q["option_d"],
            "difficulty": q["difficulty"],
            "source_chunk_id": q.get("source_chunk_id")
        })

    return {
        "concept_id": payload.concept_id,
        "questions": sanitized_questions,
        "used_fallback": bool(quiz_meta.get("used_fallback", False)),
        "fallback_reason": quiz_meta.get("fallback_reason"),
    }


@app.post("/api/admin/reset")
def reset_database_api(payload: Optional[Dict[str, Any]] = None):
    """
    Reset and clean all database tables.
    If wipe_all is True: deletes concepts and prerequisite edges as well.
    If wipe_all is False: clears student attempts, mastery, questions, lessons, chunks.
    """
    wipe_all = payload.get("wipe_all", False) if payload else False
    try:
        from src.init_db import reset_database
    except ImportError:
        from init_db import reset_database
    reset_database(wipe_all=wipe_all)
    return {"status": "success", "message": "Database wiped successfully.", "wipe_all": wipe_all}



@app.post("/api/quiz/answer")
def submit_quiz_answers(payload: QuizAnswerRequest):
    """
    Deterministically grade submitted quiz answers.
    Updates mastery score and appends to mastery_history in an atomic Db2 transaction.
    """
    if not get_student_by_id(payload.student_id):
        raise HTTPException(status_code=404, detail="Student session expired or invalid. Please log in again.")

    results = []
    for ans in payload.answers:
        q = get_question_by_id(ans.question_id)
        if not q:
            continue
        selected = ans.selected_letter.strip().upper()
        correct = q["correct_letter"].strip().upper()
        is_correct = (selected == correct)

        record_attempt_and_update_mastery(
            student_id=payload.student_id,
            concept_id=payload.concept_id,
            question_id=ans.question_id,
            selected_letter=selected,
            is_correct=is_correct,
            difficulty=q["difficulty"]
        )

        results.append({
            "question_id": ans.question_id,
            "selected_letter": selected,
            "correct_letter": correct,
            "is_correct": is_correct,
            "explanation": q["explanation"],
            "citation_chunk_id": q.get("source_chunk_id")
        })

    mastery_rec = get_current_mastery(payload.student_id, payload.concept_id)

    return {
        "results": results,
        "score": sum(1 for r in results if r["is_correct"]),
        "total": len(results),
        "mastery_score": mastery_rec["mastery_score"],
        "attempt_count": mastery_rec["attempt_count"],
        "distinct_difficulties": mastery_rec["distinct_difficulties"]
    }


@app.post("/api/gate")
def evaluate_concept_gate(payload: GateRequest):
    """
    Evaluate 3-factor mastery gate:
    mastery >= 0.80 AND attempts >= 5 AND distinct_difficulties >= 2.
    If gate fails, executes IBM Db2 recursive CTE to isolate weakest root cause prerequisite.
    """
    if not get_student_by_id(payload.student_id):
        raise HTTPException(status_code=404, detail="Student session expired or invalid. Please log in again.")
    cur_c = get_concept_by_id(payload.concept_id)
    if not cur_c:
        raise HTTPException(status_code=404, detail="Concept not found.")

    m = get_current_mastery(payload.student_id, payload.concept_id)
    passed, reason = evaluate_gate(
        mastery_score=m["mastery_score"],
        attempt_count=m["attempt_count"],
        distinct_difficulties=m["distinct_difficulties"]
    )

    if passed:
        event_id = log_loop_event(
            student_id=payload.student_id,
            concept_id=payload.concept_id,
            event_type="GATE_PASS",
            gate_passed=True,
            mastery_score=m["mastery_score"],
            attempt_count=m["attempt_count"],
            distinct_difficulties=m["distinct_difficulties"],
            root_cause_concept_id=None,
            reason=reason
        )
        # Find next concept in sequence
        next_rows = execute_query(
            "SELECT concept_id, name, seq_order FROM concepts WHERE seq_order > ? ORDER BY seq_order ASC FETCH FIRST 1 ROWS ONLY",
            (cur_c["seq_order"],)
        )
        next_c = next_rows[0] if next_rows else None
        return {
            "gate_passed": True,
            "mastery_score": m["mastery_score"],
            "attempt_count": m["attempt_count"],
            "distinct_difficulties": m["distinct_difficulties"],
            "reason": reason,
            "next_concept": next_c,
            "event_id": event_id
        }
    else:
        # Run Db2 Recursive CTE
        root_cause, sql_query, prereq_rows = find_root_cause_prereq(payload.student_id, payload.concept_id)
        root_id = root_cause["concept_id"] if root_cause else None

        event_id = log_loop_event(
            student_id=payload.student_id,
            concept_id=payload.concept_id,
            event_type="GATE_FAIL",
            gate_passed=False,
            mastery_score=m["mastery_score"],
            attempt_count=m["attempt_count"],
            distinct_difficulties=m["distinct_difficulties"],
            root_cause_concept_id=root_id,
            reason=reason,
            sql_query=sql_query
        )

        needs_human_help = (payload.loop_count >= 3)
        styles = ["overview", "worked example", "analogy", "step-by-step"]
        next_style = styles[payload.loop_count % len(styles)]

        return {
            "gate_passed": False,
            "mastery_score": m["mastery_score"],
            "attempt_count": m["attempt_count"],
            "distinct_difficulties": m["distinct_difficulties"],
            "reason": reason,
            "root_cause": root_cause,
            "prereq_chain": prereq_rows,
            "loop_count": payload.loop_count,
            "needs_human_help": needs_human_help,
            "next_style": next_style,
            "event_id": event_id
        }


@app.get("/api/progress/{student_id}")
def get_progress(student_id: int):
    """
    Read real-time progress matrix via SQL VIEW v_student_progress
    and mastery history progression from mastery_history table.
    """
    progress = get_student_progress_view(student_id)
    history = get_mastery_history_series(student_id)
    latest_events = execute_query(
        "SELECT event_id FROM loop_events WHERE student_id = ? ORDER BY event_id DESC FETCH FIRST 1 ROWS ONLY",
        (student_id,),
    )
    latest_event_id = latest_events[0]["event_id"] if latest_events else None
    return {
        "progress": progress,
        "history": history,
        "latest_event_id": latest_event_id,
    }


@app.get("/api/why/{event_id}")
def get_why_this(event_id: int):
    """
    Inspection endpoint for 'Why this?' transparency.
    Returns loop event decision, reason, and underlying Db2 SQL query.
    """
    event = get_loop_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Loop event #{event_id} not found.")

    prereq_details = []
    if event.get("root_cause_concept_id"):
        # Re-fetch candidate prerequisite rows for inspection
        _, _, prereq_details = find_root_cause_prereq(
            student_id=event["student_id"],
            current_concept_id=event["concept_id"]
        )

    return {
        "event_id": event["event_id"],
        "student_id": event["student_id"],
        "concept_id": event["concept_id"],
        "event_type": event["event_type"],
        "gate_passed": bool(event["gate_passed"]),
        "mastery_score": event["mastery_score"],
        "attempt_count": event["attempt_count"],
        "distinct_difficulties": event["distinct_difficulties"],
        "root_cause_concept_id": event.get("root_cause_concept_id"),
        "reason": event["reason"],
        "sql_query": event.get("sql_query"),
        "created_at": str(event["created_at"]),
        "prereq_rows": prereq_details
    }


@app.get("/api/illustration/{lesson_id}")
def get_illustration(lesson_id: int):
    """
    Serve generated illustration BLOB for a lesson.
    """
    img_rec = get_lesson_image(lesson_id)
    if not img_rec:
        raise HTTPException(status_code=404, detail="Illustration not found.")
    return Response(content=img_rec["image_data"], media_type=img_rec.get("mime_type", "image/png"))


# ====================================================================
# STATIC FILE SERVING FOR VANILLA FRONTEND
# ====================================================================

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "frontend"))

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_dir}. API routes active.")

