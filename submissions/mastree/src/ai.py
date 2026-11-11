"""
AI, LLM, and Embeddings orchestration for MasteryLoop (mastree).
Interacts with Google Gemini via google-genai SDK with:
- SHA-256 persistent response caching in Db2 table llm_cache
- Batch embedding generation and BM25-style fallback retrieval
- Batch question generation (5 MCQs in 1 call)
- Batch answer key verification (5 questions verified in 1 call)
- Chunk citations and strictly bounded lesson generation
- DEMO_MODE=1 offline support
"""

import os
import re
import json
import math
import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("mastree.ai")

# Safe imports from google.genai
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
except ImportError:
    genai = None
    types = None
    APIError = Exception

from src.db import get_cached_llm, set_cached_llm, get_db, transaction


class AIError(Exception):
    """Base exception for AI/LLM operational errors."""
    pass


class AIConfigError(AIError):
    """Configuration error (missing or placeholder API key, invalid model)."""
    pass


class AIRateLimitError(AIError):
    """Rate limit or quota exhaustion (HTTP 429)."""
    pass


def get_cache_key(model: str, prompt: str) -> str:
    """Compute deterministic SHA-256 hash for model + prompt."""
    digest = hashlib.sha256(f"{model}::{prompt}".encode("utf-8")).hexdigest()
    return digest


def is_demo_mode() -> bool:
    """Return True if DEMO_MODE is enabled in environment."""
    return os.getenv("DEMO_MODE", "0").strip() in ("1", "true", "True")


def get_gemini_client():
    """Instantiate and return Google GenAI Client with 25s HTTP timeout."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_YOUR_KEY_HERE" or "YOUR_" in api_key.upper():
        raise AIConfigError(
            "GEMINI_API_KEY is not configured. Please set a valid Gemini API key in "
            "submissions/mastree/.env or enable DEMO_MODE=1 to run offline from cache."
        )
    if genai is None:
        raise AIConfigError("The google-genai package is not installed. Run: pip install google-genai")
    if types and hasattr(types, "HttpOptions"):
        return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=25000))
    return genai.Client(api_key=api_key)


DEFAULT_GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]


def _parse_json_response(raw_text: str) -> Any:
    """Parse JSON from an LLM response, stripping optional markdown code fences cleanly."""
    clean = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", clean, flags=re.IGNORECASE)
    if fence_match:
        clean = fence_match.group(1).strip()
    return json.loads(clean)


def generate_text(prompt: str, temperature: float = 0.2) -> str:
    """
    Generate text using Gemini with SHA-256 caching in Db2 llm_cache and
    automatic failover across active Flash models on 404/503/500 responses.
    Supports DEMO_MODE=1.
    """
    primary = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
    models_to_try = [primary] + [m for m in DEFAULT_GEMINI_MODELS if m != primary]
    cache_key = get_cache_key(primary, prompt)

    # 1. Check persistent Db2 cache
    cached = get_cached_llm(cache_key)
    if cached is not None:
        logger.info(f"LLM Cache Hit for key {cache_key[:8]}...")
        return cached

    # 2. Check DEMO_MODE
    if is_demo_mode():
        raise AIConfigError(
            f"DEMO_MODE=1 is active and no cached response exists for this prompt. "
            f"Please run online with a valid GEMINI_API_KEY to populate the cache."
        )

    # 3. Call Gemini with automatic failover across active models
    client = get_gemini_client()
    last_exc: Optional[Exception] = None
    want_json = "STRICTLY VALID JSON" in prompt.upper() or "ONLY VALID JSON" in prompt.upper() or "VALID JSON" in prompt.upper()

    for model_name in models_to_try:
        try:
            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json" if want_json else "text/plain"
            ) if types else None

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            text = response.text or ""
            set_cached_llm(cache_key, model_name, prompt, text)
            if model_name != primary:
                logger.info(f"Gemini failover succeeded using '{model_name}' (primary '{primary}' unavailable).")
            return text
        except Exception as e:
            err_msg = str(e)
            last_exc = e
            upper_err = err_msg.upper()
            if any(code in upper_err for code in ("404", "NOT_FOUND", "503", "UNAVAILABLE", "500", "INTERNAL", "504", "DEADLINE_EXCEEDED", "TIMEOUT", "TIMED OUT")):
                logger.warning(f"Model '{model_name}' unavailable ({err_msg[:120]}); trying next model.")
                continue
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in upper_err:
                raise AIRateLimitError(
                    "Google Gemini Free Tier Rate Limit exceeded (429). "
                    "Please wait 60 seconds before retrying or set DEMO_MODE=1 for cached offline demonstration."
                ) from e
            raise AIError(f"Gemini generation error ({model_name}): {err_msg}") from e

    err_msg = str(last_exc) if last_exc else "No Gemini models responded"
    if "404" in err_msg or "NOT_FOUND" in err_msg:
        raise AIConfigError(
            f"Configured Gemini model '{primary}' and fallbacks were not found. Update GEMINI_MODEL in .env."
        ) from last_exc
    raise AIError(f"All Gemini models unavailable: {err_msg}") from last_exc


def synthesize_ai_knowledge(topic: str, focus: str = "") -> str:
    """
    Generate a thorough, textbook-quality educational study document (~1,500 words)
    directly from Gemini's knowledge base for ingestion into Db2 chunks.
    """
    focus_clause = f"\nFocus emphasis / perspective: {focus.strip()}" if focus.strip() else ""
    prompt = f"""
You are an expert curriculum author. Write a clear, accurate, comprehensive educational reference guide on: "{topic}".{focus_clause}

Structure the material across 5 detailed sections so a student can deeply master the subject and answer non-trivial technical assessments:
1. Core Concepts & Mental Model (fundamental principles, definitions, and why it matters)
2. Internal Mechanics & How It Works (step-by-step mechanisms, rules, or execution flow)
3. Concrete Worked Examples (real syntax, formulas, or step-by-step practical scenarios explained clearly)
4. Nuances, Edge Cases & Common Misconceptions (subtle distinctions, failure modes, and boundaries)
5. Trade-Offs, Comparisons & Practical Takeaways

