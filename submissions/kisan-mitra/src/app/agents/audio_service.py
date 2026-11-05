"""
Audio Service for Kisan Mitra & Gramin Mitra
Provides reliable Text-to-Speech audio generation for illiterate/neo-literate farmers.
Supports:
1. Google Text-to-Speech (gTTS) for high-quality natural Hindi & English speech.
2. macOS built-in TTS (say + afconvert with Lekha / Rishi voices) as offline fallback.
3. In-memory caching for sub-millisecond retrieval on repeated queries.
"""

import hashlib
import io
import os
import platform
import re
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

# Memory cache for generated audio bytes: key -> (audio_bytes, mime_type)
_AUDIO_CACHE = {}

def clean_text_for_speech(markdown_text: str) -> str:
    """
    Cleans markdown formatting, emojis, bullet symbols, and abbreviations
    into clean, readable conversational Hindi or English text.
    """
    text = markdown_text
    # Remove markdown bold/italics/headers
    text = re.sub(r'[*_#`]', '', text)
    # Remove markdown links [anchor](url) -> anchor
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    # Replace bullet marks with period/pause
    text = re.sub(r'^\s*[-•]\s*', '। ', text, flags=re.MULTILINE)
    # Replace newlines with pause
    text = re.sub(r'\n+', '। ', text)
    # Currency and percent symbols
    text = text.replace('₹', 'रुपये ')
    text = text.replace('%', ' प्रतिशत ')
    # Remove stray special symbols
    text = re.sub(r'[|>{}]', ' ', text)
    # Normalize multiple punctuation
    text = re.sub(r'[।\s]{2,}', '। ', text)
    # Limit length for speech synthesis (up to ~800 characters is ideal for quick voice guidance)
    clean = text.strip()
    if len(clean) > 800:
        clean = clean[:797] + "..."
    return clean

def generate_speech_audio(text: str, lang: str = "hi") -> Tuple[Optional[bytes], str]:
    """
    Generates audio bytes for the given text.
    Returns (audio_bytes, mime_type).
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text or len(clean_text) < 3:
        return None, "audio/mp3"

    cache_key = hashlib.sha256(f"{lang}:{clean_text}".encode("utf-8")).hexdigest()
    if cache_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[cache_key]

    # Strategy 1: gTTS (Google Text-to-Speech)
    try:
        from gtts import gTTS
        lang_code = "hi" if lang == "hi" else "en"
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_bytes = fp.read()
        if audio_bytes and len(audio_bytes) > 100:
            _AUDIO_CACHE[cache_key] = (audio_bytes, "audio/mp3")
            return audio_bytes, "audio/mp3"
    except Exception as e:
        print(f"ℹ️ gTTS unavailable or offline ({e}). Trying system offline TTS...")

    # Strategy 2: macOS built-in 'say' + 'afconvert'
    if platform.system() == "Darwin" and shutil.which("say") and shutil.which("afconvert"):
        try:
            voice = "Lekha" if lang == "hi" else "Rishi"
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f_aiff:
                aiff_path = f_aiff.name
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_wav:
                wav_path = f_wav.name

            try:
                # Run say
                subprocess.run(
                    ["say", "-v", voice, "-o", aiff_path, clean_text],
                    check=True,
                    timeout=8
                )
                # Convert AIFF to standard PCM WAV playable in HTML5 audio
                subprocess.run(
                    ["afconvert", "-f", "WAVE", "-d", "LEI16@22050", aiff_path, wav_path],
                    check=True,
                    timeout=5
                )
                with open(wav_path, "rb") as f_in:
                    audio_bytes = f_in.read()
                if audio_bytes and len(audio_bytes) > 100:
                    _AUDIO_CACHE[cache_key] = (audio_bytes, "audio/wav")
                    return audio_bytes, "audio/wav"
            finally:
                if os.path.exists(aiff_path):
                    os.remove(aiff_path)
                if os.path.exists(wav_path):
                    os.remove(wav_path)
        except Exception as e2:
            print(f"ℹ️ macOS TTS fallback error: {e2}")

    return None, "audio/mp3"
