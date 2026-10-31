from fastapi import APIRouter, UploadFile, File, HTTPException
from common import MAX_MEDIA_SIZE, sha256_bytes, make_report
from pathlib import Path
import subprocess
import tempfile
import os

router = APIRouter()
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".aac", ".wma"}
MEDIA_EXT = VIDEO_EXT | AUDIO_EXT

@router.post("/scan-media")
async def scan_media(file: UploadFile = File(...)):
    name = file.filename or "media.bin"
    ext = Path(name).suffix.lower()
    if ext not in MEDIA_EXT:
        raise HTTPException(415, "Unsupported media type. Upload a supported audio or video file.")
    data = await file.read(MAX_MEDIA_SIZE + 1)
    if not data:
        raise HTTPException(400, "The uploaded media file is empty.")
    if len(data) > MAX_MEDIA_SIZE:
        raise HTTPException(413, "Media exceeds the 10 MB limit.")
    findings = []
    score = 0
    # Lightweight metadata/container checks only; no claim of deepfake certainty.
    if ext in VIDEO_EXT and not data.startswith(b"\x00\x00\x00") and b"ftyp" not in data[:32] and ext == ".mp4":
        score += 10
        findings.append("MP4 container signature was not found near the beginning of the file.")
    if ext == ".wav" and not (data.startswith(b"RIFF") and b"WAVE" in data[:16]):
        score += 15
        findings.append("WAV header did not match the expected RIFF/WAVE pattern.")
    if len(data) < 2048:
        findings.append("Very small media file; it may be incomplete or not contain meaningful media.")
        score += 5
    digest = sha256_bytes(data)
    findings.append("No AI-generated/deepfake classifier is bundled in this starter version; audio/video authenticity cannot be concluded from these checks.")
    report = make_report("Media Scam Detector", score, findings,
        "This module currently performs basic file/container checks. It does not prove whether a voice or video is AI-generated.")
    report.update({"filename": name, "size_bytes": len(data), "sha256": digest, "analysis_mode": "basic media integrity checks"})
    return report
