"""
Tests for LaunchMind-AI real TTS pitch narration.
Run: python -m unittest tests/test_tts.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.tts_service import (
    build_narration_script,
    clean_spoken_text,
    chunk_script,
    validate_audio,
    get_provider,
)


class TestTTSNarration(unittest.TestCase):
    def test_provider_resolution(self):
        edge_provider, err = get_provider("edge")
        self.assertIsNotNone(edge_provider)
        self.assertEqual(edge_provider.name, "edge")

        openai_provider, err = get_provider("openai")
        if not os.getenv("OPENAI_API_KEY"):
            self.assertIsNone(openai_provider)
            self.assertIn("OPENAI_API_KEY", err)

    def test_text_cleaning_and_figures(self):
        dirty = "**Bold** text with $1.2B revenue and 25% growth. Visit https://example.com for more."
        cleaned = clean_spoken_text(dirty)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertTrue("billion dollars" in cleaned.lower() or "1.2" in cleaned)
        self.assertTrue("percent" in cleaned.lower())

    def test_script_builder(self):
        mock_plan = {
            "startup_title": "AgriTech AI",
            "idea": "AI for precision farming",
            "problem_statement": "Small farmers lose 30% crop yield annually to undetected pests.",
            "solution": "Smartphone camera pest diagnosis using lightweight computer vision models.",
            "pitch_deck_outline": "Slide 1: AgriTech AI. Precision farming.\\nSlide 2: The Problem. 30% yield loss.\\nSlide 3: Solution. Mobile camera diagnostics.",
        }
        script = build_narration_script(mock_plan)
        self.assertGreater(len(script.split()), 20)
        self.assertNotIn("Mock", script)
        self.assertNotIn("placeholder", script.lower())

    def test_chunking(self):
        long_text = "This is a sentence. " * 100
        chunks = chunk_script(long_text, max_chunk_chars=500)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 600)

    def test_validate_audio_rejects_placeholder(self):
        temp_fake = "data/audio/fake_test.mp3"
        os.makedirs("data/audio", exist_ok=True)
        with open(temp_fake, "wb") as f:
            f.write(b"Mock Audio Data")
        try:
            is_ok, err, duration = validate_audio(temp_fake, "This is a test script.")
            self.assertFalse(is_ok)
            self.assertIsNotNone(err)
        finally:
            if os.path.exists(temp_fake):
                os.remove(temp_fake)


if __name__ == "__main__":
    unittest.main()
