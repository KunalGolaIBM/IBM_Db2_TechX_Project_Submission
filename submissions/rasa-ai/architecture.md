# RASA AI --- Implementation Architecture

**Document type:** Implementation architecture\
**Project:** RASA AI --- Audition Intelligence and Casting-Support
Application\
**Architecture basis:** Existing architecture document, README, and the
reviewed `smart_audition_search.py` and `db2_store.py` source files\
**Scope:** Describes the workflows and integrations supported by the
reviewed material. Optional and environment-dependent capabilities are
labelled accordingly.

------------------------------------------------------------------------

# 1. System Overview

RASA AI is a Python and Streamlit-based audition review application. It
helps reviewers organize screenplay context, define role requirements,
inspect visual and vocal observations from audition media, manage
audition reports, and search saved records.

RASA AI is a **human decision-support tool**. Its measurements and
retrieval results are descriptive evidence for reviewers; they do not
independently determine casting outcomes or establish acting quality,
personality, internal emotion, or role suitability.

## Main application workflow

1.  The reviewer provides screenplay/story text or a text-based PDF.
2.  Screenplay processing extracts selectable PDF text and applies
    rule-based logic to identify candidate character cues and nearby
    keyword evidence.
3.  The reviewer inspects character cues and defines role-specific
    requirements.
4.  Video analysis processes sampled frames and derives observable
    measurements from OpenCV and MediaPipe detections.
5.  Optional vocal analysis derives acoustic features such as pitch and
    RMS energy.
6.  Available video and vocal observations can be aligned on a
    timestamp-based evidence timeline.
7.  Audition reports are saved and managed in the local JSON audition
    library.
8.  Smart Audition Search uses Haystack BM25 keyword retrieval over
    saved audition records.
9.  The optional Db2 connector can initialize a table, manually
    synchronize audition records, and retrieve recently synchronized
    records.

------------------------------------------------------------------------

# 2. Component Architecture Diagram

``` mermaid
flowchart TB
    Reviewer["Reviewer"]

    subgraph APP["RASA AI — Python / Streamlit Application"]
        UI["Streamlit interface — app.py"]
        SP["Screenplay processing"]
        ROLE["Character cues and role requirements"]
        VIDEO["Video analysis"]
        VOCAL["Optional vocal analysis"]
        TIMELINE["Evidence timeline"]
        LIB["Audition library and review"]
        SEARCH["Smart Audition Search"]
        DBFLOW["Optional Db2 workflow"]
    end

    subgraph PROCESSING["Processing and Retrieval"]
        PDF["pypdf — selectable PDF text extraction"]
        RULES["Rule-based screenplay cue extraction"]
        CV["OpenCV + MediaPipe"]
        LIBROSA["librosa — acoustic features"]
        ALIGN["Timestamp alignment"]
        HAYSTACK["Haystack InMemoryBM25Retriever"]
        DOCSTORE["InMemoryDocumentStore"]
    end

    JSON[("Local JSON audition library")]
    DB2[("IBM Db2 — RASA_AUDITIONS")]

    Reviewer --> UI
    UI --> SP
    UI --> ROLE
    UI --> VIDEO
    UI --> VOCAL
    UI --> TIMELINE
    UI --> LIB
    UI --> SEARCH
    UI --> DBFLOW

    SP --> PDF
    SP --> RULES
    RULES --> ROLE
    VIDEO --> CV
    VOCAL --> LIBROSA
    CV --> TIMELINE
    LIBROSA --> TIMELINE
    TIMELINE --> ALIGN
    ALIGN --> LIB

    LIB <--> JSON
    JSON --> SEARCH
    SEARCH --> HAYSTACK
    HAYSTACK --> DOCSTORE

    DBFLOW <--> DB2
    JSON -. "Manual synchronization" .-> DB2
```

## Component descriptions

### 2.1 Streamlit interface --- `app.py`

The Streamlit application provides the reviewer-facing workflows. The
existing architecture and README identify `app.py` as the main
application entry point.

### 2.2 Screenplay processing

The application accepts screenplay/story text or a text-based PDF.
`pypdf` is used to extract selectable PDF text. Rule-based processing
identifies candidate character cues and nearby keyword evidence. This is
a heuristic workflow, not an LLM-based screenplay interpretation
pipeline.

