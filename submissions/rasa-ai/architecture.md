# 1. Component Architecture Diagram

``` mermaid
flowchart TB
    Reviewer["Reviewer"]

    subgraph RASA["RASA AI — Streamlit Application (app.py)"]
        UI["Streamlit User Interface"]
        SP["Screenplay Processing"]
        ROLE["Character and Role Requirements"]
        VA["Video Analysis"]
        VOA["Vocal Analysis"]
        ET["Evidence Timeline"]
        LIB["Audition Library and Review"]
        SEARCH["Smart Audition Search"]
        DBUI["Db2 Database Workflow"]
    end

    subgraph ENGINE["Processing Components"]
        PDF["pypdf — selectable PDF text extraction"]
        RULES["Rule-based character cue extraction"]
        CV["OpenCV + MediaPipe"]
        AUDIO["librosa — acoustic analysis (optional)"]
        ALIGN["Timestamp alignment"]
        HAYSTACK["Haystack BM25 Retriever"]
    end

    JSON[("Local JSON Audition Library")]
    DB2[("Connected IBM Db2 Database")]

    Reviewer --> UI
    UI --> SP
    UI --> ROLE
    UI --> VA
    UI --> VOA
    UI --> ET
    UI --> LIB
    UI --> SEARCH
    UI --> DBUI

    SP --> PDF
    SP --> RULES
    RULES --> ROLE
    VA --> CV
    VOA --> AUDIO
    CV --> ET
    AUDIO --> ET
    ET --> ALIGN
    ALIGN --> LIB

    LIB <--> JSON
    JSON --> HAYSTACK
    SEARCH --> HAYSTACK

    DBUI <--> DB2
    JSON -. "Manual audition-record sync" .-> DB2
```

### Component explanation

1.  **Reviewer and Streamlit interface:** The reviewer accesses the
    application workflows through the Streamlit interface implemented in
    `app.py`.

2.  **Screenplay processing:** Accepts screenplay text or a text-based
    PDF. `pypdf` extracts selectable text, while rule-based processing
    identifies candidate character cues and nearby keyword evidence.

3.  **Character and role requirements:** Allows the reviewer to inspect
    character cues and define role-specific requirements. Selected
    targets are compared with available video measurements using the
    application's configured rules.

4.  **Video analysis:** OpenCV handles video frames, and MediaPipe
    provides pose and facial landmarks when detection succeeds. The
    application derives observable geometric and movement measurements.

5.  **Vocal analysis:** The optional `librosa`-based workflow calculates
    acoustic features such as pitch and RMS energy. It is separate from
    video analysis.

6.  **Evidence Timeline:** Aligns available video and vocal observations
    using timestamps, a reviewer-configured offset, and matching
    tolerance.

7.  **Audition Library:** Saves and manages audition reports in the
    local JSON library. This remains the application's source of truth
    in the reviewed implementation.

8.  **Smart Audition Search:** Uses Haystack 2.x BM25 keyword retrieval
    over saved audition records. Its in-memory document store is rebuilt
    for a search operation.

9.  **Db2 Database Workflow:** Uses the Db2 connector to communicate
    with the connected IBM Db2 database. The verified environment also
    supports successful actor-data SQL query execution. The reviewed
    connector additionally implements connection checking, table
    initialization, manual audition-record synchronization, and
    read-back.

------------------------------------------------------------------------

# 2. IBM Db2 Data Flow Diagram

``` mermaid
flowchart TD
    USER["Reviewer"]

    subgraph APP["RASA AI — Streamlit Application"]
        TAB["Db2 Database Workflow"]
        CONFIG["Load Db2 connection settings"]
        CONNECT["Connect using ibm_db"]
        QUERY["Execute reviewer-submitted SQL query"]
        RESULT["Receive and display query results"]
        SYNC["Manual audition-record synchronization"]
        READ["Read back recently synchronized records"]
    end

    DB[("Connected IBM Db2 Database")]

    USER --> TAB
    TAB --> CONFIG
    CONFIG --> CONNECT
    CONNECT <--> DB

    USER -->|"Submit actor-data SQL query"| QUERY
    QUERY --> CONNECT
    CONNECT --> DB
    DB -->|"Query result rows"| RESULT
    RESULT --> USER

    TAB -->|"When manual sync is requested"| SYNC
    SYNC -->|"MERGE by AUDITION_ID"| DB
    DB --> READ
    READ -->|"Fetched rows and decoded JSON payload"| TAB
```

### Db2 data-flow explanation

1.  **Reviewer initiates database access:** The reviewer opens the Db2
    Database workflow in RASA AI.

2.  **Connection configuration:** The application reads the Db2
    connection settings from environment variables:

    -   `DB2_HOST`
    -   `DB2_DATABASE`
    -   `DB2_USER`
    -   `DB2_PASSWORD`
    -   `DB2_PORT` (defaults to `50000`)
    -   `DB2_SSL` (optional)

3.  **Database connection:** The application uses the Python `ibm_db`
    driver to establish a connection to the IBM Db2 database. The
    connection has been successfully established in the user's
    environment.

4.  **SQL query execution:** The reviewer can execute SQL queries
    against the connected database to retrieve actor-related data.
    Successful actor-data query execution has been confirmed in the
    user's environment.

5.  **Query results:** Db2 returns the query result rows, which are made
    available to the reviewer. The exact actor table and SQL schema are
    not specified in the reviewed architecture source.

6.  **Audition-record synchronization:** Separately, the implemented
    manual synchronization workflow reads audition records from the
    local JSON library and uses a Db2 `MERGE` operation keyed by
    `AUDITION_ID`.

7.  **Read-back:** The connector retrieves recent synchronized audition
    records ordered by `UPDATED_AT` and decodes their JSON payloads.

**Persistence boundary:** The actor-data SQL query workflow and the
audition-record synchronization workflow are distinct database
operations. The reviewed application source identifies the local JSON
audition library as the source of truth; manual synchronization does not
automatically replace it with Db2.
