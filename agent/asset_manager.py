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

# Shared LLM invoker for asset generation
async def asset_llm_invoke(system_prompt: str, user_content: str, max_tokens: int = 1500) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    llm = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=api_key, max_tokens=max_tokens)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()

async def safe_json_invoke(system_prompt: str, prompt: str, max_tokens: int = 1000) -> dict:
    text = await asset_llm_invoke(system_prompt, prompt, max_tokens)
    try:
        clean = extract_code_block(text, "json")
        return json.loads(clean)
    except:
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
    
    return assets
