# MasteryLoop System Architecture

## Overview
**MasteryLoop** (project slug: `mastree`) is an open-source adaptive tutor implementing Benjamin Bloom's mastery learning pedagogy. The system dynamically adapts instructional content and assessment rigor for students learning Structured Query Language (SQL) and custom uploaded or Wikipedia-researched topics.

The architecture unites a modern **FastAPI** REST backend serving a responsive vanilla HTML5/CSS/JS frontend at `/`, an intelligent **AI / LLM Orchestration Layer** running on Google Gemini via the `google-genai` SDK, and a deep, transactional **IBM Db2 LUW** relational database layer. Background knowledge ingestion executes asynchronously in dedicated worker threads monitored via an in-memory job registry. When students struggle to advance past concept mastery gates, the engine executes an IBM Db2 **Recursive Common Table Expression (CTE)** over a directed acyclic graph (DAG) of prerequisite dependencies to identify the deepest unmastered root-cause concept, automatically routing the student through targeted multi-style remediation in their chosen format.

---

## The 8-Step System Lifecycle

```mermaid
flowchart TD
    S1[1. Student Login via Username] --> S2[2. Choose Topic: Search Wikipedia / Attach Notes / Course SQL]
    S2 --> S3[3. RAG Ingestion into Db2: Chunk ~120 words + Batch Embeddings]
    S3 --> S4[4. Choose Format: Board or Video Lecture]
    S4 --> S5[5. Grounded AI Teaching citing Chunk IDs]
    S5 --> S6[6. Assessment: 5 MCQs from Same Chunks]
    S6 --> S7[7. Gate Decision: Mastered -> Next Topic | Not Mastered -> Db2 Recursive CTE Diagnosis]
    S7 --> S8[8. End-to-End Persistence in IBM Db2 LUW]
    S7 -. Remediation Cycle (Max 3 Loops) .-> S4
```

---

## Three Input Modes & Ingestion Architecture

MasteryLoop supports three distinct knowledge acquisition channels:
1. **Search Any Topic (Wikipedia):**
   - Live query via MediaWiki API (`action=query`, `list=search`) displaying top 3 candidate articles.
   - Text extract fetched via `prop=extracts`, `explaintext=1`, capped at ~5000 words.
   - Attributed as `Source: Wikipedia - <Title>` with canonical URL stored.
2. **Attach My Notes (Upload / Paste):**
   - Supports `.txt`, `.md`, and `.pdf` files (extracted via `pypdf`) alongside raw pasted text.
   - Requires a Topic Name and allows optional prerequisite linking to existing topics.
3. **Course (SQL Curriculum):**
   - 9 Curated concepts pre-seeded in Db2 with a directed acyclic prerequisite dependency structure.

All ingested topics are partitioned into ~120-word chunks, batch-embedded, and persisted in Db2 with relational associations to `concepts`, `documents`, and `chunks`.

---

## Dual Teaching Formats

- **Board (Step-by-Step):** Progressive card deck revealing educational concepts step-by-step with explicit citation badges (`#chunk_id`).
- **Video Lecture:**
  > **Note on Implementation:** *Video lecture = in-browser narrated lecture player using the Web Speech API, not an exported MP4.*
  - Self-contained 16:9 dark classroom screen with zero CDN or external network dependencies.
  - Generates 5–6 scenes in one Gemini call, verified strictly against Db2 chunks.
  - Staggered bullet reveals synchronized with browser voice synthesis (`window.speechSynthesis`), glowing key-term badges, and animated process flow diagrams (`[Step 1] ➔ [Step 2] ➔ [Step 3]`).
  - Speed adjustments (0.8x, 1.0x, 1.25x), Play/Pause, Prev/Next, Subtitles toggle, and Mute.

---

## IBM Db2 LUW Schema & Storage Design

The application adheres strictly to the IBM Db2 LUW relational dialect:

