-- NOTE (AsOf): db2look 12.1.5 writes CREATE VECTOR INDEX without its distance metric, in
-- SYSCATSPACE and with zero build parameters, so that statement below cannot be replayed as is.
-- The real definition (WITH DISTANCE COSINE IN ASOF_TS32K COMPRESSED VECTORS IN ASOF_TS32K) is in
-- src/asof/sql/01_tables.sql, and SYSCAT.INDEXES confirms the index is in ASOF_TS32K.

-- This CLP file was created using DB2LOOK Version "12.1" 
-- Timestamp: (removed so the file only changes when the schema does)
-- Database Name: TESTDB         
-- Database Manager Version: DB2/LINUXX8664 Version 12.1.5.0
-- Database Codepage: 1208
-- Database Collating Sequence is: IDENTITY
-- Alternate collating sequence(alt_collate): null
-- varchar2 compatibility(varchar2_compat): OFF


CONNECT TO TESTDB;

------------------------------------------------
-- DDL Statements for Schemas
------------------------------------------------

-- Running the DDL below will explicitly create a schema in the
-- new database that corresponds to an implicitly created schema
-- in the original database.

CREATE SCHEMA "ASOF    ";



------------------------------------------------
-- DDL Statements for Table "ASOF    "."POLICY_DOC"
------------------------------------------------
 

CREATE TABLE "ASOF    "."POLICY_DOC"  (
		  "DOC_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "TITLE" VARCHAR(200 OCTETS) NOT NULL , 
		  "OWNER_TEAM" VARCHAR(100 OCTETS) , 
		  "SOURCE_NOTE" VARCHAR(400 OCTETS) )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."POLICY_DOC"

ALTER TABLE "ASOF    "."POLICY_DOC" 
	ADD CONSTRAINT "PK_POLICY_DOC" PRIMARY KEY
		("DOC_ID")
	ENFORCED;



------------------------------------------------
-- DDL Statements for Table "ASOF    "."POLICY_CLAUSE"
------------------------------------------------
 

CREATE TABLE "ASOF    "."POLICY_CLAUSE"  (
		  "CLAUSE_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "DOC_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "AREA" VARCHAR(40 OCTETS) NOT NULL , 
		  "TITLE" VARCHAR(200 OCTETS) NOT NULL , 
		  "VERSION_LABEL" VARCHAR(20 OCTETS) NOT NULL , 
		  "CLAUSE_TEXT" VARCHAR(4000 OCTETS) NOT NULL , 
		  "RULE_JSON" VARCHAR(2000 OCTETS) NOT NULL , 
		  "EMBEDDING" VECTOR(384,FLOAT32) NOT NULL , 
		  "CHANGE_NOTE" VARCHAR(400 OCTETS) , 
		  "CHANGED_BY" VARCHAR(128 OCTETS) NOT NULL WITH DEFAULT USER , 
		  "BUS_START" DATE NOT NULL , 
		  "BUS_END" DATE NOT NULL , 
		  "SYS_START" TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW BEGIN , 
		  "SYS_END" TIMESTAMP(12) NOT NULL GENERATED ALWAYS AS ROW END , 
		  "TRANS_ID" TIMESTAMP(12) GENERATED ALWAYS AS TRANSACTION START ID , 
		 PERIOD BUSINESS_TIME ("BUS_START","BUS_END") , 
		 PERIOD SYSTEM_TIME ("SYS_START","SYS_END") )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 

CREATE VECTOR INDEX "ASOF    "."IX_CLAUSE_EMBEDDING" ON "ASOF    "."POLICY_CLAUSE"
		("EMBEDDING") WITH DISTANCE 
		IN "SYSCATSPACE"
		COMPRESSED VECTORS IN "SYSCATSPACE"
		EXCLUDE NULL KEYS
		BUILD_MEM_BUDGET 0
		BUILD_LIST_SIZE 0
		BUILD_PARALLELISM 0
		MAX_NODE_DEGREE 0
		PCT_COMP_VECT_SIZE 0
		PCT_NODES_TO_CACHE 0;


-- DDL Statements for Primary Key on Table "ASOF    "."POLICY_CLAUSE"

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD CONSTRAINT "PK_POLICY_CLAUSE" PRIMARY KEY
		("CLAUSE_ID",
		 BUSINESS_TIME WITHOUT OVERLAPS)
	ENFORCED;



-- DDL Statements for Indexes on Table "ASOF    "."POLICY_CLAUSE"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_CLAUSE_DOC_AREA" ON "ASOF    "."POLICY_CLAUSE" 
		("DOC_ID" ASC,
		 "AREA" ASC)
		
		COMPRESS NO 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

-- DDL Statements for Indexes on Table "ASOF    "."POLICY_CLAUSE"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';


------------------------------------------------
-- DDL Statements for Table "ASOF    "."POLICY_CLAUSE_HIST"
------------------------------------------------
 

CREATE TABLE "ASOF    "."POLICY_CLAUSE_HIST"  (
		  "CLAUSE_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "DOC_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "AREA" VARCHAR(40 OCTETS) NOT NULL , 
		  "TITLE" VARCHAR(200 OCTETS) NOT NULL , 
		  "VERSION_LABEL" VARCHAR(20 OCTETS) NOT NULL , 
		  "CLAUSE_TEXT" VARCHAR(4000 OCTETS) NOT NULL , 
		  "RULE_JSON" VARCHAR(2000 OCTETS) NOT NULL , 
		  "EMBEDDING" VECTOR(384,FLOAT32) NOT NULL , 
		  "CHANGE_NOTE" VARCHAR(400 OCTETS) , 
		  "CHANGED_BY" VARCHAR(128 OCTETS) NOT NULL WITH DEFAULT USER , 
		  "BUS_START" DATE NOT NULL , 
		  "BUS_END" DATE NOT NULL , 
		  "SYS_START" TIMESTAMP(12) NOT NULL , 
		  "SYS_END" TIMESTAMP(12) NOT NULL , 
		  "TRANS_ID" TIMESTAMP(12) )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 






