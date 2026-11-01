-- ========================================================================
-- InternScrap Analytical Queries for IBM Db2 Developer Extension
-- Run these queries directly inside the IBM Db2 Developer Extension
-- ========================================================================

-- Query 1: Find Internships Matching User Skills (e.g., Python + SQL)
-- Demonstrates multi-table joins, aggregation, and HAVING filter
SELECT 
    i.ID,
    i.TITLE,
    c.NAME AS COMPANY,
    COUNT(s.ID) AS MATCHING_SKILLS_COUNT,
    VARCHAR_FORMAT(i.DEADLINE, 'YYYY-MM-DD') AS DEADLINE_FORMATTED,
    i.APPLY_URL
FROM INTERNSHIPS i
JOIN COMPANIES c ON i.COMPANY_ID = c.ID
JOIN INTERNSHIP_SKILLS isk ON i.ID = isk.INTERNSHIP_ID
JOIN SKILLS s ON isk.SKILL_ID = s.ID
WHERE s.NAME IN ('Python', 'SQL', 'IBM Db2')
  AND i.STATUS = 'ACTIVE'
GROUP BY i.ID, i.TITLE, c.NAME, i.DEADLINE, i.APPLY_URL
HAVING COUNT(s.ID) >= 2
ORDER BY MATCHING_SKILLS_COUNT DESC;

-- Query 2: In-Demand Skills Ranking with Percentage Distribution
SELECT * FROM V_TOP_IN_DEMAND_SKILLS
ORDER BY LISTING_COUNT DESC;

-- Query 3: Urgent Deadlines Expiring in the Next 14 Days
SELECT * FROM V_UPCOMING_DEADLINES
ORDER BY DAYS_REMAINING ASC;

-- Query 4: User Application Funnel Metrics & Conversion Rate
SELECT 
    STAGE,
    TOTAL_COUNT,
    ROUND(CAST(TOTAL_COUNT AS DOUBLE) * 100.0 / 
          NULLIF((SELECT COUNT(*) FROM APPLICATIONS), 0), 1) AS PERCENTAGE_OF_TOTAL
FROM V_APPLICATION_FUNNEL
ORDER BY TOTAL_COUNT DESC;

-- Query 5: Full Application Pipeline Status Detail with Company Metadata
SELECT 
    a.ID AS APPLICATION_ID,
    c.NAME AS COMPANY_NAME,
    i.TITLE AS ROLE_TITLE,
    a.STATUS,
    a.APPLIED_DATE,
    a.FOLLOW_UP_DATE,
    a.NOTES
FROM APPLICATIONS a
JOIN INTERNSHIPS i ON a.INTERNSHIP_ID = i.ID
JOIN COMPANIES c ON i.COMPANY_ID = c.ID
ORDER BY a.UPDATED_AT DESC;