### 2.3 Character and role requirements

Reviewers can inspect detected character cues and define role-specific
requirements. The application compares selected role targets with
available video measurements using its configured rules. These
comparisons are intended to support reviewer inspection.

### 2.4 Video analysis

OpenCV processes video frames and MediaPipe provides pose and facial
landmarks when detections succeed. The application derives observable
geometric and movement measurements from the available landmarks.
Results depend on the quality of the input media and successful
detection.

### 2.5 Vocal analysis

The optional `librosa` workflow calculates acoustic features, including
pitch and RMS energy summaries and timestamped observations. It is
separate from the video-processing path and depends on the relevant
optional audio-analysis dependencies being available.

### 2.6 Evidence timeline

The evidence timeline aligns available visual and vocal observations by
timestamps, using a configurable offset and matching tolerance.
Alignment of timestamps does not by itself establish lip-sync accuracy
or prove that a visual action and vocal event have the same meaning.

### 2.7 Audition library

Audition reports are stored and managed in the local JSON audition
library. In the reviewed design, this local library remains the
application's source of truth. The Db2 connector is an optional,
manually invoked synchronization path rather than an automatic
replacement for local JSON persistence.

### 2.8 Smart Audition Search --- `smart_audition_search.py`

The reviewed implementation uses Haystack's `InMemoryDocumentStore` and
`InMemoryBM25Retriever`.

For each search operation, the function:

1.  Receives the saved audition items and search query.
2.  Builds searchable text from available audition-report fields.
3.  Creates Haystack `Document` objects, retaining the original library
    index in document metadata.
4.  Writes those documents to a new in-memory document store.
5.  Runs BM25 retrieval and returns the matching library index,
    retrieval score, and searchable content.

The document store is recreated for each search call. This is **BM25
keyword retrieval**, not vector search, embedding-based semantic
retrieval, or an LLM-generated answer.

The searchable fields in the reviewed source include:

-   Actor label, analysis type, video filename, and audio filename.
-   Selected character and vocal-analysis summary.
-   Median pitch, pitch percentiles, pitch standard deviation, and
    voiced-frame fraction.
-   Mean RMS energy, energy variation, estimated low-energy duration,
    and detected energy gaps.
-   Reviewer decision, shortlist status, and reviewer notes.
-   Duration estimate, pose detection rate, and face detection rate.
-   Movement, shoulder tilt, torso offset, wrist-above-shoulder
    fraction, and facial-geometry measurements.
-   Evidence-quality notes and analysis method.
-   Up to the first 100 timestamped sample observations, including
    available pose, movement, wrist, shoulder, torso, mouth, eye, brow,
    and expression-label fields.

Only values present in a saved audition item are added to its searchable
text.

------------------------------------------------------------------------

# 3. IBM Db2 Integration Architecture

The Db2 integration is implemented in `db2_store.py` and uses the Python
`ibm_db` driver. The module treats Db2 as an optional integration: if
the driver is unavailable, it raises a clear runtime error when a Db2
operation is requested, while the rest of the application can remain
usable.

## Db2 data-flow diagram

``` mermaid
flowchart TD
    Reviewer["Reviewer"]

    subgraph RASA["RASA AI — Db2 workflow"]
        CONFIG["Read Db2 configuration"]
        CONNECT["Connect using ibm_db"]
        STATUS["Check connection — VALUES CURRENT SERVER"]
        INIT["Check current schema for RASA_AUDITIONS"]
        CREATE["Create RASA_AUDITIONS if missing"]
        LOCAL["Read audition items supplied by the application"]
        MERGE["Prepared MERGE statement"]
        FETCH["Fetch recent audition rows"]
        DECODE["Decode PAYLOAD JSON"]
    end

    JSON[("Local JSON audition records")]
    DB[("IBM Db2 database")]

    Reviewer --> CONFIG
    CONFIG --> CONNECT
    CONNECT --> STATUS
    STATUS <--> DB

    CONNECT --> INIT
    INIT <--> DB
    INIT -->|Table absent| CREATE
    CREATE --> DB

    JSON --> LOCAL
    LOCAL --> MERGE
    MERGE <--> DB

    DB --> FETCH
    FETCH --> DECODE
    DECODE --> Reviewer
```