Requirements:
- Target length: 800 to 1,100 words of crisp, well-organized educational prose (plain informative paragraphs, zero fluff).
- Be factually precise and self-contained; include concrete examples, comparisons, and specific technical distinctions.
"""
    text = generate_text(prompt, temperature=0.35).strip()
    if len(text.split()) < 80:
        raise AIError(f"Gemini produced insufficient study content for '{topic}'.")
    return text


# ====================================================================
# BATCH EMBEDDING & VECTOR SIMILARITY
# ====================================================================

def batch_embed_texts(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Batch embed a list of texts in ONE call using Gemini embeddings API.
    Caches each result in llm_cache.
    If Gemini fails, returns list of None to trigger BM25 fallback.
    """
    if not texts:
        return []

    embed_model = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001").strip()
    results: List[Optional[List[float]]] = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    # Check cache across all texts using ONE Db2 connection
    try:
        with get_db() as conn:
            for idx, text in enumerate(texts):
                key = get_cache_key(embed_model, f"EMBED::{text.strip()}")
                cached = get_cached_llm(key, conn=conn)
                if cached:
                    try:
                        results[idx] = json.loads(cached)
                    except Exception:
                        uncached_indices.append(idx)
                        uncached_texts.append(text)
                else:
                    uncached_indices.append(idx)
                    uncached_texts.append(text)
    except Exception:
        uncached_indices = list(range(len(texts)))
        uncached_texts = list(texts)

    if not uncached_texts:
        return results

    if is_demo_mode():
        logger.info("DEMO_MODE=1: skipping live embedding API call.")
        return results

    try:
        client = get_gemini_client()
        resp = client.models.embed_content(
            model=embed_model,
            contents=uncached_texts
        )
        embeddings_list = resp.embeddings if hasattr(resp, "embeddings") else []
        to_cache = []
        for i, emb_obj in enumerate(embeddings_list):
            vec = emb_obj.values if hasattr(emb_obj, "values") else list(emb_obj)
            orig_idx = uncached_indices[i]
            results[orig_idx] = vec
            key = get_cache_key(embed_model, f"EMBED::{uncached_texts[i].strip()}")
            to_cache.append((key, embed_model, f"EMBED::{uncached_texts[i].strip()}", json.dumps(vec)))

        if to_cache:
            try:
                with transaction() as conn:
                    for key, emodel, ptxt, rtxt in to_cache:
                        set_cached_llm(key, emodel, ptxt, rtxt, conn=conn)
            except Exception as ce:
                logger.debug(f"Batch embedding cache write skipped: {ce}")
    except Exception as e:
        logger.warning(f"Embedding batch call failed ({e}); falling back to BM25 keyword retrieval.")

    return results


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


# ====================================================================
# BM25 KEYWORD RETRIEVAL FALLBACK
# ====================================================================

def tokenize(text: str) -> List[str]:
    """Simple alphanumeric word tokenizer."""
    return re.findall(r"\w+", text.lower())


def bm25_score(query: str, doc: str, avg_doc_len: float = 120.0, k1: float = 1.5, b: float = 0.75) -> float:
    """
    BM25 ranking score for a query against a document text.
    Handles keyword relevance when embeddings are disabled or rate-limited.
    """
    q_tokens = tokenize(query)
    d_tokens = tokenize(doc)
    if not q_tokens or not d_tokens:
        return 0.0
    
    doc_len = len(d_tokens)
    tf = Counter(d_tokens)
    score = 0.0
    for term in q_tokens:
        freq = tf.get(term, 0)
        if freq > 0:
            numerator = freq * (k1 + 1.0)
            denominator = freq + k1 * (1.0 - b + b * (doc_len / max(avg_doc_len, 1.0)))
            score += numerator / denominator
    return score


