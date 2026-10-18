# agent/voice_generator.py
# Real text-to-speech pitch narration generator for LaunchMind-AI

import os
import logging
from typing import Optional

from agent.memory import save_audio_generation
from agent.tts_service import synthesize_pitch_narration

logger = logging.getLogger(__name__)


def generate_voice_narration(
    plan_id: str,
    plan_data: dict,
    language: Optional[str] = None,
    provider_name: Optional[str] = None,
) -> dict:
    """
    Generate authentic voice narration for a startup pitch.
    Returns a status object:
    {
        "status": "ok" | "skipped" | "failed",
        "reason": str | None,
        "path": str | None,
        "duration_seconds": float | None,
        "provider": str,
        "voice": str
    }
    No mock, stub, or silent placeholder audio is ever generated.
    """
    out_dir = "./data/audio"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.abspath(f"{out_dir}/{plan_id}_narration.mp3")

    lang = language or plan_data.get("language") or "en"

    try:
        result = synthesize_pitch_narration(
            plan_data=plan_data,
            out_path=out_path,
            language=lang,
            provider_name=provider_name,
        )
    except Exception as e:
        logger.error("Unhandled exception during pitch narration: %s", e, exc_info=True)
        result = {
            "status": "failed",
            "reason": f"Unexpected error during narration synthesis: {str(e)}",
            "path": None,
            "duration_seconds": None,
            "provider": provider_name or os.getenv("TTS_PROVIDER", "edge"),
            "voice": "unknown",
        }

    # Persist to database
    save_audio_generation(plan_id, result)
    return result
