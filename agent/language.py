# agent/language.py
# Supported languages and normalization

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
}

def validate_language(lang: str) -> str:
    """
    Validate and return canonical language display name (e.g. 'te' -> 'Telugu', 'en' -> 'English').
    Supports both code ('te') and display name ('Telugu') case-insensitively.
    If lang is empty or None, defaults to 'English'.
    Raises ValueError with supported codes if unrecognized.
    """
    if not lang or not isinstance(lang, str):
        return "English"
    normalized = lang.strip().lower()
    
    # Match code directly
    if normalized in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[normalized]
        
    # Match display name case-insensitively
    for code, name in SUPPORTED_LANGUAGES.items():
        if name.lower() == normalized:
            return name
            
    supported_codes = sorted(list(SUPPORTED_LANGUAGES.keys()))
    raise ValueError(f"Unsupported language code: '{lang}'. Supported language codes are: {supported_codes}")
