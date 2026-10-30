import io
import json
import html
import zipfile
import csv
import os
import re
import shutil
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st
from pypdf import PdfReader

try:
    from smart_audition_search import search_auditions as haystack_search_auditions
    HAYSTACK_SEARCH_IMPORT_ERROR = None
except Exception as exc:
    haystack_search_auditions = None
    HAYSTACK_SEARCH_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

st.set_page_config(page_title="RASA AI | Casting Performance Analysis", page_icon="🎬", layout="wide")

st.markdown("""
<style>
:root {
    color-scheme: dark;
}
.stApp {
    background:
        radial-gradient(ellipse at 10% 0%, rgba(77, 91, 190, 0.14), transparent 38%),
        linear-gradient(145deg, #0b0f17 0%, #101521 52%, #0b1018 100%);
    color: #edf2ff;
}
.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1, h2, h3, h4 {
    color: #f4f6ff !important;
    letter-spacing: -0.025em;
}
h1 {
    font-weight: 800 !important;
    font-size: clamp(2.5rem, 5vw, 3.6rem) !important;
    background: linear-gradient(90deg, #ffffff 0%, #b9c8ff 55%, #83e5dc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: .15rem;
}
h2 {
    font-weight: 720 !important;
    border-bottom: 1px solid rgba(148, 163, 184, .2);
    padding-bottom: .55rem;
    margin-top: 1.1rem !important;
}
h3 {
    font-weight: 650 !important;
}
p, label, .stMarkdown, .stCaption, [data-testid="stWidgetLabel"] {
    color: #d4dced;
}
[data-testid="stCaptionContainer"] p {
    color: #9eabc2 !important;
}
[data-testid="stAlert"] {
    border-radius: 14px;
    border: 1px solid rgba(129, 153, 205, .22);
}
div[data-testid="stTabs"] > div:first-child {
    gap: .4rem;
    border-bottom: 1px solid rgba(148, 163, 184, .22);
}
div[data-testid="stTabs"] button[role="tab"] {
    color: #b8c5dc;
    background: rgba(255,255,255,.025);
    border-radius: 10px 10px 0 0;
    padding: .75rem 1rem;
    font-weight: 650;
    transition: all .18s ease;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #ffffff;
    background: rgba(125, 145, 255, .10);
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #ffffff;
    background: linear-gradient(180deg, rgba(108, 128, 255, .18), rgba(108, 128, 255, .05));
    border-bottom: 3px solid #8ea0ff;
}
div[data-testid="stTabs"] [data-testid="stTabContent"] {
    padding-top: 1.25rem;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(148, 163, 184, .22);
    border-radius: 12px;
    background: rgba(255,255,255,.025);
}
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    border: 1px solid rgba(151, 166, 255, .45);
    background: linear-gradient(135deg, #5969d9, #4253b7);
    color: white;
    font-weight: 650;
    padding: .55rem 1rem;
    transition: transform .15s ease, filter .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #aab5ff;
    filter: brightness(1.12);
    transform: translateY(-1px);
}
input, textarea, [data-baseweb="select"] > div {
    border-radius: 10px !important;
}
hr {
    border-color: rgba(148, 163, 184, .18);
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid rgba(148, 163, 184, .18);
    border-radius: 12px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)


# Audition comparisons persist locally beside app.py. No cloud service is used.
AUDITION_LIBRARY_PATH = Path(__file__).resolve().parent / "rasaai_audition_library.json"
AUDITION_HISTORY_DIR = Path(__file__).resolve().parent / "rasaai_audition_history"
AUDITION_ACTIVITY_PATH = Path(__file__).resolve().parent / "rasaai_audition_activity.json"
MAX_LIBRARY_SNAPSHOTS = 20


def load_audition_library():
    """Load saved audition reports, returning an empty list if no library exists yet."""
    try:
        if AUDITION_LIBRARY_PATH.exists():
            with AUDITION_LIBRARY_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read the local audition library: {exc}")
    return []


def create_library_snapshot():
    """Preserve the current library before it is overwritten."""
    if not AUDITION_LIBRARY_PATH.exists():
        return
    AUDITION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    snapshot_path = AUDITION_HISTORY_DIR / f"audition_library_{stamp}.json"
    shutil.copy2(AUDITION_LIBRARY_PATH, snapshot_path)
    snapshots = sorted(
        AUDITION_HISTORY_DIR.glob("audition_library_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_snapshot in snapshots[MAX_LIBRARY_SNAPSHOTS:]:
        old_snapshot.unlink(missing_ok=True)


def list_library_snapshots():
    """Return newest snapshots first."""
    if not AUDITION_HISTORY_DIR.exists():
        return []
    return sorted(
        AUDITION_HISTORY_DIR.glob("audition_library_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def save_audition_library(items):
    """Persist JSON and snapshot the previous version before overwriting it."""
    try:
        AUDITION_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if AUDITION_LIBRARY_PATH.exists():
            create_library_snapshot()
        temp_path = AUDITION_LIBRARY_PATH.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(items, handle, indent=2, ensure_ascii=False)
        temp_path.replace(AUDITION_LIBRARY_PATH)
        return True
    except OSError as exc:
        st.error(f"Could not save the local audition library: {exc}")
        return False



def run_local_health_checks():
    """Return simple local environment checks without changing application data."""
    checks = []
    import sys
    checks.append({
        "Check": "Python version",
        "Status": "Pass" if sys.version_info >= (3, 10) else "Warning",
        "Details": sys.version.split()[0],
    })
    for module_name, label in [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("mediapipe", "MediaPipe"),
        ("streamlit", "Streamlit"),
        ("pypdf", "pypdf"),
    ]:
        try:
            module = __import__(module_name)
            checks.append({
                "Check": f"{label} import",
                "Status": "Pass",
                "Details": str(getattr(module, "__version__", "version not exposed")),
            })
        except Exception as exc:
            checks.append({
                "Check": f"{label} import",
                "Status": "Fail",
                "Details": f"{type(exc).__name__}: {exc}",
            })
    try:
        test_path = AUDITION_LIBRARY_PATH.parent / ".rasaai_write_test.tmp"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        checks.append({
            "Check": "Project folder write access",
            "Status": "Pass",
            "Details": str(AUDITION_LIBRARY_PATH.parent),
        })
    except OSError as exc:
        checks.append({
            "Check": "Project folder write access",
            "Status": "Fail",
            "Details": f"{type(exc).__name__}: {exc}",
        })
    return checks

def load_audition_activity():
    """Load the local activity log, returning an empty list if it is not present."""
    try:
        if AUDITION_ACTIVITY_PATH.exists():
            with AUDITION_ACTIVITY_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return [entry for entry in data if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read the local activity log: {exc}")
    return []


def record_audition_activity(action, item, details=None):
    """Append a minimal local event for important library/review actions."""
    try:
        events = load_audition_activity()
        events.append({
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "action": str(action),
            "actor_label": item.get("actor_label") or item.get("video_file") or "Unnamed audition",
            "character": item.get("selected_character") or "Unassigned",
            "review_status": item.get("reviewer_decision", "Not reviewed"),
            "shortlisted": bool(item.get("shortlisted", False)),
            "details": str(details or ""),
        })
        AUDITION_ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = AUDITION_ACTIVITY_PATH.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(events[-1000:], handle, indent=2, ensure_ascii=False)
        temp_path.replace(AUDITION_ACTIVITY_PATH)
        return True
    except OSError as exc:
        st.warning(f"Could not write the local activity log: {exc}")
        return False


def build_audition_html_report(item):
    """Build a standalone, downloadable HTML report for one saved audition."""
    def safe(value):
        if value is None or value == "":
            return "Not available"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        return html.escape(str(value)).replace("\\n", "<br>")

    actor = item.get("actor_label") or item.get("video_file") or "Unnamed audition"
    character = item.get("selected_character") or "Unassigned"
    pose_rate = item.get("pose_detection_rate")
    pose_percent = f"{pose_rate * 100:.1f}%" if isinstance(pose_rate, (int, float)) else "Not available"
    evidence_notes = item.get("evidence_quality_notes", [])
    metric_keys = [
        ("Duration (seconds)", "duration_seconds_estimate"),
        ("Pose detection rate", None),
        ("Normalized landmark movement index", "mean_normalized_landmark_movement_index"),
        ("Mean shoulder tilt index", "mean_shoulder_tilt_index"),
        ("Torso lateral offset", "mean_torso_lateral_offset"),
        ("Samples with wrist above shoulder", "fraction_samples_with_wrist_above_shoulder"),
    ]
    metric_rows = []
    for label, key in metric_keys:
        value = pose_percent if key is None else item.get(key)
        metric_rows.append(f"<tr><th>{safe(label)}</th><td>{safe(value)}</td></tr>")

    notes_html = "".join(f"<li>{safe(note)}</li>" for note in evidence_notes) or "<li>No evidence-quality notes recorded.</li>"
    reviewer_notes = safe(item.get("reviewer_notes", ""))
    timestamp_rows = item.get("samples", item.get("timestamped_samples", []))
    if not isinstance(timestamp_rows, list):
        timestamp_rows = []
    sample_html = ""
    if timestamp_rows:
        keys = list(timestamp_rows[0].keys()) if isinstance(timestamp_rows[0], dict) else []
        if keys:
            header = "".join(f"<th>{safe(key)}</th>" for key in keys)
            body = "".join(
                "<tr>" + "".join(f"<td>{safe(row.get(key))}</td>" for key in keys) + "</tr>"
                for row in timestamp_rows if isinstance(row, dict)
            )
            sample_html = f"<h2>Timestamped observations</h2><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RasaAI Audition Review — {safe(actor)}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#202124;line-height:1.5}}
h1,h2{{color:#202124}} .meta{{color:#5f6368}} table{{border-collapse:collapse;width:100%;margin:12px 0 24px}}
th,td{{border:1px solid #dadce0;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
th{{background:#f1f3f4}} .notice{{border-left:4px solid #888;padding:10px 14px;background:#f8f9fa}}
@media print{{body{{margin:0;max-width:none}}}}
</style></head><body>
<h1>RasaAI — Audition Review Report</h1>
<p class="meta">Generated from the local audition library. This report supports human review and is not an automated casting decision.</p>
<h2>Audition details</h2>
<table><tbody>
<tr><th>Actor / label</th><td>{safe(actor)}</td></tr>
<tr><th>Character</th><td>{safe(character)}</td></tr>
<tr><th>Video file</th><td>{safe(item.get("video_file"))}</td></tr>
<tr><th>Review status</th><td>{safe(item.get("reviewer_decision", "Not reviewed"))}</td></tr>
<tr><th>Shortlisted</th><td>{safe(bool(item.get("shortlisted", False)))}</td></tr>
<tr><th>Reviewer notes</th><td>{reviewer_notes}</td></tr>
</tbody></table>
<h2>Observable measurements</h2><table><tbody>{''.join(metric_rows)}</tbody></table>
<h2>Evidence-quality notes</h2><ul>{notes_html}</ul>
{sample_html}
<div class="notice"><strong>Limitations:</strong> Measurements are exploratory and sensitive to framing, lighting, occlusion, clip duration, and pose-detector limitations. They do not establish talent, emotion, personality, or casting suitability. Human review is required.</div>
</body></html>"""


def create_library_backup_bytes(items):
    """Serialize the current library into a versioned backup file."""
    payload = {
        "format": "rasaai-audition-library-backup",
        "schema_version": 1,
        "created_at_local": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "record_count": len(items),
        "auditions": items,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def parse_library_backup(uploaded_file):
    """Validate a backup before any restore operation is allowed."""
    try:
        payload = json.loads(uploaded_file.getvalue().decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"Backup is not valid UTF-8 JSON: {exc}"

    if not isinstance(payload, dict):
        return None, "Backup must be a JSON object."
    if payload.get("format") != "rasaai-audition-library-backup":
        return None, "This file is not a recognized RasaAI audition-library backup."
    if payload.get("schema_version") != 1:
        return None, "This backup uses an unsupported schema version."
    auditions = payload.get("auditions")
    if not isinstance(auditions, list) or not all(isinstance(item, dict) for item in auditions):
        return None, "Backup auditions must be a list of JSON objects."

    return auditions, None


def audition_record_key(item):
    """Return a conservative duplicate key for a saved audition."""
    return (
        str(item.get("actor_label") or "").strip().casefold(),
        str(item.get("video_file") or "").strip().casefold(),
        str(item.get("selected_character") or "").strip().casefold(),
    )


def inspect_audition_library(items):
    """Report likely duplicates and incomplete records without changing data."""
    duplicate_groups = {}
    incomplete = []
    for index, item in enumerate(items):
        key = audition_record_key(item)
        # Do not flag records with no identifying information as duplicates of one another.
        if any(key):
            duplicate_groups.setdefault(key, []).append(index)

        missing = []
        if not item.get("video_file"):
            missing.append("video filename")
        if not item.get("selected_character"):
            missing.append("character assignment")
        if not isinstance(item.get("pose_detection_rate"), (int, float)):
            missing.append("pose detection rate")
        if not item.get("analysis_method"):
            missing.append("analysis method metadata")
        if missing:
            incomplete.append({"index": index, "item": item, "missing": missing})

    duplicates = [
        {"indices": indices, "items": [items[index] for index in indices]}
        for indices in duplicate_groups.values() if len(indices) > 1
    ]
    return duplicates, incomplete


def build_audition_export_bundle(items):
    """Build a ZIP with the saved library, summary CSV/JSON, and per-audition HTML reports."""
    buffer = io.BytesIO()
    summary_rows = []
    for index, item in enumerate(items, start=1):
        pose_rate = item.get("pose_detection_rate")
        summary_rows.append({
            "Record": index,
            "Actor / label": item.get("actor_label") or item.get("video_file") or "Unnamed audition",
            "Character": item.get("selected_character") or "Unassigned",
            "Review status": item.get("reviewer_decision", "Not reviewed"),
            "Shortlisted": bool(item.get("shortlisted", False)),
            "Reviewer notes": item.get("reviewer_notes", ""),
            "Duration (s)": item.get("duration_seconds_estimate"),
            "Pose detection (%)": round(pose_rate * 100, 1)
            if isinstance(pose_rate, (int, float)) else None,
            "Video file": item.get("video_file", ""),
        })

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "rasaai_audition_library_backup.json",
            create_library_backup_bytes(items),
        )

        csv_buffer = io.StringIO(newline="")
        fieldnames = list(summary_rows[0].keys()) if summary_rows else [
            "Record", "Actor / label", "Character", "Review status",
            "Shortlisted", "Reviewer notes", "Duration (s)",
            "Pose detection (%)", "Video file",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
        archive.writestr("audition_summary.csv", csv_buffer.getvalue().encode("utf-8-sig"))

        archive.writestr(
            "audition_summary.json",
            json.dumps({
                "total_saved_auditions": len(items),
                "auditions": summary_rows,
            }, indent=2, ensure_ascii=False),
        )

        for index, item in enumerate(items, start=1):
            label = item.get("actor_label") or item.get("video_file") or f"audition_{index}"
            safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label)).strip("_") or f"audition_{index}"
            archive.writestr(
                f"individual_reports/{index:03d}_{safe_label}.html",
                build_audition_html_report(item),
            )
    return buffer.getvalue()


if "rasa_audition_comparisons" not in st.session_state:
    st.session_state["rasa_audition_comparisons"] = load_audition_library()

st.title("RASA AI")
st.subheader("The essence of a performance, explored through story and evidence.")
st.caption("Inspired by Rasa—the essence or emotional flavour of a story and its performance. Screenplay cues · Body movement · Facial features · Vocal patterns.")

workflow_tabs = st.tabs([
    "Screenplay",
    "Character Cues",
    "Role Requirements",
    "Video Analysis",
    "Vocal Analysis",
    "Evidence Timeline",
    "Haystack Retrieval",
    "Db2 Database",
])


# ---------- Traditional NLP / deterministic screenplay parsing ----------
ROLE_KEYWORDS = {
    "high movement": ["runs", "running", "chases", "fight", "fights", "jumps", "dances", "falls", "struggles", "moves quickly"],
    "hand gestures": ["points", "pointing", "gestures", "gesture", "waves", "waves a hand", "raises a hand", "raises his hand", "raises her hand", "clenches a fist", "reaches", "signals"],
    "stillness / controlled posture": ["stands still", "stands motionless", "sits silently", "freezes", "does not move", "remains motionless", "holds still", "standing still"],
    "physical tension": ["shakes", "shake", "trembles", "trembling", "tremble", "paces", "pacing", "clenches", "clenching", "tightens", "breathes heavily", "hands trembling"],
    "visible expression changes (review manually)": ["smiles", "laughs", "cries", "weeps", "frowns", "grimaces", "gasps"],
    "dialogue-heavy scene": ["says", "asks", "shouts", "whispers", "replies", "answers", "yells", "speaks"],
}
AUDITION_TESTS = {
    "high movement": "Perform the scripted physical action at a safe, controlled pace.",
    "hand gestures": "Deliver the same short line once with natural gestures and once with restrained gestures.",
    "stillness / controlled posture": "Deliver a short line while maintaining a deliberate, stable posture.",
    "physical tension": "Perform the scene using the written physical action; avoid forcing or exaggerating movement.",
    "visible expression changes (review manually)": "Perform the scene and have a human reviewer note visible expression changes in context.",
    "dialogue-heavy scene": "Read the same lines with the intended pacing and emphasis; review audio separately if needed.",
}



def extract_character_specific_cues(story, character_name):
    """Find keyword evidence near a character's name/cue lines; heuristic only."""
    lines = story.splitlines()
    name_re = re.compile(r"(?<!\w)" + re.escape(character_name) + r"(?!\w)", re.I)
    relevant_indices = set()
    for idx, line in enumerate(lines):
        if name_re.search(line):
            relevant_indices.update(range(max(0, idx - 2), min(len(lines), idx + 3)))
        # In screenplay format, the character cue is often on a line by itself,
        # with action text immediately before or after the dialogue block.
        if line.strip().casefold() == character_name.casefold():
            relevant_indices.update(range(max(0, idx - 3), min(len(lines), idx + 5)))
    context = "\n".join(lines[i] for i in sorted(relevant_indices))
    context_lower = context.lower()
    cues = []
    for label, words in ROLE_KEYWORDS.items():
        hits = [word for word in words if re.search(r"\b" + re.escape(word) + r"\b", context_lower)]
        if hits:
            cues.append({
                "requirement": label,
                "evidence_in_context": "Nearby text contains: " + ", ".join(hits[:4]),
                "context_excerpt": context[:500],
                "audition_test": AUDITION_TESTS[label],
                "status": "heuristic — verify manually"
            })
    return cues


def extract_pdf_text(uploaded_file):
    reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip(), len(reader.pages)


def normalize_name(name):
    name = re.sub(r"\([^)]*\)", "", name).strip(" .:-\t")
    name = re.sub(r"\s+", " ", name)
    return name[:60]


def parse_screenplay(story, manually_entered_names=""):
    """Heuristic parser only. Screenplay character cues are usually ALL CAPS on their own line."""
    lines = [line.rstrip() for line in story.splitlines()]
    names = []
    cue_pattern = re.compile(r"^[ \t]{0,12}([A-Z][A-Z0-9 ._'’-]{1,35})(?:\s*\([^)]*\))?[ \t]*$")
    excluded = {"INT", "EXT", "INT./EXT", "EXT./INT", "CUT TO", "FADE IN", "FADE OUT", "CONTINUED", "CONT'D", "THE END", "MONTAGE", "DAY", "NIGHT", "LATER", "CONTINUOUS"}
    for line in lines:
        stripped = line.strip()
        if not stripped or len(stripped) > 38:
            continue
        match = cue_pattern.match(line)
        if not match:
            continue
        raw = normalize_name(match.group(1))
        upper = raw.upper()
        if upper in excluded or upper.startswith(("INT. ", "EXT. ", "INT/EXT")):
            continue
        if not re.search(r"[A-Z]", upper):
            continue
        # Exclude common scene headings and transitions.
        if any(upper.startswith(prefix) for prefix in ["INT ", "EXT ", "FADE ", "CUT ", "DISSOLVE ", "SMASH CUT"]):
            continue
        # Avoid obvious action words; keep two-word names and likely cue names.
        if upper in {"CONTINUED", "CONTINUOUS", "SAME", "LATER", "DAY", "NIGHT", "MORNING", "EVENING"}:
            continue
        if raw not in names:
            names.append(raw.title() if raw.isupper() else raw)
    for raw in re.split(r"[,;\n]+", manually_entered_names or ""):
        name = normalize_name(raw)
        if name and name.lower() not in {n.lower() for n in names}:
            names.append(name)
    # Extract scene headings for a basic synopsis cue, not a generated summary.
    scene_count = sum(1 for line in lines if re.match(r"^\s*(INT\.|EXT\.|INT/EXT\.|INT\./EXT\.)", line, re.I))
    character_profiles = []
    lowered = story.lower()
    for name in names[:20]:
        # A rough, explicit frequency count. Not semantic understanding.
        mentions = len(re.findall(r"(?<!\w)" + re.escape(name) + r"(?!\w)", story, re.I))
        cues = extract_character_specific_cues(story, name)
        character_profiles.append({
            "name": name,
            "mention_count": mentions,
            "role_in_story": "Not inferred by this rule-based prototype",
            "character_description": "Not automatically inferred. Add a human-written description below if needed.",
            "performance_requirements": cues,
            "limitations": "Cues are matched from text near this character's name/cue lines. Proximity is heuristic and may still associate unrelated actions; verify manually."
        })
    return {
        "method": "Rule-based parsing; no LLM or trained semantic model",
        "story_characters": character_profiles,
        "screenplay_scene_heading_count": scene_count,
        "notes": [
            "Character candidates are detected from ALL-CAPS screenplay cue lines and/or names entered by the user.",
            "Prose stories may not contain screenplay-style character cues; enter character names manually in that case.",
            "Character cue matches use nearby text and are approximate; verify that each action belongs to the character.",
            "This tool does not infer personality, mental health, or internal emotion from appearance."
        ]
    }


def build_requirement_evidence(targets, video_report):
    """Compare role targets with observable video features; this is not a talent score."""
    movement = video_report.get("mean_normalized_landmark_movement_index")
    wrist_fraction = video_report.get("fraction_samples_with_wrist_above_shoulder")
    shoulder_tilt = video_report.get("mean_shoulder_tilt_index")
    evidence_rows = []
    for target in targets:
        observed = None
        metric = "Not available"
        interpretation = "No corresponding measurement is available."
        threshold = None
        if target == "More visible body movement":
            metric, observed, threshold = "Mean normalized landmark movement index", movement, 0.025
            if observed is None:
                interpretation = "Movement measurement unavailable."
            elif observed >= threshold:
                interpretation = "Movement index is at or above the exploratory threshold."
            else:
                interpretation = "Movement index is below the exploratory threshold."
        elif target == "Less visible body movement / controlled stillness":
            metric, observed, threshold = "Mean normalized landmark movement index", movement, 0.025
            if observed is None:
                interpretation = "Movement measurement unavailable."
            elif observed < threshold:
                interpretation = "Movement index is below the exploratory threshold."
            else:
                interpretation = "Movement index is at or above the exploratory threshold."
        elif target == "Frequent hands above shoulder level":
            metric, observed, threshold = "Fraction of sampled frames with a wrist above shoulder", wrist_fraction, 0.25
            if observed is None:
                interpretation = "Hand measurement unavailable."
            elif observed >= threshold:
                interpretation = "Wrist-above-shoulder observation is at or above the exploratory threshold."
            else:
                interpretation = "Wrist-above-shoulder observation is below the exploratory threshold."
        elif target == "More level shoulder alignment":
            metric, observed, threshold = "Mean shoulder tilt index", shoulder_tilt, 0.04
            if observed is None:
                interpretation = "Shoulder measurement unavailable."
            elif observed < threshold:
                interpretation = "Measured shoulder tilt is below the exploratory threshold."
            else:
                interpretation = "Measured shoulder tilt is at or above the exploratory threshold."
        evidence_rows.append({
            "Role requirement": target,
            "Measured feature": metric,
            "Observed value": round(observed, 4) if isinstance(observed, (int, float)) else observed,
            "Exploratory threshold": threshold,
            "Rule-based observation": interpretation,
        })
    return evidence_rows



def build_timestamped_evidence(targets, video_report):
    """Summarize timestamps where a measurable target's proxy is observed."""
    observations = video_report.get("sample_observations", [])
    rows = []
    for target in targets:
        matches = []
        for item in observations:
            if not item.get("pose_detected"):
                continue
            if target == "More visible body movement":
                value = item.get("movement_since_previous_sample_index")
                if isinstance(value, (int, float)) and value >= 0.025:
                    matches.append(item.get("timestamp_seconds"))
            elif target == "Less visible body movement / controlled stillness":
                value = item.get("movement_since_previous_sample_index")
                if isinstance(value, (int, float)) and value < 0.025:
                    matches.append(item.get("timestamp_seconds"))
            elif target == "Frequent hands above shoulder level" and item.get("wrist_above_shoulder") is True:
                matches.append(item.get("timestamp_seconds"))
            elif target == "More level shoulder alignment":
                value = item.get("shoulder_tilt_index")
                if isinstance(value, (int, float)) and value < 0.04:
                    matches.append(item.get("timestamp_seconds"))
        if matches:
            times = ", ".join(f"{t:.1f}s" for t in matches[:20] if isinstance(t, (int, float)))
            note = f"Proxy observed at {len(matches)} sampled timestamp(s): {times}"
            if len(matches) > 20:
                note += f" … (+{len(matches) - 20} more)"
        elif target in ("More visible body movement", "Less visible body movement / controlled stillness"):
            note = "No matching sampled movement observations were found. The first detected pose has no previous sample for comparison, and samples without comparable landmarks are omitted."
        else:
            note = "No matching observation found in sampled frames, or pose was not detected."
        rows.append({"Role requirement": target, "Timestamp evidence": note})
    return rows


# ---------- Story input ----------
with workflow_tabs[0]:
    st.header("Add a film story / screenplay")
    source = st.radio("Story input method", ["Paste story / screenplay", "Upload screenplay PDF"], horizontal=True)
    story_text = ""
    if source == "Paste story / screenplay":
        story_text = st.text_area("Paste screenplay text", height=230, placeholder="For best automatic character-cue detection, use screenplay format with character names on their own ALL-CAPS lines.")
    else:
        pdf = st.file_uploader("Upload screenplay PDF", type=["pdf"], key="story_pdf")
        if pdf:
            try:
                story_text, pages = extract_pdf_text(pdf)
                st.caption(f"Extracted selectable text from {pages} page(s). Scanned PDFs need OCR, which is not included.")
                with st.expander("Preview extracted text"):
                    st.text(story_text[:10000])
            except Exception as exc:
                st.error(f"Could not read PDF: {exc}")
    manual_names = st.text_input("Character names (optional; comma-separated)", placeholder="e.g. MAYA, ARJUN, INSPECTOR RAO")
    st.caption("Use this field if the story is prose, or if character names are not formatted as ALL-CAPS screenplay cues.")

    if st.button("Parse screenplay with rules", type="primary", disabled=len(story_text.strip()) < 20):
        st.session_state["rasa_story_report"] = parse_screenplay(story_text, manual_names)
        st.session_state["rasa_story_text"] = story_text

    story_report = st.session_state.get("rasa_story_report")

    # Keep the workflow numbering stable: sections 1–4 are always visible.
with workflow_tabs[1]:
    st.header("Character candidates and story cues")
    if story_report:
        st.write(f"Detected {len(story_report['story_characters'])} character candidate(s) and {story_report['screenplay_scene_heading_count']} scene heading(s).")
        for i, character in enumerate(story_report["story_characters"], 1):
            with st.expander(f"{i}. {character['name']} · {character['mention_count']} name mention(s)", expanded=(i == 1)):
                st.write(character["character_description"])
                st.caption(character["limitations"])
                if character["performance_requirements"]:
                    st.markdown("**Nearby screenplay cues (verify manually)**")
                    for req in character["performance_requirements"]:
                        st.markdown(f"- **{req['requirement']}**")
                        st.caption(req.get("evidence_in_context", req.get("evidence_in_story", "Keyword evidence found near this character; verify manually.")))
                        st.caption(f"Audition test: {req['audition_test']}")
                else:
                    st.write("No configured performance keywords were detected. Add explicit requirements manually during casting review.")
        for note in story_report["notes"]:
            st.caption("• " + note)
        st.download_button("Download screenplay analysis (JSON)", json.dumps(story_report, indent=2, ensure_ascii=False), "rasaai_screenplay_analysis.json", "application/json")
    else:
        st.info("This section will show detected character candidates and story cues after you enter a screenplay and click **Parse screenplay with rules**.")

    # ---------- Explicit role requirements for transparent matching ----------
with workflow_tabs[2]:
    st.header("Define role requirements")
    if story_report and story_report.get("story_characters"):
        st.write("Choose observable requirements for the selected role. These are filmmaker-defined targets, not automatically inferred acting judgments.")
        requirement_options = [
            "More visible body movement",
            "Less visible body movement / controlled stillness",
            "Frequent hands above shoulder level",
            "More level shoulder alignment",
            "Frequent mouth opening / visible mouth movement",
            "Greater variation in eye openness",
            "Greater variation in eyebrow-to-eye spacing",
        ]
        cue_to_targets = {
            "high movement": ["More visible body movement"],
            "stillness / controlled posture": ["Less visible body movement / controlled stillness"],
            "hand gestures": ["Frequent hands above shoulder level"],
        }
        role_requirements = {}
        for idx, character in enumerate(story_report["story_characters"]):
            with st.expander(f"Requirements for {character['name']}", expanded=(len(story_report["story_characters"]) == 1)):
                detected_cues = character.get("performance_requirements", [])
                suggested = []
                for cue in detected_cues:
                    suggested.extend(cue_to_targets.get(cue.get("requirement"), []))
                suggested = list(dict.fromkeys(suggested))
                if detected_cues:
                    st.caption("Text cues found near this character (verify manually): " + ", ".join(cue.get("requirement", "") for cue in detected_cues))
                if suggested:
                    st.info("Suggested measurable targets are preselected from nearby screenplay cues. Review them before using.")
                role_requirements[character["name"]] = st.multiselect(
                    "Select measurable audition targets",
                    requirement_options,
                    default=suggested,
                    key=f"role_requirements_{idx}_" + re.sub(r"[^a-zA-Z0-9_]", "_", character["name"]),
                    help="Targets map only to rough video measurements. They do not determine talent, emotion, personality, or casting suitability.",
                )
        st.session_state["rasa_role_requirements"] = role_requirements

        st.subheader("Character emotion-performance brief")
        st.caption("Choose the intended portrayal to create a human-review checklist. This is not an automatic emotion detector and does not diagnose the actor.")
        portrayal_options = [
            "Sadness / grief",
            "Anxiety / fear",
            "Anger / confrontation",
            "Joy / excitement",
            "Restrained / stoic performance",
            "Other / mixed emotional state",
        ]
        selected_portrayal = st.selectbox(
            "What emotional portrayal does the scene call for?",
            portrayal_options,
            key="rasa_character_portrayal_intent",
        )
        review_guides = {
            "Sadness / grief": [
                "Review whether facial changes, gaze and posture fit the scene context; do not treat lowered gaze or reduced movement as proof of sadness.",
                "Check the actor's choices at the relevant dialogue and action beats.",
                "Consider whether the performance changes appropriately across the scene rather than remaining uniformly still.",
            ],
            "Anxiety / fear": [
                "Review timing and context of visible facial and body changes.",
                "Check whether movement, gaze and pauses fit the character's stated objective and scene beats.",
                "Do not interpret eye openness or movement alone as proof of fear.",
            ],
            "Anger / confrontation": [
                "Review facial and body changes at confrontation beats.",
                "Check whether gesture intensity and timing fit the director's brief.",
                "Do not treat eyebrow spacing or mouth opening alone as proof of anger.",
            ],
            "Joy / excitement": [
                "Review visible facial changes and gesture timing in scene context.",
                "Check whether changes align with the character's reactions and dialogue.",
                "A smile or increased movement alone does not establish joy or convincing acting.",
            ],
            "Restrained / stoic performance": [
                "Review whether facial and body changes are controlled in the intended moments.",
                "Check for meaningful variation at scripted beats; low movement alone is not proof of restraint.",
                "Consider dialogue delivery and scene context during human review.",
            ],
            "Other / mixed emotional state": [
                "Write down the specific visible performance cues expected by the director.",
                "Review timestamped evidence against scene beats and dialogue.",
                "Do not infer an internal emotional state from facial geometry alone.",
            ],
        }
        st.markdown(f"**Human-review checklist for: {selected_portrayal}**")
        for guide in review_guides[selected_portrayal]:
            st.markdown(f"- {guide}")
        # The selectbox key already stores this value in session_state.
        # Do not assign to it after the widget has been instantiated.
    else:
        st.info("After screenplay parsing, this section will let you define measurable performance requirements for each detected character.")

    # ---------- Local computer vision ----------
with workflow_tabs[3]:
    st.header("Upload an actor audition video")
    st.write("Upload an audition clip with the actor's consent. RasaAI measures body movement and facial geometry. Optional FER mode adds model-estimated facial-expression labels for human review; these are uncertain visual predictions, not proof of internal emotion or acting ability.")
    character_options = [c["name"] for c in story_report.get("story_characters", [])] if story_report else []
    selected_character = st.selectbox("Character being auditioned for", character_options, key="selected_character") if character_options else st.text_input("Character being auditioned for", placeholder="Enter character name")
    actor_label = st.text_input("Actor / audition label", placeholder="e.g., Audition A or actor name", key="rasa_actor_label")
    actor_video = st.file_uploader("Choose actor video", type=["mp4", "mov", "avi", "m4v"], key="actor_video")
    if actor_video:
        video_bytes = actor_video.getvalue()
        video_suffix = Path(actor_video.name).suffix.lower() or ".mp4"
        playable_video_bytes = video_bytes
        video_format = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}.get(video_suffix, "video/mp4")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            st.error("FFmpeg is not installed. Add 'ffmpeg' to packages.txt in the deployed app's root, then redeploy. Automatic browser-compatible conversion is required for reliable previews.")
        else:
            source_video_path = None
            converted_video_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=video_suffix) as source_tmp:
                    source_tmp.write(video_bytes)
                    source_video_path = source_tmp.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as converted_tmp:
                    converted_video_path = converted_tmp.name
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source_video_path,
                     "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "ultrafast",
                     "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                     converted_video_path],
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode != 0 or not os.path.exists(converted_video_path) or os.path.getsize(converted_video_path) <= 0:
                    detail = (result.stderr or "Unknown FFmpeg conversion error").strip()[-1200:]
                    st.error(f"Video conversion failed; no broken preview was shown. Re-export as H.264 MP4. Details: {detail}")
                else:
                    playable_video_bytes = Path(converted_video_path).read_bytes()
                    video_format = "video/mp4"
            except Exception as convert_exc:
                st.error(f"Could not prepare browser-compatible video: {type(convert_exc).__name__}: {convert_exc}")
            finally:
                for temp_name in (source_video_path, converted_video_path):
                    if temp_name:
                        try:
                            os.unlink(temp_name)
                        except OSError:
                            pass

        # Use the converted MP4 whenever FFmpeg is available; keep preview and analysis on the same bytes.
        if ffmpeg and playable_video_bytes != video_bytes:
            st.video(playable_video_bytes, format="video/mp4")
        elif not ffmpeg:
            # Original file may still play if the browser supports its container/codec.
            st.video(video_bytes, format=video_format)
        else:
            # Conversion may have failed; do not label the original file as MP4.
            st.video(video_bytes, format=video_format)

        preview_path = None
        preview_cap = None
        try:
            import cv2
            import numpy as np
            from PIL import Image
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4" if video_format == "video/mp4" else video_suffix) as preview_tmp:
                preview_tmp.write(playable_video_bytes)
                preview_path = preview_tmp.name
            preview_cap = cv2.VideoCapture(preview_path)
            preview_ok, preview_frame = preview_cap.read()
            if preview_ok and preview_frame is not None:
                rgb_frame = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
                st.image(Image.fromarray(np.asarray(rgb_frame)), caption="Video preview · first decoded frame", use_container_width=True)
            else:
                st.error("The uploaded video could not be decoded into a preview frame. Confirm FFmpeg is installed and try a valid MP4/MOV file.")
        except Exception as preview_exc:
            st.error(f"Video preview failed: {type(preview_exc).__name__}: {preview_exc}")
        finally:
            if preview_cap is not None:
                preview_cap.release()
            if preview_path and os.path.exists(preview_path):
                try:
                    os.unlink(preview_path)
                except OSError:
                    pass
        st.caption(f"Selected: {actor_video.name} · {actor_video.size / (1024 * 1024):.1f} MB")
        st.warning("For comparisons, use similar framing, lighting, camera distance and audition instructions for every actor.")
        enable_fer = st.checkbox(
            "Also run experimental facial-expression model (requires the optional 'fer' package)",
            value=False,
            help="Runs a pretrained expression classifier on sampled frames. Outputs can be wrong, especially during speech, with poor lighting, or with occlusion. Use only as review evidence.",
        )
        if st.button("Analyze video locally", type="primary"):
            temp_path = None
            cap = None
            try:
                import cv2
                import mediapipe as mp
                import numpy as np
                emotion_detector = None
                fer_enabled = False
                if enable_fer:
                    try:
                        from fer import FER
                        emotion_detector = FER(mtcnn=False)
                        fer_enabled = True
                    except Exception as fer_exc:
                        st.warning(
                            "FER facial-expression analysis could not be loaded in this deployment "
                            f"({type(fer_exc).__name__}: {fer_exc}). Continuing with body-movement "
                            "and facial-geometry analysis only. Check the pinned FER/TensorFlow "
                            "dependencies in requirements.txt and redeploy."
                        )
                suffix = Path(actor_video.name).suffix or ".mp4"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(playable_video_bytes)
                    temp_path = tmp.name
                cap = cv2.VideoCapture(temp_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 0
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                duration = total_frames / fps if fps > 0 else 0
                sample_every = max(1, int(fps)) if fps > 0 else 24
                frame_index = checked = detected = 0
                face_detected = 0
                previous_points = None
                movements, shoulder_tilts, torso_offsets, wrist_above = [], [], [], []
                mouth_open_ratios, eye_openness_values, brow_eye_distances = [], [], []
                emotion_scores_by_label = {}
                emotion_predictions = []
                observations = []
                pose_api = mp.solutions.pose
                face_api = mp.solutions.face_mesh
                def point_distance(a, b):
                    return float(np.hypot(a.x - b.x, a.y - b.y))
                with pose_api.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose, face_api.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5) as face_mesh:
                    while cap.isOpened():
                        ok, frame = cap.read()
                        if not ok:
                            break
                        current = frame_index
                        frame_index += 1
                        if current % sample_every:
                            continue
                        checked += 1
                        timestamp = current / fps if fps > 0 else float(current)
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        model_emotion = None
                        model_emotion_scores = None
                        if emotion_detector is not None:
                            try:
                                face_predictions = emotion_detector.detect_emotions(frame)
                                if face_predictions:
                                    raw_scores = face_predictions[0].get("emotions", {})
                                    if raw_scores:
                                        model_emotion_scores = {str(k): round(float(v), 4) for k, v in raw_scores.items()}
                                        model_emotion = max(model_emotion_scores, key=model_emotion_scores.get)
                                        emotion_predictions.append({"timestamp_seconds": round(timestamp, 1), "label": model_emotion, "scores": model_emotion_scores})
                                        for label, score in model_emotion_scores.items():
                                            emotion_scores_by_label.setdefault(label, []).append(score)
                            except Exception:
                                # A single frame's model failure should not stop pose/facial-geometry analysis.
                                pass
                        result = pose.process(rgb_frame)
                        face_result = face_mesh.process(rgb_frame)
                        face_metrics = {"face_detected": False, "mouth_opening_ratio": None, "eye_openness_proxy": None, "brow_eye_spacing_proxy": None, "model_expression_label": model_emotion, "model_expression_scores": model_emotion_scores}
                        if face_result.multi_face_landmarks:
                            face_detected += 1
                            flm = face_result.multi_face_landmarks[0].landmark
                            # Ratios are normalized to facial dimensions, reducing—but not removing—scale effects.
                            mouth_width = point_distance(flm[61], flm[291])
                            if mouth_width > 1e-6:
                                mouth_ratio = point_distance(flm[13], flm[14]) / mouth_width
                                mouth_open_ratios.append(mouth_ratio)
                                face_metrics["mouth_opening_ratio"] = round(mouth_ratio, 4)
                            def ear(indices):
                                p1,p2,p3,p4,p5,p6 = [flm[i] for i in indices]
                                horizontal = point_distance(p1,p4)
                                return ((point_distance(p2,p6) + point_distance(p3,p5)) / (2 * horizontal)) if horizontal > 1e-6 else None
                            ears = [v for v in (ear([33,160,158,133,153,144]), ear([362,385,387,263,373,380])) if v is not None]
                            if ears:
                                eye_value = float(np.mean(ears))
                                eye_openness_values.append(eye_value)
                                face_metrics["eye_openness_proxy"] = round(eye_value, 4)
                            # Average vertical brow-to-upper-eye spacing, normalized by face width.
                            face_width = point_distance(flm[234], flm[454])
                            if face_width > 1e-6:
                                spacing = float(np.mean([abs(flm[105].y-flm[159].y), abs(flm[334].y-flm[386].y)]) / face_width)
                                brow_eye_distances.append(spacing)
                                face_metrics["brow_eye_spacing_proxy"] = round(spacing, 4)
                        if not result.pose_landmarks:
                            observations.append({"timestamp_seconds": round(timestamp, 1), "pose_detected": False, **face_metrics})
                            continue
                        detected += 1
                        lm = result.pose_landmarks.landmark
                        get = lambda key: lm[getattr(pose_api.PoseLandmark, key).value]
                        ls, rs, lh, rh = get("LEFT_SHOULDER"), get("RIGHT_SHOULDER"), get("LEFT_HIP"), get("RIGHT_HIP")
                        lw, rw = get("LEFT_WRIST"), get("RIGHT_WRIST")
                        shoulder_tilt = abs(ls.y - rs.y)
                        shoulder_tilts.append(shoulder_tilt)
                        shoulder_mid_x = (ls.x + rs.x) / 2
                        hip_mid_x = (lh.x + rh.x) / 2
                        torso_offset = abs(shoulder_mid_x - hip_mid_x)
                        torso_offsets.append(torso_offset)
                        above = bool(lw.y < ls.y or rw.y < rs.y)
                        wrist_above.append(above)
                        points = np.array([[p.x, p.y] for p in lm if p.visibility > 0.5], dtype=float)
                        # Normalize coordinates around the shoulder midpoint and by shoulder width.
                        # This reduces (but does not eliminate) sensitivity to camera distance.
                        shoulder_width = float(np.hypot(ls.x - rs.x, ls.y - rs.y))
                        shoulder_midpoint = np.array([(ls.x + rs.x) / 2, (ls.y + rs.y) / 2], dtype=float)
                        normalized_points = None
                        if points.size and shoulder_width > 1e-4:
                            normalized_points = (points - shoulder_midpoint) / shoulder_width
                        sample_movement = None
                        if normalized_points is not None and previous_points is not None and normalized_points.shape == previous_points.shape and normalized_points.size:
                            sample_movement = float(np.mean(np.linalg.norm(normalized_points - previous_points, axis=1)))
                            movements.append(sample_movement)
                        previous_points = normalized_points
                        observations.append({
                            "timestamp_seconds": round(timestamp, 1),
                            "pose_detected": True,
                            "movement_since_previous_sample_index": round(sample_movement, 4) if sample_movement is not None else None,
                            "wrist_above_shoulder": above,
                            "shoulder_tilt_index": round(shoulder_tilt, 4),
                            "torso_lateral_offset": round(torso_offset, 4),
                            **face_metrics
                        })
                if cap:
                    cap.release()
                    cap = None
                if checked == 0:
                    st.error("Could not read video frames. Try a short MP4 using a common H.264 encoding.")
                else:
                    report = {
                        "video_file": actor_video.name,
                        "actor_label": actor_label.strip() or Path(actor_video.name).stem,
                        "selected_character": selected_character,
                        "duration_seconds_estimate": round(duration, 1),
                        "sample_interval_seconds_approx": 1,
                        "per_sample_movement_definition": "Mean Euclidean change between sampled visible landmarks after centering coordinates on the shoulder midpoint and dividing by shoulder width. Samples are compared only when landmark arrays have matching shapes. This reduces sensitivity to camera distance but remains sensitive to camera angle, framing, occlusion, tracking and body orientation.",
                        "sampled_frames": checked,
                        "frames_with_detected_pose": detected,
                        "pose_detection_rate": round(detected / checked, 3) if checked else None,
                        "frames_with_detected_face": face_detected,
                        "face_detection_rate": round(face_detected / checked, 3) if checked else None,
                        "mean_mouth_opening_ratio": round(float(np.mean(mouth_open_ratios)), 4) if mouth_open_ratios else None,
                        "mouth_opening_variability": round(float(np.std(mouth_open_ratios)), 4) if len(mouth_open_ratios) > 1 else None,
                        "mean_eye_openness_proxy": round(float(np.mean(eye_openness_values)), 4) if eye_openness_values else None,
                        "eye_openness_variability": round(float(np.std(eye_openness_values)), 4) if len(eye_openness_values) > 1 else None,
                        "mean_brow_eye_spacing_proxy": round(float(np.mean(brow_eye_distances)), 4) if brow_eye_distances else None,
                        "brow_eye_spacing_variability": round(float(np.std(brow_eye_distances)), 4) if len(brow_eye_distances) > 1 else None,
                        "mean_normalized_landmark_movement_index": round(float(np.mean(movements)), 4) if movements else None,
                        "mean_shoulder_tilt_index": round(float(np.mean(shoulder_tilts)), 4) if shoulder_tilts else None,
                        "mean_torso_lateral_offset": round(float(np.mean(torso_offsets)), 4) if torso_offsets else None,
                        "fraction_samples_with_wrist_above_shoulder": round(sum(wrist_above) / len(wrist_above), 3) if wrist_above else None,
                        "sample_observations": observations,
                        "facial_expression_model_enabled": bool(fer_enabled),
                        "facial_expression_model_mean_scores": {label: round(float(np.mean(scores)), 4) for label, scores in emotion_scores_by_label.items()},
                        "facial_expression_predictions": emotion_predictions,
                        "interpretation_limit": "Facial geometry metrics are not emotion labels. Optional FER model labels are probabilistic visual classifications and can be wrong due to lighting, camera angle, speech, occlusion, culture, individual differences and model bias. They do not diagnose depression or establish internal emotion, acting ability, personality, or role suitability. Use timestamped predictions as prompts for human review only."
                    }
                    st.session_state["rasa_video_report"] = report
                    st.success("Local video analysis complete.")
            except ImportError as exc:
                st.error(f"A required video dependency is missing: {exc}. Run pip install -r requirements.txt and restart the app.")
            except Exception as exc:
                st.error(f"Video analysis failed: {exc}")
                st.caption("Try a 10–30 second MP4 clip with the actor's upper body and hands visible.")
            finally:
                if cap is not None:
                    cap.release()
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass

    video_report = st.session_state.get("rasa_video_report")
    if video_report:
        st.subheader("Observable movement and facial-feature report")
        c1, c2, c3 = st.columns(3)
        c1.metric("Clip duration", f"{video_report['duration_seconds_estimate']} s")
        c2.metric("Sampled frames", video_report["sampled_frames"])
        c3.metric("Pose detection", f"{video_report['pose_detection_rate'] * 100:.0f}%" if video_report.get("pose_detection_rate") is not None else "N/A")
        f1, f2, f3 = st.columns(3)
        f1.metric("Face detection", f"{video_report['face_detection_rate'] * 100:.0f}%" if video_report.get("face_detection_rate") is not None else "N/A")
        f2.metric("Mouth opening variability", str(video_report.get("mouth_opening_variability", "N/A")))
        f3.metric("Eye openness variability", str(video_report.get("eye_openness_variability", "N/A")))
        st.caption("Facial geometry is not an emotion label. Optional FER predictions are uncertain visual classifications and must be reviewed in context.")

        # Experimental portrayal evidence summary: reports observed model labels only;
        # it does not assign a suitability score or infer the actor's internal state.
        portrayal_label_map = {
            "Sadness / grief": {"sad"},
            "Anxiety / fear": {"fear"},
            "Anger / confrontation": {"angry"},
            "Joy / excitement": {"happy"},
            "Restrained / stoic performance": {"neutral"},
            "Other / mixed emotional state": set(),
        }
        intended_portrayal = st.session_state.get("rasa_character_portrayal_intent", "Other / mixed emotional state")
        expected_labels = portrayal_label_map.get(intended_portrayal, set())
        predictions = video_report.get("facial_expression_predictions", [])
        if video_report.get("facial_expression_model_enabled"):
            st.subheader("Experimental portrayal evidence")
            st.write(f"**Director's intended portrayal:** {intended_portrayal}")
            if expected_labels and predictions:
                confidence_threshold = st.slider(
                    "Minimum model score to count a prediction as review evidence",
                    min_value=0.0, max_value=1.0, value=0.60, step=0.05,
                    help="This is a review filter, not a calibrated probability that the actor feels an emotion or performs it convincingly.",
                    key="rasa_fer_confidence_threshold",
                )
                evidence_rows = []
                matched_confident = 0
                confident_count = 0
                label_counts = {}
                for prediction in predictions:
                    label = str(prediction.get("label", "")).casefold()
                    scores = prediction.get("scores") or {}
                    top_score = max(scores.values(), default=None)
                    is_confident = top_score is not None and float(top_score) >= confidence_threshold
                    if is_confident:
                        confident_count += 1
                        if label in expected_labels:
                            matched_confident += 1
                    if label:
                        label_counts[label] = label_counts.get(label, 0) + 1
                    evidence_rows.append({
                        "Timestamp (s)": prediction.get("timestamp_seconds"),
                        "Predicted label": prediction.get("label"),
                        "Top-label score": round(float(top_score), 3) if top_score is not None else None,
                        "Meets review threshold": "Yes" if is_confident else "Low confidence / unavailable",
                        "Matches selected category": "Yes" if label in expected_labels else "No",
                    })
                coverage = matched_confident / confident_count if confident_count else None
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "Matching labels among threshold-passing samples",
                    f"{coverage * 100:.1f}%" if coverage is not None else "N/A",
                )
                m2.metric("Threshold-passing samples", f"{confident_count}/{len(predictions)}")
                m3.metric("Samples needing closer review", len(predictions) - confident_count)
                st.caption(
                    "Descriptive model output only. The percentage is calculated only among samples whose top score meets your chosen threshold. "
                    "Scores are not necessarily calibrated probabilities; this is not a role-fit score or a measure of acting quality. "
                    "A different expression at a particular story beat may be entirely appropriate."
                )
                st.write("**Predicted-label distribution**")
                if label_counts:
                    st.dataframe(
                        [{"Predicted label": label, "Sample count": count}
                         for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))],
                        use_container_width=True,
                    )
                st.write("**Timestamped evidence**")
                st.dataframe(evidence_rows, use_container_width=True)
                st.write("**Human review:** inspect the listed timestamps alongside the dialogue, scene beat, and director's brief before making a casting decision.")
            elif not expected_labels:
                st.info("For mixed portrayals, review the timestamped predictions against the director's scene-specific notes; this version does not calculate a single target category.")
            else:
                st.warning("No facial-expression predictions were recorded. Check face visibility, lighting, and whether the optional FER model ran successfully.")
        else:
            st.info("Enable the optional facial-expression model during video analysis to show experimental timestamped expression labels for human review.")
        st.json({k: v for k, v in video_report.items() if k != "sample_observations"})
        st.markdown("**Sample observations**")
        st.dataframe(video_report["sample_observations"], use_container_width=True)
        st.download_button("Download movement report (JSON)", json.dumps(video_report, indent=2, ensure_ascii=False), "rasaai_actor_movement_report.json", "application/json")

        st.subheader("Multi-audition comparison")
        st.caption(f"Saved locally in {AUDITION_LIBRARY_PATH.name}. Add each analyzed audition to keep it available after restarting RasaAI. Compare similar clips; these are descriptive measurements, not a talent ranking.")

        # Browse, filter, and selectively remove saved auditions.
        library_items = list(st.session_state.get("rasa_audition_comparisons", []))
        if library_items:
            st.divider()
            library_characters = sorted({
                str(item.get("selected_character") or "Unassigned")
                for item in library_items
            })
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                library_filter = st.selectbox(
                    "Filter by character",
                    ["All characters"] + library_characters,
                    key="rasa_library_character_filter",
                )
                search_text = st.text_input(
                    "Search actor, video, character, or reviewer notes",
                    key="rasa_library_search",
                    placeholder="Type to search...",
                )
            with filter_col2:
                status_filter = st.selectbox(
                    "Filter by review status",
                    ["All statuses", "Not reviewed", "Consider", "Callback", "Hold", "Not selected"],
                    key="rasa_library_status_filter",
                )
                shortlist_only = st.checkbox(
                    "Show shortlisted auditions only",
                    key="rasa_library_shortlist_only",
                )

            normalized_search = search_text.strip().casefold()
            filtered_items = []
            for idx, item in enumerate(library_items):
                character = str(item.get("selected_character") or "Unassigned")
                actor = str(item.get("actor_label") or "")
                video = str(item.get("video_file") or "")
                notes = str(item.get("reviewer_notes") or "")
                status = str(item.get("reviewer_decision") or "Not reviewed")
                matches_character = library_filter == "All characters" or character == library_filter
                matches_status = status_filter == "All statuses" or status == status_filter
                matches_shortlist = not shortlist_only or bool(item.get("shortlisted", False))
                searchable_text = " ".join([actor, video, character, notes]).casefold()
                matches_search = not normalized_search or normalized_search in searchable_text
                if matches_character and matches_status and matches_shortlist and matches_search:
                    filtered_items.append((idx, item))

            st.caption(f"{len(filtered_items)} saved audition(s) shown · {len(library_items)} total")
            for original_index, item in filtered_items:
                label = item.get("actor_label") or item.get("video_file") or f"Audition {original_index + 1}"
                character = item.get("selected_character") or "Unassigned"
                with st.expander(f"{label} — {character}", expanded=False):
                    st.write(f"**Video:** {item.get('video_file', 'Unknown')}")
                    st.write(f"**Duration:** {item.get('duration_seconds_estimate', 'N/A')} seconds")
                    pose_rate = item.get("pose_detection_rate")
                    st.write(f"**Pose detection:** {round(pose_rate * 100, 1)}%" if isinstance(pose_rate, (int, float)) else "**Pose detection:** N/A")
                    st.json({
                        "mean_normalized_landmark_movement_index": item.get("mean_normalized_landmark_movement_index"),
                        "mean_shoulder_tilt_index": item.get("mean_shoulder_tilt_index"),
                        "fraction_samples_with_wrist_above_shoulder": item.get("fraction_samples_with_wrist_above_shoulder"),
                        "evidence_quality_notes": item.get("evidence_quality_notes", []),
                    })
                    report_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label)).strip("_") or "audition"
                    st.download_button(
                        "Download audition review report (HTML)",
                        data=build_audition_html_report(item).encode("utf-8"),
                        file_name=f"rasaai_audition_review_{report_name}.html",
                        mime="text/html",
                        key=f"rasa_audition_html_report_{original_index}",
                        help="Open the downloaded report in a browser and use Print → Save as PDF if a PDF copy is needed.",
                    )

                    st.markdown("**Human reviewer feedback**")
                    decision_options = ["Not reviewed", "Consider", "Callback", "Hold", "Not selected"]
                    current_decision = item.get("reviewer_decision", "Not reviewed")
                    if current_decision not in decision_options:
                        current_decision = "Not reviewed"
                    reviewer_decision = st.selectbox(
                        "Review status",
                        decision_options,
                        index=decision_options.index(current_decision),
                        key=f"rasa_review_decision_{original_index}",
                        help="This is a human-entered workflow status, not an automated recommendation.",
                    )
                    shortlisted = st.checkbox(
                        "Add to casting shortlist",
                        value=bool(item.get("shortlisted", False)),
                        key=f"rasa_shortlist_{original_index}",
                        help="A human-managed shortlist marker; it is not an automated recommendation.",
                    )
                    reviewer_notes = st.text_area(
                        "Reviewer notes",
                        value=item.get("reviewer_notes", ""),
                        key=f"rasa_review_notes_{original_index}",
                        placeholder="Record observable strengths, questions, callbacks, or follow-up items.",
                        help="Notes are stored in the local JSON library. Avoid entering unnecessary sensitive personal information.",
                    )
                    if st.button("Save reviewer feedback", key=f"rasa_save_review_{original_index}"):
                        updated_items = [dict(saved_item) for saved_item in library_items]
                        updated_items[original_index]["reviewer_decision"] = reviewer_decision
                        updated_items[original_index]["shortlisted"] = bool(shortlisted)
                        updated_items[original_index]["reviewer_notes"] = reviewer_notes.strip()
                        if save_audition_library(updated_items):
                            record_audition_activity(
                                "Reviewer feedback saved",
                                updated_items[original_index],
                                "Review status, shortlist marker, and reviewer notes saved.",
                            )
                            st.session_state["rasa_audition_comparisons"] = updated_items
                            st.success("Reviewer feedback saved locally.")
                            st.rerun()

                    if st.button("Remove this audition", key=f"rasa_remove_saved_{original_index}"):
                        updated_items = [
                            saved_item for idx, saved_item in enumerate(library_items)
                            if idx != original_index
                        ]
                        if save_audition_library(updated_items):
                            record_audition_activity(
                                "Audition removed",
                                item,
                                "Removed from the saved audition library.",
                            )
                            st.session_state["rasa_audition_comparisons"] = updated_items
                            st.rerun()

        if st.button("Add this audition to comparison", key="rasa_add_audition"):
            saved = list(st.session_state.get("rasa_audition_comparisons", []))
            actor_label_value = video_report.get("actor_label") or video_report.get("video_file", "Audition")
            duplicate = any(
                item.get("actor_label") == actor_label_value
                and item.get("video_file") == video_report.get("video_file")
                and item.get("selected_character") == video_report.get("selected_character")
                for item in saved
            )
            if duplicate:
                st.info("This actor/video is already in the comparison list.")
            else:
                saved.append(video_report)
                if save_audition_library(saved):
                    record_audition_activity(
                        "Audition added",
                        saved[-1],
                        "New audition added to the local comparison library.",
                    )
                    st.session_state["rasa_audition_comparisons"] = saved
                    st.success("Audition added to the local library and saved for future sessions.")

        comparison_items = [
            item for item in st.session_state.get("rasa_audition_comparisons", [])
            if item.get("selected_character") == video_report.get("selected_character")
        ]
        if comparison_items:
            comparison_rows = []
            for item in comparison_items:
                comparison_rows.append({
                    "Actor / label": item.get("actor_label") or item.get("video_file"),
                    "Character": item.get("selected_character"),
                    "Video": item.get("video_file"),
                    "Duration (s)": item.get("duration_seconds_estimate"),
                    "Pose detection (%)": round(item["pose_detection_rate"] * 100, 1) if isinstance(item.get("pose_detection_rate"), (int, float)) else None,
                    "Mean movement index": item.get("mean_normalized_landmark_movement_index"),
                    "Mean shoulder tilt": item.get("mean_shoulder_tilt_index"),
                    "Wrist-above-shoulder fraction": item.get("fraction_samples_with_wrist_above_shoulder"),
                    "Reviewer decision": item.get("reviewer_decision", "Not reviewed"),
                    "Shortlisted": bool(item.get("shortlisted", False)),
                    "Reviewer notes": item.get("reviewer_notes", ""),
                    "Evidence quality": (
                        "Low pose coverage"
                        if isinstance(item.get("pose_detection_rate"), (int, float)) and item.get("pose_detection_rate") < 0.5
                        else "Short clip"
                        if isinstance(item.get("duration_seconds_estimate"), (int, float)) and item.get("duration_seconds_estimate") < 10
                        else "Review framing"
                        if isinstance(item.get("pose_detection_rate"), (int, float)) and item.get("pose_detection_rate") < 0.8
                        else "Review manually"
                    ),
                })
            st.dataframe(comparison_rows, use_container_width=True, hide_index=True)
            st.caption("Evidence-quality flags are simple review prompts, not validated confidence scores. Low pose coverage may reflect occlusion, framing, lighting, or pose-detector limitations; short clips provide less evidence.")
            st.download_button(
                "Download multi-audition comparison (JSON)",
                json.dumps(comparison_rows, indent=2, ensure_ascii=False),
                "rasaai_multi_audition_comparison.json",
                "application/json",
                key="rasa_comparison_download"
            )
            if st.button("Clear comparison list", key="rasa_clear_comparisons"):
                if save_audition_library([]):
                    st.session_state["rasa_audition_comparisons"] = []
                    st.rerun()
        else:
            st.info("No auditions have been added for this character yet. Analyze a clip and click **Add this audition to comparison**.")

        st.subheader("Role requirement evidence comparison")
        st.caption("Exploratory rule-based indicators only; thresholds are not trained or validated and should not be interpreted as an actor score.")
        targets = st.session_state.get("rasa_role_requirements", {}).get(video_report.get("selected_character", ""), [])
        if not targets:
            st.info("No measurable targets were selected for this character. Select requirements above to compare them with the video measurements.")
        else:
            evidence_rows = build_requirement_evidence(targets, video_report)
            st.dataframe(evidence_rows, use_container_width=True, hide_index=True)
            timestamp_rows = build_timestamped_evidence(targets, video_report)
            st.markdown("**Timestamped observable evidence**")
            st.caption("Movement timestamps use changes in visible landmark positions, centered on the shoulder midpoint and scaled by shoulder width, between adjacent sampled frames (about one second apart). This partially reduces camera-distance effects; it is still an experimental proxy, not a validated performance measure.")
            st.dataframe(timestamp_rows, use_container_width=True, hide_index=True)
            st.warning("These comparisons are sensitive to camera framing, pose visibility, action context and clip differences. Review the timestamped observations yourself; do not use this as an automated casting decision.")
            combined_report = {
                "project": "RasaAI",
                "analysis_method": "Local rule-based NLP and observable computer-vision measurements; no LLM or cloud API",
                "character": video_report.get("selected_character"),
                "role_requirements_selected_by_filmmaker": targets,
                "intended_character_portrayal": st.session_state.get("rasa_character_portrayal_intent", "Not specified"),
                "portrayal_analysis_note": "The selected portrayal is a filmmaker-provided brief, not a detected emotion label. Facial measurements are geometric proxies and must be interpreted by a human reviewer in scene context.",
                "role_requirement_evidence": evidence_rows,
                "timestamped_observable_evidence": timestamp_rows,
                "screenplay_analysis": story_report,
                "actor_video_analysis": video_report,
                "matching_limitations": "Exploratory indicators only. No trained actor-ranking model is used. Measurements do not establish talent, emotion, personality, or casting suitability. Human review is required."
            }
            st.download_button("Download combined role review (JSON)", json.dumps(combined_report, indent=2, ensure_ascii=False), "rasaai_combined_role_review.json", "application/json")


    # ---------- Vocal performance analysis (audio-only, experimental) ----------
