-- ====================================================================
-- MasteryLoop (mastree) IBM Db2 LUW Relational Schema DDL
-- Dialect: IBM Db2 LUW (No LIMIT, No IF NOT EXISTS, FETCH FIRST n ROWS ONLY)
-- ====================================================================

-- 1. Students Table
CREATE TABLE students (
    student_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Concepts Table
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

-- 3. Concept Prerequisites Graph Table
CREATE TABLE concept_prereqs (
    concept_id INTEGER NOT NULL,
    prereq_id INTEGER NOT NULL,
    PRIMARY KEY (concept_id, prereq_id),
    CONSTRAINT fk_cp_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE,
    CONSTRAINT fk_cp_prereq FOREIGN KEY (prereq_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
);

-- 4. Documents Table (Seed, Wikipedia, and Student-Uploaded Notes)
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

-- 5. Text Chunks & Vector Embeddings Table
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

-- 6. Interactive Lessons Table
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

-- ====================================================================
-- Foreign Key and Performance Optimization Indexes
-- ====================================================================
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

-- ====================================================================
-- Analytics View: Student Progress Matrix
-- ====================================================================
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
