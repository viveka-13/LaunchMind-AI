# agent/language.py
# Supported languages and normalization

SUPPORTED_LANGUAGES = {
    "english": "English",
    "en": "English",
    "spanish": "Spanish",
    "es": "Spanish",
    "french": "French",
    "fr": "French",
    "german": "German",
    "de": "German",
    "hindi": "Hindi",
    "hi": "Hindi",
    "telugu": "Telugu",
    "te": "Telugu",
    "chinese": "Chinese",
    "zh": "Chinese",
    "japanese": "Japanese",
    "ja": "Japanese",
    "arabic": "Arabic",
    "ar": "Arabic",
    "portuguese": "Portuguese",
    "pt": "Portuguese",
}

def validate_language(lang: str) -> str:
    """Validate and return canonical language name. Raises ValueError if unsupported."""
    if not lang or not isinstance(lang, str):
        return "English"
    normalized = lang.strip().lower()
    if normalized in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[normalized]
    raise ValueError(f"Unsupported language: '{lang}'. Supported languages are: {sorted(list(set(SUPPORTED_LANGUAGES.values())))}")
