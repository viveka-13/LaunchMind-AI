import asyncio
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from typing import Optional, Protocol, Tuple, List, Dict
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception,
)

logger = logging.getLogger(__name__)

# Constants
MAX_CHUNK_CHARS = 3000
MIN_AUDIO_BYTES = 10240  # 10 KB
DEFAULT_PROVIDER = "edge"


class TTSProvider(Protocol):
    name: str

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        ...

    def default_voice(self, language: str) -> str:
        ...

    def is_configured(self) -> bool:
        ...


# ─────────────────────────────────────────────
# Edge TTS Provider (Free, default, no API key)
# ─────────────────────────────────────────────

EDGE_VOICES: Dict[str, str] = {
    "en": "en-US-ChristopherNeural",
    "hi": "hi-IN-SwaraNeural",
    "te": "te-IN-ShrutiNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-KillianNeural",
}


def _run_async_safely(coro):
    """Run an async coroutine safely even if an event loop is already running in current thread."""
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class EdgeTTSProvider:
    name: str = "edge"

    def default_voice(self, language: str) -> str:
        lang_norm = (language or "en").lower().strip()
        # Handle full names or ISO codes
        lang_map = {
            "english": "en",
            "hindi": "hi",
            "telugu": "te",
            "spanish": "es",
            "french": "fr",
            "german": "de",
        }
        lang_code = lang_map.get(lang_norm, lang_norm[:2])
        if lang_code in EDGE_VOICES:
            return EDGE_VOICES[lang_code]
        logger.warning("Unknown language '%s', falling back to English voice", language)
        return EDGE_VOICES["en"]

    def is_configured(self) -> bool:
        return True

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        import edge_tts

        async def _synthesize():
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(out_path)

        _run_async_safely(_synthesize())


# ─────────────────────────────────────────────
# OpenAI TTS Provider (Keyed provider)
# ─────────────────────────────────────────────

OPENAI_VOICES: Dict[str, str] = {
    "en": "alloy",
    "hi": "alloy",
    "te": "alloy",
    "es": "alloy",
    "fr": "alloy",
    "de": "alloy",
}


class OpenAITTSProvider:
    name: str = "openai"

    def default_voice(self, language: str) -> str:
        lang_norm = (language or "en").lower().strip()
        lang_map = {
            "english": "en",
            "hindi": "hi",
            "telugu": "te",
            "spanish": "es",
            "french": "fr",
            "german": "de",
        }
        lang_code = lang_map.get(lang_norm, lang_norm[:2])
        return OPENAI_VOICES.get(lang_code, "alloy")

    def is_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def synthesize(self, text: str, voice: str, out_path: str) -> None:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")

        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
        )
        response.stream_to_file(out_path)


# ─────────────────────────────────────────────
# Provider Registry & Retry Policy
# ─────────────────────────────────────────────

def is_retryable_error(exception: BaseException) -> bool:
    """Determine whether an exception is retryable (timeouts, 429, 5xx, connection)."""
    exc_name = exception.__class__.__name__
    status_code = getattr(exception, "status_code", None)
    if status_code is None and hasattr(exception, "response"):
        status_code = getattr(exception.response, "status_code", None)

    # Never retry on 401 or 403 or invalid voice / bad request
    if status_code in (401, 403, 400, 404):
        return False
    if "Auth" in exc_name or "Permission" in exc_name:
        return False

    # Retry on 429, 5xx
    if status_code and (status_code == 429 or status_code >= 500):
        return True

    # Retry on timeouts, connection errors
    msg = str(exception).lower()
    if any(k in msg for k in ("timeout", "connection", "connect", "reset by peer", "rate limit")):
        return True
    if any(k in exc_name.lower() for k in ("timeout", "connection", "network", "ratelimit")):
        return True

    return False


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception(is_retryable_error),
    reraise=True,
)
def synthesize_with_retry(provider: TTSProvider, text: str, voice: str, out_path: str) -> None:
    provider.synthesize(text, voice, out_path)


