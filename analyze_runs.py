import json
from agent.memory import get_plan_by_id

old_p = get_plan_by_id('271bf37d-6b75-4118-8582-5e9e9b9342b6')
p1 = get_plan_by_id('9c85cb9e-cfa8-43d4-848f-b8428d8dfba2')
p2 = get_plan_by_id('58d090a1-b4c4-47c4-b451-4bc3c648b0a7')

sections = [
    'problem_statement', 'target_audience', 'market_gap', 'solution',
    'core_features', 'revenue_model', 'pricing_model', 'financial_projection',
    'cap_table', 'implementation_roadmap', 'pitch_deck_outline', 'executive_summary',
    'matched_investors', 'market_sizing', 'competitor_swot', 'critique'
]

print("=== SECTION CHARACTER COUNTS ===")
print(f"{'Section':<25} | {'Before (Old)':<14} | {'After Run 1 (Female)':<22} | {'After Run 2 (B2B)':<20}")
print("-" * 88)
for s in sections:
    c_old = len(str(old_p.get(s, '') or '')) if old_p else 0
    c_p1 = len(str(p1.get(s, '') or '')) if p1 else 0
    c_p2 = len(str(p2.get(s, '') or '')) if p2 else 0
    print(f"{s:<25} | {c_old:<14} | {c_p1:<22} | {c_p2:<20}")

print("\n" + "=" * 60)
print("RUN 1: AI app for female protection")
print("=" * 60)
cs1 = json.loads(p1.get('competitor_swot', '{}'))
print(f"Competitor count: {len(cs1.get('competitors', []))}")
for c in cs1.get('competitors', []):
    print(f"  - {c.get('name')}: strengths='{c.get('strengths')[:40]}...', pricing='{c.get('pricing')}'")
swot1 = cs1.get('swot_analysis', {})
for q in ['strengths', 'weaknesses', 'opportunities', 'threats']:
    print(f"  SWOT {q} count: {len(swot1.get(q, []))}")

pr1 = json.loads(p1.get('pricing_model', '{}'))
print(f"Pricing tiers count: {len(pr1.get('tiers', []))}")
for t in pr1.get('tiers', []):
    print(f"  - Tier '{t.get('name')}' (${t.get('monthly_price')}/mo): {len(t.get('features', []))} features -> {t.get('features')}")

ms1 = json.loads(p1.get('market_sizing', '{}'))
print(f"Market Sizing TAM: {ms1.get('tam')}")
print(f"Market Sizing SAM: {ms1.get('sam')}")
print(f"Market Sizing SOM: {ms1.get('som')}")

print("\n" + "=" * 60)
print("RUN 2: B2B invoice automation SaaS")
print("=" * 60)
cs2 = json.loads(p2.get('competitor_swot', '{}'))
print(f"Competitor count: {len(cs2.get('competitors', []))}")
for c in cs2.get('competitors', []):
    print(f"  - {c.get('name')}: strengths='{c.get('strengths')[:40]}...', pricing='{c.get('pricing')}'")
swot2 = cs2.get('swot_analysis', {})
for q in ['strengths', 'weaknesses', 'opportunities', 'threats']:
    print(f"  SWOT {q} count: {len(swot2.get(q, []))}")

pr2 = json.loads(p2.get('pricing_model', '{}'))
print(f"Pricing tiers count: {len(pr2.get('tiers', []))}")
for t in pr2.get('tiers', []):
    print(f"  - Tier '{t.get('name')}' (${t.get('monthly_price')}/mo): {len(t.get('features', []))} features -> {t.get('features')}")

ms2 = json.loads(p2.get('market_sizing', '{}'))
print(f"Market Sizing TAM: {ms2.get('tam')}")
print(f"Market Sizing SAM: {ms2.get('sam')}")
print(f"Market Sizing SOM: {ms2.get('som')}")