## 3.1 Connection configuration

The connector reads configuration from environment variables first and
then attempts to read the same keys from Streamlit secrets.

  -----------------------------------------------------------------------
  Setting                 Purpose                 Default / requirement
  ----------------------- ----------------------- -----------------------
  `DB2_HOST`              Db2 server host         Required

  `DB2_DATABASE`          Database name           Required

  `DB2_USER`              Database user           Required

  `DB2_PASSWORD`          Database password       Required

  `DB2_PORT`              Db2 server port         Defaults to `50000`

  `DB2_SSL`               Enables SSL connection  Optional; otherwise SSL
                          security when set to    is not added
                          `1`, `true`, `yes`, or  
                          `on`                    
  -----------------------------------------------------------------------

The connector constructs a TCP/IP connection string using `DATABASE`,
`HOSTNAME`, `PORT`, `PROTOCOL`, `UID`, and `PWD`. When SSL is enabled,
it adds `SECURITY=SSL`.

The `connection_status()` function opens a connection, executes
`VALUES CURRENT SERVER`, returns the current server name when available,
and closes the connection in a `finally` block.

## 3.2 Table initialization and actual schema

`ensure_schema()` checks `SYSCAT.TABLES` for a table named
`RASA_AUDITIONS` in the current schema. If the table is not found, the
connector creates it with the following schema:

``` sql
CREATE TABLE RASA_AUDITIONS (
    AUDITION_ID VARCHAR(64) NOT NULL PRIMARY KEY,
    ACTOR_LABEL VARCHAR(256),
    CHARACTER_NAME VARCHAR(256),
    REVIEW_STATUS VARCHAR(64),
    SHORTLISTED SMALLINT NOT NULL DEFAULT 0,
    PAYLOAD CLOB(2M) NOT NULL,
    UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
);
```

The table stores selected summary fields for filtering or inspection and
retains the full audition record as JSON text in the `PAYLOAD` CLOB
column.

## 3.3 Audition record identifier

The connector determines `AUDITION_ID` in this order:

1.  `audition_id`
2.  `id`
3.  `record_id`
4.  If none is present, a SHA-256 hash of the record's canonical JSON
    representation (`sort_keys=True`).

The resulting identifier is limited to 64 characters.

## 3.4 Manual synchronization using MERGE

`sync_auditions(items)` first calls `ensure_schema()`, opens a Db2
connection, prepares a parameterized `MERGE` statement, and processes
the supplied list of audition dictionaries.

The reviewed SQL statement is:

``` sql
MERGE INTO RASA_AUDITIONS AS T
USING (VALUES (?, ?, ?, ?, ?, ?)) AS S
    (AUDITION_ID, ACTOR_LABEL, CHARACTER_NAME, REVIEW_STATUS, SHORTLISTED, PAYLOAD)
ON T.AUDITION_ID = S.AUDITION_ID
WHEN MATCHED THEN UPDATE SET
    ACTOR_LABEL = S.ACTOR_LABEL,
    CHARACTER_NAME = S.CHARACTER_NAME,
    REVIEW_STATUS = S.REVIEW_STATUS,
    SHORTLISTED = S.SHORTLISTED,
    PAYLOAD = S.PAYLOAD,
    UPDATED_AT = CURRENT TIMESTAMP
WHEN NOT MATCHED THEN INSERT
    (AUDITION_ID, ACTOR_LABEL, CHARACTER_NAME, REVIEW_STATUS,
     SHORTLISTED, PAYLOAD, UPDATED_AT)
VALUES
    (S.AUDITION_ID, S.ACTOR_LABEL, S.CHARACTER_NAME, S.REVIEW_STATUS,
     S.SHORTLISTED, S.PAYLOAD, CURRENT TIMESTAMP);
```