def get_provider(provider_name: Optional[str] = None) -> Tuple[Optional[TTSProvider], Optional[str]]:
    """Get provider instance and configuration status or error reason."""
    chosen = (provider_name or os.getenv("TTS_PROVIDER", DEFAULT_PROVIDER)).lower().strip()
    if chosen == "edge":
        return EdgeTTSProvider(), None
    elif chosen == "openai":
        p = OpenAITTSProvider()
        if not p.is_configured():
            return None, "OPENAI_API_KEY is not configured"
        return p, None
    else:
        return None, f"Unknown TTS provider: '{chosen}'. Supported providers are 'edge' and 'openai'."


# ─────────────────────────────────────────────
# FFmpeg Check Helper
# ─────────────────────────────────────────────

def check_ffmpeg() -> Optional[str]:
    """Check if ffmpeg executable is available on PATH."""
    return shutil.which("ffmpeg")


def get_ffmpeg_missing_reason() -> str:
    return (
        "ffmpeg not found. To install ffmpeg: on Windows, run 'winget install Gyan.FFmpeg' "
        "or download from https://ffmpeg.org; on macOS, run 'brew install ffmpeg'; "
        "on Linux, run 'sudo apt install ffmpeg'."
    )


# ─────────────────────────────────────────────
# Spoken Text Normalization & Script Builder
# ─────────────────────────────────────────────

def _expand_figures(text: str) -> str:
    """Expand financial and numerical expressions to natural spoken form."""
    # Remove commas from numbers first (e.g., $2,903.7 -> $2903.7)
    text = re.sub(r'(\d),(\d)', r'\1\2', text)
    # $1.2B -> 1.2 billion dollars
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*[bB](?:illion)?\b', r'\1 billion dollars', text)
    # $1.2M -> 1.2 million dollars
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*[mM](?:illion)?\b', r'\1 million dollars', text)
    # $500K -> 500 thousand dollars
    text = re.sub(r'\$(\d+(?:\.\d+)?)\s*[kK]\b', r'\1 thousand dollars', text)
    # $50 -> 50 dollars
    text = re.sub(r'\$(\d+(?:\.\d+)?)', r'\1 dollars', text)
    # 5% -> 5 percent
    text = re.sub(r'(\d+(?:\.\d+)?)\s*%', r'\1 percent', text)

    # Word conversions for common decimals like "1.2 billion dollars" -> "one point two billion dollars"
    num_words = {
        "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
    }
    def replace_small_decimal(m):
        whole, frac, unit = m.group(1), m.group(2), m.group(3)
        w_word = num_words.get(whole, whole)
        f_word = " ".join(num_words.get(c, c) for c in frac)
        return f"{w_word} point {f_word} {unit} dollars"

    text = re.sub(r'\b(\d+)\.(\d+)\s*(million|billion|thousand)\s+dollars\b', replace_small_decimal, text)
    return text


def clean_spoken_text(text: str) -> str:
    """Clean text for natural TTS output by stripping markdown, links, and symbols."""
    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove code blocks and inline backticks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Expand figures
    text = _expand_figures(text)
    # Remove markdown headers, bold, italics, strikethrough, blockquotes
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Remove table delimiters
    text = re.sub(r'\|', ' ', text)
    # Turn bullet points into clean spoken sentences
    text = re.sub(r'^\s*[-*•]\s*', '', text, flags=re.MULTILINE)
    # Remove stray brackets
    text = re.sub(r'[\[\]\(\)]', ' ', text)
    # Normalize whitespaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Ensure proper punctuation at ends of lines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    cleaned_lines = []
    for line in lines:
        if line and line[-1] not in '.!?':
            line += '.'
        cleaned_lines.append(line)
    return " ".join(cleaned_lines)