-- DDL Statements for Indexes on Table "ASOF    "."POLICY_CLAUSE_HIST"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_CLAUSE_HIST_ID" ON "ASOF    "."POLICY_CLAUSE_HIST" 
		("CLAUSE_ID" ASC,
		 "SYS_END" ASC)
		
		COMPRESS NO 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

------------------------------------------------
-- DDL Statements for Table "ASOF    "."ANSWER_LEDGER"
------------------------------------------------
 

CREATE TABLE "ASOF    "."ANSWER_LEDGER"  (
		  "LEDGER_ID" BIGINT NOT NULL , 
		  "REQUEST_ID" CHAR(36 OCTETS) NOT NULL , 
		  "CREATED_AT" TIMESTAMP(12) NOT NULL , 
		  "CHANNEL" VARCHAR(20 OCTETS) NOT NULL , 
		  "DOC_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "AS_OF_DATE" DATE NOT NULL , 
		  "QUESTION_REDACTED" VARCHAR(2000 OCTETS) NOT NULL , 
		  "DRAFT_REDACTED" VARCHAR(4000 OCTETS) NOT NULL , 
		  "FINAL_ANSWER" VARCHAR(4000 OCTETS) NOT NULL , 
		  "DECISION" VARCHAR(12 OCTETS) NOT NULL , 
		  "REASON_CODE" VARCHAR(40 OCTETS) NOT NULL , 
		  "MODEL_INFO" VARCHAR(200 OCTETS) NOT NULL , 
		  "PROMPT_VERSION" VARCHAR(40 OCTETS) NOT NULL , 
		  "LATENCY_MS" INTEGER NOT NULL , 
		  "VERDICTS_JSON" VARCHAR(30000 OCTETS) NOT NULL , 
		  "PREV_HASH" CHAR(64 OCTETS) NOT NULL , 
		  "ROW_HASH" CHAR(64 OCTETS) NOT NULL )   
		 COMPRESS YES ADAPTIVE  
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."ANSWER_LEDGER"

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "PK_ANSWER_LEDGER" PRIMARY KEY
		("LEDGER_ID")
	ENFORCED;


-- DDL Statements for Unique Constraints on Table "ASOF    "."ANSWER_LEDGER"


ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "UQ_LEDGER_HASH" UNIQUE
		("ROW_HASH")
	ENFORCED;


ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "UQ_LEDGER_REQUEST" UNIQUE
		("REQUEST_ID")
	ENFORCED;


-- DDL Statements for Indexes on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_LEDGER_CREATED" ON "ASOF    "."ANSWER_LEDGER" 
		("CREATED_AT" ASC)
		
		COMPRESS YES 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

-- DDL Statements for Indexes on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_LEDGER_DECISION" ON "ASOF    "."ANSWER_LEDGER" 
		("DECISION" ASC,
		 "CREATED_AT" ASC)
		
		COMPRESS YES 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

------------------------------------------------
-- DDL Statements for Table "ASOF    "."CLAIM_CITATION"
------------------------------------------------
 

CREATE TABLE "ASOF    "."CLAIM_CITATION"  (
		  "LEDGER_ID" BIGINT NOT NULL , 
		  "PASS_NO" SMALLINT NOT NULL , 
		  "CLAIM_NO" SMALLINT NOT NULL , 
		  "CLAIM_TEXT" VARCHAR(1000 OCTETS) NOT NULL , 
		  "AREA" VARCHAR(40 OCTETS) NOT NULL , 
		  "VERDICT" VARCHAR(14 OCTETS) NOT NULL , 
		  "LLM_VERDICT" VARCHAR(14 OCTETS) , 
		  "RULE_CHECK" VARCHAR(16 OCTETS) NOT NULL , 
		  "CLAUSE_ID" VARCHAR(32 OCTETS) , 
		  "CLAUSE_VERSION" VARCHAR(20 OCTETS) , 
		  "CLAUSE_BUS_START" DATE , 
		  "CLAUSE_SYS_START" TIMESTAMP(12) , 
		  "DISTANCE" DOUBLE , 
		  "QUOTED_SPAN" VARCHAR(1000 OCTETS) )   
		 COMPRESS YES ADAPTIVE  
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."CLAIM_CITATION"

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "PK_CLAIM_CITATION" PRIMARY KEY
		("LEDGER_ID",
		 "PASS_NO",
		 "CLAIM_NO")
	ENFORCED;



-- DDL Statements for Indexes on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_CITATION_CLAUSE" ON "ASOF    "."CLAIM_CITATION" 
		("CLAUSE_ID" ASC,
		 "CLAUSE_BUS_START" ASC)
		
		COMPRESS YES 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

------------------------------------------------
-- DDL Statements for Table "ASOF    "."CHAIN_HEAD"
------------------------------------------------
 

CREATE TABLE "ASOF    "."CHAIN_HEAD"  (
		  "HEAD_ID" SMALLINT NOT NULL , 
		  "LAST_LEDGER_ID" BIGINT NOT NULL , 
		  "LAST_HASH" CHAR(64 OCTETS) NOT NULL )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."CHAIN_HEAD"

ALTER TABLE "ASOF    "."CHAIN_HEAD" 
	ADD CONSTRAINT "PK_CHAIN_HEAD" PRIMARY KEY
		("HEAD_ID")
	ENFORCED;



------------------------------------------------
-- DDL Statements for Table "ASOF    "."PUBLISHED_ANSWER"
------------------------------------------------
 

CREATE TABLE "ASOF    "."PUBLISHED_ANSWER"  (
		  "ANSWER_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "DOC_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "QUESTION" VARCHAR(1000 OCTETS) NOT NULL , 
		  "ANSWER_TEXT" VARCHAR(4000 OCTETS) NOT NULL , 
		  "CITED_CLAUSE_ID" VARCHAR(32 OCTETS) NOT NULL , 
		  "CITED_VERSION" VARCHAR(20 OCTETS) NOT NULL , 
		  "CITED_BUS_START" DATE NOT NULL , 
		  "APPLIES_FROM" DATE NOT NULL , 
		  "APPLIES_TO" DATE NOT NULL , 
		  "STATUS" VARCHAR(12 OCTETS) NOT NULL WITH DEFAULT 'LIVE' )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."PUBLISHED_ANSWER"

