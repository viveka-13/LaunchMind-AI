async def generate_brand_kit(idea: str, language: str, safe_json_invoke) -> dict:
    prompt = f"""
You are an expert branding agency.
Generate a brand identity for this startup idea:
"{idea}"

Return ONLY valid JSON:
{{
  "brand_name": "Modern, catchy one or two words",
  "tagline": "Short, punchy tagline",
  "colors": {{
    "primary": "#HEX",
    "secondary": "#HEX",
    "accent": "#HEX",
    "background": "#HEX"
  }},
  "typography": {{
    "heading_font": "e.g., 'Inter', sans-serif",
    "body_font": "e.g., 'Roboto', sans-serif"
  }},
  "psychology": "Brief explanation of why these colors/fonts fit the brand"
}}
"""
    system = "You are a brand identity expert. Output ONLY valid JSON."
    return await safe_json_invoke(system, prompt, max_tokens=600)
