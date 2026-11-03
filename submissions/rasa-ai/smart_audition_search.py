"""Haystack-powered keyword search over RasaAI's saved audition library.

This first version uses BM25 keyword retrieval and an in-memory document store.
It does not make casting decisions or infer talent, emotion, or suitability.
"""
from haystack import Document
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore


def _display(value):
    """Convert a saved value into compact, searchable text."""
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return str(value)
    return str(value)


def _audition_content(item):
    """Build search text from fields already present in a saved audition report."""
    fields = [
        ("Actor", item.get("actor_label")),
        ("Analysis type", item.get("analysis_type", "video")),
        ("Video file", item.get("video_file")),
        ("Audio file", item.get("audio_file")),
        ("Character", item.get("selected_character")),
        ("Vocal analysis", item.get("vocal_analysis")),
        ("Median pitch Hz", item.get("median_pitch_hz")),
        ("Pitch 10th percentile Hz", item.get("pitch_10th_percentile_hz")),
        ("Pitch 90th percentile Hz", item.get("pitch_90th_percentile_hz")),
        ("Pitch standard deviation Hz", item.get("pitch_standard_deviation_hz")),
        ("Voiced frame fraction", item.get("voiced_frame_fraction")),
        ("Mean RMS energy", item.get("mean_rms_energy")),
        ("Energy variation std", item.get("energy_variation_std")),
        ("Estimated low-energy seconds", item.get("estimated_low_energy_seconds")),
        ("Detected energy gaps over 0.35 seconds", item.get("detected_energy_gaps_over_0_35s")),
        ("Review status", item.get("reviewer_decision", "Not reviewed")),
        ("Shortlisted", item.get("shortlisted", False)),
        ("Reviewer notes", item.get("reviewer_notes")),
        ("Duration seconds", item.get("duration_seconds_estimate")),
        ("Pose detection rate", item.get("pose_detection_rate")),
        ("Face detection rate", item.get("face_detection_rate")),
        ("Mean normalized landmark movement index", item.get("mean_normalized_landmark_movement_index")),
        ("Mean shoulder tilt index", item.get("mean_shoulder_tilt_index")),
        ("Mean torso lateral offset", item.get("mean_torso_lateral_offset")),
        ("Fraction samples with wrist above shoulder", item.get("fraction_samples_with_wrist_above_shoulder")),
        ("Mean mouth opening ratio", item.get("mean_mouth_opening_ratio")),
        ("Mouth opening variability", item.get("mouth_opening_variability")),
        ("Mean eye openness proxy", item.get("mean_eye_openness_proxy")),
        ("Eye openness variability", item.get("eye_openness_variability")),
        ("Mean brow eye spacing proxy", item.get("mean_brow_eye_spacing_proxy")),
        ("Brow eye spacing variability", item.get("brow_eye_spacing_variability")),
        ("Evidence quality notes", item.get("evidence_quality_notes")),
        ("Analysis method", item.get("analysis_method")),
    ]
    parts = [f"{label}: {_display(value)}" for label, value in fields if value not in (None, "", [], {})]

    # Timestamped observations make concrete recorded cues searchable too.
    observations = item.get("sample_observations", item.get("samples", []))
    if isinstance(observations, list):
        for observation in observations[:100]:
            if isinstance(observation, dict):
                cue_parts = []
                for key in (
                    "timestamp_seconds", "pose_detected",
                    "movement_since_previous_sample_index", "wrist_above_shoulder",
                    "shoulder_tilt_index", "torso_lateral_offset",
                    "mouth_opening_ratio", "eye_openness_proxy",
                    "brow_eye_spacing_proxy", "model_expression_label",
                ):
                    if observation.get(key) is not None:
                        cue_parts.append(f"{key}: {observation[key]}")
                if cue_parts:
                    parts.append("Timestamped observation: " + ", ".join(cue_parts))
    return "\n".join(parts)


def search_auditions(items, query, top_k=10):
    """Return matching saved auditions using Haystack's BM25 keyword retriever."""
    if not query or not query.strip() or not items:
        return []

    store = InMemoryDocumentStore()
    documents = []
    for index, item in enumerate(items):
        content = _audition_content(item)
        if content.strip():
            documents.append(
                Document(
                    id=f"audition-{index}",
                    content=content,
                    meta={"library_index": index},
                )
            )
    if not documents:
        return []

    store.write_documents(documents)
    retriever = InMemoryBM25Retriever(document_store=store)
    response = retriever.run(query=query.strip(), top_k=min(top_k, len(documents)))
    return [
        {
            "library_index": int(doc.meta["library_index"]),
            "score": doc.score,
            "content": doc.content,
        }
        for doc in response.get("documents", [])
        if "library_index" in doc.meta
    ]