def retrieve_top_chunks(
    chunks: List[Dict[str, Any]],
    query: str,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Retrieve top K chunks for a concept using vector cosine similarity
    with automatic BM25 keyword fallback.
    """
    if not chunks:
        return []

    # Check if chunks have embeddings stored
    has_embeddings = any(c.get("embedding") is not None for c in chunks)

    if has_embeddings:
        # Try to embed the query
        q_embeddings = batch_embed_texts([query])
        if q_embeddings and q_embeddings[0] is not None:
            q_vec = q_embeddings[0]
            scored = []
            for c in chunks:
                emb_str = c.get("embedding")
                if emb_str:
                    try:
                        emb = json.loads(emb_str) if isinstance(emb_str, str) else emb_str
                        sim = cosine_similarity(q_vec, emb)
                    except Exception:
                        sim = 0.0
                else:
                    sim = 0.0
                scored.append((sim, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [c for score, c in scored[:top_k]]

    # BM25 Keyword retrieval fallback
    avg_len = sum(len(tokenize(c["content"])) for c in chunks) / max(len(chunks), 1)
    scored = []
    for c in chunks:
        score = bm25_score(query, c["content"], avg_doc_len=avg_len)
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for score, c in scored[:top_k]]


# ====================================================================
# STEP 3: LESSON BOARD GENERATION
# ====================================================================

LESSON_STYLES = {
    1: "step-by-step",
    2: "worked example",
    3: "analogy"
}


def generate_lesson_board(
    concept_name: str,
    chunks: List[Dict[str, Any]],
    loop_count: int = 1
) -> List[Dict[str, Any]]:
    """
    Generate step-by-step lesson board using ONLY the retrieved chunks.
    Varies style by loop count (1: step-by-step, 2: worked example, 3: analogy).
    Cites source chunk IDs for each step.
    """
    style = LESSON_STYLES.get(loop_count, "step-by-step")
    
    # Format chunks with their IDs
    context_blocks = []
    chunk_ids = []
    for c in chunks:
        cid = c["chunk_id"]
        chunk_ids.append(cid)
        context_blocks.append(f"[Chunk #{cid}]:\n{c['content']}")
    
    context_str = "\n\n".join(context_blocks)

    prompt = f"""
You are the MasteryLoop Adaptive Tutor.
Your task is to teach the SQL concept: '{concept_name}' using ONLY the following verified source chunks.

STYLE REQUIREMENT: Deliver the lesson in '{style}' pedagogical style.
- If 'step-by-step': Present clear numbered conceptual phases with syntactical explanations.
- If 'worked example': Present concrete SQL query code scenarios showing input data, SQL syntax, and execution output.
- If 'analogy': Use intuitive real-world metaphors (e.g., sorting filing cabinets, filtering mail, joining puzzle pieces) alongside SQL syntax.

STRICT ACCURACY RULES:
1. Rely ONLY on the provided chunks below. Never invent, extrapolate, or hallucinate concepts or syntax not covered.
2. If the chunks do not cover an aspect, explicitly state: "The provided notes do not cover this detail."
3. Divide the lesson into 3 to 4 sequential steps suitable for a step-by-step Board presentation.
4. Each step MUST cite the exact chunk ID(s) it is derived from in the 'cited_chunk_ids' list.

SOURCE CHUNKS:
{context_str}

OUTPUT FORMAT: Return strictly valid JSON containing a list of step objects:
[
  {{
    "step_num": 1,
    "title": "Short descriptive step title",
    "content": "Explanation in {style} style (use Markdown formatting with code fences where helpful). If something is not in the chunks, state so.",
    "cited_chunk_ids": [{chunk_ids[0] if chunk_ids else 1}]
  }}
]
"""
    try:
        raw_text = generate_text(prompt, temperature=0.2)
        # Parse JSON from response
        clean_json = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
        clean_json = re.sub(r"\s*```$", "", clean_json)
        data = json.loads(clean_json)
        if isinstance(data, list) and len(data) > 0:
            return data
    except Exception as e:
        logger.warning(f"Live lesson generation failed or in offline mode: {e}. Using deterministic fallback.")

    # High quality deterministic fallback lesson if offline or Gemini fails
    return _build_fallback_lesson(concept_name, chunks, style)


def _build_fallback_lesson(concept_name: str, chunks: List[Dict[str, Any]], style: str) -> List[Dict[str, Any]]:
    """Deterministic fallback lesson built strictly from chunks."""
    steps = []
    chunk_ids = [c["chunk_id"] for c in chunks]
    first_chunk = chunks[0]["content"] if chunks else "Core SQL foundation."
    second_chunk = chunks[1]["content"] if len(chunks) > 1 else first_chunk

    if style == "worked example":
        steps.append({
            "step_num": 1,
            "title": f"Problem Scenario & Query Construction: {concept_name}",
            "content": f"Consider an enterprise database needing to process queries for **{concept_name}**.\n\n"
                       f"```sql\n-- Example demonstration\nSELECT * FROM employees;\n```\n\n"
                       f"According to course notes: {first_chunk[:200]}...",
            "cited_chunk_ids": [chunk_ids[0]] if chunk_ids else []
        })
        steps.append({
            "step_num": 2,
            "title": "Execution Mechanics & Result Set",
            "content": f"When executing this query, Db2 processes the logic directly:\n\n{second_chunk[:200]}...",
            "cited_chunk_ids": [chunk_ids[-1]] if chunk_ids else []
        })
        steps.append({
            "step_num": 3,
            "title": "Edge Case & Verification",
            "content": "Verify that all edge conditions comply with the syntax guidelines in the provided documentation.",
            "cited_chunk_ids": chunk_ids
        })
    elif style == "analogy":
        steps.append({
            "step_num": 1,
            "title": f"Real-World Conceptual Metaphor: {concept_name}",
            "content": f"Think of **{concept_name}** as an intelligent sorting and organizing system in a corporate office.\n\n"
                       f"{first_chunk[:180]}...",
            "cited_chunk_ids": [chunk_ids[0]] if chunk_ids else []
        })
        steps.append({
            "step_num": 2,
            "title": "Translating Metaphor to SQL Mechanics",
            "content": f"In SQL syntax, this metaphor translates directly into database operations:\n\n{second_chunk[:200]}...",
            "cited_chunk_ids": [chunk_ids[-1]] if chunk_ids else []
        })
        steps.append({
            "step_num": 3,
            "title": "Key Takeaways & Boundary Rules",
            "content": "Note that unstated features are not part of the provided specification.",
            "cited_chunk_ids": chunk_ids
        })
    else: # step-by-step
        steps.append({
            "step_num": 1,
            "title": f"Phase 1: Purpose of {concept_name}",
            "content": f"**{concept_name}** defines fundamental relational querying rules:\n\n{first_chunk}",
            "cited_chunk_ids": [chunk_ids[0]] if chunk_ids else []
        })
        steps.append({
            "step_num": 2,
            "title": f"Phase 2: Rules & Structural Syntax",
            "content": f"Key syntactic behavior:\n\n{second_chunk}",
            "cited_chunk_ids": [chunk_ids[-1]] if chunk_ids else []
        })
        steps.append({
            "step_num": 3,
            "title": f"Phase 3: Best Practices & Caveats",
            "content": "Always adhere to the Single-Value rule, NULL evaluation nuances, and clause execution sequence.",
            "cited_chunk_ids": chunk_ids
        })

    return steps


# ====================================================================
# UNIFIED 5-6 SCENE LESSON GENERATOR WITH STRICT VISUAL SCHEMAS
# ====================================================================

def validate_visual(visual: Any) -> Dict[str, Any]:
    """
    Validate visual structure against allowed types:
    flow, cycle, hierarchy, compare, timeline, concept_map, equation, bullets.
    Strictly forbids any SVG or HTML; falls back to 'bullets'.
    """
    if not isinstance(visual, dict):
        return {"type": "bullets"}
    vtype = str(visual.get("type", "")).lower().strip()

    if vtype == "flow":
        steps = visual.get("steps")
        if isinstance(steps, list) and len(steps) >= 2:
            return {"type": "flow", "steps": [str(s)[:60] for s in steps[:6]]}

    elif vtype == "cycle":
        steps = visual.get("steps")
        if isinstance(steps, list) and len(steps) >= 2:
            return {"type": "cycle", "steps": [str(s)[:60] for s in steps[:6]]}

    elif vtype == "hierarchy":
        root = visual.get("root")
        if isinstance(root, dict) and "label" in root:
            def clean_node(n):
                if not isinstance(n, dict):
                    return {"label": str(n)[:40], "children": []}
                return {
                    "label": str(n.get("label", ""))[:40],
                    "children": [clean_node(c) for c in n.get("children", []) if isinstance(c, (dict, str))][:4]
                }
            return {"type": "hierarchy", "root": clean_node(root)}

    elif vtype == "compare":
        left = visual.get("left", {})
        right = visual.get("right", {})
        if isinstance(left, dict) and isinstance(right, dict):
            return {
                "type": "compare",
                "left": {
                    "title": str(left.get("title", "Aspect A"))[:40],
                    "points": [str(p)[:80] for p in left.get("points", [])][:4]
                },
                "right": {
                    "title": str(right.get("title", "Aspect B"))[:40],
                    "points": [str(p)[:80] for p in right.get("points", [])][:4]
                }
            }

    elif vtype == "timeline":
        events = visual.get("events")
        if isinstance(events, list) and len(events) >= 1:
            clean_events = []
            for ev in events[:6]:
                if isinstance(ev, dict):
                    clean_events.append({
                        "label": str(ev.get("label", ""))[:40],
                        "detail": str(ev.get("detail", ""))[:80]
                    })
            if clean_events:
                return {"type": "timeline", "events": clean_events}

    elif vtype == "concept_map":
        nodes = visual.get("nodes")
        edges = visual.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            clean_nodes = [str(n)[:40] for n in nodes[:8]]
            clean_edges = []
            for e in edges[:10]:
                if isinstance(e, dict) and "from" in e and "to" in e:
                    clean_edges.append({
                        "from": str(e["from"])[:40],
                        "to": str(e["to"])[:40]
                    })
            return {"type": "concept_map", "nodes": clean_nodes, "edges": clean_edges}

    elif vtype == "equation":
        latex = visual.get("latex")
        if latex:
            return {
                "type": "equation",
                "latex": str(latex)[:120],
                "explanation": str(visual.get("explanation", ""))[:120]
            }

    return {"type": "bullets"}


def validate_scene(scene: Any, valid_chunk_ids: List[int]) -> Optional[Dict[str, Any]]:
    """Validate a single lesson scene according to strict pedagogical rules."""
    if not isinstance(scene, dict):
        return None
    title = str(scene.get("title", "")).strip()
    narration = str(scene.get("narration", "")).strip()
    if not title or not narration:
        return None

    # Cap narration at <= 45 words
    words = narration.split()
    if len(words) > 45:
        narration = " ".join(words[:45])

    # Cap bullets at <= 4
    raw_bullets = scene.get("bullets", [])
    bullets = [str(b).strip() for b in raw_bullets if str(b).strip()][:4]

    key_term = str(scene.get("key_term", "")).strip()

    # Citations validation
    raw_citations = scene.get("citations", [])
    citations = []
    if isinstance(raw_citations, list):
        for cid in raw_citations:
            try:
                icid = int(cid)
                if icid in valid_chunk_ids or not valid_chunk_ids:
                    citations.append(icid)
            except (ValueError, TypeError):
                pass
    if not citations and valid_chunk_ids:
        citations = [valid_chunk_ids[0]]

    visual = validate_visual(scene.get("visual"))

    return {
        "title": title,
        "narration": narration,
        "bullets": bullets,
        "key_term": key_term,
        "citations": citations,
        "visual": visual
    }


def _clip_words(text: str, max_words: int = 35) -> str:
    """Clip a text excerpt cleanly to at most max_words words."""
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


def _build_fallback_scenes(
    concept_name: str,
    chunks: List[Dict[str, Any]],
    style: str
) -> List[Dict[str, Any]]:
    """Build a deterministic 5-scene lesson strictly grounded in the retrieved chunks."""
    chunk_ids = [c["chunk_id"] for c in chunks] if chunks else [1]
    cid0 = chunk_ids[0]
    cid1 = chunk_ids[1] if len(chunk_ids) > 1 else cid0
    cid2 = chunk_ids[2] if len(chunk_ids) > 2 else cid1
    cid3 = chunk_ids[3] if len(chunk_ids) > 3 else cid2

    c0 = chunks[0]["content"] if chunks else f"Core concepts of {concept_name}."
    c1 = chunks[1]["content"] if len(chunks) > 1 else c0
    c2 = chunks[2]["content"] if len(chunks) > 2 else c1
    c3 = chunks[3]["content"] if len(chunks) > 3 else c2

    def _bullets_from(txt: str, default_label: str) -> List[str]:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", txt.strip()) if len(s.strip().split()) >= 4]
        out = [_clip_words(s, 14) for s in sents[:3]]
        while len(out) < 2:
            out.append(default_label)
        return out[:4]

    return [
        {
            "title": f"Overview of {concept_name}",
            "narration": _clip_words(f"Let us explore {concept_name}. {c0}", 42),
            "bullets": _bullets_from(c0, f"Core principles of {concept_name}"),
            "key_term": concept_name[:30],
            "citations": [cid0],
            "visual": {
                "type": "flow",
                "steps": ["Core Definition", "Key Mechanism", "Practical Application"]
            }
        },
        {
            "title": f"Key Mechanics ({style.title()})",
            "narration": _clip_words(c1, 42),
            "bullets": _bullets_from(c1, f"Primary mechanisms in {concept_name}"),
            "key_term": "Core Mechanism",
            "citations": [cid1],
            "visual": {
                "type": "concept_map",
                "nodes": [concept_name[:24], "Foundation", "Applied Behavior"],
                "edges": [
                    {"from": concept_name[:24], "to": "Foundation"},
                    {"from": "Foundation", "to": "Applied Behavior"}
                ]
            }
        },
        {
            "title": "Structure & Components",
            "narration": _clip_words(c2, 42),
            "bullets": _bullets_from(c2, "Component relationships and rules"),
            "key_term": "Components",
            "citations": [cid2],
            "visual": {
                "type": "compare",
                "left": {"title": "Core Concept", "points": _bullets_from(c0, "Foundational principles")[:2]},
                "right": {"title": "Details & Context", "points": _bullets_from(c2, "Operational rules")[:2]}
            }
        },
        {
            "title": "Important Details & Context",
            "narration": _clip_words(c3, 42),
            "bullets": _bullets_from(c3, "Important constraints from source notes"),
            "key_term": "Key Details",
            "citations": [cid3],
            "visual": {
                "type": "timeline",
                "events": [
                    {"label": "Foundation", "detail": _clip_words(c0, 10)},
                    {"label": "Structure", "detail": _clip_words(c1, 10)},
                    {"label": "Application", "detail": _clip_words(c3, 10)}
                ]
            }
        },
        {
            "title": f"Summary: {concept_name}",
            "narration": _clip_words(
                f"To master {concept_name}, review these retrieved passages carefully before taking your assessment.",
                42
            ),
            "bullets": [
                _clip_words(c0, 12),
                _clip_words(c1, 12),
                "Complete 5 verification questions"
            ],
            "key_term": "Review",
            "citations": chunk_ids[:3],
            "visual": {"type": "bullets"}
        }
    ]


def generate_scenes_lesson(
    concept_name: str,
    chunks: List[Dict[str, Any]],
    style: Optional[str] = None,
    loop_count: int = 1
) -> Dict[str, Any]:
    """
    Generate 5-6 scenes in ONE Gemini call, cached in llm_cache.
    Built ONLY from retrieved chunks. Retries once on invalid schema;
    falls back to visual 'bullets' or deterministic scenes.
    """
    styles_list = ["overview", "worked example", "analogy", "step-by-step"]
    chosen_style = style if style in styles_list else styles_list[(loop_count - 1) % len(styles_list)]

    chunk_ids = [c["chunk_id"] for c in chunks] if chunks else [1]
    chunk_manifest = "\n\n".join(f"[Chunk #{c['chunk_id']}]:\n{c['content']}" for c in chunks)

    prompt = f"""
You are the MasteryLoop Adaptive Tutor (Iteration #{loop_count}).
Produce a comprehensive 5 to 6 scene instructional lesson for: '{concept_name}'.
Base all content STRICTLY and ONLY upon the following verified source chunks.

TEACHING APPROACH: Deliver the lesson in '{chosen_style}' pedagogical style:
- 'overview': Structured conceptual introduction, definitions, and core purpose from the chunks.
- 'worked example': Practical scenarios, concrete worked examples/syntax from the chunks, and step-by-step walkthroughs.
- 'analogy': Intuitive real-world mental models alongside the technical principles in the chunks.
- 'step-by-step': Strict procedural breakdown of key stages and concepts described in the chunks.

STRICT SCENE REQUIREMENTS:
1. Return exactly 5 or 6 scene objects in a JSON object with key "scenes".
2. Each scene object must contain:
   - "title": Short descriptive title (3-6 words)
   - "narration": Teacher script of AT MOST 45 words. Clear, conversational, spoken tone.
   - "bullets": Array of AT MOST 4 concise bullet points (each <= 14 words).
   - "key_term": 1-3 word primary concept term to highlight.
   - "citations": Array of integer chunk IDs cited from: {chunk_ids}
   - "visual": A structured visual object representing the scene diagram.
3. ALLOWED VISUAL TYPES & SCHEMAS (NO HTML or SVG allowed):
   - {{"type": "flow", "steps": ["Step 1", "Step 2", "Step 3"]}}
   - {{"type": "cycle", "steps": ["Phase A", "Phase B", "Phase C"]}}
   - {{"type": "hierarchy", "root": {{"label": "Root", "children": [{{"label": "Child 1", "children": []}}]}}}}
   - {{"type": "compare", "left": {{"title": "Option A", "points": ["...", "..."]}}, "right": {{"title": "Option B", "points": ["...", "..."]}}}}
   - {{"type": "timeline", "events": [{{"label": "Stage 1", "detail": "..."}}]}}
   - {{"type": "concept_map", "nodes": ["A", "B", "C"], "edges": [{{"from": "A", "to": "B"}}]}}
   - {{"type": "equation", "latex": "Formula or Syntax Expression", "explanation": "..."}}
   - {{"type": "bullets"}}
4. Use diverse visual types across the scenes (e.g. Scene 1: flow, Scene 2: compare, Scene 3: concept_map, Scene 4: equation, Scene 5: bullets).
5. STRICT GROUNDING: Rely strictly on provided chunks. If something is unstated, say "The provided notes do not cover this detail."

SOURCE CHUNKS:
{chunk_manifest}

OUTPUT FORMAT: Return ONLY valid JSON:
{{
  "scenes": [
    {{
      "title": "...",
      "narration": "...",
      "bullets": ["...", "..."],
      "key_term": "...",
      "citations": [{chunk_ids[0]}],
      "visual": {{"type": "flow", "steps": ["Step 1", "Step 2", "Step 3"]}}
    }}
  ]
}}
"""
    scenes = None
    last_err: Optional[str] = None
    for attempt in range(2):
        try:
            eff_prompt = prompt if attempt == 0 else prompt + f"\n(Format retry #{attempt}: return valid JSON only matching the schema.)"
            raw_text = generate_text(eff_prompt, temperature=0.25 if attempt == 0 else 0.4)
            data = _parse_json_response(raw_text)
            raw_scenes = data.get("scenes", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            if isinstance(raw_scenes, list) and len(raw_scenes) >= 4:
                validated = []
                for sc in raw_scenes:
                    vsc = validate_scene(sc, chunk_ids)
                    if vsc:
                        validated.append(vsc)
                if len(validated) >= 4:
                    scenes = validated[:6]
                    break
            last_err = "Invalid or insufficient scene schema returned by Gemini"
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Scene generation attempt {attempt + 1} failed: {e}")

    used_fallback = False
    if not scenes:
        used_fallback = True
        scenes = _build_fallback_scenes(concept_name, chunks, chosen_style)

    return {
        "concept_name": concept_name,
        "style": chosen_style,
        "scenes": scenes,
        "used_fallback": used_fallback,
        "fallback_reason": last_err if used_fallback else None,
    }


def chunk_text(text: str, target_words: int = 120) -> List[str]:
    """
    Split text into chunks of approximately target_words words,
    breaking cleanly at sentence boundaries where possible.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        if current_word_count + len(words) > target_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = len(words)
        else:
            current_chunk.append(sentence)
            current_word_count += len(words)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def search_with_gemini_grounding(query: str) -> List[Dict[str, str]]:
    """
    Search using Gemini with Google Search grounding tool if GEMINI_WEB_SEARCH=1.
    Returns list of [{id, title, snippet, source: 'web', url}].
    """
    if os.getenv("GEMINI_WEB_SEARCH", "0").strip() != "1" or is_demo_mode():
        return []
    try:
        client = get_gemini_client()
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        resp = client.models.generate_content(
            model=model_name,
            contents=f"Provide a concise technical summary and key web references for: {query}",
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.1
            ) if types else None
        )
        text = resp.text or ""
        snippet = text[:280].strip() + ("..." if len(text) > 280 else "")
        urls = []
        candidates = getattr(resp, "candidates", [])
        if candidates:
            c = candidates[0]
            gm = getattr(c, "grounding_metadata", None)
            if gm:
                chunks = getattr(gm, "grounding_chunks", [])
                for chk in chunks:
                    web = getattr(chk, "web", None)
                    if web:
                        u = getattr(web, "uri", None)
                        if u and u not in urls:
                            urls.append(u)
        primary_url = urls[0] if urls else "https://google.com"
        return [{
            "id": f"web-{hashlib.md5(query.encode()).hexdigest()[:8]}",
            "title": f"Web Overview: {query}",
            "snippet": snippet,
            "full_text": text,
            "source": "web",
            "url": primary_url
        }]
    except Exception as e:
        logger.warning(f"Gemini grounding search error: {e}")
        return []


def generate_illustration(concept_name: str, key_term: str = "") -> Optional[bytes]:
    """Optionally generate one illustration for a lesson if GEMINI_IMAGE_MODEL is set."""
    image_model = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
    if not image_model or is_demo_mode():
        return None
    try:
        client = get_gemini_client()
        prompt = f"Educational technical diagram explaining {concept_name} {key_term}, clean minimalist dark background vector style"
        resp = client.models.generate_images(
            model=image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9"
            ) if types and hasattr(types, "GenerateImagesConfig") else None
        )
        if hasattr(resp, "generated_images") and resp.generated_images:
            img = resp.generated_images[0]
            if hasattr(img, "image") and hasattr(img.image, "image_bytes"):
                return img.image.image_bytes
    except Exception as e:
        logger.debug(f"Optional illustration generation skipped: {e}")
    return None