```sql
-- 1. Students Table
CREATE TABLE students (
    student_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Concepts Table (Supports Seed and Custom User/Wikipedia Topics)
CREATE TABLE concepts (
    concept_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description VARCHAR(500),
    seq_order INTEGER NOT NULL,
    is_custom SMALLINT DEFAULT 0,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_concept_creator FOREIGN KEY (created_by) REFERENCES students(student_id) ON DELETE SET NULL
);

-- 3. Concept Prerequisites Graph Table (DAG Structure)
CREATE TABLE concept_prereqs (
    concept_id INTEGER NOT NULL,
    prereq_id INTEGER NOT NULL,
    PRIMARY KEY (concept_id, prereq_id),
    CONSTRAINT fk_cp_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_cp_prereq FOREIGN KEY (prereq_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 4. Documents Table (Seed, Wikipedia, Upload, Paste)
CREATE TABLE documents (
    doc_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    concept_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    source VARCHAR(50) NOT NULL,
    source_type VARCHAR(20) DEFAULT 'seed',
    source_url VARCHAR(500),
    content CLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_doc_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 5. Text Chunks & Vector Embeddings Table (RAG Knowledge Base)
CREATE TABLE chunks (
    chunk_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    content CLOB NOT NULL,
    embedding CLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chunk_doc FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE,
    CONSTRAINT fk_chunk_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 6. Interactive Lessons Table (Board steps & Video lecture scenes)
CREATE TABLE lessons (
    lesson_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    loop_count INTEGER DEFAULT 1,
    style VARCHAR(50) DEFAULT 'step-by-step',
    steps_json CLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_les_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_les_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 7. Quiz Questions Pool Table
CREATE TABLE questions (
    question_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    concept_id INTEGER NOT NULL,
    source_chunk_id INTEGER,
    question_text CLOB NOT NULL,
    option_a VARCHAR(500) NOT NULL,
    option_b VARCHAR(500) NOT NULL,
    option_c VARCHAR(500) NOT NULL,
    option_d VARCHAR(500) NOT NULL,
    correct_letter VARCHAR(2) NOT NULL,
    explanation CLOB NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    loop_index INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_q_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_q_chunk FOREIGN KEY (source_chunk_id) REFERENCES chunks(chunk_id) ON DELETE SET NULL
);

-- 8. Student Quiz Attempts Table
CREATE TABLE attempts (
    attempt_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_letter VARCHAR(2) NOT NULL,
    is_correct SMALLINT NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_att_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_question FOREIGN KEY (question_id) REFERENCES questions(question_id) ON DELETE CASCADE
);

-- 9. Student Concept Current Mastery Table
CREATE TABLE mastery (
    mastery_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    mastery_score DOUBLE NOT NULL,
    attempt_count INTEGER NOT NULL,
    distinct_difficulties INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stud_concept UNIQUE (student_id, concept_id),
    CONSTRAINT fk_mas_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_mas_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 10. Append-Only Mastery History Table
CREATE TABLE mastery_history (
    history_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    mastery_score DOUBLE NOT NULL,
    attempt_id INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mh_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_mh_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_mh_attempt FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id) ON DELETE SET NULL
);

-- 11. Loop Events & Gate Decisions Log Table
CREATE TABLE loop_events (
    event_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    gate_passed SMALLINT NOT NULL,
    mastery_score DOUBLE NOT NULL,
    attempt_count INTEGER NOT NULL,
    distinct_difficulties INTEGER NOT NULL,
    root_cause_concept_id INTEGER,
    reason CLOB NOT NULL,
    sql_query CLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_le_student FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    CONSTRAINT fk_le_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_le_rc FOREIGN KEY (root_cause_concept_id) REFERENCES concepts(concept_id) ON DELETE SET NULL
);

-- 12. Persistent LLM & Embedding Cache Table
CREATE TABLE llm_cache (
    cache_key VARCHAR(64) NOT NULL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    prompt_text CLOB NOT NULL,
    response_text CLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Optional Generated Lesson Illustrations Table
CREATE TABLE lesson_images (
    image_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lesson_id INTEGER,
    concept_id INTEGER NOT NULL,
    image_data BLOB(5M) NOT NULL,
    mime_type VARCHAR(50) DEFAULT 'image/png',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_lim_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- Indexes for Foreign Keys & Composite Lookups
CREATE INDEX idx_cp_prereq ON concept_prereqs (prereq_id);
CREATE INDEX idx_doc_concept ON documents (concept_id);
CREATE INDEX idx_chk_doc ON chunks (doc_id);
CREATE INDEX idx_chk_concept ON chunks (concept_id);
CREATE INDEX idx_les_sc ON lessons (student_id, concept_id);
CREATE INDEX idx_q_concept ON questions (concept_id);
CREATE INDEX idx_q_chunk ON questions (source_chunk_id);
CREATE INDEX idx_att_sc ON attempts (student_id, concept_id);
CREATE INDEX idx_att_q ON attempts (question_id);
CREATE INDEX idx_mas_sc ON mastery (student_id, concept_id);
CREATE INDEX idx_mh_sc ON mastery_history (student_id, concept_id);
CREATE INDEX idx_le_sc ON loop_events (student_id, concept_id);

-- Analytics View: Student Progress Matrix
CREATE VIEW v_student_progress AS
SELECT 
    s.student_id,
    s.username,
    c.concept_id,
    c.name AS concept_name,
    c.seq_order,
    COALESCE(m.mastery_score, 0.0) AS current_mastery,
    COALESCE(m.attempt_count, 0) AS total_attempts,
    COALESCE(m.distinct_difficulties, 0) AS distinct_difficulties,
    CASE 
        WHEN COALESCE(m.mastery_score, 0.0) >= 0.8 
             AND COALESCE(m.attempt_count, 0) >= 5 
             AND COALESCE(m.distinct_difficulties, 0) >= 2 THEN 1 
        ELSE 0 
    END AS is_mastered,
    m.updated_at AS last_assessed_at
FROM students s
CROSS JOIN concepts c
LEFT JOIN mastery m ON s.student_id = m.student_id AND c.concept_id = m.concept_id;
```

