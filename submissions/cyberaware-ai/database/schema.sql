-- CyberAware AI Database Schema

-- 1. Cybersecurity Lessons
CREATE TABLE LESSONS (
    LESSON_ID INTEGER
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,
    TITLE VARCHAR(200) NOT NULL,
    CATEGORY VARCHAR(100) NOT NULL,
    LESSON_CONTENT CLOB(10K) NOT NULL,
    CREATED_AT TIMESTAMP DEFAULT CURRENT TIMESTAMP
);

-- 2. Quiz Questions
CREATE TABLE QUIZ_QUESTIONS (
    QUESTION_ID INTEGER
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,
    QUESTION_TEXT VARCHAR(1000) NOT NULL,
    OPTION_A VARCHAR(500) NOT NULL,
    OPTION_B VARCHAR(500) NOT NULL,
    OPTION_C VARCHAR(500) NOT NULL,
    CORRECT_OPTION CHAR(1) NOT NULL,
    EXPLANATION VARCHAR(1000),
    CONSTRAINT VALID_OPTION
        CHECK (CORRECT_OPTION IN ('A', 'B', 'C'))
);

-- 3. Learning Progress
CREATE TABLE LEARNING_PROGRESS (
    PROGRESS_ID INTEGER
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,
    LEARNER_NAME VARCHAR(100),
    LESSON_ID INTEGER NOT NULL,
    COMPLETION_STATUS VARCHAR(20) DEFAULT 'STARTED',
    COMPLETED_AT TIMESTAMP,
    CONSTRAINT FK_LESSON
        FOREIGN KEY (LESSON_ID)
        REFERENCES LESSONS(LESSON_ID)
);

-- Sample cybersecurity lessons
INSERT INTO LESSONS
(TITLE, CATEGORY, LESSON_CONTENT)
VALUES
(
    'Understanding Phishing',
    'Phishing',
    'Phishing is a cyberattack where criminals use fake messages or websites to steal personal information. Always verify links before clicking.'
);

INSERT INTO LESSONS
(TITLE, CATEGORY, LESSON_CONTENT)
VALUES
(
    'Mobile Money Security',
    'Mobile Money',
    'Never share your mobile money PIN or verification code. Contact your provider through official channels if you suspect fraud.'
);

INSERT INTO LESSONS
(TITLE, CATEGORY, LESSON_CONTENT)
VALUES
(
    'Creating Strong Passwords',
    'Password Security',
    'Use long, unique passwords for different accounts. Enable two-factor authentication whenever possible.'
);

-- Sample quiz questions
INSERT INTO QUIZ_QUESTIONS
(QUESTION_TEXT, OPTION_A, OPTION_B, OPTION_C,
 CORRECT_OPTION, EXPLANATION)
VALUES
(
    'Someone asks you for your mobile money PIN. What should you do?',
    'Share it',
    'Refuse to share it',
    'Send it by SMS',
    'B',
    'Never share your mobile money PIN with anyone.'
);

INSERT INTO QUIZ_QUESTIONS
(QUESTION_TEXT, OPTION_A, OPTION_B, OPTION_C,
 CORRECT_OPTION, EXPLANATION)
VALUES
(
    'What should you do before clicking an unfamiliar link?',
    'Click immediately',
    'Verify the link source',
    'Share it with friends',
    'B',
    'Always verify suspicious links before opening them.'
);
