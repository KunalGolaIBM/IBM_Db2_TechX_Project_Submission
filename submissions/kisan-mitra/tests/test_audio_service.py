"""
Unit tests for Audio Service (Text-to-Speech)
Verifies audio generation for Hindi and English, text cleaning, and caching.
"""

import pytest
from app.agents.audio_service import clean_text_for_speech, generate_speech_audio

def test_clean_text_for_speech():
    raw_md = "**राम-राम किसान भाई!**\n• आपको ₹6,000 मिलेंगे (100% गारंटी)।\n[विस्तार देखें](http://pmkisan.gov.in)"
    cleaned = clean_text_for_speech(raw_md)
    assert "*" not in cleaned
    assert "http" not in cleaned
    assert "रुपये" in cleaned
    assert "प्रतिशत" in cleaned
    assert len(cleaned) < 850

def test_generate_speech_audio_hindi():
    sample_text = "राम-राम किसान भाई! आपका स्वागत है।"
    audio_bytes, mime = generate_speech_audio(sample_text, lang="hi")
    assert audio_bytes is not None
    assert len(audio_bytes) > 500
    assert mime in ["audio/mp3", "audio/wav"]

def test_generate_speech_audio_english():
    sample_text = "Welcome farmer friend. Mathura potato price is 1520 rupees."
    audio_bytes, mime = generate_speech_audio(sample_text, lang="en")
    assert audio_bytes is not None
    assert len(audio_bytes) > 500
    assert mime in ["audio/mp3", "audio/wav"]

def test_generate_speech_audio_caching():
    sample_text = "परीक्षण ऑडियो संदेश"
    a1, m1 = generate_speech_audio(sample_text, lang="hi")
    a2, m2 = generate_speech_audio(sample_text, lang="hi")
    assert a1 == a2
    assert m1 == m2