ALTER TABLE "ASOF    "."PUBLISHED_ANSWER" 
	ADD CONSTRAINT "PK_PUBLISHED_ANSWER" PRIMARY KEY
		("ANSWER_ID")
	ENFORCED;



-- DDL Statements for Indexes on Table "ASOF    "."PUBLISHED_ANSWER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

CREATE INDEX "ASOF    "."IX_PUBLISHED_CLAUSE" ON "ASOF    "."PUBLISHED_ANSWER" 
		("CITED_CLAUSE_ID" ASC,
		 "CITED_BUS_START" ASC)
		
		COMPRESS NO 
		INCLUDE NULL KEYS ALLOW REVERSE SCANS;

------------------------------------------------
-- DDL Statements for Table "ASOF    "."FAQ_KB"
------------------------------------------------
 

CREATE TABLE "ASOF    "."FAQ_KB"  (
		  "ID" CHAR(16 OCTETS) NOT NULL , 
		  "TEXT" CLOB(1048576 OCTETS) LOGGED NOT COMPACT , 
		  "METADATA" BLOB(1048576) LOGGED NOT COMPACT , 
		  "EMBEDDING" VECTOR(384,FLOAT32) )   
		 IN "ASOF_TS32K"  
		 ORGANIZE BY ROW; 


-- DDL Statements for Primary Key on Table "ASOF    "."FAQ_KB"

ALTER TABLE "ASOF    "."FAQ_KB" 
	ADD PRIMARY KEY
		("ID")
	ENFORCED;



--------------------------------------------------------------
-- DDL Statements for system-period temporal table "ASOF    "."POLICY_CLAUSE"
--------------------------------------------------------------

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD VERSIONING USE HISTORY TABLE "ASOF    "."POLICY_CLAUSE_HIST";

