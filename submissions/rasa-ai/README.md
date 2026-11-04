# RASA AI --- Audition Intelligence & Casting Support

**An AI-assisted audition review workspace for screenplay-guided,
evidence-informed human casting decisions.**

RASA AI is a Python and Streamlit application that brings screenplay
context, role requirements, audition-media observations, reviewer notes,
audition comparison, and audition-record retrieval into one review
workflow.

> **Decision-support notice:** RASA AI does not make casting decisions.
> Computer-vision measurements, optional facial-expression labels, vocal
> features, rule-based screenplay cues, and retrieval scores are signals
> for human review---not validated measures of acting quality,
> personality, internal emotion, diagnosis, or role suitability.
> Qualified human reviewers remain responsible for evaluating
> performances and making casting decisions.

------------------------------------------------------------------------

## Table of contents

-   [Project overview](#project-overview)
-   [Problem statement](#problem-statement)
-   [What RASA AI does](#what-rasa-ai-does)
-   [Application workflow](#application-workflow)
-   [Technology stack](#technology-stack)
-   [Project files](#project-files)
-   [Requirements and prerequisites](#requirements-and-prerequisites)
-   [Installation](#installation)
-   [Run the application](#run-the-application)
-   [Haystack retrieval](#haystack-retrieval)
-   [IBM Db2 integration](#ibm-db2-integration)
-   [Data storage and privacy](#data-storage-and-privacy)
-   [Known limitations](#known-limitations)
-   [Troubleshooting](#troubleshooting)

------------------------------------------------------------------------

## Project overview

Audition evaluation can involve reviewing a screenplay, understanding
the intended role, watching multiple recordings, listening to vocal
performances, taking notes, and revisiting earlier auditions. RASA AI
provides a single workspace to organize these activities and inspect
available evidence in context.

The application supports:

-   Screenplay and story-text input, including text-based PDF
    extraction.
-   Rule-based identification of candidate character cues and
    scene-heading patterns.
-   Reviewer-defined role requirements and audition prompts.
-   Video-based pose, movement, and facial-geometry measurements when
    landmarks can be detected.
-   Optional audio-only acoustic analysis.
-   A timestamp-based evidence timeline when both video and vocal
    reports are available.
-   Local audition-record storage, review notes, status, shortlist
    markers, comparison, and export.
-   Haystack BM25 keyword retrieval over saved audition records.
-   An optional IBM Db2 connector for connection checking,
    audition-table initialization, manual synchronization, and
    read-back.

RASA AI is implemented as a Streamlit application. The reviewed
implementation uses deterministic/rule-based screenplay processing,
computer-vision and acoustic-analysis libraries, local JSON persistence,
Haystack BM25 retrieval, and a Python Db2 driver. The reviewed retrieval
workflow does not use an LLM to generate answers.

## Problem statement

Audition information is often reviewed across separate materials:
screenplay documents, role descriptions, video recordings, audio
recordings, reviewer notes, and previously assessed auditions. When
these materials are handled independently, it can be difficult to keep
the intended character requirements connected to the evidence observed
in each audition and to revisit earlier assessments consistently.

RASA AI addresses this workflow problem by organizing screenplay
context, role requirements, observable audition-media measurements,
reviewer-managed assessment information, and saved audition records in
one application.

The application is intended to help reviewers:

1.  Identify candidate character cues in screenplay text and verify them
    against the source material.
2.  Define role-specific requirements before reviewing audition
    evidence.
3.  Inspect timestamped visual and vocal observations where the relevant
    analysis is available.
4.  Compare saved audition records and retain human reviewer notes and
    decisions.
5.  Retrieve previously saved audition records using keyword-based
    search.
6.  Optionally connect to IBM Db2 for database operations supported by
    the connector.

**Scope:** RASA AI supports structured review. It does not determine
whether an actor is suitable for a role, infer a person's internal
emotional state, or replace professional casting judgment.

## What RASA AI does

### 1. Screenplay analysis

-   Accepts screenplay or story text entered by the reviewer.
-   Accepts text-based PDF uploads and extracts selectable text using
    `pypdf`.
-   Uses deterministic, rule-based processing to identify candidate
    character cues and scene-heading patterns.
-   Presents candidate characters, nearby cue evidence, and suggested
    audition-test context for reviewer inspection.
-   Supports JSON export of screenplay-analysis output where provided by
    the UI.

Scanned or image-only PDFs are not OCR-processed by the reviewed
workflow. Character and cue extraction is heuristic and should be
checked against the original screenplay.

### 2. Character cues and role requirements

-   Presents candidate character cues identified from screenplay text.
-   Lets reviewers inspect the evidence associated with those
    candidates.
-   Allows reviewers to define role requirements and a character
    emotion-performance brief to guide human review of the intended
    portrayal.
-   Compares selected role targets with available video measurements
    where supported by the implementation.

The role description and intended portrayal remain reviewer-provided
context. Rule-based cue extraction is not a complete semantic
interpretation of a screenplay.

### 3. Video analysis

-   Accepts an audition video and an actor/audition label.
-   Uses OpenCV for video-frame handling.
-   Uses MediaPipe landmarks for pose/body and facial-geometry
    measurements when detection succeeds.
-   Produces sampled, timestamped observations and evidence-quality
    information.
-   Includes measurements such as movement and landmark geometry where
    available.
-   Can optionally expose experimental facial-expression labels when the
    optional `fer` package/model is installed.
-   Supports saving completed audition reports to the local audition
    library.

Results depend on recording conditions and successful landmark
detection. Lighting, camera placement, framing, angle, occlusion,
movement, and tracking quality can affect measurements. Facial geometry
is not itself an emotion label; optional expression classifications may
be inaccurate and should only prompt manual review.

### 4. Vocal analysis

-   Provides optional audio-only analysis when the required audio
    dependencies are installed.
-   Produces acoustic summaries such as pitch and signal-energy
    measurements where available.
-   Provides timestamped vocal evidence and JSON output where supported
    by the UI.

Vocal features describe properties of the audio signal. They are not
speech transcription and do not reliably establish emotion, intent, or
acting ability.

### 5. Combined evidence timeline

-   Combines available video and vocal observations when both reports
    are present.
-   Aligns observations by timestamp using the configured audio offset
    and matching tolerance.
-   Helps reviewers inspect visual and vocal observations along a shared
    timeline.

Timestamp alignment is a review aid. It does not verify lip
synchronization or infer emotional meaning.

### 6. Audition library and comparison

The application provides local audition-library functionality to:

-   Save and reload audition reports.
-   Review and compare saved auditions.
-   Inspect available measurements and evidence notes.
-   Filter records by text, character, review status, and shortlist
    state where available.
-   Add or update reviewer notes, review status, and shortlist markers.
-   Export audition information and individual reports where offered by
    the UI.
-   Remove a saved audition from the local library when required.

Review status, notes, and shortlist markers are reviewer-managed
information. A shortlist marker is not an automated casting
recommendation.

### 7. Haystack BM25 retrieval

The `smart_audition_search.py` helper uses Haystack 2.x BM25 keyword
retrieval to search saved audition reports.

Depending on the saved record, searchable content can include actor
labels, character details, reviewer notes, review status, shortlist
state, filenames, and available analysis fields. The UI can display
retrieved records and BM25 scores, apply supported filters, export the
current result set to CSV, and show session-only search history.

BM25 measures keyword relevance within a search. Its score is not an
acting-quality score, role-fit score, or casting probability. The
implementation creates an in-memory document store for a search
operation; it is not a persistent vector database or semantic-search
index.

### 8. IBM Db2 integration

RASA AI includes a Db2 Database workflow implemented through
`db2_store.py` and the Python `ibm_db` driver. The reviewed connector
provides:

-   Db2 connection checking.
-   Initialization of the `RASA_AUDITIONS` table when it does not exist.
-   Manual upsert of local audition records using `MERGE`, keyed by
    `AUDITION_ID`.
-   Storage of the full audition payload as JSON in a CLOB, alongside
    summary fields.
-   Retrieval of recent audition records and decoding of their JSON
    payloads.

**Current environment note:** Db2 connectivity and successful execution
of actor-data SQL queries have been confirmed in the project
environment. This confirms that the environment can connect to the
configured database and query actor data. It should not be confused with
a claim that every optional RASA AI audition-table operation has been
independently validated. Test table initialization, audition-record
synchronization, and read-back separately before relying on those
operations.

**Persistence boundary:** The local JSON audition library remains the
source of truth in the reviewed application design. Db2 synchronization
is manual; the connector does not delete database rows or automatically
switch the rest of the application to Db2. The reviewed connector uses
Db2 LUW-style catalog SQL; compatibility with other Db2 editions should
be checked.

------------------------------------------------------------------------

## Application workflow

A typical reviewer workflow is:

1.  Enter screenplay/story text or upload a text-based PDF.
2.  Inspect the candidate character cues and relevant screenplay
    evidence.
3.  Define role requirements and audition-test context.
4.  Upload and analyze an audition video.
5.  Optionally run vocal analysis on the audition audio.
6.  Review the evidence timeline when both visual and vocal reports are
    available.
7.  Save the audition report to the local library.
8.  Add reviewer notes, review status, or a shortlist marker.
9.  Compare auditions or search saved records with Haystack BM25.
10. Optionally use the Db2 Database workflow to connect, initialize the
    audition table, manually synchronize local audition records, and
    read records back.

------------------------------------------------------------------------

## Technology stack

  Technology       Role in RASA AI
  ---------------- -----------------------------------------------------
  Python           Application and helper implementation
  Streamlit        Web interface and reviewer workflows
  `pypdf`          Extraction of selectable text from PDF files
  OpenCV           Video-frame handling
  MediaPipe        Pose and landmark detection for visual measurements
  NumPy / pandas   Numerical processing and tabular evidence handling
  `librosa`        Optional vocal/acoustic analysis
  FER              Optional experimental facial-expression labels
  Haystack 2.x     In-memory BM25 keyword retrieval
  `ibm_db`         IBM Db2 connectivity

The reviewed screenplay-processing and BM25 retrieval paths do not
require an LLM.

## Project files

Keep the application and its required helper modules together in the
project directory.

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `app.py`                            Main Streamlit application and
                                      workflow tabs

  `smart_audition_search.py`          Haystack BM25 retrieval helper

  `db2_store.py`                      Db2 connection, table
                                      initialization, synchronization,
                                      and read helpers

  `requirements.txt`                  Python dependency declarations

  `rasaai_audition_library.json`      Local audition library created/used
                                      by the application
  -----------------------------------------------------------------------

The application may create additional local data, backup, or export
files while it runs. Preserve the existing project data when updating
application files.

------------------------------------------------------------------------

## Using the deployed application

If you are using a hosted RASA AI deployment, open the application URL in a modern web browser. No local installation of Python, Streamlit, Haystack, OpenCV, MediaPipe, or the other application dependencies is required for ordinary users.

The application and its Python dependencies run in the deployment environment. Users interact with the application through the browser.

The deployed application must have been built with the project's required dependencies and configured with any server-side settings needed for the enabled features. Availability of optional analysis or database features depends on the deployment configuration.

## Local development setup

This section is for developers who want to run, test, or modify RASA AI on their own machine. It is not a setup requirement for users of the deployed application.

### Requirements and prerequisites

Before starting local development, ensure that you have:

- Python version compatible with the packages in `requirements.txt`.
- A copy of the RASA AI project.
- A terminal opened in the directory containing `app.py` and `requirements.txt`.
- Permission to install the project dependencies.
- For Db2 features, network access to the configured Db2 instance and valid connection details.

Optional features such as vocal analysis or experimental facial-expression labels require their corresponding dependencies and any required model assets to be available in the local Python environment.

### Install dependencies — Windows PowerShell

Open PowerShell in the RASA AI project directory (the directory containing `app.py` and `requirements.txt`).

**1. Create a Python 3.12 virtual environment**

Python 3.12 is recommended for compatibility with the pinned project dependencies.

```powershell
py -3.12 -m venv .venv
```

**2. Activate the virtual environment**

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**3. Verify Python**

```powershell
python --version
```

Expected version: `Python 3.12.x`

**4. Upgrade pip and install dependencies**

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Wait until the installation completes successfully before proceeding.

### Install dependencies — macOS / Linux

From the RASA AI project directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate

python --version

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Use Python 3.12 and the same virtual environment when running the application.

### Run RASA AI locally

With the virtual environment activated, run the command from the directory containing `app.py`:

```bash
python -m streamlit run app.py
```

Streamlit prints a local URL in the terminal. Open that URL in your browser. To stop the application, return to the terminal and press `Ctrl+C`.

> **Important:** Run the command from the directory that actually contains `app.py`. If `app.py` is in a subdirectory, change into that directory first or provide the correct relative path.

### Gmail OTP Configuration (Local Setup)

Reviewers running RASA AI locally must configure their own Gmail SMTP credentials to enable email OTP verification.

**1. Create the configuration directory**

Inside the `rasa-ai` project directory, create:

`.streamlit`

**2. Create the secrets file**

Inside `.streamlit`, create:

`secrets.toml`

**3. Add your Gmail credentials**

```toml
GMAIL_ADDRESS = "yourname@gmail.com"
GMAIL_APP_PASSWORD = "your-16-character-gmail-app-password"
```

**4. Generate Gmail App Password**

1. Use your own Gmail account.
2. Enable Google 2-Step Verification.
3. Generate a Gmail App Password.
4. Add your email address and App Password to `secrets.toml`.

**5. Launch RASA AI**

```powershell
python -m streamlit run app.py
```

Alternatively, reviewers can access the deployed application without performing the local installation:

https://db2hack2026-9gfducsfracrhhqecjey2j.streamlit.app/

**Security Notice:** Never share your regular Gmail password or commit actual SMTP credentials or `secrets.toml` to GitHub. Each reviewer must configure their own credentials for local email OTP verification.

## Haystack retrieval

Haystack is an application dependency, not a separate installation step for end users. The deployed environment must install a compatible Haystack 2.x version as part of the application's dependencies (normally through `requirements.txt`). When the deployed application is running with that dependency available, users can access the retrieval feature through the RASA AI interface without installing Haystack on their own devices.

For local development, install the dependencies from `requirements.txt`. If Haystack is missing from the active local environment, install a compatible 2.x release:

```bash
python -m pip install "haystack-ai>=2.0,<3"
```

The `smart_audition_search.py` helper must be available to the application (in the same project directory as `app.py`, unless another import path is configured). Search results depend on saved audition records; an empty library will not produce audition matches.

## IBM Db2 integration

### Connection configuration

The connector reads connection settings from environment variables. Configure these values in the environment where the RASA AI server process runs.

- **Deployed application:** Add the Db2 settings using the hosting platform's environment-variable or secrets configuration. Do not ask ordinary application users to enter database credentials.
- **Local development:** Set the variables in the same terminal session used to start Streamlit, as shown below.

**Note:** IBM Db2 integration is optional for launching and exploring the main RASA AI application. Reviewers who want to test the Db2 Database workflow must configure their own accessible Db2 instance and valid connection credentials. The application does not require reviewers to use the developer's personal database credentials.

Windows PowerShell:

``` powershell
$env:DB2_HOST = "your-db2-host"
$env:DB2_PORT = "50000"
$env:DB2_DATABASE = "your-database"
$env:DB2_USER = "your-username"
$env:DB2_PASSWORD = "your-password"
$env:DB2_SSL = "true"
```

macOS / Linux:

``` bash
export DB2_HOST="your-db2-host"
export DB2_PORT="50000"
export DB2_DATABASE="your-database"
export DB2_USER="your-username"
export DB2_PASSWORD="your-password"
export DB2_SSL="true"
```

Replace the example values with the connection details supplied for your
Db2 instance. `DB2_PORT` defaults to `50000` in the reviewed connector.
Set `DB2_SSL` according to the requirements of your Db2 service.

Do not commit real credentials, paste passwords into shared logs, or
hard-code secrets in source files. Use the hosting platform's secrets
facility or a protected local environment configuration when
appropriate.

### Use the Db2 workflow

For a deployed application, configure the variables in the hosting environment and restart/redeploy the application as required by that platform. For local development, configure the variables in the terminal before starting Streamlit.

Then:

1. Open RASA AI.
2. Open the Db2 Database workflow in the application.
3. Run the connection check.
4. If using the audition-record connector, initialize `RASA_AUDITIONS` if needed.
5. Manually synchronize the local audition library if required.
6. Load recent Db2 records to inspect the read-back result.

The successful connection and actor-data SQL query execution in the
project environment are confirmed. The audition-table initialization,
manual audition-record upsert, and read-back are separate connector
operations and should each be tested in the target environment.

------------------------------------------------------------------------

## Data storage and privacy

-   The existing audition-library workflow stores saved audition records
    in a local JSON file.
-   Streamlit session state holds session-scoped workflow information.
-   Haystack's in-memory document store is rebuilt for a search
    operation.
-   Db2 is an additional, manually operated persistence path in the
    reviewed design; it does not automatically replace the local JSON
    source of truth.
-   The Db2 upsert workflow does not delete existing database rows.
-   Keep credentials outside source control.
-   Do not commit private audition recordings, personal information, or
    real database secrets to a public repository.
-   Obtain appropriate consent and follow applicable rules before
    processing or storing performer video/audio.
-   Restrict access to audition data and retain or delete it according
    to the applicable project or organizational policy.
-   Back up local audition data before replacing files or changing
    storage behavior.

## Known limitations

-   RASA AI is a human decision-support tool, not an automated casting
    judge.
-   Screenplay parsing is deterministic and rule-based; it can miss
    context or produce incorrect candidate cues.
-   Scanned/image-only PDFs are not OCR-processed by the reviewed
    workflow.
-   Video measurements depend on visible landmarks and successful
    tracking.
-   Optional facial-expression labels are experimental and may be
    inaccurate or biased.
-   Vocal features describe acoustic signals; they do not establish a
    person's internal emotional state.
-   Timestamp alignment does not verify lip synchronization.
-   Haystack BM25 is keyword retrieval, not semantic/vector search.
    Queries may miss records when relevant wording does not overlap.
-   Haystack's document store is in memory and rebuilt for a search
    operation.
-   Search history is session-only.
-   The local JSON library remains the source of truth; Db2
    synchronization is manual.
-   The reviewed Db2 connector uses Db2 LUW-style catalog SQL. Other Db2
    editions may require changes and separate validation.

## Troubleshooting

### `File does not exist: app.py`

The terminal is not in the directory containing `app.py`. Navigate to
the correct project directory and run:

``` bash
python -m streamlit run app.py
```

If `app.py` is inside a subdirectory, run the command from that
subdirectory or specify its relative path.

### `ModuleNotFoundError: No module named 'smart_audition_search'`

Confirm that `smart_audition_search.py` is present in the expected
project directory and that Streamlit is running with the same Python
environment in which the project dependencies were installed.

### MediaPipe installation error

If dependency installation fails with an error such as:

`No matching distribution found for mediapipe==0.10.21`

Check your active Python version:

```powershell
python --version
```

The recommended project environment uses Python 3.12.

If you created the virtual environment with an incompatible Python version:

1. Deactivate the current environment:

```powershell
deactivate
```

2. Remove the old `.venv` directory.
3. Recreate it using Python 3.12:

```powershell
py -3.12 -m venv .venv
```

4. Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

5. Reinstall the project dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Haystack import or retrieval errors

Activate the project's virtual environment and install a compatible
Haystack 2.x release:

``` bash
python -m pip install "haystack-ai>=2.0,<3"
```

Then verify the helper import using the command in the [Haystack
retrieval](#haystack-retrieval) section.

### Db2 connection errors

-   Confirm that the Db2 instance is running and reachable from the
    machine running RASA AI.
-   Verify the host, port, database name, username, and password.
-   Confirm whether the service requires SSL and configure `DB2_SSL`
    accordingly.
-   Check network and firewall access.
-   Confirm that `ibm_db` is installed in the active Python environment.
-   Do not expose passwords in source code, screenshots, or shared logs.

### No audition records appear in search

Haystack searches saved audition records. Analyze and save at least one
audition to the local library, then run the search again.

### No records appear in Db2 read-back

Confirm that the Db2 connection succeeded, that the audition table is
initialized in the expected schema, and that a manual synchronization
has completed. A successful connection alone does not mean audition
records have been inserted.

------------------------------------------------------------------------

## Project status

RASA AI brings together screenplay cue extraction, reviewer-defined role
requirements, visual and optional vocal evidence analysis, a
timestamp-based evidence timeline, local audition management, Haystack
BM25 retrieval, and an IBM Db2 connector.

Db2 connectivity and actor-data query execution have been confirmed in
the project environment. The optional audition-table synchronization and
read-back workflow should be validated independently before being
treated as verified in another environment.

The application is intended to support transparent, evidence-informed
human review. It does not replace professional casting judgment.
