import logging
from agent.language import validate_language
from agent.models_pydantic import BrandKitModel

logger = logging.getLogger(__name__)


async def generate_brand_kit(idea: str, language: str = "en", safe_json_invoke=None) -> dict:
    canonical_lang = validate_language(language) if language else "English"

    prompt = f"""You are an expert branding agency.
Generate a brand identity for this startup idea:
"{idea}"

CRITICAL LANGUAGE REQUIREMENT:
- Write all customer-facing brand copy (tagline, brand voice description, messaging pillars, value propositions, taglines, sample social copy, psychology, brand_strategy, logo_meaning, customer_personas, marketing_strategy) in {canonical_lang}.
- Keep every JSON key strictly in English as shown below.
- Keep the brand/product name as is unless the idea itself is in {canonical_lang}.
- Keep hex colour codes, font names and URLs unchanged.
- Do not translate field names, enum values, or anything code reads programmatically.

Return ONLY valid JSON matching this schema:
{{
  "brand_name": "Modern, catchy one or two words",
  "tagline": "Short, punchy tagline in {canonical_lang}",
  "colors": {{
    "primary": "#6366f1",
    "secondary": "#06b6d4",
    "accent": "#f59e0b",
    "background": "#0f172a"
  }},
  "typography": {{
    "heading_font": "'Inter', sans-serif",
    "body_font": "'Roboto', sans-serif"
  }},
  "psychology": "Explanation in {canonical_lang} of why these colors/fonts fit the brand",
  "brand_strategy": "A paragraph in {canonical_lang} explaining core brand positioning and tone of voice.",
  "logo_meaning": "A paragraph in {canonical_lang} explaining the concept and meaning behind the logo.",
  "customer_personas": ["Persona 1 description in {canonical_lang}", "Persona 2 description in {canonical_lang}"],
  "marketing_strategy": "A high-level 3-step go-to-market strategy in {canonical_lang}."
}}
"""
    system = f"You are a brand identity expert. Output ONLY valid JSON. All customer-facing brand copy must be in {canonical_lang}. Keep all JSON keys in English."
    raw_data = await safe_json_invoke(system, prompt, max_tokens=2000)

    try:
        validated = BrandKitModel.model_validate(raw_data)
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"[BrandService] Brand kit validation warning: {e}. Using fallback structure.")
        return raw_data if isinstance(raw_data, dict) else BrandKitModel(
            brand_name=idea.split()[0].title() if idea else "Startup",
            tagline=f"Empowering {idea}",
        ).model_dump()