-- DDL Statements for Foreign Keys on Table "ASOF    "."POLICY_CLAUSE"

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD CONSTRAINT "FK_CLAUSE_DOC" FOREIGN KEY
		("DOC_ID")
	REFERENCES "ASOF    "."POLICY_DOC"
		("DOC_ID")
	ON DELETE NO ACTION
	ON UPDATE NO ACTION
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."POLICY_CLAUSE"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD CONSTRAINT "CK_CLAUSE_AREA" CHECK 
		(AREA IN ('bereavement', 'cancellation', 'change_fee', 'baggage',       
                                     'refund', 'delay', 'travel_credit',
'pets', 'other'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."POLICY_CLAUSE"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD CONSTRAINT "CK_CLAUSE_RULE_JSON" CHECK 
		(JSON_EXISTS(RULE_JSON, '$'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."POLICY_CLAUSE"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."POLICY_CLAUSE" 
	ADD CONSTRAINT "CK_CLAUSE_VERSION" CHECK 
		(VERSION_LABEL LIKE 'v%')
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "CK_LEDGER_CHANNEL" CHECK 
		(CHANNEL IN ('chat', 'email', 'faq', 'api', 'eval', 'demo'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "CK_LEDGER_DECISION" CHECK 
		(DECISION IN ('PASS', 'CORRECTED', 'ESCALATED'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "CK_LEDGER_ID" CHECK 
		(LEDGER_ID >= 1)
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "CK_LEDGER_LATENCY" CHECK 
		(LATENCY_MS >= 0)
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."ANSWER_LEDGER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."ANSWER_LEDGER" 
	ADD CONSTRAINT "CK_LEDGER_VERDICTS" CHECK 
		(JSON_EXISTS(VERDICTS_JSON, '$'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Foreign Keys on Table "ASOF    "."CLAIM_CITATION"

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "FK_CITATION_LEDGER" FOREIGN KEY
		("LEDGER_ID")
	REFERENCES "ASOF    "."ANSWER_LEDGER"
		("LEDGER_ID")
	ON DELETE NO ACTION
	ON UPDATE NO ACTION
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_CLAIM_NO" CHECK 
		(CLAIM_NO BETWEEN 1 AND 8)
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_CLAUSE" CHECK 
		((CLAUSE_ID IS NULL) = (CLAUSE_BUS_START IS NULL))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_LLM_VERDICT" CHECK 
		(LLM_VERDICT IS NULL OR LLM_VERDICT IN ('SUPPORTED', 'CONTRADICTED', 'NOT_COVERED'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_PASS" CHECK 
		(PASS_NO IN (1, 2))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_RULE" CHECK 
		(RULE_CHECK IN ('MATCH', 'MISMATCH', 'NOT_APPLICABLE'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CLAIM_CITATION"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CLAIM_CITATION" 
	ADD CONSTRAINT "CK_CITATION_VERDICT" CHECK 
		(VERDICT IN ('SUPPORTED', 'CONTRADICTED', 'NOT_COVERED'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."CHAIN_HEAD"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."CHAIN_HEAD" 
	ADD CONSTRAINT "CK_CHAIN_HEAD_SINGLE" CHECK 
		(HEAD_ID = 1)
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Foreign Keys on Table "ASOF    "."PUBLISHED_ANSWER"

ALTER TABLE "ASOF    "."PUBLISHED_ANSWER" 
	ADD CONSTRAINT "FK_PUBLISHED_DOC" FOREIGN KEY
		("DOC_ID")
	REFERENCES "ASOF    "."POLICY_DOC"
		("DOC_ID")
	ON DELETE NO ACTION
	ON UPDATE NO ACTION
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."PUBLISHED_ANSWER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."PUBLISHED_ANSWER" 
	ADD CONSTRAINT "CK_PUBLISHED_RANGE" CHECK 
		(APPLIES_TO > APPLIES_FROM)
	ENFORCED
	ENABLE QUERY OPTIMIZATION;

-- DDL Statements for Check Constraints on Table "ASOF    "."PUBLISHED_ANSWER"

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';

ALTER TABLE "ASOF    "."PUBLISHED_ANSWER" 
	ADD CONSTRAINT "CK_PUBLISHED_STATUS" CHECK 
		(STATUS IN ('LIVE', 'NEEDS_REVIEW', 'RETIRED'))
	ENFORCED
	ENABLE QUERY OPTIMIZATION;






---------------------------------
-- DDL Statements for User Defined Functions
---------------------------------


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE FUNCTION ASOF.SHA256_HEX (P_TEXT VARCHAR(30000))
  RETURNS CHAR(64)
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  CONTAINS SQL
  RETURN LOWER(HEX(HASH(P_TEXT, 2)));


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE FUNCTION ASOF.LEDGER_ROW_HASH (
    P_PREV_HASH CHAR(64), P_LEDGER_ID BIGINT, P_REQUEST_ID CHAR(36), P_CREATED_AT TIMESTAMP(12),
    P_CHANNEL VARCHAR(20), P_DOC_ID VARCHAR(32), P_AS_OF DATE, P_QUESTION VARCHAR(2000),
    P_DRAFT VARCHAR(4000), P_FINAL VARCHAR(4000), P_DECISION VARCHAR(12), P_REASON VARCHAR(40),
    P_MODEL VARCHAR(200), P_PROMPT_VERSION VARCHAR(40), P_LATENCY_MS INTEGER, P_VERDICTS VARCHAR(30000))
  RETURNS CHAR(64)
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  CONTAINS SQL
  RETURN ASOF.SHA256_HEX(
       P_PREV_HASH
    || ASOF.SHA256_HEX(RTRIM(CHAR(P_LEDGER_ID)))
    || ASOF.SHA256_HEX(P_REQUEST_ID)
    || ASOF.SHA256_HEX(CHAR(P_CREATED_AT))
    || ASOF.SHA256_HEX(P_CHANNEL)
    || ASOF.SHA256_HEX(P_DOC_ID)
    || ASOF.SHA256_HEX(CHAR(P_AS_OF, ISO))
    || ASOF.SHA256_HEX(P_QUESTION)
    || ASOF.SHA256_HEX(P_DRAFT)
    || ASOF.SHA256_HEX(P_FINAL)
    || ASOF.SHA256_HEX(P_DECISION)
    || ASOF.SHA256_HEX(P_REASON)
    || ASOF.SHA256_HEX(P_MODEL)
    || ASOF.SHA256_HEX(P_PROMPT_VERSION)
    || ASOF.SHA256_HEX(RTRIM(CHAR(P_LATENCY_MS)))
    || ASOF.SHA256_HEX(P_VERDICTS));


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE FUNCTION ASOF.CLAIMS_FROM_JSON (P_VERDICTS VARCHAR(30000))
  RETURNS TABLE (PASS_NO SMALLINT, CLAIM_NO SMALLINT, CLAIM_TEXT VARCHAR(1000), AREA VARCHAR(40), VERDICT VARCHAR(14), LLM_VERDICT VARCHAR(14), RULE_CHECK VARCHAR(16), CLAUSE_ID VARCHAR(32), CLAUSE_VERSION VARCHAR(20), CLAUSE_BUS_START DATE, CLAUSE_SYS_START TIMESTAMP(12), DISTANCE DOUBLE, QUOTED_SPAN VARCHAR(1000))
  LANGUAGE SQL
  DETERMINISTIC
  NO EXTERNAL ACTION
  READS SQL DATA
  RETURN
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[0].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[0].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[0].text',
                   AREA             VARCHAR(40)   PATH '$.claims[0].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[0].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[0].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[0].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[0].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[0].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[0].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[0].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[0].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[0].quoted_span')
           ERROR ON ERROR) AS J0
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[1].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[1].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[1].text',
                   AREA             VARCHAR(40)   PATH '$.claims[1].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[1].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[1].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[1].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[1].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[1].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[1].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[1].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[1].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[1].quoted_span')
           ERROR ON ERROR) AS J1
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[2].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[2].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[2].text',
                   AREA             VARCHAR(40)   PATH '$.claims[2].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[2].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[2].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[2].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[2].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[2].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[2].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[2].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[2].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[2].quoted_span')
           ERROR ON ERROR) AS J2
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[3].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[3].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[3].text',
                   AREA             VARCHAR(40)   PATH '$.claims[3].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[3].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[3].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[3].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[3].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[3].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[3].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[3].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[3].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[3].quoted_span')
           ERROR ON ERROR) AS J3
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[4].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[4].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[4].text',
                   AREA             VARCHAR(40)   PATH '$.claims[4].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[4].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[4].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[4].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[4].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[4].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[4].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[4].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[4].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[4].quoted_span')
           ERROR ON ERROR) AS J4
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[5].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[5].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[5].text',
                   AREA             VARCHAR(40)   PATH '$.claims[5].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[5].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[5].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[5].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[5].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[5].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[5].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[5].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[5].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[5].quoted_span')
           ERROR ON ERROR) AS J5
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[6].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[6].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[6].text',
                   AREA             VARCHAR(40)   PATH '$.claims[6].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[6].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[6].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[6].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[6].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[6].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[6].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[6].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[6].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[6].quoted_span')
           ERROR ON ERROR) AS J6
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[7].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[7].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[7].text',
                   AREA             VARCHAR(40)   PATH '$.claims[7].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[7].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[7].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[7].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[7].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[7].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[7].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[7].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[7].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[7].quoted_span')
           ERROR ON ERROR) AS J7
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[8].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[8].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[8].text',
                   AREA             VARCHAR(40)   PATH '$.claims[8].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[8].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[8].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[8].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[8].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[8].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[8].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[8].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[8].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[8].quoted_span')
           ERROR ON ERROR) AS J8
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[9].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[9].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[9].text',
                   AREA             VARCHAR(40)   PATH '$.claims[9].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[9].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[9].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[9].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[9].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[9].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[9].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[9].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[9].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[9].quoted_span')
           ERROR ON ERROR) AS J9
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[10].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[10].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[10].text',
                   AREA             VARCHAR(40)   PATH '$.claims[10].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[10].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[10].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[10].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[10].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[10].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[10].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[10].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[10].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[10].quoted_span')
           ERROR ON ERROR) AS J10
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[11].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[11].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[11].text',
                   AREA             VARCHAR(40)   PATH '$.claims[11].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[11].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[11].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[11].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[11].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[11].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[11].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[11].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[11].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[11].quoted_span')
           ERROR ON ERROR) AS J11
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[12].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[12].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[12].text',
                   AREA             VARCHAR(40)   PATH '$.claims[12].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[12].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[12].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[12].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[12].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[12].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[12].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[12].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[12].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[12].quoted_span')
           ERROR ON ERROR) AS J12
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[13].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[13].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[13].text',
                   AREA             VARCHAR(40)   PATH '$.claims[13].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[13].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[13].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[13].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[13].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[13].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[13].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[13].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[13].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[13].quoted_span')
           ERROR ON ERROR) AS J13
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[14].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[14].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[14].text',
                   AREA             VARCHAR(40)   PATH '$.claims[14].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[14].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[14].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[14].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[14].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[14].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[14].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[14].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[14].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[14].quoted_span')
           ERROR ON ERROR) AS J14
    WHERE CLAIM_NO IS NOT NULL
    UNION ALL
    SELECT PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT, RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN
    FROM JSON_TABLE(P_VERDICTS, 'strict $'
           COLUMNS (PASS_NO          SMALLINT      PATH '$.claims[15].pass',
                   CLAIM_NO         SMALLINT      PATH '$.claims[15].claim_no',
                   CLAIM_TEXT       VARCHAR(1000) PATH '$.claims[15].text',
                   AREA             VARCHAR(40)   PATH '$.claims[15].area',
                   VERDICT          VARCHAR(14)   PATH '$.claims[15].verdict',
                   LLM_VERDICT      VARCHAR(14)   PATH '$.claims[15].llm_verdict',
                   RULE_CHECK       VARCHAR(16)   PATH '$.claims[15].rule_check',
                   CLAUSE_ID        VARCHAR(32)   PATH '$.claims[15].clause_id',
                   CLAUSE_VERSION   VARCHAR(20)   PATH '$.claims[15].clause_version',
                   CLAUSE_BUS_START DATE          PATH '$.claims[15].clause_bus_start',
                   CLAUSE_SYS_START TIMESTAMP(12) PATH '$.claims[15].clause_sys_start',
                   DISTANCE         DOUBLE        PATH '$.claims[15].distance',
                   QUOTED_SPAN      VARCHAR(1000) PATH '$.claims[15].quoted_span')
           ERROR ON ERROR) AS J15
    WHERE CLAIM_NO IS NOT NULL;