def build_narration_script(plan_data: dict, max_words: int = 500) -> str:
    """
    Build spoken pitch deck script from slide title + key points per slide.
    Targets ~2-4 minutes total (~300-500 words).
    """
    title = plan_data.get("startup_title") or plan_data.get("idea") or "Our Startup"
    intro = f"This is the pitch for {title}."
    outro = f"Thank you for listening to the pitch for {title}."

    pitch_deck = plan_data.get("pitch_deck_outline", "")
    slides_content: List[str] = []

    if pitch_deck:
        # Parse slide sections
        raw_slides = re.split(r'\n(?=\s*(?:Slide\s*\d+|#+\s*Slide))', pitch_deck, flags=re.IGNORECASE)
        for s in raw_slides:
            s_clean = clean_spoken_text(s)
            if s_clean:
                # Keep slide title plus first 2 sentences / points
                sentences = re.split(r'(?<=[.!?])\s+', s_clean)
                slides_content.append(" ".join(sentences[:3]))
    else:
        # Fallback to key plan fields if no pitch deck outline
        fields = [
            ("The Problem", plan_data.get("problem_statement", "")),
            ("The Solution", plan_data.get("solution", "")),
            ("Key Features", plan_data.get("core_features", "")),
            ("Business Model", plan_data.get("business_model", "") or plan_data.get("revenue_model", "")),
            ("Market Opportunity", plan_data.get("market_gap", "")),
        ]
        for heading, body in fields:
            if body:
                b_clean = clean_spoken_text(body)
                sentences = re.split(r'(?<=[.!?])\s+', b_clean)
                slides_content.append(f"{heading}. " + " ".join(sentences[:2]))

    # Join and enforce word boundary limit
    body_text = " ".join(slides_content)
    words = body_text.split()
    if len(words) > max_words:
        # Trim on full sentences within limit
        sentences = re.split(r'(?<=[.!?])\s+', body_text)
        accumulated = []
        cur_count = 0
        for s in sentences:
            s_words = len(s.split())
            if cur_count + s_words > max_words:
                break
            accumulated.append(s)
            cur_count += s_words
        body_text = " ".join(accumulated)

    full_script = f"{intro} {body_text} {outro}".strip()
    return clean_spoken_text(full_script)


# ─────────────────────────────────────────────
# Sentence Chunking
# ─────────────────────────────────────────────

