# RASA AI --- Audition Intelligence & Casting Support

RASA AI is a Streamlit-based audition review and performance-evidence
workspace. It helps filmmakers and casting teams organize screenplay
context, define role requirements, inspect observable visual and vocal
evidence, compare auditions, and retrieve saved audition records.

> **Important:** RASA AI is a human decision-support tool. Its
> computer-vision measurements, optional expression labels, vocal
> features, and text-retrieval scores are experimental signals---not
> validated measures of acting quality, personality, emotion, diagnosis,
> or role suitability. Casting decisions must remain with qualified
> human reviewers.

## Table of contents

-   [Core features](#core-features)
-   [Application workflow](#application-workflow)
-   [Technology stack](#technology-stack)
-   [Project files](#project-files)
-   [Installation](#installation)
-   [Run locally](#run-locally)
-   [Haystack Retrieval setup](#haystack-retrieval-setup)
-   [Optional Db2 database
    integration](#optional-db2-database-integration)
-   [Data and privacy](#data-and-privacy)
-   [Known limitations](#known-limitations)
-   [Troubleshooting](#troubleshooting)

## Core features

### 1. Screenplay analysis

-   Enter a story or screenplay as text, or upload a text-based PDF.
-   Extract selectable text from PDFs using `pypdf`.
-   Use deterministic, rule-based text analysis to identify role and
    scene cues.
-   Review character candidates and suggested audition tests.
-   Download screenplay analysis as JSON.

Scanned/image-only PDFs require OCR, which is not included in the
current workflow.

### 2. Character cues

-   Inspect candidate characters and cues extracted from the screenplay.
-   Review the evidence and suggested audition-test context before
    defining role requirements.

The results are rule-based suggestions, not a full semantic
understanding of a screenplay.

### 3. Role requirements

-   Define the requirements for a role.
-   Create a character emotion-performance brief to guide human review
    of the intended portrayal.
-   Compare observed audition evidence against the role requirements.
-   Keep the intended portrayal separate from any model-generated visual
    label.

### 4. Video analysis

-   Upload an audition video and label the actor/audition.
-   Run local computer-vision analysis of sampled video frames.
-   Calculate observable pose/movement and facial-geometry features when
    the relevant landmarks are visible.
-   Review timestamped observations and evidence-quality notes.
-   Optionally enable experimental facial-expression labels if the
    optional `fer` package/model is installed.
-   Save completed audition reports to the local audition library.

Measurements are sensitive to lighting, framing, camera angle,
occlusion, speech, tracking quality, and scene context. Facial geometry
values are not emotion labels. Optional expression classifications can
be wrong and should only prompt manual review.

### 5. Vocal analysis

-   Run experimental, audio-only analysis when the required audio
    tooling is installed.
-   Inspect acoustic summaries and timestamped vocal evidence.
-   Review pitch and signal-energy patterns where available.
-   Download vocal-analysis output as JSON.

Vocal measurements are acoustic features and should not be treated as a
reliable detector of emotion, intent, or acting ability.

### 6. Combined evidence timeline

-   Combine video and vocal evidence generated during the current
    session.
-   Inspect evidence along a shared timeline when both analyses are
    available.
-   Use timestamps as review aids rather than automated judgments.

### 7. Audition library and comparison

The Video Analysis workflow includes library management and review
tools:

-   Save analyzed auditions locally for future sessions.
-   Review saved audition reports.
-   Compare multiple auditions and inspect observable metrics.
-   Filter the library by text, character, review status, and shortlist
    state where available.
-   Add or update reviewer decisions, shortlist markers, and reviewer
    notes.
-   Export audition information and individual reports where offered by
    the UI.
-   Remove a saved audition from the local library when required.

The shortlist marker is human-managed; it is not an automated casting
recommendation.

### 8. Haystack Retrieval

-   Search saved audition reports with Haystack 2.x BM25 keyword
    retrieval.
-   Retrieve relevant records using actor labels, character details,
    reviewer notes, status, and available analysis fields.
-   Narrow results with character, review-status, and shortlisted-only
    filters.
-   Inspect the retrieved records and their BM25 scores.
-   Export the current retrieved result set to CSV.
-   View recent search history for the current Streamlit session and
    clear that history.

BM25 is keyword-based retrieval. Its score represents textual relevance
within the search---not acting quality, role fit, or the probability of
success. Search history is session-only and is not a permanent audit
log.

### 9. Optional Db2 Database integration

The Db2 Database tab provides an initial, optional persistence
connector:

-   Check whether the configured Db2 server is reachable.
-   Initialize the `RASA_AUDITIONS` table if it does not exist.
-   Manually upsert the local audition library into Db2.
-   Load recent audition records from Db2 and inspect stored payload
    data.
-   Store the complete audition record as JSON in a CLOB, alongside
    searchable summary columns.

**Current integration scope:** The local JSON audition library remains
the application's existing source of truth. Sync is manual, and the
connector does not delete database rows or automatically switch the rest
of the app to Db2. A live cloud connection has not been verified yet.
The initial connector uses Db2 LUW catalog SQL; other Db2 editions may
require adjustments.

## Application workflow

A typical workflow is:

1.  Add a screenplay or story.
2.  Review character cues and define role requirements.
3.  Upload and analyze an audition video.
4.  Optionally analyze the audition audio.
5.  Inspect the combined evidence timeline and compare auditions.
6.  Add reviewer notes, review status, and shortlist decisions.
7.  Use Haystack Retrieval to find relevant saved records.
8.  Optionally configure Db2 and manually sync audition records.

## Technology stack

-   **Python**
-   **Streamlit** --- web UI
-   **pypdf** --- extraction of selectable text from PDFs
-   **OpenCV** --- video frame handling
-   **MediaPipe** --- pose/landmark analysis
-   **NumPy** --- numerical operations
-   **librosa** --- optional vocal/acoustic analysis
-   **FER** --- optional experimental facial-expression labels
-   **Haystack 2.x** --- BM25 keyword retrieval
-   **ibm_db** --- optional Db2 connectivity

The current screenplay analysis is deterministic/rule-based; Haystack
retrieval does not require an LLM.

## Project files

Keep these files together in the project directory:

  -----------------------------------------------------------------------
  File                                Purpose
  ----------------------------------- -----------------------------------
  `app.py`                            Main Streamlit application and
                                      workflow tabs

  `smart_audition_search.py`          Haystack BM25 retrieval helper

  `db2_store.py`                      Optional Db2 connection, table
                                      initialization, sync, and read
                                      helpers

  `requirements.txt`                  Python dependencies
  -----------------------------------------------------------------------

The app also uses local files/directories for its audition library and
generated data. Back up the project and local data before replacing
files or changing storage behavior.

## Installation

Use a supported Python environment compatible with the installed
dependencies. On Windows PowerShell, from the project folder:

``` powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation in the current terminal, you can use the
process-scoped execution policy for that terminal only:

``` powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Do not install packages into a different Python environment from the one
used to run Streamlit.

## Run locally

From the project directory with the virtual environment activated:

``` powershell
streamlit run app.py
```

Streamlit prints a local URL in the terminal. Open that URL in your
browser.

## Haystack Retrieval setup

Install Haystack 2.x if it is not already in the active environment:

``` powershell
python -m pip install "haystack-ai>=2.0,<3"
```

Confirm the helper can be imported:

``` powershell
python -c "from smart_audition_search import search_auditions; print('Haystack helper import OK')"
```

The helper file must be in the same directory as `app.py`. Search
results depend on saved audition records; an empty library will not
return audition matches.

## Optional Db2 Database integration

The Db2 connector requires access to a Db2 instance and valid connection
details. Do not set placeholders as real credentials.

Set environment variables in the same PowerShell session before
launching Streamlit:

``` powershell
$env:DB2_HOST = "your-db2-host"
$env:DB2_PORT = "50000"
$env:DB2_DATABASE = "your-database"
$env:DB2_USER = "your-username"
$env:DB2_PASSWORD = "your-password"
$env:DB2_SSL = "true"
```

Use the host, port, database name, username, password, and TLS
instructions supplied by your Db2 provider. Do not share passwords in
chat, commit them to source control, or hard-code them in Python files.

Then:

1.  Start RASA AI with `streamlit run app.py`.
2.  Open **Db2 Database**.
3.  Select **Check Db2 connection**.
4.  Select **Initialize audition table**.
5.  Select **Sync local audition library to Db2**.
6.  Select **Load recent Db2 records** to inspect records read back.

The first connector implementation targets Db2 LUW-style catalog
queries. Confirm compatibility with your chosen Db2 service before
relying on it. Do not treat the feature as production-ready until
connection, schema creation, synchronization, and read-back have been
tested against the real instance.

## Data and privacy

-   Audition records are stored locally by the existing application
    workflow; back up local data files.
-   Db2 is optional and synchronization is manual in the current
    implementation.
-   Sync performs upserts for records sent to Db2; it does not delete
    database rows.
-   Keep database credentials in environment variables or a secrets
    manager.
-   Do not commit credentials, private audition videos, or personal
    information to Git.
-   Obtain appropriate consent and follow applicable rules before
    processing or storing performer video/audio.
-   Limit access to audition data and remove it when no longer needed
    under your organization's retention policy.

## Known limitations

-   The system is a decision-support aid, not an automated casting
    judge.
-   Computer-vision results can be affected by camera placement,
    lighting, occlusion, framing, movement, and tracking errors.
-   Optional facial-expression labels are probabilistic and may be
    inaccurate or biased.
-   Vocal features describe acoustic signals and do not establish
    internal emotional state.
-   Screenplay parsing uses deterministic rules and may miss context or
    interpret phrases incorrectly.
-   OCR for scanned PDFs is not included.
-   Haystack BM25 is keyword retrieval, not semantic understanding;
    synonyms may not match unless terms overlap.
-   Search history is session-only.
-   Db2 cloud connectivity has not yet been verified; credentials and
    service-specific settings must be configured first.
-   The app's existing local library is not automatically replaced by
    Db2.

## Troubleshooting

### `ModuleNotFoundError: No module named 'smart_audition_search'`

Make sure `smart_audition_search.py` is saved beside `app.py`, then run
Streamlit from that project directory.

### Haystack is unavailable in the app

Activate the correct virtual environment and run:

``` powershell
python -m pip install "haystack-ai>=2.0,<3"
```

### Db2 connection fails

-   Confirm the Db2 instance is running and reachable from your machine.
-   Check the hostname, port, database name, and username.
-   Confirm whether the provider requires TLS and set `DB2_SSL`
    accordingly.
-   Ensure the current network or firewall permits the connection.
-   Check that the IBM Db2 driver installed successfully.
-   Do not paste the password into shared logs or source code.

### No audition records appear

Analyze and save at least one audition in the Video Analysis workflow.
Haystack searches saved records; the Db2 tab only shows database records
after a successful connection and read operation.

------------------------------------------------------------------------

## Project status

RASA AI currently combines screenplay cue extraction, role-requirement
planning, local visual and vocal evidence analysis, audition review and
comparison, Haystack BM25 retrieval, and an initial optional Db2
connector. Before deployment or production use, validate the complete
workflow in the target environment, including dependencies, storage,
privacy controls, and a live Db2 integration test.