The parameter values are mapped as follows:

  ---------------------------------------------------------------------
  Db2 column                         Source value
  ---------------------------------- ----------------------------------
  `AUDITION_ID`                      `audition_id`, `id`, or
                                     `record_id`; otherwise generated
                                     SHA-256 identifier

  `ACTOR_LABEL`                      `actor_label`, truncated to 256
                                     characters

  `CHARACTER_NAME`                   `selected_character`, truncated to
                                     256 characters

  `REVIEW_STATUS`                    `reviewer_decision`, defaulting to
                                     `Not reviewed`, truncated to 64
                                     characters

  `SHORTLISTED`                      `1` when `shortlisted` is truthy;
                                     otherwise `0`

  `PAYLOAD`                          Full audition dictionary
                                     serialized as JSON
  ---------------------------------------------------------------------

The function skips list entries that are not dictionaries and returns
the number of dictionary records processed. The implementation updates
matching records and inserts new records. It does not delete Db2 rows
that are absent from the local JSON library.

## 3.5 Read-back query

`fetch_auditions(limit=100)` ensures the table exists, clamps the
requested limit to the range 1--1000, and retrieves the most recently
updated records:

``` sql
SELECT
    AUDITION_ID,
    ACTOR_LABEL,
    CHARACTER_NAME,
    REVIEW_STATUS,
    SHORTLISTED,
    PAYLOAD,
    UPDATED_AT
FROM RASA_AUDITIONS
ORDER BY UPDATED_AT DESC
FETCH FIRST 100 ROWS ONLY;
```

The actual query inserts the validated numeric limit into the
`FETCH FIRST` clause. The connector attempts to decode `PAYLOAD` as
JSON. If decoding fails, it returns the original payload text under a
`payload_text` key.

The returned record maps the database columns back to application-style
keys: `audition_id`, `actor_label`, `selected_character`,
`reviewer_decision`, `shortlisted`, `updated_at`, and `payload`.

## 3.6 Persistence boundary

There are two distinct Db2-related operations:

-   **Reviewer SQL workflow:** Reviewer-submitted SQL queries against
    the connected database, such as actor-data queries. The existing
    project notes report successful actor-data query execution in the
    user's environment.
-   **Audition synchronization:** The `db2_store.py` connector's manual
    `MERGE` and read-back operations for records originating in the
    local JSON audition library.

The reviewed connector source confirms the implementation of connection
checking, schema initialization, manual upsert, and read-back. The
source files supplied for this review do not by themselves establish
that every one of these audition synchronization operations has been
successfully exercised against the live database. The local JSON library
remains the source of truth in the documented design.

------------------------------------------------------------------------

# 4. Source File Responsibilities

  ---------------------------------------------------------------------
  Source file                        Responsibility supported by
                                     reviewed material
  ---------------------------------- ----------------------------------
  `app.py`                           Main Streamlit application entry
                                     point and reviewer-facing
                                     workflows, as identified by the
                                     existing architecture and README

  `smart_audition_search.py`         Builds searchable audition text
                                     and runs Haystack in-memory BM25
                                     keyword retrieval

  `db2_store.py`                     Optional Db2 connection,
                                     connection status, table
                                     initialization, manual
                                     audition-record MERGE
                                     synchronization, and record
                                     read-back

  `requirements.txt`                 Python dependency installation, as
                                     identified by the README

  `rasaai_audition_library.json`     Local audition-library data file,
                                     as identified by the README
  ---------------------------------------------------------------------

The reviewed source set for this update includes
`smart_audition_search.py`, `db2_store.py`, and the supplied
`requirements.txt`. The requirements file documents dependency
constraints and pins; it does not prove which versions are currently
installed in a particular runtime.

## 4.1 Python dependencies declared in `requirements.txt`

The supplied requirements file declares the following dependencies:

  --------------------------------------------------------------------------
  Package                    Requirement in the      Role indicated by the
                             supplied file           project
  -------------------------- ----------------------- -----------------------
  `streamlit`                `>=1.36,<2`             Streamlit application
                                                     interface

  `pypdf`                    `>=4.2,<6`              PDF text extraction

  `opencv-python-headless`   `==4.11.0.86`           Video/frame processing

  `mediapipe`                `==0.10.21`             Pose and facial
                                                     landmark processing

  `numpy`                    `==1.26.4`              Numerical operations

  `protobuf`                 `==4.25.9`              Dependency declared
                                                     alongside the analysis
                                                     stack

  `librosa`                  No version pin          Optional audio/acoustic
                                                     analysis

  `fer`                      `==22.5.1`              Facial-expression
                                                     package declared in
                                                     requirements

  `tensorflow`               `==2.19.1`              Machine-learning
                                                     dependency declared
                                                     alongside `fer`

  `haystack-ai`              `>=2.0,<3`              Haystack 2.x retrieval
                                                     components

  `ibm_db`                   `>=3.2.6`               Optional IBM Db2
                                                     connectivity

  `moviepy`                  `==1.0.3`               Video/media handling
                                                     dependency

  `setuptools`               `==80.9.0`              Python packaging/build
                                                     tooling
  --------------------------------------------------------------------------