def chunk_script(script: str, max_chunk_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    """Split script on sentence boundaries into chunks under max_chunk_chars."""
    if not script:
        return []

    # Split into sentences preserving punctuation
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        sent_len = len(sent) + (1 if current_chunk else 0)
        if current_length + sent_len > max_chunk_chars and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_length = len(sent)
        else:
            current_chunk.append(sent)
            current_length += sent_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ─────────────────────────────────────────────
# Output Validation (mutagen)
# ─────────────────────────────────────────────

def validate_audio(file_path: str, script_text: str) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Validate output MP3 with mutagen:
    - File exists and >= 10 KB
    - Duration > 0
    - Duration plausible (roughly 120 - 200 wpm)
    """
    if not os.path.exists(file_path):
        return False, "Audio output file does not exist", None

    file_size = os.path.getsize(file_path)
    if file_size < MIN_AUDIO_BYTES:
        return False, f"Audio file is too small ({file_size} bytes, minimum {MIN_AUDIO_BYTES} required)", None

    import mutagen.mp3
    try:
        audio = mutagen.mp3.MP3(file_path)
        duration = float(audio.info.length)
    except Exception as e:
        return False, f"Failed to parse MP3 audio header: {e}", None

    if duration <= 0:
        return False, "Audio file has zero or negative duration", duration

    # Plausibility check: 120 - 200 spoken words per minute (~2.0 - 3.3 words/sec)
    words = script_text.split()
    word_count = len(words)
    if word_count > 0:
        expected_duration = word_count / 2.67  # ~160 wpm
        min_allowed = max(3.0, 0.20 * expected_duration)
        max_allowed = max(10.0, 3.00 * expected_duration)

        if duration < min_allowed or duration > max_allowed:
            return (
                False,
                f"audio duration inconsistent with script length: {duration:.1f}s for {word_count} words (expected {min_allowed:.1f}s - {max_allowed:.1f}s)",
                duration,
            )

    return True, None, duration


# ─────────────────────────────────────────────
# Synthesis & Concatenation Service
# ─────────────────────────────────────────────

def synthesize_pitch_narration(
    plan_data: dict,
    out_path: str,
    language: str = "en",
    provider_name: Optional[str] = None,
) -> dict:
    """
    Main orchestration function:
    1. Check ffmpeg
    2. Get TTS Provider & verify configuration
    3. Build narration script
    4. Chunk and synthesize
    5. Concat chunks with pause
    6. Validate audio output with mutagen
    7. Clean up temporary files
    """
    # 1. Check ffmpeg
    ffmpeg_exe = check_ffmpeg()
    if not ffmpeg_exe:
        return {
            "status": "skipped",
            "reason": get_ffmpeg_missing_reason(),
            "path": None,
            "duration_seconds": None,
            "provider": provider_name or os.getenv("TTS_PROVIDER", DEFAULT_PROVIDER),
            "voice": "unknown",
        }

    # 2. Provider resolution
    provider, config_err = get_provider(provider_name)
    chosen_provider_name = provider_name or os.getenv("TTS_PROVIDER", DEFAULT_PROVIDER)

    if not provider:
        status = "skipped" if "configured" in (config_err or "") else "failed"
        return {
            "status": status,
            "reason": config_err,
            "path": None,
            "duration_seconds": None,
            "provider": chosen_provider_name,
            "voice": "unknown",
        }

    voice = provider.default_voice(language)

    # 3. Build script
    script = build_narration_script(plan_data)
    if not script.strip():
        return {
            "status": "failed",
            "reason": "Pitch script is empty or could not be generated from plan data",
            "path": None,
            "duration_seconds": None,
            "provider": provider.name,
            "voice": voice,
        }

    # 4. Chunk script
    chunks = chunk_script(script)
    if not chunks:
        return {
            "status": "failed",
            "reason": "Script chunking produced no chunks",
            "path": None,
            "duration_seconds": None,
            "provider": provider.name,
            "voice": voice,
        }

    # 5. Synthesize chunks into temp files
    temp_dir = tempfile.mkdtemp(prefix="pitch_audio_")
    chunk_files: List[str] = []

    try:
        for idx, chunk in enumerate(chunks):
            chunk_file = os.path.join(temp_dir, f"chunk_{idx:03d}.mp3")
            try:
                synthesize_with_retry(provider, chunk, voice, chunk_file)
            except Exception as e:
                logger.error("TTS synthesis error for chunk %d: %s", idx, e)
                return {
                    "status": "failed",
                    "reason": f"TTS synthesis failed on chunk {idx}: {str(e)}",
                    "path": None,
                    "duration_seconds": None,
                    "provider": provider.name,
                    "voice": voice,
                }
            chunk_files.append(chunk_file)

        # 6. Concatenate chunks
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        if len(chunk_files) == 1:
            shutil.copyfile(chunk_files[0], out_path)
        else:
            # Multi-chunk concatenation using ffmpeg concat demuxer
            concat_list_path = os.path.join(temp_dir, "concat.txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for cf in chunk_files:
                    safe_path = os.path.abspath(cf).replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            ffmpeg_bin = check_ffmpeg() or "ffmpeg"
            cmd = [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", out_path]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0 or not os.path.exists(out_path):
                # Fallback to direct byte concatenation for valid MP3 frames
                with open(out_path, "wb") as out_f:
                    for cf in chunk_files:
                        with open(cf, "rb") as in_f:
                            out_f.write(in_f.read())

        # 7. Validate output
        is_ok, val_err, duration = validate_audio(out_path, script)
        if not is_ok:
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            return {
                "status": "failed",
                "reason": val_err,
                "path": None,
                "duration_seconds": duration,
                "provider": provider.name,
                "voice": voice,
            }

        return {
            "status": "ok",
            "reason": None,
            "path": out_path,
            "duration_seconds": round(duration, 2) if duration else None,
            "provider": provider.name,
            "voice": voice,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
