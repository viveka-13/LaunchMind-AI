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
  "psychology": "Brief explanation of why these colors/fonts fit the brand",
  "brand_strategy": "A paragraph explaining the core brand positioning and tone of voice.",
  "logo_meaning": "A paragraph explaining the concept and meaning behind the future logo design.",
  "customer_personas": ["Persona 1: Description", "Persona 2: Description"],
  "marketing_strategy": "A high-level 3-step go-to-market and branding strategy."
}}
"""
    system = "You are a brand identity expert. Output ONLY valid JSON."
    return await safe_json_invoke(system, prompt, max_tokens=1200)
