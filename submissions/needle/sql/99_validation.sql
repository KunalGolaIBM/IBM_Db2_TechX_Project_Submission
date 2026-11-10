-- NEEDLE validation queries. Run with the Db2 CLP: db2 connect to VECDB; db2 -tvf sql/99_validation.sql
-- Each section names its owner. Sections never modify data.

-- ===================================================================================================
-- [data] V1  Row counts of the data tables.
-- ===================================================================================================
SELECT 'ADV_RAW' AS T, COUNT(*) AS N FROM NEEDLE.ADV_RAW
UNION ALL SELECT 'ADV_DOC', COUNT(*) FROM NEEDLE.ADV_DOC
UNION ALL SELECT 'ADV_ALIAS', COUNT(*) FROM NEEDLE.ADV_ALIAS
UNION ALL SELECT 'ADV_AFFECTED', COUNT(*) FROM NEEDLE.ADV_AFFECTED;

-- ===================================================================================================
-- [data] V2  JSON_TABLE over the raw OSV JSON in ADV_RAW.
-- Db2 12.1 JSON_TABLE takes the row path 'strict $' only (one output row per JSON document; no
-- '$.a[*]' row paths and no NESTED PATH). That is why 'strict $.a[*]' failed with SQL0104N.
-- Here JSON_TABLE shreds the scalar fields of one advisory and Db2 checks them against ADV_DOC.
-- ===================================================================================================
SELECT VARCHAR(J.ID, 20) AS ID, VARCHAR(J.PUBLISHED, 24) AS PUBLISHED, J.PACKAGES_JSON,
       CASE WHEN D.ADV_ID = J.ID
             AND D.PUBLISHED - MICROSECOND(D.PUBLISHED) MICROSECONDS
                 = TIMESTAMP(SUBSTR(J.PUBLISHED, 1, 10) || ' ' || SUBSTR(J.PUBLISHED, 12, 8))
            THEN 'MATCHES ADV_DOC' ELSE 'MISMATCH' END AS CHECK_RESULT
FROM NEEDLE.ADV_RAW R,
     JSON_TABLE(R.RAW, 'strict $'
                COLUMNS (ID        VARCHAR(64)  PATH '$.id',
                         PUBLISHED VARCHAR(40)  PATH '$.published',
                         MODIFIED  VARCHAR(40)  PATH '$.modified',
                         PACKAGES_JSON VARCHAR(200) FORMAT JSON PATH '$.affected[*].package.name'
                                   WITH UNCONDITIONAL ARRAY WRAPPER)
                ERROR ON ERROR) AS J,
     NEEDLE.ADV_DOC D
WHERE R.ADV_ID = 'GHSA-27px-qpmj-qg38'
  AND D.ADV_ID = R.ADV_ID;

-- ===================================================================================================
-- [data] V3  Reproduce NEEDLE.ADV_AFFECTED for one advisory from ADV_RAW, entirely in SQL.
-- Because JSON_TABLE cannot iterate arrays, a recursive common table expression walks the array
-- subscripts $.affected[i].versions[j] with JSON_VALUE (the path argument may be an expression).
-- strict mode + NULL ON ERROR returns NULL past the end of an array, which ends the recursion.
-- PACKAGE uses the same PEP 503 normalization as the Python loader.
-- Expected: ROWS_FROM_JSON = ROWS_IN_TABLE and both EXCEPT counts = 0.
-- ===================================================================================================
WITH R (ADV_ID, RAW) AS (
       SELECT ADV_ID, RAW FROM NEEDLE.ADV_RAW WHERE ADV_ID = 'GHSA-27px-qpmj-qg38'),
     A (I) AS (
       VALUES 0 UNION ALL SELECT I + 1 FROM A WHERE I < 63),
     PK (ADV_ID, AI, ECOSYSTEM, PACKAGE) AS (
       SELECT R.ADV_ID, A.I,
              JSON_VALUE(R.RAW, 'strict $.affected[' || VARCHAR(A.I) || '].package.ecosystem'
                         RETURNING VARCHAR(32) NULL ON EMPTY NULL ON ERROR),
              JSON_VALUE(R.RAW, 'strict $.affected[' || VARCHAR(A.I) || '].package.name'
                         RETURNING VARCHAR(256) NULL ON EMPTY NULL ON ERROR)
       FROM R, A),
     V (ADV_ID, AI, ECOSYSTEM, PACKAGE, VI, VERSION) AS (
       SELECT PK.ADV_ID, PK.AI, PK.ECOSYSTEM, PK.PACKAGE, 0,
              JSON_VALUE(R.RAW, 'strict $.affected[' || VARCHAR(PK.AI) || '].versions[0]'
                         RETURNING VARCHAR(128) NULL ON EMPTY NULL ON ERROR)
       FROM PK, R
       WHERE R.ADV_ID = PK.ADV_ID AND PK.PACKAGE IS NOT NULL
       UNION ALL
       SELECT V.ADV_ID, V.AI, V.ECOSYSTEM, V.PACKAGE, V.VI + 1,
              JSON_VALUE(R.RAW, 'strict $.affected[' || VARCHAR(V.AI) || '].versions[' || VARCHAR(V.VI + 1) || ']'
                         RETURNING VARCHAR(128) NULL ON EMPTY NULL ON ERROR)
       FROM V, R
       WHERE R.ADV_ID = V.ADV_ID AND V.VERSION IS NOT NULL AND V.VI < 20000),
     SHRED (ADV_ID, ECOSYSTEM, PACKAGE, VERSION) AS (
       SELECT DISTINCT ADV_ID, ECOSYSTEM, LOWER(REGEXP_REPLACE(PACKAGE, '[-_.]+', '-')), VERSION
       FROM V WHERE VERSION IS NOT NULL),
     TBL (ADV_ID, ECOSYSTEM, PACKAGE, VERSION) AS (
       SELECT ADV_ID, ECOSYSTEM, PACKAGE, VERSION FROM NEEDLE.ADV_AFFECTED
       WHERE ADV_ID = 'GHSA-27px-qpmj-qg38')
SELECT (SELECT COUNT(*) FROM SHRED) AS ROWS_FROM_JSON,
       (SELECT COUNT(*) FROM TBL) AS ROWS_IN_TABLE,
       (SELECT COUNT(*) FROM (SELECT * FROM SHRED EXCEPT SELECT * FROM TBL) X) AS ONLY_IN_JSON,
       (SELECT COUNT(*) FROM (SELECT * FROM TBL EXCEPT SELECT * FROM SHRED) Y) AS ONLY_IN_TABLE
FROM SYSIBM.SYSDUMMY1;

-- ===================================================================================================
-- [data] V4  Vector index present and EMB NOT NULL (needed for FETCH APPROX to use the index).
-- ===================================================================================================
SELECT VARCHAR(INDNAME, 30) AS INDNAME, INDEXTYPE, VARCHAR(COLNAMES, 30) AS COLNAMES FROM SYSCAT.INDEXES WHERE TABSCHEMA = 'NEEDLE' AND TABNAME = 'ADV_DOC';
SELECT VARCHAR(COLNAME, 10) AS COLNAME, VARCHAR(TYPENAME, 10) AS TYPENAME, NULLS FROM SYSCAT.COLUMNS WHERE TABSCHEMA = 'NEEDLE' AND TABNAME = 'ADV_DOC' AND COLNAME = 'EMB';
