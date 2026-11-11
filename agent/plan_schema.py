"""
agent/plan_schema.py
Single source of truth for plan section keys, output contracts, and node validation.
"""
import json
import re
from typing import Dict, List, Tuple, Optional, Any

PLAN_SECTION_KEYS = [
    "startup_title",
    "problem_statement",
    "target_audience",
    "market_research",
    "competitor_analysis",
    "market_gap",
    "solution_strategy",
    "core_features",
    "revenue_model",
    "pricing_model",
    "financial_projection",
    "cap_table",
    "implementation_roadmap",
    "pitch_deck_outline",
    "executive_summary",
    "matched_investors",
    "critique",
    "market_sizing",
    "competitor_swot",
    "tasks",
]

# Per-node output contracts: required keys and minimum contents
NODE_OUTPUT_CONTRACTS: Dict[str, Dict[str, Any]] = {
    "decompose": {
        "required_keys": ["tasks"],
        "min_list_count": {"tasks": 5},
    },
    "research_market": {
        "required_keys": ["market_research"],
        "min_lengths": {"market_research": 50},
    },
    "research_competitors": {
        "required_keys": ["competitor_analysis"],
        "min_lengths": {"competitor_analysis": 50},
    },
    "synthesize_research": {
        "required_keys": ["research_brief"],
        "min_lengths": {"research_brief": 20},
    },
    "competitor_swot": {
        "required_keys": ["competitor_swot"],
        "min_lengths": {"competitor_swot": 20},
    },
    "store_research": {
        "required_keys": [],
    },
    "analyze_gaps": {
        "required_keys": ["market_gap"],
        "min_lengths": {"market_gap": 20},
    },
    "calculate_market_size": {
        "required_keys": ["market_sizing"],
        "min_lengths": {"market_sizing": 20},
    },
    "generate_solution": {
        "required_keys": ["solution_strategy", "startup_title"],
        "min_lengths": {"solution_strategy": 30, "startup_title": 2},
    },
    "generate_features": {
        "required_keys": ["core_features"],
        "min_lengths": {"core_features": 30},
    },
    "generate_revenue": {
        "required_keys": ["revenue_model"],
        "min_lengths": {"revenue_model": 20},
    },
    "pricing_model": {
        "required_keys": ["pricing_model"],
        "min_lengths": {"pricing_model": 20},
    },
    "financial_projection": {
        "required_keys": ["financial_projection"],
        "min_lengths": {"financial_projection": 20},
    },
    "cap_table": {
        "required_keys": ["cap_table"],
        "min_lengths": {"cap_table": 20},
    },
    "investor_matching": {
        "required_keys": ["matched_investors"],
        "min_lengths": {"matched_investors": 20},
    },
    "generate_roadmap": {
        "required_keys": ["implementation_roadmap"],
        "min_lengths": {"implementation_roadmap": 30},
    },
    "generate_pitch": {
        "required_keys": ["pitch_deck_outline"],
        "min_lengths": {"pitch_deck_outline": 30},
    },
    "compile_plan": {
        "required_keys": ["executive_summary", "problem_statement", "target_audience", "startup_title"],
        "min_lengths": {
            "executive_summary": 30,
            "problem_statement": 20,
            "target_audience": 10,
            "startup_title": 2,
        },
    },
    "adversarial_review": {
        "required_keys": ["critique"],
        "min_lengths": {"critique": 20},
    },
    "save_plan": {
        "required_keys": ["plan_id"],
    },
    "generate_assets": {
        "required_keys": ["assets"],
    },
}


def _safe_load_json(val: Any) -> Optional[dict]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


def validate_node_output(node_name: str, output: Optional[dict]) -> Tuple[bool, Optional[str]]:
    """
    Validate that a node produced its contractually required output keys, minimum content lengths,
    and semantic completeness (e.g. non-empty SWOT quadrants, 3 pricing tiers with features, 4 roadmap phases).
    Returns (is_valid, error_reason).
    """
    if output is None or not isinstance(output, dict):
        return False, f"Node '{node_name}' returned empty or non-dict output"

    contract = NODE_OUTPUT_CONTRACTS.get(node_name)
    if not contract:
        return True, None

    # Check required keys
    for key in contract.get("required_keys", []):
        val = output.get(key)
        if val is None:
            return False, f"Missing required key '{key}' in node '{node_name}' output"
        if isinstance(val, str) and not val.strip():
            return False, f"Empty string for required key '{key}' in node '{node_name}' output"
        if isinstance(val, (list, dict)) and len(val) == 0:
            return False, f"Empty collection for required key '{key}' in node '{node_name}' output"

    # Check minimum string lengths
    for key, min_len in contract.get("min_lengths", {}).items():
        val = str(output.get(key, ""))
        if len(val.strip()) < min_len:
            return False, f"Key '{key}' in node '{node_name}' too short (len={len(val.strip())}, min={min_len})"

    # Check minimum list items
    for key, min_count in contract.get("min_list_count", {}).items():
        items = output.get(key, [])
        if not isinstance(items, list) or len(items) < min_count:
            return False, f"Key '{key}' in node '{node_name}' has {len(items)} items, minimum {min_count} required"

    # Semantic non-empty checks for specific nodes
    if node_name == "competitor_swot":
        cs_data = _safe_load_json(output.get("competitor_swot"))
        if not cs_data:
            return False, "Node 'competitor_swot' output is not valid JSON"
        comps = cs_data.get("competitors") or cs_data.get("competitor_matrix") or []
        if len(comps) < 3:
            return False, f"Competitor analysis must have >= 3 competitors, got {len(comps)}"
        swot = cs_data.get("swot_analysis") or cs_data.get("swot") or {}
        for q in ["strengths", "weaknesses", "opportunities", "threats"]:
            items = swot.get(q) or []
            if len(items) < 3:
                return False, f"SWOT quadrant '{q}' must have >= 3 items, got {len(items)}"

    elif node_name == "pricing_model":
        p_data = _safe_load_json(output.get("pricing_model"))
        if not p_data:
            return False, "Node 'pricing_model' output is not valid JSON"
        tiers = p_data.get("tiers") or []
        if len(tiers) != 3:
            return False, f"Pricing model must have exactly 3 tiers, got {len(tiers)}"
        for i, t in enumerate(tiers):
            feats = t.get("features") or []
            if len(feats) < 1:
                return False, f"Pricing tier {i+1} ('{t.get('name')}') must have non-empty features list"

    elif node_name == "generate_roadmap":
        roadmap_text = str(output.get("implementation_roadmap", ""))
        for phase_num in ["1", "2", "3", "4"]:
            if not re.search(rf"Phase\s*{phase_num}", roadmap_text, re.IGNORECASE):
                return False, f"Roadmap must contain Phase {phase_num}"

    elif node_name == "calculate_market_size":
        ms_data = _safe_load_json(output.get("market_sizing"))
        if not ms_data:
            return False, "Node 'calculate_market_size' output is not valid JSON"
        if not ms_data.get("methodology") or len(str(ms_data.get("methodology")).strip()) < 20:
            return False, "Market sizing methodology is missing or too short (min 20 chars)"
        assump = ms_data.get("assumptions") or []
        if len(assump) < 2:
            return False, f"Market sizing must have >= 2 assumptions, got {len(assump)}"

    return True, None