with workflow_tabs[4]:
    st.header("Vocal performance analysis")
    st.write(
        "Upload an audition audio track to inspect pitch, loudness, pauses and vocal variation. "
        "This measures acoustic patterns; it does not determine whether an actor is truly sad, happy, angry, "
        "or suitable for a role. For best comparisons, use clean dialogue with minimal music and similar recording conditions."
    )
    st.caption("Audio processing is local. Supported formats depend on the installed librosa/audio backend; WAV is the safest option.")
    audio_actor_label = st.text_input(
        "Actor / audition label for vocal analysis",
        placeholder="e.g., Audition A or actor name",
        key="rasa_vocal_actor_label",
    )
    audio_character_options = [c["name"] for c in story_report.get("story_characters", [])] if story_report else []
    if audio_character_options:
        audio_character = st.selectbox(
            "Character for this vocal audition", ["Unassigned"] + audio_character_options,
            key="rasa_vocal_character",
        )
    else:
        audio_character = st.text_input(
            "Character for this vocal audition (optional)",
            placeholder="e.g., Arjun", key="rasa_vocal_character_text",
        ) or "Unassigned"
    audio_file = st.file_uploader(
        "Upload audition audio", type=["wav", "mp3", "m4a", "flac", "ogg"], key="rasa_vocal_audio"
    )
    if audio_file:
        audio_bytes = audio_file.getvalue()
        audio_suffix = Path(audio_file.name).suffix.lower() or ".audio"
        playable_audio_bytes = audio_bytes
        audio_format = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg"}.get(audio_suffix, "application/octet-stream")
        ffmpeg = shutil.which("ffmpeg")
        source_audio_path = None
        converted_audio_path = None
        if ffmpeg:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=audio_suffix) as source_tmp:
                    source_tmp.write(audio_bytes)
                    source_audio_path = source_tmp.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as converted_tmp:
                    converted_audio_path = converted_tmp.name
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source_audio_path,
                     "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", converted_audio_path],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0 and os.path.exists(converted_audio_path) and os.path.getsize(converted_audio_path) > 44:
                    playable_audio_bytes = Path(converted_audio_path).read_bytes()
                    audio_format = "audio/wav"
                else:
                    detail = (result.stderr or "Unknown FFmpeg conversion error").strip()[-800:]
                    st.error(f"Audio conversion failed. Try exporting as PCM WAV. Details: {detail}")
            except Exception as convert_exc:
                st.error(f"Audio conversion failed: {type(convert_exc).__name__}: {convert_exc}")
            finally:
                for temp_name in (source_audio_path, converted_audio_path):
                    if temp_name:
                        try:
                            os.unlink(temp_name)
                        except OSError:
                            pass
        else:
            st.error("FFmpeg is not installed. Add 'ffmpeg' to packages.txt in the deployed app's root, then redeploy. WAV playback may work without conversion, but automatic normalization is unavailable.")
        st.audio(playable_audio_bytes, format=audio_format)
        if st.button("Analyze vocal acoustics", type="primary", key="rasa_analyze_vocal"):
            try:
                import librosa
                import numpy as np
                import pandas as pd
                audio, sr = librosa.load(io.BytesIO(playable_audio_bytes), sr=22050, mono=True)
                if audio.size == 0:
                    st.error("The uploaded audio contains no readable samples.")
                else:
                    duration_s = float(len(audio) / sr)
                    frame_length = 2048
                    hop_length = 512
                    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
                    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
                    # pyin is relatively expensive, so cap the analysis duration to keep local use practical.
                    max_duration = 180.0
                    analyzed_audio = audio[: int(max_duration * sr)]
                    f0, voiced_flag, voiced_prob = librosa.pyin(
                        analyzed_audio, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"),
                        sr=sr, frame_length=2048, hop_length=512
                    )
                    pitch_times = librosa.times_like(f0, sr=sr, hop_length=512)
                    valid_pitch = f0[np.isfinite(f0)]
                    voiced_fraction = float(np.isfinite(f0).mean()) if len(f0) else 0.0
                    # Relative energy threshold provides a rough pause proxy, not speech recognition.
                    energy_floor = max(float(np.max(rms)) * 0.12, 1e-5)
                    active = rms > energy_floor
                    frame_seconds = hop_length / sr
                    pause_seconds = float((~active).sum() * frame_seconds)
                    changes = np.diff(np.r_[False, active, False].astype(int))
                    starts = np.where(changes == 1)[0]
                    ends = np.where(changes == -1)[0]
                    pauses = []
                    for a, b in zip(ends[:-1], starts[1:]):
                        gap = (starts[np.where(starts > a)[0][0]] - a) * frame_seconds if np.any(starts > a) else 0
                        if gap >= 0.35:
                            pauses.append({"start_seconds": round(float(a * frame_seconds), 2), "duration_seconds": round(float(gap), 2)})
                    features = {
                        "audio_file": audio_file.name,
                        "duration_seconds": round(duration_s, 2),
                        "analyzed_duration_seconds": round(min(duration_s, max_duration), 2),
                        "median_pitch_hz": round(float(np.median(valid_pitch)), 1) if len(valid_pitch) else None,
                        "pitch_10th_percentile_hz": round(float(np.percentile(valid_pitch, 10)), 1) if len(valid_pitch) else None,
                        "pitch_90th_percentile_hz": round(float(np.percentile(valid_pitch, 90)), 1) if len(valid_pitch) else None,
                        "pitch_standard_deviation_hz": round(float(np.std(valid_pitch)), 1) if len(valid_pitch) else None,
                        "voiced_frame_fraction": round(voiced_fraction, 3),
                        "mean_rms_energy": round(float(np.mean(rms)), 5),
                        "energy_variation_std": round(float(np.std(rms)), 5),
                        "estimated_low_energy_seconds": round(pause_seconds, 2),
                        "detected_energy_gaps_over_0_35s": len(pauses),
                        "energy_gap_examples": pauses[:100],
                        "note": "Acoustic descriptors only; low energy is not necessarily silence, and pitch/energy do not establish emotion or acting quality."
                    }
                    st.session_state["rasa_vocal_analysis"] = {
                        "features": features,
                        "pitch_times": pitch_times.tolist(),
                        "pitch_hz": [float(x) if np.isfinite(x) else None for x in f0],
                        "rms_times": rms_times.tolist(),
                        "rms": rms.tolist(),
                        "actor_label": audio_actor_label.strip() or Path(audio_file.name).stem,
                        "selected_character": audio_character or "Unassigned",
                    }
            except ImportError:
                st.error("Vocal analysis needs librosa. In the active Python 3.12 environment, run: python -m pip install librosa")
            except Exception as exc:
                st.error(f"Audio analysis failed: {type(exc).__name__}: {exc}")

    vocal_result = st.session_state.get("rasa_vocal_analysis")
    if vocal_result:
        # Streamlit reruns the script after a button click. Re-import these here so
        # the results-rendering pass does not depend on imports from the click branch.
        try:
            import numpy as np
            import pandas as pd
        except ImportError as exc:
            st.error(f"Cannot display saved vocal results because a required package is missing: {exc}")
            st.stop()
        vf = vocal_result["features"]
        st.subheader("Vocal acoustics summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median pitch", f"{vf['median_pitch_hz']} Hz" if vf["median_pitch_hz"] is not None else "Unavailable")
        c2.metric("Pitch range (P10–P90)", f"{vf['pitch_10th_percentile_hz']}–{vf['pitch_90th_percentile_hz']} Hz" if vf["pitch_10th_percentile_hz"] is not None else "Unavailable")
        c3.metric("Pitch variability", f"{vf['pitch_standard_deviation_hz']} Hz" if vf["pitch_standard_deviation_hz"] is not None else "Unavailable")
        c4.metric("Energy gaps ≥ 0.35 s", str(vf["detected_energy_gaps_over_0_35s"]))
        pitch_df = pd.DataFrame({"Time (s)": vocal_result["pitch_times"], "Pitch (Hz)": vocal_result["pitch_hz"]}).set_index("Time (s)")
        st.markdown("**Pitch contour**")
        st.line_chart(pitch_df, height=220)
        rms_df = pd.DataFrame({"Time (s)": vocal_result["rms_times"], "RMS energy": vocal_result["rms"]}).set_index("Time (s)")
        st.markdown("**Relative loudness / energy**")
        st.line_chart(rms_df, height=180)
        st.dataframe(pd.DataFrame([vf]), use_container_width=True, hide_index=True)
        st.download_button("Download vocal analysis (JSON)", json.dumps(vf, indent=2, ensure_ascii=False), "rasaai_vocal_analysis.json", "application/json", key="rasa_vocal_json")
        if st.button("Save vocal analysis to audition library / Haystack", type="primary", key="rasa_save_vocal_analysis"):
            saved_items = [dict(item) for item in st.session_state.get("rasa_audition_comparisons", [])]
            actor_value = vocal_result.get("actor_label") or Path(vf.get("audio_file", "audition_audio")).stem
            character_value = vocal_result.get("selected_character") or "Unassigned"
            duplicate_index = next((i for i, item in enumerate(saved_items)
                if item.get("analysis_type") == "vocal"
                and item.get("audio_file") == vf.get("audio_file")
                and item.get("actor_label") == actor_value
                and item.get("selected_character") == character_value), None)
            vocal_record = {
                "analysis_type": "vocal",
                "actor_label": actor_value,
                "selected_character": character_value,
                "audio_file": vf.get("audio_file"),
                "video_file": "",
                "vocal_analysis": vf,
                "median_pitch_hz": vf.get("median_pitch_hz"),
                "pitch_10th_percentile_hz": vf.get("pitch_10th_percentile_hz"),
                "pitch_90th_percentile_hz": vf.get("pitch_90th_percentile_hz"),
                "pitch_standard_deviation_hz": vf.get("pitch_standard_deviation_hz"),
                "voiced_frame_fraction": vf.get("voiced_frame_fraction"),
                "mean_rms_energy": vf.get("mean_rms_energy"),
                "energy_variation_std": vf.get("energy_variation_std"),
                "estimated_low_energy_seconds": vf.get("estimated_low_energy_seconds"),
                "detected_energy_gaps_over_0_35s": vf.get("detected_energy_gaps_over_0_35s"),
                "reviewer_decision": "Not reviewed",
                "shortlisted": False,
                "reviewer_notes": "",
                "analysis_method": "Local librosa acoustic analysis; no speech transcription or emotion inference",
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            if duplicate_index is not None:
                saved_items[duplicate_index] = {**saved_items[duplicate_index], **vocal_record}
            else:
                saved_items.append(vocal_record)
            if save_audition_library(saved_items):
                st.session_state["rasa_audition_comparisons"] = saved_items
                record_audition_activity("Vocal analysis saved", vocal_record, "Saved vocal acoustics for Haystack keyword retrieval.")
                st.success("Vocal analysis saved to the local library. It is now available in Haystack Retrieval.")

        # Export a compact, timestamped evidence table so reviewers can inspect
        # acoustic measurements alongside the actual recording. This is not speech
        # transcription or emotion recognition.
        st.subheader("Timestamped vocal evidence")
        try:
            evidence_df = pd.DataFrame({
                "time_seconds": vocal_result["pitch_times"],
                "pitch_hz": vocal_result["pitch_hz"],
            })
            rms_df_export = pd.DataFrame({
                "time_seconds": vocal_result["rms_times"],
                "rms_energy": vocal_result["rms"],
            })
            evidence_df = evidence_df.dropna(subset=["time_seconds"])
            evidence_df["time_seconds"] = pd.to_numeric(evidence_df["time_seconds"], errors="coerce")
            rms_df_export["time_seconds"] = pd.to_numeric(rms_df_export["time_seconds"], errors="coerce")
            evidence_df = evidence_df.dropna(subset=["time_seconds"])
            rms_df_export = rms_df_export.dropna(subset=["time_seconds"])
            if not evidence_df.empty and not rms_df_export.empty:
                evidence_df["rms_energy"] = np.interp(
                    evidence_df["time_seconds"].to_numpy(),
                    rms_df_export["time_seconds"].to_numpy(),
                    rms_df_export["rms_energy"].to_numpy(),
                )
                evidence_df["time_seconds"] = evidence_df["time_seconds"].round(2)
                evidence_df["pitch_hz"] = pd.to_numeric(evidence_df["pitch_hz"], errors="coerce").round(1)
                evidence_df["rms_energy"] = evidence_df["rms_energy"].round(6)
                st.dataframe(evidence_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download timestamped vocal evidence (CSV)",
                    evidence_df.to_csv(index=False).encode("utf-8"),
                    "rasaai_vocal_evidence.csv",
                    "text/csv",
                    key="rasa_vocal_evidence_csv",
                )
            else:
                st.info("No timestamped samples were available to export.")
        except Exception as exc:
            st.warning(f"Could not prepare the timestamped evidence table: {type(exc).__name__}: {exc}")

        st.subheader("Dialogue delivery by time segment")
        st.caption(
            "Summarizes acoustic changes in fixed time windows. These are delivery descriptors, "
            "not labels for sadness, happiness, anger, or acting quality."
        )
        segment_seconds = st.select_slider(
            "Segment length (seconds)",
            options=[3, 5, 10, 15],
            value=5,
            key="rasa_vocal_segment_length",
        )
        pitch_frame = pd.DataFrame({
            "time_seconds": vocal_result["pitch_times"],
            "pitch_hz": vocal_result["pitch_hz"],
        })
        energy_frame = pd.DataFrame({
            "time_seconds": vocal_result["rms_times"],
            "rms_energy": vocal_result["rms"],
        })
        pitch_frame["time_seconds"] = pd.to_numeric(pitch_frame["time_seconds"], errors="coerce")
        pitch_frame["pitch_hz"] = pd.to_numeric(pitch_frame["pitch_hz"], errors="coerce")
        energy_frame["time_seconds"] = pd.to_numeric(energy_frame["time_seconds"], errors="coerce")
        energy_frame["rms_energy"] = pd.to_numeric(energy_frame["rms_energy"], errors="coerce")
        pitch_frame = pitch_frame.dropna(subset=["time_seconds"])
        energy_frame = energy_frame.dropna(subset=["time_seconds", "rms_energy"])
        if not pitch_frame.empty and not energy_frame.empty:
            max_time = min(
                float(pitch_frame["time_seconds"].max()),
                float(energy_frame["time_seconds"].max()),
            )
            boundaries = np.arange(0, max_time + segment_seconds, segment_seconds)
            segment_rows = []
            for start in boundaries[:-1]:
                end = min(float(start + segment_seconds), max_time + 1e-6)
                pseg = pitch_frame[
                    (pitch_frame["time_seconds"] >= start) &
                    (pitch_frame["time_seconds"] < end)
                ]["pitch_hz"].dropna()
                eseg = energy_frame[
                    (energy_frame["time_seconds"] >= start) &
                    (energy_frame["time_seconds"] < end)
                ]["rms_energy"].dropna()
                if pseg.empty and eseg.empty:
                    continue
                segment_rows.append({
                    "start_seconds": round(float(start), 2),
                    "end_seconds": round(float(end), 2),
                    "median_pitch_hz": round(float(pseg.median()), 1) if not pseg.empty else None,
                    "pitch_variability_std_hz": round(float(pseg.std(ddof=0)), 1) if not pseg.empty else None,
                    "mean_rms_energy": round(float(eseg.mean()), 6) if not eseg.empty else None,
                    "energy_variability_std": round(float(eseg.std(ddof=0)), 6) if not eseg.empty else None,
                    "pitch_frames": int(len(pseg)),
                    "energy_frames": int(len(eseg)),
                })
            if segment_rows:
                segment_df = pd.DataFrame(segment_rows)
                st.dataframe(segment_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download segment delivery summary (CSV)",
                    segment_df.to_csv(index=False).encode("utf-8"),
                    "rasaai_vocal_segment_summary.csv",
                    "text/csv",
                    key="rasa_vocal_segment_summary_csv",
                )
            else:
                st.info("No usable samples were available for segment summaries.")
        else:
            st.info("No timestamped pitch or energy samples are available for segment summaries.")

        st.warning("These acoustic features are not an emotion classifier. Pitch and loudness vary with the actor, language, dialogue, microphone, music and recording conditions. Review the audio in context; do not use these measurements alone to rank or reject actors.")


    st.divider()
    st.caption("Privacy: processing is designed to run locally. Use only actor media you have permission to analyze. This is an experimental casting-support tool; final decisions remain with the filmmaker and casting team.")


    # ---------- Combined vocal + visual evidence timeline (experimental) ----------
    st.divider()
with workflow_tabs[5]:
    st.header("Combined vocal + visual evidence timeline")
    st.write(
        "Align timestamped video observations with nearby vocal measurements for reviewer inspection. "
        "This does not infer a person's true emotion or calculate a validated acting score."
    )
    video_report = st.session_state.get("rasa_video_report")
    vocal_result = st.session_state.get("rasa_vocal_analysis")
    if not video_report or not vocal_result:
        st.info("Run both video analysis and vocal analysis in this session to build a combined timeline.")
    else:
        import pandas as pd
        import numpy as np

        sync_offset = st.number_input(
            "Audio offset relative to video (seconds)",
            min_value=-3600.0,
            max_value=3600.0,
            value=0.0,
            step=0.1,
            help="Positive values mean the audio starts later than the video. Adjust only if you know the recordings are offset."
        )
        tolerance = st.slider(
            "Maximum time difference for matching samples (seconds)",
            min_value=0.25,
            max_value=5.0,
            value=1.0,
            step=0.25,
        )
        observations = video_report.get("sample_observations", [])
        if not observations:
            st.warning("The video report has no timestamped observations to align.")
        else:
            pitch_times = np.asarray(vocal_result.get("pitch_times", []), dtype=float)
            pitch_values = vocal_result.get("pitch_hz", [])
            rms_times = np.asarray(vocal_result.get("rms_times", []), dtype=float)
            rms_values = vocal_result.get("rms", [])
            vocal_rows = []
            for i, t in enumerate(pitch_times):
                value = pitch_values[i] if i < len(pitch_values) else None
                if value is not None and np.isfinite(value):
                    vocal_rows.append({"time": float(t) + float(sync_offset), "pitch_hz": float(value)})
            for i, t in enumerate(rms_times):
                value = rms_values[i] if i < len(rms_values) else None
                if value is not None and np.isfinite(value):
                    vocal_rows.append({"time": float(t) + float(sync_offset), "rms_energy": float(value)})
            pitch_df = pd.DataFrame(vocal_rows)
            if not pitch_df.empty:
                if "pitch_hz" not in pitch_df:
                    pitch_df["pitch_hz"] = np.nan
                if "rms_energy" not in pitch_df:
                    pitch_df["rms_energy"] = np.nan
                pitch_df = pitch_df.groupby("time", as_index=False).agg(
                    pitch_hz=("pitch_hz", "mean"), rms_energy=("rms_energy", "mean")
                )
            prediction_rows = video_report.get("facial_expression_predictions", [])
            aligned = []
            for obs in observations:
                video_time = float(obs.get("timestamp_seconds", 0.0))
                row = {
                    "video_time_seconds": round(video_time, 2),
                    "pose_detected": obs.get("pose_detected"),
                    "mouth_opening_ratio": obs.get("mouth_opening_ratio"),
                    "eye_openness_proxy": obs.get("eye_openness_proxy"),
                    "movement_index": obs.get("movement_since_previous_sample_index"),
                    "shoulder_tilt_index": obs.get("shoulder_tilt_index"),
                    "facial_expression_prediction": None,
                    "expression_model_score": None,
                    "matched_audio_time_seconds": None,
                    "pitch_hz_nearby": None,
                    "rms_energy_nearby": None,
                    "audio_match_difference_seconds": None,
                }
                if prediction_rows:
                    candidates = [
                        p for p in prediction_rows
                        if p.get("timestamp_seconds") is not None and p.get("label")
                    ]
                    if candidates:
                        nearest_prediction = min(
                            candidates, key=lambda p: abs(float(p["timestamp_seconds"]) - video_time)
                        )
                        if abs(float(nearest_prediction["timestamp_seconds"]) - video_time) <= tolerance:
                            row["facial_expression_prediction"] = nearest_prediction.get("label")
                            scores = nearest_prediction.get("scores", {})
                            if isinstance(scores, dict) and scores:
                                row["expression_model_score"] = round(max(float(v) for v in scores.values()), 4)
                if not pitch_df.empty:
                    nearest_idx = (pitch_df["time"] - video_time).abs().idxmin()
                    nearest = pitch_df.loc[nearest_idx]
                    difference = abs(float(nearest["time"]) - video_time)
                    if difference <= tolerance:
                        row["matched_audio_time_seconds"] = round(float(nearest["time"]), 2)
                        row["audio_match_difference_seconds"] = round(difference, 2)
                        if pd.notna(nearest["pitch_hz"]):
                            row["pitch_hz_nearby"] = round(float(nearest["pitch_hz"]), 1)
                        if pd.notna(nearest["rms_energy"]):
                            row["rms_energy_nearby"] = round(float(nearest["rms_energy"]), 6)
                aligned.append(row)
            combined_df = pd.DataFrame(aligned)
            st.caption(
                f"Video: {video_report.get('video_file', 'current video')} · "
                f"Audio: aligned using offset {sync_offset:.2f}s · "
                f"Matching tolerance: {tolerance:.2f}s"
            )
            st.dataframe(combined_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download combined evidence timeline (CSV)",
                combined_df.to_csv(index=False).encode("utf-8"),
                "rasaai_combined_evidence_timeline.csv",
                "text/csv",
                key="rasa_combined_evidence_csv",
            )
            st.download_button(
                "Download combined evidence timeline (JSON)",
                json.dumps({
                    "video_file": video_report.get("video_file"),
                    "audio_offset_seconds": float(sync_offset),
                    "matching_tolerance_seconds": float(tolerance),
                    "observations": combined_df.where(pd.notna(combined_df), None).to_dict(orient="records"),
                    "interpretation_limit": "Time-aligned measurements and model predictions are evidence for human review only. They do not establish internal emotion, mental health, acting ability, or casting suitability."
                }, indent=2, ensure_ascii=False, default=str),
                "rasaai_combined_evidence_timeline.json",
                "application/json",
                key="rasa_combined_evidence_json",
            )
            st.warning(
                "Audio/video timestamps must refer to the same recording timeline. This tool aligns measurements by time; "
                "it does not verify lip-sync or infer emotional meaning. Review the original footage and audio."
            )


# ---------- Standalone Haystack Retrieval tab ----------
with workflow_tabs[6]:
    st.header("Haystack Retrieval")
    st.caption(
        "Search saved audition reports using Haystack BM25 keyword retrieval. "
        "Results are relevant recorded evidence for human review, not casting recommendations."
    )

    saved_auditions = list(st.session_state.get("rasa_audition_comparisons", []))
    if not saved_auditions:
        st.info(
            "No saved auditions are available yet. Go to Video Analysis, analyze a clip, "
            "and click **Add this audition to comparison**. Then return here to search it."
        )
    else:
        st.write(f"Saved audition records available: **{len(saved_auditions)}**")
        if haystack_search_auditions is None:
            st.error(
                "Haystack is not available in this deployment. Check that `haystack-ai>=2.0,<3` "
                "is in requirements.txt and review the deployment logs."
            )
            with st.expander("Import error details"):
                st.code(HAYSTACK_SEARCH_IMPORT_ERROR or "Haystack import unavailable")
        else:
            # Filters are applied before BM25 retrieval so the result limit is
            # filled from the selected subset rather than filtering a small top-k afterward.
            character_options = sorted({
                str(item.get("selected_character") or "Unassigned")
                for item in saved_auditions
            }, key=str.casefold)
            status_options = sorted({
                str(item.get("reviewer_decision") or "Not reviewed")
                for item in saved_auditions
            }, key=str.casefold)

            filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
            with filter_col1:
                retrieval_character = st.selectbox(
                    "Character", ["All characters"] + character_options,
                    key="rasa_haystack_character_filter",
                )
            with filter_col2:
                retrieval_status = st.selectbox(
                    "Review status", ["All statuses"] + status_options,
                    key="rasa_haystack_status_filter",
                )
            with filter_col3:
                retrieval_shortlisted_only = st.checkbox(
                    "Shortlisted only", key="rasa_haystack_shortlisted_filter"
                )

            query_col, limit_col = st.columns([5, 1])
            with query_col:
                retrieval_query = st.text_input(
                    "Search saved audition evidence",
                    placeholder="e.g. callback with reviewer notes about hand gestures",
                    key="rasa_haystack_standalone_query",
                )
            with limit_col:
                retrieval_limit = st.selectbox(
                    "Max results", [5, 10, 20], index=1,
                    key="rasa_haystack_standalone_limit",
                )

            search_clicked = st.button(
                "Retrieve auditions", type="primary",
                key="rasa_haystack_standalone_button",
                disabled=not bool(retrieval_query.strip()),
            )
            if search_clicked:
                try:
                    candidate_records = []
                    original_indices = []
                    for original_index, item in enumerate(saved_auditions):
                        character = str(item.get("selected_character") or "Unassigned")
                        status = str(item.get("reviewer_decision") or "Not reviewed")
                        if retrieval_character != "All characters" and character != retrieval_character:
                            continue
                        if retrieval_status != "All statuses" and status != retrieval_status:
                            continue
                        if retrieval_shortlisted_only and not bool(item.get("shortlisted", False)):
                            continue
                        candidate_records.append(item)
                        original_indices.append(original_index)

                    retrieval_results = haystack_search_auditions(
                        candidate_records, retrieval_query.strip(), top_k=retrieval_limit
                    ) if candidate_records else []

                    # The helper returns indices relative to candidate_records.
                    # Convert them back to indices in the full saved audition library.
                    mapped_results = []
                    for result in retrieval_results:
                        candidate_index = int(result.get("library_index", -1))
                        if 0 <= candidate_index < len(original_indices):
                            mapped = dict(result)
                            mapped["library_index"] = original_indices[candidate_index]
                            mapped_results.append(mapped)

                    st.session_state["rasa_haystack_standalone_results"] = {
                        "query": retrieval_query.strip(),
                        "character": retrieval_character,
                        "status": retrieval_status,
                        "shortlisted_only": retrieval_shortlisted_only,
                        "candidate_count": len(candidate_records),
                        "results": mapped_results,
                    }

                    # Keep a short session-only history so users can track recent searches.
                    history = st.session_state.get("rasa_haystack_search_history", [])
                    history.insert(0, {
                        "query": retrieval_query.strip(),
                        "character": retrieval_character,
                        "status": retrieval_status,
                        "shortlisted_only": retrieval_shortlisted_only,
                        "candidate_count": len(candidate_records),
                        "result_count": len(mapped_results),
                        "searched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    st.session_state["rasa_haystack_search_history"] = history[:10]
                except Exception as exc:
                    st.session_state.pop("rasa_haystack_standalone_results", None)
                    st.error(f"Haystack retrieval failed: {type(exc).__name__}: {exc}")

            search_history = st.session_state.get("rasa_haystack_search_history", [])
            if search_history:
                with st.expander("Recent search history (this session)", expanded=False):
                    st.caption("The latest 10 searches are kept in this browser session only; history is not saved to disk.")
                    for history_index, history_item in enumerate(search_history, start=1):
                        history_filters = []
                        if history_item.get("character") != "All characters":
                            history_filters.append(f"Character: {history_item['character']}")
                        if history_item.get("status") != "All statuses":
                            history_filters.append(f"Status: {history_item['status']}")
                        if history_item.get("shortlisted_only"):
                            history_filters.append("Shortlisted only")
                        st.write(
                            f"**{history_index}. {history_item.get('query', '')}** — "
                            f"{history_item.get('result_count', 0)} result(s) · "
                            f"{history_item.get('searched_at', '')}"
                        )
                        st.caption("Filters: " + (" · ".join(history_filters) if history_filters else "None"))

            retrieval_state = st.session_state.get("rasa_haystack_standalone_results", {})
            if retrieval_state.get("query"):
                st.subheader("Retrieved results")
                st.caption(f"Query: {retrieval_state['query']}")
                filter_summary = []
                if retrieval_state.get("character", "All characters") != "All characters":
                    filter_summary.append(f"Character: {retrieval_state['character']}")
                if retrieval_state.get("status", "All statuses") != "All statuses":
                    filter_summary.append(f"Status: {retrieval_state['status']}")
                if retrieval_state.get("shortlisted_only"):
                    filter_summary.append("Shortlisted only")
                st.caption("Filters: " + (" · ".join(filter_summary) if filter_summary else "None"))
                st.caption(f"Searched {retrieval_state.get('candidate_count', 0)} audition(s) matching the filters.")
                results = retrieval_state.get("results", [])
                if not results:
                    st.info("No matching records were returned. Try different keywords or broaden the filters.")
                else:
                    st.write(f"Found **{len(results)}** matching audition(s).")
                    for rank, result in enumerate(results, start=1):
                        try:
                            index = int(result.get("library_index", -1))
                        except (TypeError, ValueError):
                            continue
                        if not 0 <= index < len(saved_auditions):
                            continue
                        item = saved_auditions[index]
                        label = item.get("actor_label") or item.get("video_file") or f"Audition {index + 1}"
                        character = item.get("selected_character") or "Unassigned"
                        score = result.get("score")
                        score_label = f" · BM25 score {score:.3f}" if isinstance(score, (int, float)) else ""
                        with st.expander(f"{rank}. {label} — {character}{score_label}", expanded=(rank == 1)):
                            if item.get("analysis_type") == "vocal":
                                st.write(f"**Audio:** {item.get('audio_file') or 'Not available'}")
                                st.write(f"**Median pitch:** {item.get('median_pitch_hz', 'N/A')} Hz")
                                st.write(f"**Energy gaps:** {item.get('detected_energy_gaps_over_0_35s', 'N/A')}")
                            else:
                                st.write(f"**Video:** {item.get('video_file') or 'Not available'}")
                            st.write(f"**Analysis type:** {item.get('analysis_type') or 'video'}")
                            st.write(f"**Review status:** {item.get('reviewer_decision') or 'Not reviewed'}")
                            st.write(f"**Shortlisted:** {'Yes' if item.get('shortlisted', False) else 'No'}")
                            st.write(f"**Reviewer notes:** {item.get('reviewer_notes') or 'No reviewer notes'}")
                            st.caption("Matching indexed evidence")
                            st.text(str(result.get("content", ""))[:2500])

                    # Export only the currently displayed retrieval results.
                    export_rows = []
                    for rank, result in enumerate(results, start=1):
                        try:
                            index = int(result.get("library_index", -1))
                        except (TypeError, ValueError):
                            continue
                        if not 0 <= index < len(saved_auditions):
                            continue
                        item = saved_auditions[index]
                        export_rows.append({
                            "Rank": rank,
                            "Actor": item.get("actor_label") or "",
                            "Video file": item.get("video_file") or "",
                            "Character": item.get("selected_character") or "Unassigned",
                            "Review status": item.get("reviewer_decision") or "Not reviewed",
                            "Shortlisted": bool(item.get("shortlisted", False)),
                            "Reviewer notes": item.get("reviewer_notes") or "",
                            "BM25 score": result.get("score", ""),
                        })
                    if export_rows:
                        csv_buffer = io.StringIO(newline="")
                        writer = csv.DictWriter(csv_buffer, fieldnames=list(export_rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(export_rows)
                        st.download_button(
                            "Download results as CSV",
                            data="\ufeff" + csv_buffer.getvalue(),
                            file_name="rasa_haystack_retrieval_results.csv",
                            mime="text/csv",
                            key="rasa_haystack_download_results",
                        )
                st.caption(
                    "BM25 is keyword-based retrieval. It does not reliably understand every paraphrase, "
                    "and its score is not a measure of acting quality or role suitability."
                )
            if st.button("Clear retrieval results", key="rasa_haystack_standalone_clear"):
                st.session_state.pop("rasa_haystack_standalone_results", None)
                st.rerun()


# ---------- Optional Db2 integration ----------
with workflow_tabs[7]:
    st.header("Db2 Database")
    st.caption(
        "Optional Db2 persistence for audition records. The local JSON library remains the existing source; "
        "sync is manual and upserts records into Db2 without deleting database rows."
    )

    try:
        from db2_store import connection_status, ensure_schema, sync_auditions, fetch_auditions
        DB2_MODULE_ERROR = None
    except Exception as exc:
        connection_status = ensure_schema = sync_auditions = fetch_auditions = None
        DB2_MODULE_ERROR = f"{type(exc).__name__}: {exc}"

    with st.expander("Connection configuration", expanded=True):
        st.write("Set these environment variables before starting Streamlit:")
        st.code(
            "DB2_HOST=your-db2-host\n"
            "DB2_PORT=50000\n"
            "DB2_DATABASE=your-database\n"
            "DB2_USER=your-username\n"
            "DB2_PASSWORD=your-password\n"
            "DB2_SSL=true  # use true if your Db2 service requires TLS",
            language="text",
        )
        st.warning("Do not paste database passwords into chat or commit them to Git. Db2 LUW catalog SQL is used by this initial connector.")

    if DB2_MODULE_ERROR:
        st.error(f"Could not load the Db2 integration: {DB2_MODULE_ERROR}")
    else:
        db2_col1, db2_col2 = st.columns(2)
        with db2_col1:
            if st.button("Check Db2 connection", key="rasa_db2_check"):
                try:
                    st.success(connection_status())
                except Exception as exc:
                    st.error(f"Db2 connection failed: {type(exc).__name__}: {exc}")
        with db2_col2:
            if st.button("Initialize audition table", key="rasa_db2_init"):
                try:
                    ensure_schema()
                    st.success("RASA_AUDITIONS table is ready in the current Db2 schema.")
                except Exception as exc:
                    st.error(f"Could not initialize Db2 table: {type(exc).__name__}: {exc}")

        db2_auditions = list(st.session_state.get("rasa_audition_comparisons", []))
        st.write(f"Local audition records available to sync: **{len(db2_auditions)}**")
        if st.button(
            "Sync local audition library to Db2",
            type="primary",
            key="rasa_db2_sync",
            disabled=not bool(db2_auditions),
        ):
            try:
                synced_count = sync_auditions(db2_auditions)
                st.success(f"Synced {synced_count} audition record(s) to Db2. The JSON library was not changed.")
            except Exception as exc:
                st.error(f"Db2 sync failed: {type(exc).__name__}: {exc}")

        if st.button("Load recent Db2 records", key="rasa_db2_load"):
            try:
                st.session_state["rasa_db2_records"] = fetch_auditions(100)
            except Exception as exc:
                st.error(f"Could not load Db2 records: {type(exc).__name__}: {exc}")

        db2_records = st.session_state.get("rasa_db2_records", [])
        if db2_records:
            st.write(f"Records currently loaded from Db2: **{len(db2_records)}**")
            st.dataframe(
                [{
                    "Actor": row.get("actor_label"),
                    "Character": row.get("selected_character"),
                    "Review status": row.get("reviewer_decision"),
                    "Shortlisted": row.get("shortlisted"),
                    "Updated at": row.get("updated_at"),
                } for row in db2_records],
                use_container_width=True,
                hide_index=True,
            )
            with st.expander("Inspect full record payload"):
                st.json(db2_records[0].get("payload", {}))
        else:
            st.info("After configuring Db2, check the connection, initialize the table, then sync the local library.")
