"""
Run real LLM end-to-end tests on both ideas and capture character counts, item counts,
and raw outputs before and after.
"""
import asyncio
import json
import uuid
from agent.workflow import run_agent, event_queues
from agent.memory import get_plan_by_id


async def run_idea_and_analyze(idea: str, language: str = "English"):
    print(f"\n=======================================================")
    print(f"STARTING REAL LLM RUN FOR: '{idea}' ({language})")
    print(f"=======================================================")
    
    session_id = str(uuid.uuid4())
    queue = asyncio.Queue()
    event_queues[session_id] = queue

    # Task to drain queue so it doesn't block
    completed_events = []
    plan_id_holder = {"plan_id": None}

    async def drain():
        while True:
            evt = await queue.get()
            if evt is None:
                break
            completed_events.append(evt)
            if evt.get("type") == "step":
                print(f"  [Step {evt.get('step')}/19] {evt.get('title')}")
            elif evt.get("type") == "node_error":
                print(f"  ❌ NODE ERROR: {evt.get('node')} -> {evt.get('reason')}")
            elif evt.get("type") == "complete":
                plan_id_holder["plan_id"] = evt.get("plan_id")
                print(f"  ✅ COMPLETE! Plan ID: {plan_id_holder['plan_id']}")

    drain_task = asyncio.create_task(drain())

    try:
        await run_agent(idea=idea, session_id=session_id, language=language, doc_format="ppt")
    finally:
        await queue.put(None)
        await drain_task
        if session_id in event_queues:
            del event_queues[session_id]

    plan_id = plan_id_holder["plan_id"]
    if not plan_id:
        print("ERROR: No plan ID produced!")
        return None

    plan = get_plan_by_id(plan_id)
    return plan


async def main():
    ideas = [
        "AI app for female protection",
        "B2B invoice automation SaaS",
    ]

    results = {}
    for idea in ideas:
        plan = await run_idea_and_analyze(idea, "English")
        results[idea] = plan

    with open("real_run_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n\nAll real runs completed and saved to real_run_results.json")


if __name__ == "__main__":
    asyncio.run(main())