----------------------------

-- DDL Statements for Views

----------------------------
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE VIEW ASOF.V_POLICY_TIMELINE AS   SELECT C.CLAUSE_ID, C.DOC_ID,
C.AREA, C.TITLE, C.VERSION_LABEL, C.BUS_START, C.BUS_END,          C.CHANGED_BY,
C.CHANGE_NOTE, C.SYS_START, C.CLAUSE_TEXT, C.RULE_JSON,          J.FIRST_BAG_FEE_USD,
J.SECOND_BAG_FEE_USD, J.CHANGE_FEE_USD, J.PET_FEE_USD, J.CANCELLATION_FEE_USD,
         J.COMPENSATION_USD, J.DISCOUNT_PCT, J.REQUEST_WINDOW_DAYS, J.FREE_CANCEL_WINDOW_HOURS,
         J.MIN_DAYS_BEFORE_DEPARTURE, J.CREDIT_VALIDITY_MONTHS, J.MAX_PASSENGERS,
J.RETROACTIVE_ALLOWED,          J.TRANSFER_ALLOWED, J.CHANGES_ALLOWED 
 FROM ASOF.POLICY_CLAUSE C,        JSON_TABLE(C.RULE_JSON, 'strict $' 
        COLUMNS (FIRST_BAG_FEE_USD         DECIMAL(9, 2) PATH '$.first_bag_fee_usd',
                  SECOND_BAG_FEE_USD        DECIMAL(9, 2) PATH '$.second_bag_fee_usd',
                  CHANGE_FEE_USD            DECIMAL(9, 2) PATH '$.change_fee_usd',
                  PET_FEE_USD               DECIMAL(9, 2) PATH '$.pet_fee_usd',
                  CANCELLATION_FEE_USD      DECIMAL(9, 2) PATH '$.cancellation_fee_usd',
                  COMPENSATION_USD          DECIMAL(9, 2) PATH '$.compensation_usd',
                  DISCOUNT_PCT              DECIMAL(5, 2) PATH '$.discount_pct',
                  REQUEST_WINDOW_DAYS       INTEGER       PATH '$.request_window_days',
                  FREE_CANCEL_WINDOW_HOURS  INTEGER       PATH '$.free_cancel_window_hours',
                  MIN_DAYS_BEFORE_DEPARTURE INTEGER       PATH '$.min_days_before_departure',
                  CREDIT_VALIDITY_MONTHS    INTEGER       PATH '$.credit_validity_months',
                  MAX_PASSENGERS            INTEGER       PATH '$.max_passengers',
                  RETROACTIVE_ALLOWED       VARCHAR(5)    PATH '$.retroactive_allowed',
                  TRANSFER_ALLOWED          VARCHAR(5)    PATH '$.transfer_allowed',
                  CHANGES_ALLOWED           VARCHAR(5)    PATH '$.changes_allowed')
         ERROR ON ERROR) AS J;


SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE VIEW ASOF.V_DECISION_STATS AS   SELECT CHANNEL, DECISION,
REASON_CODE, COUNT(*) AS DECISIONS,          INTEGER(AVG(LATENCY_MS)) AS
AVG_LATENCY_MS, MIN(CREATED_AT) AS FIRST_AT, MAX(CREATED_AT) AS LAST_AT
  FROM ASOF.ANSWER_LEDGER   GROUP BY CHANNEL, DECISION, REASON_CODE;


SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE VIEW ASOF.V_CLAIM_OUTCOMES_BY_AREA AS   SELECT AREA, 
        SUM(CASE WHEN VERDICT = 'SUPPORTED' THEN 1 ELSE 0 END)    AS SUPPORTED,
         SUM(CASE WHEN VERDICT = 'CONTRADICTED' THEN 1 ELSE 0 END) AS CONTRADICTED,
         SUM(CASE WHEN VERDICT = 'NOT_COVERED' THEN 1 ELSE 0 END)  AS NOT_COVERED,
         COUNT(*) AS CLAIMS   FROM ASOF.CLAIM_CITATION   WHERE PASS_NO
= 1   GROUP BY AREA;


SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE VIEW ASOF.V_RULE_OVERRIDES AS   SELECT L.LEDGER_ID, L.CREATED_AT,
L.AS_OF_DATE, L.DECISION, C.PASS_NO, C.CLAIM_NO, C.CLAIM_TEXT,        
 C.CLAUSE_ID, C.CLAUSE_VERSION   FROM ASOF.CLAIM_CITATION C   JOIN ASOF.ANSWER_LEDGER
L ON L.LEDGER_ID = C.LEDGER_ID   WHERE C.LLM_VERDICT = 'SUPPORTED' AND
C.VERDICT = 'CONTRADICTED' AND C.RULE_CHECK = 'MISMATCH';





---------------------------------
-- DDL Statements for Stored Procedures
---------------------------------


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE PROCEDURE ASOF.APPEND_LEDGER (
    IN  P_REQUEST_ID     CHAR(36),
    IN  P_CHANNEL        VARCHAR(20),
    IN  P_DOC_ID         VARCHAR(32),
    IN  P_AS_OF          DATE,
    IN  P_QUESTION       VARCHAR(2000),
    IN  P_DRAFT          VARCHAR(4000),
    IN  P_FINAL          VARCHAR(4000),
    IN  P_DECISION       VARCHAR(12),
    IN  P_REASON         VARCHAR(40),
    IN  P_MODEL          VARCHAR(200),
    IN  P_PROMPT_VERSION VARCHAR(40),
    IN  P_LATENCY_MS     INTEGER,
    IN  P_VERDICTS       VARCHAR(30000),
    OUT P_LEDGER_ID      BIGINT,
    OUT P_ROW_HASH       CHAR(64),
    OUT P_CREATED_AT     TIMESTAMP(12))
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  DECLARE V_LAST BIGINT;--
  DECLARE V_PREV CHAR(64);--

  UPDATE ASOF.CHAIN_HEAD SET LAST_LEDGER_ID = LAST_LEDGER_ID WHERE HEAD_ID = 1;--
  SET (V_LAST, V_PREV) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);--
  IF V_PREV IS NULL THEN
    SIGNAL SQLSTATE '75002' SET MESSAGE_TEXT = 'CHAIN_HEAD is missing: run setup';--
  END IF;--
  IF JSON_EXISTS(P_VERDICTS, '$.claims[16]') THEN
    SIGNAL SQLSTATE '75003' SET MESSAGE_TEXT = 'A decision may carry at most 8 claims per check';--
  END IF;--

  SET P_LEDGER_ID = V_LAST + 1;--
  SET P_CREATED_AT = CURRENT TIMESTAMP(12);--
  SET P_ROW_HASH = ASOF.LEDGER_ROW_HASH(V_PREV, P_LEDGER_ID, P_REQUEST_ID, P_CREATED_AT, P_CHANNEL,
                                        P_DOC_ID, P_AS_OF, P_QUESTION, P_DRAFT, P_FINAL, P_DECISION,
                                        P_REASON, P_MODEL, P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS);--

  INSERT INTO ASOF.ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE,
      QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO,
      PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH)
    VALUES (P_LEDGER_ID, P_REQUEST_ID, P_CREATED_AT, P_CHANNEL, P_DOC_ID, P_AS_OF,
      P_QUESTION, P_DRAFT, P_FINAL, P_DECISION, P_REASON, P_MODEL,
      P_PROMPT_VERSION, P_LATENCY_MS, P_VERDICTS, V_PREV, P_ROW_HASH);--

  INSERT INTO ASOF.CLAIM_CITATION (LEDGER_ID, PASS_NO, CLAIM_NO, CLAIM_TEXT, AREA, VERDICT, LLM_VERDICT,
      RULE_CHECK, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START, CLAUSE_SYS_START, DISTANCE, QUOTED_SPAN)
    SELECT P_LEDGER_ID, j.PASS_NO, j.CLAIM_NO, j.CLAIM_TEXT, j.AREA, j.VERDICT, j.LLM_VERDICT,
           j.RULE_CHECK, j.CLAUSE_ID, j.CLAUSE_VERSION, j.CLAUSE_BUS_START, j.CLAUSE_SYS_START,
           j.DISTANCE, j.QUOTED_SPAN
    FROM TABLE(ASOF.CLAIMS_FROM_JSON(P_VERDICTS)) AS j;--

  UPDATE ASOF.CHAIN_HEAD SET LAST_LEDGER_ID = P_LEDGER_ID, LAST_HASH = P_ROW_HASH WHERE HEAD_ID = 1;--
END;

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE PROCEDURE ASOF.VERIFY_CHAIN (
    OUT P_STATUS    VARCHAR(12),
    OUT P_CHECKED   BIGINT,
    OUT P_FIRST_BAD BIGINT,
    OUT P_DETAIL    VARCHAR(300))
  LANGUAGE SQL
  READS SQL DATA
