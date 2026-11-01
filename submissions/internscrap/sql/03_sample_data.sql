-- ========================================================================
-- InternScrap Seed Data for IBM Db2
-- Populates initial companies, skills, postings, and tracked applications
-- ========================================================================

-- Insert Companies
INSERT INTO COMPANIES (NAME, WEBSITE, LOCATION, INDUSTRY, TIER) VALUES
('IBM', 'https://www.ibm.com', 'Armonk, NY', 'Cloud & AI Enterprise', 'Enterprise'),
('Red Hat', 'https://www.redhat.com', 'Raleigh, NC', 'Open Source Software', 'Enterprise'),
('Google', 'https://careers.google.com', 'Mountain View, CA', 'Internet & Software', 'FAANG'),
('Microsoft', 'https://careers.microsoft.com', 'Redmond, WA', 'Enterprise Cloud & OS', 'FAANG'),
('Databricks', 'https://www.databricks.com', 'San Francisco, CA', 'Data & AI Platform', 'Enterprise'),
('Stripe', 'https://stripe.com', 'San Francisco, CA', 'Fintech & Payments', 'Enterprise'),
('Scale AI', 'https://scale.com', 'San Francisco, CA', 'AI Data Infrastructure', 'Startup');

-- Insert Skills
INSERT INTO SKILLS (NAME, CATEGORY) VALUES
('Python', 'Backend/AI'),
('IBM Db2', 'Database'),
('SQL', 'Database'),
('Docker', 'DevOps'),
('React', 'Frontend'),
('TypeScript', 'Frontend'),
('C++', 'Systems'),
('Java', 'Backend'),
('Machine Learning', 'AI'),
('Data Engineering', 'Data');

-- Insert Sample Internships
-- 1. IBM Software Engineer Intern (Db2 & Data Platforms)
INSERT INTO INTERNSHIPS (TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX, CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, POSTED_DATE, DEADLINE, STATUS) VALUES
('Software Development Intern - Db2 Engine', 1, 'San Jose, CA', 0, 48.00, 62.00, 'USD', 'https://ibm.biz/intern-db2-2025', 'TechX', 'IBM-DB2-001', CURRENT DATE - 5 DAYS, CURRENT DATE + 30 DAYS, 'ACTIVE');

-- 2. Red Hat OpenShift Intern
INSERT INTO INTERNSHIPS (TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX, CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, POSTED_DATE, DEADLINE, STATUS) VALUES
('Open Source Cloud Platform Intern', 2, 'Remote', 1, 40.00, 52.00, 'USD', 'https://redhat.com/careers/intern', 'GitHub', 'RH-OS-002', CURRENT DATE - 3 DAYS, CURRENT DATE + 12 DAYS, 'ACTIVE');

-- 3. Google Software Engineering Summer Intern
INSERT INTO INTERNSHIPS (TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX, CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, POSTED_DATE, DEADLINE, STATUS) VALUES
('Software Engineering Intern - Summer', 3, 'Sunnyvale, CA', 0, 55.00, 65.00, 'USD', 'https://careers.google.com/jobs/results/intern', 'Direct', 'GOOG-SWE-003', CURRENT DATE - 10 DAYS, CURRENT DATE + 8 DAYS, 'ACTIVE');

-- 4. Databricks Data Engineering Intern
INSERT INTO INTERNSHIPS (TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX, CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, POSTED_DATE, DEADLINE, STATUS) VALUES
('Data Systems & Spark Intern', 5, 'Remote', 1, 58.00, 70.00, 'USD', 'https://databricks.com/intern-swe', 'RemoteOK', 'DBX-DATA-004', CURRENT DATE - 2 DAYS, CURRENT DATE + 20 DAYS, 'ACTIVE');

-- 5. Scale AI Machine Learning Intern
INSERT INTO INTERNSHIPS (TITLE, COMPANY_ID, LOCATION, IS_REMOTE, STIPEND_MIN, STIPEND_MAX, CURRENCY, APPLY_URL, SOURCE, EXTERNAL_ID, POSTED_DATE, DEADLINE, STATUS) VALUES
('Machine Learning Research Intern', 7, 'San Francisco, CA', 0, 50.00, 65.00, 'USD', 'https://scale.com/careers/ml-intern', 'GitHub', 'SCALE-ML-005', CURRENT DATE - 1 DAYS, CURRENT DATE + 25 DAYS, 'ACTIVE');

-- Link Skills to Internships
-- IBM Db2 Intern -> Python, IBM Db2, SQL, C++
INSERT INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) VALUES
(1, 1), (1, 2), (1, 3), (1, 7);

-- Red Hat Intern -> Python, Docker, Go/Systems
INSERT INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) VALUES
(2, 1), (2, 4);

-- Google Intern -> C++, Python, SQL
INSERT INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) VALUES
(3, 1), (3, 3), (3, 7);

-- Databricks Intern -> Python, SQL, Data Engineering
INSERT INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) VALUES
(4, 1), (4, 3), (4, 10);

-- Scale AI Intern -> Python, Machine Learning
INSERT INTO INTERNSHIP_SKILLS (INTERNSHIP_ID, SKILL_ID) VALUES
(5, 1), (5, 9);

-- Insert Sample Tracked Applications
INSERT INTO APPLICATIONS (INTERNSHIP_ID, USER_IDENTIFIER, STATUS, APPLIED_DATE, FOLLOW_UP_DATE, NOTES) VALUES
(1, 'local_user', 'APPLIED', CURRENT DATE - 2 DAYS, CURRENT DATE + 7 DAYS, 'Applied with tailored resume highlighting IBM Db2 & C++ contributions.'),
(3, 'local_user', 'ONLINE_ASSESSMENT', CURRENT DATE - 4 DAYS, CURRENT DATE + 2 DAYS, 'Received OA invitation. Solved graphs and dynamic programming questions.');
