import json
from agent.investor_personas import INVESTOR_PERSONAS

async def generate_pitch_question(idea: str, core_features: str, revenue_model: str, persona_id: str, history: list):
    from agent.workflow import llm_invoke
    persona = INVESTOR_PERSONAS.get(persona_id, INVESTOR_PERSONAS["seed_vc"])
    
    # Format history for prompt
    history_text = ""
    for msg in history:
        history_text += f"{msg['role'].upper()}: {msg['content']}\n"
        
    prompt = f"""{persona['prompt']}

You are interviewing the founder of: {idea}
Core Features: {core_features[:300]}
Revenue Model: {revenue_model[:300]}

Conversation History:
{history_text}

Generate your next question for the founder. Ask ONE concise, challenging question based on your persona. Do not be overly polite.
"""

    question = await llm_invoke("You are a demanding startup investor.", prompt, "English", max_tokens=200)
    return question

EVAL_PROMPT = """You are evaluating a founder's answer to an investor's question.

Investor Question: {question}
Founder Answer: {answer}

Provide an evaluation of their answer. Return ONLY valid JSON matching this schema:
{{
  "score": 8,
  "strengths": ["Strong point 1", "Strong point 2"],
  "weaknesses": ["Weakness 1", "Weakness 2"],
  "suggested_improved_answer": "An example of a better way to answer this question."
}}
"""

async def evaluate_pitch_answer(question: str, answer: str):
    from agent.workflow import safe_json_parse
    prompt = EVAL_PROMPT.format(question=question, answer=answer)
    result = await safe_json_parse(prompt, "English", max_tokens=1000)
    return result