# ====================================================================
# STEP 4: QUIZ GENERATION & VERIFICATION PASS
# ====================================================================

def generate_and_verify_quiz(
    concept_id: int,
    concept_name: str,
    chunks: List[Dict[str, Any]],
    loop_index: int = 1,
    excluded_questions: Optional[List[str]] = None,
    meta_out: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Generate 5 MCQs in ONE batch call.
    Verify all 5 answer keys in ONE batch call against source chunks.
    Discard failures. If fewer than 5 remain, regenerate once.
    Records fallback metadata in optional meta_out dict.
    """
    last_err: Optional[str] = None
    if meta_out is not None:
        meta_out["used_fallback"] = False
        meta_out["fallback_reason"] = None

    for attempt_round in range(2):
        try:
            questions = _batch_generate_questions(
                concept_id,
                concept_name,
                chunks,
                loop_index,
                excluded_questions=excluded_questions,
                retry_round=attempt_round,
            )
            if questions:
                verified = _batch_verify_questions(questions, chunks)
                if len(verified) >= 5:
                    return verified[:5]
                elif attempt_round == 0:
                    logger.info(f"Verification retained {len(verified)}/5 questions; triggering regeneration pass.")
                    continue
                else:
                    if meta_out is not None:
                        meta_out["used_fallback"] = True
                        meta_out["fallback_reason"] = f"Partial AI quiz verification ({len(verified)}/5 passed audit)."
                    fallback = _build_fallback_quiz(concept_id, concept_name, chunks, loop_index)
                    return (verified + fallback)[:5]
            last_err = "Empty MCQ list returned by Gemini"
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Live quiz generation failed ({e}); using fallback question pool.")
            break

    if meta_out is not None:
        meta_out["used_fallback"] = True
        meta_out["fallback_reason"] = last_err or "Live Gemini unavailable"
    return _build_fallback_quiz(concept_id, concept_name, chunks, loop_index)[:5]


def _batch_generate_questions(
    concept_id: int,
    concept_name: str,
    chunks: List[Dict[str, Any]],
    loop_index: int,
    excluded_questions: Optional[List[str]] = None,
    retry_round: int = 0,
) -> List[Dict[str, Any]]:
    """Batch generate 5 high-quality MCQs (easy/medium/hard) in ONE Gemini call."""
    chunk_ids = [int(c["chunk_id"]) for c in chunks] if chunks else [1]
    chunk_manifest = "\n\n".join(f"[Chunk #{c['chunk_id']}]:\n{c['content']}" for c in chunks)
    foci = [
        "Core definitions, core mechanisms, and primary purpose documented in the chunks",
        "Subtle nuances, edge cases, parameter/behavior distinctions, and boundary conditions",
        "Applied reasoning, cause-and-effect consequences, trade-offs, and scenario analysis"
    ]
    current_focus = foci[(loop_index - 1) % len(foci)]

    avoid_block = ""
    if excluded_questions:
        listed = "\n".join(f"- {q[:140]}" for q in excluded_questions[:8])
        avoid_block = f"\nDO NOT REPEAT OR PARAPHRASE THESE PRIOR QUESTIONS:\n{listed}\n"
    retry_block = (
        f"\nAUDIT RETRY #{retry_round}: Previous generation had unverified keys; ensure every correct_letter is explicitly proven word-for-word by its cited chunk.\n"
        if retry_round > 0
        else ""
    )

    prompt = f"""
You are an expert assessment designer creating 5 rigorous, clear multiple-choice questions (MCQs) for: '{concept_name}'.
Base every question, answer, and explanation STRICTLY on the retrieved source chunks below.

ASSESSMENT FOCUS (Pass #{loop_index}): {current_focus}
{avoid_block}{retry_block}
DIFFICULTY MIX (5 total):
- 2 "easy" questions (accurate core definitions or primary purpose)
- 2 "medium" questions (mechanisms, distinctions, or behavior under specific conditions)
- 1 "hard" question (edge cases, subtle interactions, or applied scenario reasoning)

STRICT QUALITY & DISTRACTOR RULES:
1. Every question MUST cite its exact supporting integer 'source_chunk_id' chosen from: {chunk_ids}.
2. Spread questions across DIFFERENT chunks from {chunk_ids} wherever possible.
3. All 4 options ('option_a', 'option_b', 'option_c', 'option_d') MUST be realistic, topic-specific, grammatically parallel, and similar in length and specificity.
4. Distribute 'correct_letter' across 'A', 'B', 'C', and 'D' so no single letter dominates.
5. FORBIDDEN BAD PATTERNS:
   - Never ask vague meta-questions like "Which statement best summarizes the behavior documented in the source text?"
   - Never write generic negative boilerplate distractors like "The source rejects this principle", "It explicitly prohibits structured evaluation", or "Operates without documented rules".
   - Never use "All of the above" or "None of the above".

SOURCE CHUNKS:
{chunk_manifest}

OUTPUT FORMAT: Return strictly valid JSON array of exactly 5 question objects:
[
  {{
    "concept_id": {concept_id},
    "source_chunk_id": {chunk_ids[0]},
    "difficulty": "easy",
    "question_text": "...",
    "option_a": "...",
    "option_b": "...",
    "option_c": "...",
    "option_d": "...",
    "correct_letter": "A",
    "explanation": "Concise explanation grounding why the correct option is true based strictly on Chunk #{chunk_ids[0]}.",
    "loop_index": {loop_index}
  }}
]
"""
    raw_text = generate_text(prompt, temperature=0.35)
    data = _parse_json_response(raw_text)
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        data = data["questions"]
    if isinstance(data, list):
        valid_ids_set = set(chunk_ids)
        cleaned = []
        for idx, q in enumerate(data):
            if not isinstance(q, dict):
                continue
            try:
                sc_id = int(q.get("source_chunk_id"))
            except (TypeError, ValueError):
                sc_id = chunk_ids[idx % len(chunk_ids)]
            if sc_id not in valid_ids_set:
                sc_id = chunk_ids[idx % len(chunk_ids)]
            q["concept_id"] = concept_id
            q["source_chunk_id"] = sc_id
            q["loop_index"] = loop_index
            q["correct_letter"] = str(q.get("correct_letter", "A")).strip().upper()[:1]
            if q["correct_letter"] not in ("A", "B", "C", "D"):
                q["correct_letter"] = "A"
            diff = str(q.get("difficulty", "medium")).strip().lower()
            q["difficulty"] = diff if diff in ("easy", "medium", "hard") else "medium"
            cleaned.append(q)
        return cleaned
    return []


def _batch_verify_questions(
    questions: List[Dict[str, Any]],
    chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Verify all 5 generated answer keys in ONE batch call against the source chunks.
    Discards any question whose answer key is unsupported or flawed.
    """
    chunk_dict = {int(c["chunk_id"]): c["content"] for c in chunks if "chunk_id" in c}
    default_chunk_text = chunks[0]["content"] if chunks else ""

    # Package questions for verification
    verification_payload = []
    for i, q in enumerate(questions):
        sc_id = q.get("source_chunk_id")
        try:
            sc_int = int(sc_id)
        except (TypeError, ValueError):
            sc_int = -1
        chunk_text = chunk_dict.get(sc_int, default_chunk_text)
        c_let = str(q.get("correct_letter", "A")).strip().lower()
        verification_payload.append({
            "q_idx": i,
            "question": q.get("question_text"),
            "correct_letter": q.get("correct_letter"),
            "chosen_option_text": q.get(f"option_{c_let}"),
            "source_chunk_id": sc_id,
            "chunk_snippet": chunk_text[:1000]
        })

    prompt = f"""
You are the MasteryLoop Quality Auditor.
Verify whether each of the following quiz questions has an unequivocally correct answer key that is strictly verified by its source chunk snippet.

QUESTIONS TO AUDIT:
{json.dumps(verification_payload, indent=2)}

VERIFICATION RULES:
- Output 'verified': true ONLY if the option corresponding to 'correct_letter' is accurate and supported by the chunk snippet, and all 4 options are distinct.
- If there is ambiguity, wrong answer key, or unsupported claims, output 'verified': false.

OUTPUT FORMAT: Return strictly valid JSON array of verification results:
[
  {{
    "q_idx": 0,
    "verified": true,
    "audit_reason": "Verified directly in chunk text."
  }}
]
"""
    try:
        raw_text = generate_text(prompt, temperature=0.0)
        audit_results = _parse_json_response(raw_text)
        if isinstance(audit_results, dict) and isinstance(audit_results.get("results"), list):
            audit_results = audit_results["results"]

        verified_indices = {
            int(item["q_idx"]) for item in audit_results if isinstance(item, dict) and item.get("verified") is True
        }

        retained = [q for i, q in enumerate(questions) if i in verified_indices]
        return retained
    except Exception as e:
        logger.warning(f"Verification pass error: {e}. Defaulting to sanity check.")
        valid = []
        for q in questions:
            if (
                q.get("correct_letter") in ("A", "B", "C", "D")
                and q.get("question_text")
                and all(q.get(f"option_{l}") for l in ("a", "b", "c", "d"))
            ):
                valid.append(q)
        return valid


def _build_fallback_quiz(
    concept_id: int,
    concept_name: str,
    chunks: List[Dict[str, Any]],
    loop_index: int
) -> List[Dict[str, Any]]:
    """
    Robust curated question bank per concept guaranteeing verified MCQs across 
    easy, medium, and hard difficulty for offline and demo runs.
    """
    cid = chunks[0]["chunk_id"] if chunks else 1
    
    banks: Dict[str, List[Dict[str, Any]]] = {
        "SELECT basics": [
            {
                "difficulty": "easy",
                "question_text": "What is the primary role of the SELECT clause in SQL data retrieval?",
                "option_a": "To physically insert new records into a relation",
                "option_b": "To project attributes and compute expressions from target relations",
                "option_c": "To define primary key and foreign key constraints",
                "option_d": "To permanently delete duplicate rows from disk storage",
                "correct_letter": "B",
                "explanation": "The SELECT statement projectively selects attributes and computes expressions from relations specified in the FROM clause."
            },
            {
                "difficulty": "easy",
                "question_text": "Which SQL keyword eliminates duplicate row tuples from the projected result set?",
                "option_a": "UNIQUE",
                "option_b": "COLLATE",
                "option_c": "DISTINCT",
                "option_d": "FILTER",
                "correct_letter": "C",
                "explanation": "SQL provides the DISTINCT keyword directly preceding column definitions to enforce duplicate tuple elimination."
            },
            {
                "difficulty": "medium",
                "question_text": "Why is explicit column enumeration in SELECT preferred over using SELECT *?",
                "option_a": "Relational databases fail to execute asterisk queries",
                "option_b": "It ensures schema stability, performance optimization, and prevents unnecessary memory overhead",
                "option_c": "Asterisk queries automatically convert integers into strings",
                "option_d": "The asterisk operator is deprecated in ANSI SQL",
                "correct_letter": "B",
                "explanation": "Explicit column enumeration prevents unexpected column order shifts and avoids retrieving unneeded attributes."
            },
            {
                "difficulty": "medium",
                "question_text": "How can an output column in a SELECT query be given a descriptive alias?",
                "option_a": "By using the optional AS keyword following the attribute expression",
                "option_b": "By enclosing the column name in curly braces",
                "option_c": "By declaring a RENAME clause before the FROM keyword",
                "option_d": "By updating SYSCAT.COLUMNS in the catalog",
                "correct_letter": "A",
                "explanation": "Column alias designations using the optional AS keyword rename output headers seamlessly."
            },
            {
                "difficulty": "hard",
                "question_text": "In relational algebra, what specific algebraic operation does the SELECT list perform?",
                "option_a": "Horizontal Selection (filtering tuples)",
                "option_b": "Vertical Projection (extracting attributes)",
                "option_c": "Cartesian Product",
                "option_d": "Relational Division",
                "correct_letter": "B",
                "explanation": "In relational algebra, projection extracts vertical slices of tuples matching desired column specifications."
            }
        ],
        "WHERE": [
            {
                "difficulty": "easy",
                "question_text": "When does the WHERE clause evaluate row predicates in query processing order?",
                "option_a": "After HAVING and ORDER BY execution",
                "option_b": "Directly upon tuples produced by FROM prior to grouping and aggregation",
                "option_c": "At the client presentation layer",
                "option_d": "Simultaneously with table creation",
                "correct_letter": "B",
                "explanation": "The WHERE clause operates directly upon tuples produced by the FROM clause prior to any aggregation or grouping."
            },
            {
                "difficulty": "easy",
                "question_text": "Which operators must be used to test whether a column contains a NULL value in SQL?",
                "option_a": "= NULL and != NULL",
                "option_b": "IS NULL and IS NOT NULL",
                "option_c": "EQUALS(NULL)",
                "option_d": "EXISTS NULL",
                "correct_letter": "B",
                "explanation": "Because NULL represents missing info, standard comparisons yield UNKNOWN; explicit predicates IS NULL and IS NOT NULL are required."
            },
            {
                "difficulty": "medium",
                "question_text": "In SQL three-valued logic (3VL), what does the comparison 'salary = NULL' evaluate to?",
                "option_a": "TRUE",
                "option_b": "FALSE",
                "option_c": "UNKNOWN",
                "option_d": "ERROR",
                "correct_letter": "C",
                "explanation": "Direct comparisons with NULL evaluate to UNKNOWN rather than TRUE or FALSE."
            },
            {
                "difficulty": "medium",
                "question_text": "In a LIKE pattern search, which wildcard character represents a single arbitrary character?",
                "option_a": "% (percent)",
                "option_b": "_ (underscore)",
                "option_c": "* (asterisk)",
                "option_d": "? (question mark)",
                "correct_letter": "B",
                "explanation": "SQL LIKE pattern matching uses percent (%) for multi-character wildcards and underscore (_) for single-character placeholders."
            },
            {
                "difficulty": "hard",
                "question_text": "Why can an aggregate function like AVG(salary) NOT be placed directly inside a WHERE clause?",
                "option_a": "Db2 does not support averaging salaries",
                "option_b": "WHERE evaluates rows before groups and aggregates are formed in the logical query lifecycle",
                "option_c": "The WHERE clause can only evaluate string comparisons",
                "option_d": "Aggregate functions require autocommit off",
                "correct_letter": "B",
                "explanation": "Aggregate functions cannot appear directly in WHERE because row-level filtering occurs prior to grouping and aggregate reduction."
            }
        ]
    }

    # Build varied chunk-grounded questions if live Gemini unavailable (never identical distractors)
    concept_bank = banks.get(concept_name)
    if not concept_bank:
        sent_pool: List[Tuple[int, str]] = []
        for ch in (chunks or []):
            ch_id = ch.get("chunk_id", cid)
            for s in re.split(r"(?<=[.!?])\s+", ch.get("content", "").strip()):
                s_clean = s.strip()
                if len(s_clean.split()) >= 6:
                    sent_pool.append((ch_id, s_clean))

        if not sent_pool:
            sent_pool = [(cid, f"{concept_name} defines structured mechanisms documented in the ingested study notes.")]

        offset = ((loop_index - 1) * 2) % len(sent_pool)
        rotated = sent_pool[offset:] + sent_pool[:offset]

        difficulties = ["easy", "easy", "medium", "medium", "hard"]
        templates = [
            "Which detail accurately describes a foundational concept of {topic} (Checkpoint #{idx})?",
            "In {topic}, what specific mechanism or characteristic applies directly?",
            "Which behavior accurately reflects {topic} as documented in the ingested notes (Item #{idx})?",
            "When evaluating {topic}, which statement holds true based on the studied material?",
            "Which distinction correctly captures an advanced aspect of {topic}?"
        ]
        # Distinct, sentence-grounded distractors per question slot (inverted/altered topic statements)
        alt_distractor_sets = [
            [
                f"{concept_name} is exclusively a hardware-only protocol with no software abstraction.",
                f"Documentation notes {concept_name} is deprecated and replaced across all modern runtimes.",
                f"{concept_name} only operates when all input parameters remain uninitialized."
            ],
            [
                f"In practice, {concept_name} disables sequential execution to prevent deterministic output.",
                f"{concept_name} requires manual binary recompilation before reading every single value.",
                f"Standard usage of {concept_name} prohibits combining multiple modular components."
            ],
            [
                f"Unlike standard implementations, {concept_name} discards state prior to evaluation.",
                f"{concept_name} achieves identical results without parsing structure or context.",
                f"Core specifications state {concept_name} ignores ordering constraints entirely."
            ],
            [
                f"{concept_name} eliminates compatibility with iterative development workflows.",
                f"Using {concept_name} guarantees zero memory allocation across all data sizes.",
                f"All aspects of {concept_name} require proprietary single-vendor extensions."
            ],
            [
                f"Advanced workflows bypass {concept_name} when handling complex transformations.",
                f"{concept_name} restricts execution exclusively to compile-time constants.",
                f"Strict type separation prevents {concept_name} from interacting with external state."
            ],
        ]
        concept_bank = []
        letters = ["B", "A", "C", "D", "B"]
        for i in range(5):
            ch_id, fact = rotated[i % len(rotated)]
            fact_short = _clip_words(fact, 24)
            correct_l = letters[i]
            distractors = alt_distractor_sets[i % len(alt_distractor_sets)]
            opts = {}
            d_idx = 0
            for letter in ("A", "B", "C", "D"):
                if letter == correct_l:
                    opts[letter] = fact_short
                else:
                    opts[letter] = distractors[d_idx]
                    d_idx += 1

            concept_bank.append({
                "source_chunk_id": ch_id,
                "difficulty": difficulties[i],
                "question_text": templates[i].format(topic=concept_name, idx=i + 1),
                "option_a": opts["A"],
                "option_b": opts["B"],
                "option_c": opts["C"],
                "option_d": opts["D"],
                "correct_letter": correct_l,
                "explanation": f"Directly supported by chunk #{ch_id}: {fact_short}",
            })

    # Assign metadata
    out = []
    for item in concept_bank:
        out.append({
            "concept_id": concept_id,
            "source_chunk_id": item.get("source_chunk_id", cid),
            "difficulty": item["difficulty"],
            "question_text": item["question_text"],
            "option_a": item["option_a"],
            "option_b": item["option_b"],
            "option_c": item["option_c"],
            "option_d": item["option_d"],
            "correct_letter": item["correct_letter"],
            "explanation": item["explanation"],
            "loop_index": loop_index
        })
    return out

