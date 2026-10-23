import asyncio
import os
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

from agent.brand_service import generate_brand_kit
from agent.logo_service import generate_logo
from agent.poster_service import generate_poster
from agent.landing_service import generate_landing_page
from agent.wireframe_service import generate_wireframes
from agent.architecture_service import generate_architecture
from agent.investor_service import generate_investor_report

from agent.llm_client import llm_call

# Shared LLM invoker for asset generation using central wrapper
async def asset_llm_invoke(system_prompt: str, user_content: str, max_tokens: int = 1500) -> str:
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    result = await llm_call(messages, node="studio_assets", max_tokens=max_tokens)
    return result.text

async def safe_json_invoke(system_prompt: str, prompt: str, max_tokens: int = 1000) -> dict:
    text = await asset_llm_invoke(system_prompt, prompt, max_tokens)
    try:
        clean = extract_code_block(text, "json")
        return json.loads(clean)
    except Exception:
        # One repair attempt
        repair_prompt = f"{prompt}\n\nCRITICAL: The previous output was invalid JSON. Return ONLY valid JSON."
        try:
            repair_text = await asset_llm_invoke(system_prompt, repair_prompt, max_tokens)
            clean = extract_code_block(repair_text, "json")
            return json.loads(clean)
        except Exception:
            return {}


def extract_code_block(text: str, lang: str = "") -> str:
    # Extracts code from markdown blocks
    if f"```{lang}" in text:
        return text.split(f"```{lang}")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text.strip()

async def generate_all_assets(state: dict, emit_callback) -> dict:
    """
    Orchestrates the generation of all assets sequentially to avoid rate limits.
    """
    idea = state.get("idea", "")
    language = state.get("language", "English")
    
    assets = {
        "brand_kit": {},
        "logo_svg": "",
        "poster_html": "",
        "landing_page_html": "",
        "wireframes_svg": "",
        "architecture_html": "",
        "investor_report_pdf": "",
        "brand_strategy_html": "",
    }

    # 1. Brand Kit
    await emit_callback("Generating Brand Identity...")
    assets["brand_kit"] = await generate_brand_kit(idea, language, safe_json_invoke)
    
    # 2. Logo
    await emit_callback("Generating Logo...")
    images = state.get("images", [])
    assets["logo_svg"] = await generate_logo(idea, assets["brand_kit"], images, asset_llm_invoke, extract_code_block)
    
    # 3. Poster
    await emit_callback("Generating Marketing Poster...")
    assets["poster_html"] = await generate_poster(idea, assets["brand_kit"], images, asset_llm_invoke, extract_code_block)
    
    # 4. Landing Page
    await emit_callback("Generating Landing Page...")
    features = state.get("core_features", "")
    assets["landing_page_html"] = await generate_landing_page(idea, features, assets["brand_kit"], asset_llm_invoke, extract_code_block)
    
    # 5. Wireframes
    await emit_callback("Generating MVP Wireframes...")
    assets["wireframes_svg"] = await generate_wireframes(idea, asset_llm_invoke, extract_code_block)
    
    # 6. Architecture
    await emit_callback("Generating System Architecture...")
    assets["architecture_html"] = await generate_architecture(idea, state["plan_id"], safe_json_invoke)
    
    # 7. Investor Report
    await emit_callback("Generating Investor Report...")
    critique = state.get("critique", "{}")
    plan_id = state.get("plan_id", "unknown")
    assets["investor_report_pdf"] = await generate_investor_report(idea, critique, plan_id)
    
    # 8. Brand Strategy Document
    await emit_callback("Generating Brand Strategy Document...")
    bk = assets["brand_kit"]
    brand_name = bk.get("brand_name", "Startup")
    primary_c = bk.get("colors", {}).get("primary", "#6366f1")
    personas_html = ""
    for p in bk.get("customer_personas", []):
        personas_html += f"<li>{p}</li>"
    assets["brand_strategy_html"] = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{brand_name} - Brand Strategy</title>
<style>body{{font-family:'Inter',sans-serif;max-width:800px;margin:2rem auto;padding:2rem;background:#0f172a;color:#e2e8f0;}}
h1{{color:{primary_c};}} h2{{color:#94a3b8;border-bottom:1px solid #334155;padding-bottom:0.5rem;margin-top:2rem;}}
ul{{padding-left:1.5rem;}} li{{margin-bottom:0.5rem;}} .section{{margin-bottom:2rem;}}
</style></head><body>
<h1>🎯 {brand_name} — Brand Strategy</h1>
<div class="section"><h2>Brand Strategy</h2><p>{bk.get('brand_strategy', 'N/A')}</p></div>
<div class="section"><h2>Logo Concept & Meaning</h2><p>{bk.get('logo_meaning', 'N/A')}</p></div>
<div class="section"><h2>Color Psychology</h2><p>{bk.get('psychology', 'N/A')}</p></div>
<div class="section"><h2>Customer Personas</h2><ul>{personas_html if personas_html else '<li>No personas generated</li>'}</ul></div>
<div class="section"><h2>Marketing Strategy</h2><p>{bk.get('marketing_strategy', 'N/A')}</p></div>
</body></html>"""
    
    return assets