**Requirements-file observation:** `moviepy==1.0.3` appears twice in the
supplied file. This is a duplicate declaration; it does not represent
two separate installations.

These are the constraints declared by the submitted requirements file.
They should not be described as verified installed versions unless the
environment's installed package list has also been checked.

------------------------------------------------------------------------

# 5. Implementation Boundaries and Limitations

-   Screenplay character-cue extraction is rule-based and heuristic.
-   Video measurements depend on successful frame and landmark
    detection.
-   Vocal analysis is optional and dependency-dependent.
-   Acoustic features such as pitch and RMS energy are measurements;
    they do not independently establish emotion, intent, or vocal
    meaning.
-   The evidence timeline aligns timestamps; it does not itself prove
    lip synchronization or semantic correspondence.
-   Smart Audition Search uses BM25 keyword retrieval with a newly
    created in-memory document store for each search.
-   The reviewed search implementation does not use embeddings, a vector
    database, or an LLM.
-   Db2 is an optional integration and does not replace the local JSON
    audition library as the source of truth.
-   The Db2 table initialization query checks the current schema and the
    table name `RASA_AUDITIONS`.
-   The connector's table-check and schema SQL are written for Db2 LUW
    catalog conventions; compatibility with other Db2 editions should be
    verified in the target environment.
-   The reviewed Python connector source documents the Db2 audition
    table and SQL used for synchronization. It does not identify the
    separate actor-data table/schema used by reviewer-submitted SQL
    queries.
-   `requirements.txt` contains both version ranges and exact pins. The
    file declares `moviepy==1.0.3` twice. Dependency installation
    success and runtime compatibility are not established by the
    requirements file itself.

------------------------------------------------------------------------

# 6. Verification Status

  ---------------------------------------------------------------------
  Capability                         What the reviewed material
                                     supports
  ---------------------------------- ----------------------------------
  Streamlit application and reviewer Described in the existing
  workflows                          architecture and README

  Screenplay text/PDF processing     Described as selectable PDF
                                     extraction and rule-based cue
                                     processing

  Video analysis                     Described as OpenCV and
                                     MediaPipe-based observable
                                     measurements

  Vocal analysis                     Described as optional `librosa`
                                     acoustic analysis

  Evidence timeline                  Described as timestamp alignment
                                     when visual and vocal reports are
                                     available

  Local audition library             Identified as the source of truth

  Haystack BM25 search               Confirmed by the supplied
                                     `smart_audition_search.py`
                                     implementation

  Db2 connection configuration and   Confirmed by the supplied
  connection check                   `db2_store.py` implementation

  Db2 table DDL                      Confirmed by the supplied
                                     `db2_store.py` implementation

  Db2 MERGE synchronization SQL      Confirmed by the supplied
                                     `db2_store.py` implementation

  Db2 read-back SQL and JSON         Confirmed by the supplied
  decoding                           `db2_store.py` implementation

  Successful live execution of all   Not established by the supplied
  audition sync/read-back operations source files alone

  Exact actor-data table schema      Not specified in the reviewed
                                     architecture/source material

  Complete internal source mapping   Not independently verified from
  for `app.py`                       `app.py` in this review

  Exact installed dependency         Not independently verified from
  versions                           `requirements.txt` in this review
  ---------------------------------------------------------------------

------------------------------------------------------------------------

**Architecture note:** This document distinguishes implemented
source-code behavior from environment-dependent features and runtime
verification. It does not claim that optional integrations or unverified
database operations have been tested successfully.