BEGIN
  DECLARE V_PREV CHAR(64);--
  DECLARE V_EXPECT BIGINT DEFAULT 1;--
  DECLARE V_HEAD_ID BIGINT;--
  DECLARE V_HEAD_HASH CHAR(64);--

  SET V_PREV = REPEAT('0', 64);--
  SET P_STATUS = 'OK';--
  SET P_CHECKED = 0;--
  SET P_FIRST_BAD = NULL;--
  SET P_DETAIL = NULL;--

  ROWS: FOR R AS SELECT LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, QUESTION_REDACTED,
                        DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, PROMPT_VERSION,
                        LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH
                 FROM ASOF.ANSWER_LEDGER ORDER BY LEDGER_ID
  DO
    IF R.LEDGER_ID <> V_EXPECT THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', V_EXPECT, 'ledger row is missing: IDs are not consecutive');--
      LEAVE ROWS;--
    END IF;--
    IF R.PREV_HASH <> V_PREV THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', R.LEDGER_ID, 'PREV_HASH does not match the previous row');--
      LEAVE ROWS;--
    END IF;--
    IF ASOF.LEDGER_ROW_HASH(R.PREV_HASH, R.LEDGER_ID, R.REQUEST_ID, R.CREATED_AT, R.CHANNEL, R.DOC_ID,
                            R.AS_OF_DATE, R.QUESTION_REDACTED, R.DRAFT_REDACTED, R.FINAL_ANSWER,
                            R.DECISION, R.REASON_CODE, R.MODEL_INFO, R.PROMPT_VERSION, R.LATENCY_MS,
                            R.VERDICTS_JSON) <> R.ROW_HASH THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', R.LEDGER_ID, 'row content does not match its ROW_HASH');--
      LEAVE ROWS;--
    END IF;--
    SET V_PREV = R.ROW_HASH;--
    SET V_EXPECT = V_EXPECT + 1;--
    SET P_CHECKED = P_CHECKED + 1;--
  END FOR;--

  IF P_STATUS = 'OK' THEN
    SET (V_HEAD_ID, V_HEAD_HASH) = (SELECT LAST_LEDGER_ID, LAST_HASH FROM ASOF.CHAIN_HEAD WHERE HEAD_ID = 1);--
    IF V_HEAD_ID IS NULL OR V_HEAD_ID <> P_CHECKED OR V_HEAD_HASH <> V_PREV THEN
      SET (P_STATUS, P_FIRST_BAD, P_DETAIL) = ('BROKEN', P_CHECKED + 1, 'chain head does not point at the last ledger row');--
    END IF;--
  END IF;--

  IF P_STATUS = 'OK' THEN
    SET P_FIRST_BAD = (
      SELECT MIN(L.LEDGER_ID)
      FROM ASOF.ANSWER_LEDGER L
      WHERE (SELECT COUNT(*) FROM ASOF.CLAIM_CITATION C WHERE C.LEDGER_ID = L.LEDGER_ID)
            <> (SELECT COUNT(*) FROM TABLE(ASOF.CLAIMS_FROM_JSON(L.VERDICTS_JSON)) AS J)
         OR EXISTS (
            SELECT 1 FROM ASOF.CLAIM_CITATION C
            WHERE C.LEDGER_ID = L.LEDGER_ID
              AND NOT EXISTS (
                SELECT 1 FROM TABLE(ASOF.CLAIMS_FROM_JSON(L.VERDICTS_JSON)) AS J
                WHERE J.PASS_NO = C.PASS_NO AND J.CLAIM_NO = C.CLAIM_NO AND J.VERDICT = C.VERDICT
                  AND COALESCE(J.CLAUSE_ID, '') = COALESCE(C.CLAUSE_ID, '')
                  AND COALESCE(J.CLAUSE_BUS_START, DATE('0001-01-01')) = COALESCE(C.CLAUSE_BUS_START, DATE('0001-01-01')))));--
    IF P_FIRST_BAD IS NOT NULL THEN
      SET (P_STATUS, P_DETAIL) = ('BROKEN', 'claim citations do not match the hashed verdicts');--
    END IF;--
  END IF;--

  SET P_FIRST_BAD = COALESCE(P_FIRST_BAD, 0);--
  SET P_DETAIL = COALESCE(P_DETAIL, 'every row, link and citation verified');--
END;

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE PROCEDURE ASOF.APPLY_POLICY_CHANGE (
    IN  P_CLAUSE_ID     VARCHAR(32),
    IN  P_FROM          DATE,
    IN  P_TO            DATE,
    IN  P_VERSION_LABEL VARCHAR(20),
    IN  P_TEXT          VARCHAR(4000),
    IN  P_RULE_JSON     VARCHAR(2000),
    IN  P_EMBEDDING     VARCHAR(12000),
    IN  P_NOTE          VARCHAR(400),
    OUT P_ROWS          INTEGER,
    OUT P_FLAGGED       INTEGER)
  LANGUAGE SQL
  MODIFIES SQL DATA
BEGIN
  IF P_FROM IS NULL OR P_TO IS NULL OR P_TO <= P_FROM THEN
    SIGNAL SQLSTATE '75010' SET MESSAGE_TEXT = 'The change must end after it starts';--
  END IF;--
  IF NOT EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID) THEN
    SIGNAL SQLSTATE '75011' SET MESSAGE_TEXT = 'Unknown clause';--
  END IF;--
  IF EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE WHERE CLAUSE_ID = P_CLAUSE_ID AND VERSION_LABEL = P_VERSION_LABEL) THEN
    SIGNAL SQLSTATE '75012' SET MESSAGE_TEXT = 'That version label is already in use for this clause';--
  END IF;--

  UPDATE ASOF.POLICY_CLAUSE
    FOR PORTION OF BUSINESS_TIME FROM P_FROM TO P_TO
    SET VERSION_LABEL = P_VERSION_LABEL,
        CLAUSE_TEXT   = P_TEXT,
        RULE_JSON     = P_RULE_JSON,
        EMBEDDING     = VECTOR(P_EMBEDDING, 384, FLOAT32),
        CHANGE_NOTE   = P_NOTE,
        CHANGED_BY    = SESSION_USER
    WHERE CLAUSE_ID = P_CLAUSE_ID;--
  GET DIAGNOSTICS P_ROWS = ROW_COUNT;--
  IF P_ROWS = 0 THEN
    SIGNAL SQLSTATE '75013' SET MESSAGE_TEXT = 'No existing version of this clause overlaps that period';--
  END IF;--

  UPDATE ASOF.PUBLISHED_ANSWER
    SET STATUS = 'NEEDS_REVIEW'
    WHERE CITED_CLAUSE_ID = P_CLAUSE_ID AND STATUS = 'LIVE'
      AND APPLIES_FROM < P_TO AND APPLIES_TO > P_FROM;--
  GET DIAGNOSTICS P_FLAGGED = ROW_COUNT;--
