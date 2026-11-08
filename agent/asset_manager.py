import asyncio
import os
import json
import html
from langchain_core.messages import SystemMessage, HumanMessage

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
    try:
        text = await asset_llm_invoke(system_prompt, prompt, max_tokens)
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
    language = state.get("language", "en")
    
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
    try:
        await emit_callback("Generating Brand Identity...")
        assets["brand_kit"] = await asyncio.wait_for(
            generate_brand_kit(idea, language, safe_json_invoke),
            timeout=35.0
        )
    except Exception as e:
        assets["brand_kit"] = {
            "brand_name": idea.title(),
            "tagline": f"AI-Powered Solution for {idea}",
            "colors": {"primary": "#6366f1", "secondary": "#06b6d4", "accent": "#f59e0b", "background": "#0f172a"},
        }

    # 2. Logo
    try:
        await emit_callback("Generating Logo...")
        images = state.get("images", [])
        assets["logo_svg"] = await asyncio.wait_for(
            generate_logo(idea, assets["brand_kit"], images, asset_llm_invoke, extract_code_block),
            timeout=35.0
        )
    except Exception as e:
        assets["logo_svg"] = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400"><rect width="400" height="400" rx="40" fill="#0f172a"/><text x="200" y="220" font-size="100" text-anchor="middle" fill="#6366f1">🚀</text></svg>'

    # 3. Poster
    try:
        await emit_callback("Generating Marketing Poster...")
        images = state.get("images", [])
        assets["poster_html"] = await asyncio.wait_for(
            generate_poster(idea, assets["brand_kit"], images, asset_llm_invoke, extract_code_block),
            timeout=35.0
        )
    except Exception as e:
        assets["poster_html"] = f"<div><h3>{html.escape(idea)}</h3><p>Poster could not be rendered.</p></div>"

    # 4. Landing Page
    try:
        await emit_callback("Generating Landing Page...")
        features = state.get("core_features", "")
        assets["landing_page_html"] = await asyncio.wait_for(
            generate_landing_page(idea, features, assets["brand_kit"], asset_llm_invoke, extract_code_block),
            timeout=35.0
        )
    except Exception as e:
        assets["landing_page_html"] = f"<div><h1>{html.escape(idea)}</h1><p>Landing page preview unavailable.</p></div>"

    # 5. Wireframes
    try:
        await emit_callback("Generating MVP Wireframes...")
        assets["wireframes_svg"] = await asyncio.wait_for(
            generate_wireframes(idea, asset_llm_invoke, extract_code_block),
            timeout=35.0
        )
    except Exception as e:
        assets["wireframes_svg"] = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600"><rect width="800" height="600" fill="#0f172a"/><text x="400" y="300" font-size="24" text-anchor="middle" fill="#64748b">Wireframe Preview</text></svg>'

    # 6. Architecture
    try:
        await emit_callback("Generating System Architecture...")
        assets["architecture_html"] = await asyncio.wait_for(
            generate_architecture(idea, state.get("plan_id", "unknown"), safe_json_invoke),
            timeout=35.0
        )
    except Exception as e:
        assets["architecture_html"] = f"<div><p>System architecture diagram unavailable.</p></div>"

    # 7. Investor Report
    try:
        await emit_callback("Generating Investor Report...")
        critique = state.get("critique", "{}")
        plan_id = state.get("plan_id", "unknown")
        report_res = await asyncio.wait_for(
            generate_investor_report(idea, critique, plan_id),
            timeout=35.0
        )
        assets["investor_report_pdf"] = report_res.get("path") if isinstance(report_res, dict) and report_res.get("status") == "ok" else (report_res if isinstance(report_res, str) else "")
    except Exception as e:
        assets["investor_report_pdf"] = ""
    
    # 8. Brand Strategy Document
    await emit_callback("Generating Brand Strategy Document...")
    bk = assets["brand_kit"]
    brand_name = html.escape(str(bk.get("brand_name", "Startup")))
    primary_c = html.escape(str(bk.get("colors", {}).get("primary", "#6366f1")))
    personas_html = ""
    for p in bk.get("customer_personas", []):
        personas_html += f"<li>{html.escape(str(p))}</li>"
    assets["brand_strategy_html"] = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{brand_name} - Brand Strategy</title>
<style>body{{font-family:'Inter',sans-serif;max-width:800px;margin:2rem auto;padding:2rem;background:#0f172a;color:#e2e8f0;}}
h1{{color:{primary_c};}} h2{{color:#94a3b8;border-bottom:1px solid #334155;padding-bottom:0.5rem;margin-top:2rem;}}
ul{{padding-left:1.5rem;}} li{{margin-bottom:0.5rem;}} .section{{margin-bottom:2rem;}}
</style></head><body>
<h1>🎯 {brand_name} — Brand Strategy</h1>
<div class="section"><h2>Brand Strategy</h2><p>{html.escape(str(bk.get('brand_strategy', 'N/A')))}</p></div>
<div class="section"><h2>Logo Concept & Meaning</h2><p>{html.escape(str(bk.get('logo_meaning', 'N/A')))}</p></div>
<div class="section"><h2>Color Psychology</h2><p>{html.escape(str(bk.get('psychology', 'N/A')))}</p></div>
<div class="section"><h2>Customer Personas</h2><ul>{personas_html if personas_html else '<li>No personas generated</li>'}</ul></div>
<div class="section"><h2>Marketing Strategy</h2><p>{html.escape(str(bk.get('marketing_strategy', 'N/A')))}</p></div>
</body></html>"""
    
    return assets