---

## Recursive CTE Prerequisite Root-Cause Query

When a student fails the mastery gate, Db2 LUW traverses ancestor prerequisites to locate the weakest unmastered concept:

```sql
WITH prereq_tree (concept_id, prereq_id, depth) AS (
    -- Anchor member: Direct prerequisites of the target concept (depth = 1)
    SELECT cp.concept_id, cp.prereq_id, 1
    FROM concept_prereqs cp
    WHERE cp.concept_id = ?
    UNION ALL
    -- Recursive member: Ancestor prerequisites (depth + 1)
    -- Uses comma-join syntax with WHERE to strictly comply with Db2 rule SQL0345N
    SELECT pt.concept_id, cp2.prereq_id, pt.depth + 1
    FROM prereq_tree pt, concept_prereqs cp2
    WHERE pt.prereq_id = cp2.concept_id
)
SELECT c.concept_id, c.name, c.seq_order,
       MIN(pt.depth) AS min_depth,
       COALESCE(m.mastery_score, 0.0) AS mastery_score,
       COALESCE(m.attempt_count, 0) AS attempt_count,
       COALESCE(m.distinct_difficulties, 0) AS distinct_difficulties
FROM prereq_tree pt
JOIN concepts c ON pt.prereq_id = c.concept_id
LEFT JOIN mastery m ON m.student_id = ? AND m.concept_id = c.concept_id
GROUP BY c.concept_id, c.name, c.seq_order, m.mastery_score, m.attempt_count, m.distinct_difficulties
ORDER BY mastery_score ASC, min_depth DESC;
```

### How the Diagnostic Engine Works:
1. **Anchor Execution:** Evaluates `cp.concept_id = ?` to seed the queue with direct prerequisites.
2. **Recursive Traversal:** Iterates upward through the directed acyclic graph (DAG) to collect all transitive ancestor dependencies. Db2 LUW dialect rules require omitting the `RECURSIVE` keyword (`WITH name (cols) AS ...`) and using comma-separated join syntax in the recursive member to prevent `SQL0345N`.
3. **Weakest-Link Diagnosis:** Joins the transitive prerequisites with the student's recorded mastery scores (`mastery` table). The results are ranked primarily by `mastery_score ASC` (lowest mastery score first) and secondarily by `min_depth DESC` (deepest unmastered foundation first). The top candidate with mastery $< 0.80$ is flagged as the root cause.
4. **Pedagogical Action:** The tutor dynamically shifts context to re-teach this foundational prerequisite before returning the learner to the original target concept.

---

## Security, Attributions & Secrets Management
- **Author:** Suryakanth ([@Suryakanth25](https://github.com/Suryakanth25)), solo participant.
- All database credentials (`DB2_HOST`, `DB2_PORT`, `DB2_DATABASE`, `DB2_USER`, `DB2_PASSWORD`) and Google Gemini API keys are loaded at runtime from environment variables.
- Parameterized queries (`?` parameter markers) prevent SQL injection across all query execution paths.
- **Wikipedia:** Fetched text is licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **DeepTutor Attribution:** "Inspired by the teach-and-assess idea in DeepTutor (HKUDS/DeepTutor, Apache-2.0). All code in this project was written from scratch. Wikipedia text is CC BY-SA."
