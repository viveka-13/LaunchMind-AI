import pytest
import json
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from agent.language import validate_language, SUPPORTED_LANGUAGES
from agent.brand_service import generate_brand_kit
from agent.asset_manager import generate_all_assets
from agent.word_generator import generate_business_plan_word
from agent.ppt_generator import generate_pitch_deck_ppt
from agent.pdf_generator import generate_business_plan_pdf
from main import app, IdeaRequest


@pytest.mark.asyncio
async def test_brand_kit_prompt_contains_telugu_and_english_keys():
    """1. Prompt test: call brand-kit builder with language='te' and verify prompt."""
    captured_prompt = {}

    async def mock_safe_json(system, prompt, max_tokens=1200):
        captured_prompt["system"] = system
        captured_prompt["prompt"] = prompt
        return {
            "brand_name": "AgriTech",
            "tagline": "రైతుల కోసం సాంకేతిక విప్లవం",
            "colors": {"primary": "#6366f1"},
            "typography": {"heading_font": "'Inter', sans-serif"},
            "psychology": "విశ్వసనీయత కోసం నీలి రంగు",
            "brand_strategy": "గ్రామీణ ప్రాంతాల్లో విశ్వసనీయత",
            "logo_meaning": "రైతు మరియు సాంకేతికత కలయిక",
            "customer_personas": ["చిన్న రైతు", "సేంద్రీయ వ్యవసాయదారుడు"],
            "marketing_strategy": "వాట్సాప్ ద్వారా ప్రచారం"
        }

    result = await generate_brand_kit("AI farm monitor", language="te", safe_json_invoke=mock_safe_json)

    assert "Telugu" in captured_prompt["prompt"]
    assert "keep every json key strictly in english" in captured_prompt["prompt"].lower() or "keep all json keys strictly in english" in captured_prompt["prompt"].lower() or "keys strictly in english" in captured_prompt["prompt"].lower()
    assert "Telugu" in captured_prompt["system"]
    assert result["tagline"] == "రైతుల కోసం సాంకేతిక విప్లవం"


@pytest.mark.asyncio
async def test_brand_kit_default_language_is_english():
    """2. Default test: with no language, assert prompt asks for English."""
    captured_prompt = {}

    mock_resp = {
        "brand_name": "AgriPulse",
        "tagline": "Smart farming made simple",
        "colors": {"primary": "#6366f1", "secondary": "#06b6d4", "accent": "#f59e0b", "background": "#0f172a"},
        "typography": {"heading_font": "'Inter', sans-serif", "body_font": "'Roboto', sans-serif"},
        "psychology": "Green reflects growth and prosperity",
        "brand_strategy": "Positioned as an accessible precision farming copilot",
        "logo_meaning": "Sprout merging with data circuit",
        "customer_personas": ["Commercial crop grower", "Agronomist consultant"],
        "marketing_strategy": "Community ag workshops, field demos, and grower partnerships"
    }

    async def mock_safe_json(system, prompt, max_tokens=1200):
        captured_prompt["system"] = system
        captured_prompt["prompt"] = prompt
        return mock_resp

    result_default = await generate_brand_kit("AI farm monitor", safe_json_invoke=mock_safe_json)
    assert "English" in captured_prompt["prompt"]
    assert "English" in captured_prompt["system"]
    assert result_default["tagline"] == "Smart farming made simple"

    # Also test explicit language='en'
    result_en = await generate_brand_kit("AI farm monitor", language="en", safe_json_invoke=mock_safe_json)
    assert "English" in captured_prompt["prompt"]
    assert result_en["tagline"] == "Smart farming made simple"


def test_validation_unsupported_language_returns_422():
    """3. Validation test: POST with language='xx' returns 422 listing supported codes."""
    client = TestClient(app)
    response = client.post("/api/generate", json={"idea": "AI farming tool", "language": "xx"})
    assert response.status_code == 422
    data = response.json()
    err_text = json.dumps(data)
    assert "Unsupported language code" in err_text or "Supported language codes are" in err_text
    for code in SUPPORTED_LANGUAGES.keys():
        assert code in err_text


@pytest.mark.asyncio
async def test_state_language_reaches_brand_kit():
    """4. State test: the language from request reaches the brand-kit generation call."""
    mock_emit = AsyncMock()
    mock_safe_json = AsyncMock(return_value={
        "brand_name": "KisanAI",
        "tagline": "किसान की सच्ची शक्ति",
        "colors": {"primary": "#22c55e"},
        "typography": {"heading_font": "Inter"},
        "psychology": "हरा रंग हरियाली का प्रतीक",
        "brand_strategy": "सशक्त किसान समृद्ध भारत",
        "logo_meaning": "हल और डिजिटल लहर का संगम",
        "customer_personas": ["छोटा किसान"],
        "marketing_strategy": "कृषि मेला प्रदर्शन"
    })

    state = {
        "idea": "Smart irrigation for farmers",
        "language": "hi",
        "core_features": "Soil moisture sensor, weather alerts",
        "images": [],
        "plan_id": "test_plan_lang_123"
    }

    with patch("agent.asset_manager.generate_brand_kit", wraps=generate_brand_kit) as spy_brand_kit:
        with patch("agent.asset_manager.safe_json_invoke", mock_safe_json):
            with patch("agent.asset_manager.asset_llm_invoke", AsyncMock(return_value="🌱")):
                assets = await generate_all_assets(state, mock_emit)
                spy_brand_kit.assert_called_once()
                called_idea, called_lang, _ = spy_brand_kit.call_args[0]
                assert called_lang == "hi"
                assert assets["brand_kit"]["tagline"] == "किसान की सच्ची शक्ति"