END;

SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";

CREATE PROCEDURE ASOF.CHANGE_IMPACT (IN P_CLAUSE_ID VARCHAR(32))
  LANGUAGE SQL
  READS SQL DATA
  DYNAMIC RESULT SETS 1
BEGIN
  DECLARE C1 CURSOR WITH RETURN TO CALLER FOR
    WITH RELEASED AS (
      SELECT DISTINCT L.LEDGER_ID, L.AS_OF_DATE, L.DECISION, L.CREATED_AT, C.CLAUSE_VERSION, C.CLAUSE_BUS_START
      FROM ASOF.ANSWER_LEDGER L
      JOIN ASOF.CLAIM_CITATION C ON C.LEDGER_ID = L.LEDGER_ID
      WHERE C.CLAUSE_ID = P_CLAUSE_ID AND C.VERDICT = 'SUPPORTED'
        AND ((L.DECISION = 'PASS' AND C.PASS_NO = 1) OR (L.DECISION = 'CORRECTED' AND C.PASS_NO = 2))
    )
    SELECT 'ANSWER' AS KIND, RTRIM(CHAR(R.LEDGER_ID)) AS REF_ID, R.AS_OF_DATE AS FOR_FROM,
           CAST(NULL AS DATE) AS FOR_TO, R.DECISION AS STATE, R.CREATED_AT,
           R.CLAUSE_VERSION AS CITED_VERSION, COALESCE(P.VERSION_LABEL, '(none)') AS CURRENT_VERSION,
           CASE WHEN P.VERSION_LABEL = R.CLAUSE_VERSION THEN 'HISTORICALLY_VALID' ELSE 'STALE' END AS STATUS,
           CASE WHEN P.VERSION_LABEL = R.CLAUSE_VERSION THEN CAST(NULL AS DATE) ELSE R.AS_OF_DATE END AS STALE_FROM
    FROM RELEASED R
    LEFT JOIN ASOF.POLICY_CLAUSE P
      ON P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START <= R.AS_OF_DATE AND P.BUS_END > R.AS_OF_DATE
    UNION ALL
    SELECT 'PUBLISHED', A.ANSWER_ID, A.APPLIES_FROM, A.APPLIES_TO, A.STATUS, CAST(NULL AS TIMESTAMP(12)),
           A.CITED_VERSION,
           COALESCE((SELECT LISTAGG(DISTINCT P.VERSION_LABEL, ', ') WITHIN GROUP (ORDER BY P.VERSION_LABEL)
                     FROM ASOF.POLICY_CLAUSE P
                     WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM), '(none)'),
           CASE WHEN EXISTS (SELECT 1 FROM ASOF.POLICY_CLAUSE P
                             WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM
                               AND P.VERSION_LABEL <> A.CITED_VERSION)
                THEN 'NEEDS_REVIEW' ELSE 'STILL_VALID' END,
           (SELECT MIN(GREATEST(P.BUS_START, A.APPLIES_FROM)) FROM ASOF.POLICY_CLAUSE P
             WHERE P.CLAUSE_ID = P_CLAUSE_ID AND P.BUS_START < A.APPLIES_TO AND P.BUS_END > A.APPLIES_FROM
               AND P.VERSION_LABEL <> A.CITED_VERSION)
    FROM ASOF.PUBLISHED_ANSWER A
    WHERE A.CITED_CLAUSE_ID = P_CLAUSE_ID
    ORDER BY 1, 3, 2;--
  OPEN C1;--
END;

-------------------------------
-- DDL Statements for Triggers
-------------------------------


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE TRIGGER ASOF.ANSWER_LEDGER_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.ANSWER_LEDGER
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'ANSWER_LEDGER is append-only: rows cannot be deleted';


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE TRIGGER ASOF.ANSWER_LEDGER_NO_UPDATE
  NO CASCADE BEFORE UPDATE ON ASOF.ANSWER_LEDGER
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'ANSWER_LEDGER is append-only: rows cannot be updated';


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE TRIGGER ASOF.CHAIN_HEAD_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.CHAIN_HEAD
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'CHAIN_HEAD cannot be deleted';


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE TRIGGER ASOF.CLAIM_CITATION_NO_DELETE
  NO CASCADE BEFORE DELETE ON ASOF.CLAIM_CITATION
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'CLAIM_CITATION is append-only: rows cannot be deleted';


SET SYSIBM.NLS_STRING_UNITS = 'SYSTEM';
SET CURRENT SCHEMA = "DB2INST1";
SET CURRENT PATH = "SYSIBM","SYSFUN","SYSPROC","SYSIBMADM","SYSHADOOP","DB2INST1";
CREATE TRIGGER ASOF.CLAIM_CITATION_NO_UPDATE
  NO CASCADE BEFORE UPDATE ON ASOF.CLAIM_CITATION
  FOR EACH ROW
  SIGNAL SQLSTATE '75001' SET MESSAGE_TEXT = 'CLAIM_CITATION is append-only: rows cannot be updated';


COMMIT WORK;

CONNECT RESET;

TERMINATE;

