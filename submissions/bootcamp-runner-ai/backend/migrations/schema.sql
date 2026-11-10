CREATE TABLE learners (
    learner_id VARCHAR(128) NOT NULL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(320) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE TABLE quiz_attempts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id VARCHAR(128) NOT NULL REFERENCES learners(learner_id),
    topic VARCHAR(200) NOT NULL,
    score DECIMAL(5,2) NOT NULL CHECK (score BETWEEN 0 AND 100),
    difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    questions_count INTEGER NOT NULL CHECK (questions_count > 0),
    attempted_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE INDEX idx_attempts_learner_topic ON quiz_attempts(learner_id, topic, attempted_at);
CREATE TABLE learning_profiles (
    learner_id VARCHAR(128) NOT NULL PRIMARY KEY REFERENCES learners(learner_id),
    strengths VARCHAR(4000), weaknesses VARCHAR(4000),
    preferred_difficulty VARCHAR(10) NOT NULL DEFAULT 'medium' CHECK (preferred_difficulty IN ('easy','medium','hard')),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE TABLE ai_recommendations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learner_id VARCHAR(128) NOT NULL REFERENCES learners(learner_id),
    topic VARCHAR(200) NOT NULL, recommendation VARCHAR(4000) NOT NULL,
    difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    source VARCHAR(40) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
CREATE INDEX idx_recommendations_learner ON ai_recommendations(learner_id, created_at);