@pytest.mark.asyncio
async def test_key_stability_with_non_english_values():
    """5. Key-stability test: with a mocked non-English response, parsed JSON maintains standard English keys."""
    mock_hindi_response = {
        "brand_name": "किसानसाथी",
        "tagline": "खेती की नई पहचान",
        "colors": {
            "primary": "#16a34a",
            "secondary": "#0284c7",
            "accent": "#eab308",
            "background": "#022c22"
        },
        "typography": {
            "heading_font": "'Inter', sans-serif",
            "body_font": "'Roboto', sans-serif"
        },
        "psychology": "हरा रंग समृद्धि और विकास को दर्शाता है",
        "brand_strategy": "किसानों को आधुनिक तकनीक से जोड़ना",
        "logo_meaning": "अन्नदाता और तकनीक का सामंजस्य",
        "customer_personas": [
            "ग्रामीण किसान जो स्मार्टफोन इस्तेमाल करते हैं",
            "कृषि विज्ञान केंद्र के अधिकारी"
        ],
        "marketing_strategy": "गाँव-गाँव में प्रचार और डेमो"
    }

    async def mock_invoke(system, prompt, max_tokens=1200):
        return mock_hindi_response

    kit = await generate_brand_kit("Drone farming", language="hi", safe_json_invoke=mock_invoke)

    expected_top_keys = {
        "brand_name", "tagline", "colors", "typography",
        "psychology", "brand_strategy", "logo_meaning",
        "customer_personas", "marketing_strategy"
    }
    assert set(kit.keys()) == expected_top_keys
    assert set(kit["colors"].keys()) == {"primary", "secondary", "accent", "background"}
    assert set(kit["typography"].keys()) == {"heading_font", "body_font"}
    assert kit["tagline"] == "खेती की नई पहचान"


def test_rendering_non_ascii_docx_pptx_and_pdf(tmp_path):
    """6. Rendering test: brand kit with Hindi & Telugu renders safely in DOCX and PPTX, and returns clear skipped status in PDF."""
    plan_data = {
        "startup_title": "రైతు నేస్తం - किसान साथी",
        "executive_summary": "రైతుల కోసం సరికొత్త ఏఐ సాంకేతిక వేదిక. किसान की उपज बढ़ाने के लिए आधुनिक उपकरण।",
        "problem_statement": "రైతులకు సరైన సమయంలో సమాచారం అందకపోవడం.",
        "target_audience": "భారతీయ రైతులు మరియు వ్యవసాయ నిపుణులు.",
        "solution": "ఏఐ ఆధారిత వ్యవసాయ సలహాదారు.",
        "core_features": "1. వాతావరణ సమాచారం\n2. పంట వ్యాధుల గుర్తింపు\n3. మార్కెట్ ధరలు",
        "market_gap": "సమగ్ర సమాచార లోపం.",
        "revenue_model": "సబ్‌స్క్రిప్షన్ మోడల్.",
        "implementation_roadmap": "Q1: యాప్ విడుదల, Q2: విస్తరణ.",
        "brand_kit": {
            "brand_name": "రైతు నేస్తం",
            "tagline": "రైతుల కోసం సాంకేతిక విప్లవం"
        }
    }

    docx_path = str(tmp_path / "plan.docx")
    pptx_path = str(tmp_path / "deck.pptx")
    pdf_path = str(tmp_path / "plan.pdf")

    # DOCX: Must not crash on non-ASCII characters
    generate_business_plan_word(plan_data, docx_path)
    assert os.path.exists(docx_path)
    assert os.path.getsize(docx_path) > 0

    # PPTX: Must not crash on non-ASCII characters
    generate_pitch_deck_ppt(plan_data, pptx_path)
    assert os.path.exists(pptx_path)
    assert os.path.getsize(pptx_path) > 0

    # PDF: FPDF default fonts lack Devanagari/Telugu glyphs; must return clear status object without crashing
    pdf_result = generate_business_plan_pdf(plan_data, pdf_path)
    assert isinstance(pdf_result, dict)
    assert pdf_result["status"] == "skipped"
    assert "font does not support this language" in pdf_result["reason"]
