import sys
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"
PLAN_ID = "271bf37d-6b75-4118-8582-5e9e9b9342b6"

def post_json(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode('utf-8')}")
        raise

def get_json(endpoint):
    url = f"{BASE_URL}{endpoint}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def run_simulation(persona_id, persona_name):
    print(f"\n=======================================================")
    print(f"STARTING PITCH PRACTICE FOR PERSONA: {persona_name} ({persona_id})")
    print(f"=======================================================")
    
    # 1. Start session
    start_payload = {
        "persona": persona_id,
        "num_questions": 3
    }
    start_res = post_json(f"/api/practice/start/{PLAN_ID}", start_payload)
    session_id = start_res["session_id"]
    current_q = start_res["question"]
    print(f"[Session Started] ID: {session_id}")
    print(f"[Q1]: {current_q}")
    
    # Turn 1: Strong, plan-grounded answer citing real plan facts
    a1 = (
        "We keep COGS at 25% by running the acoustic audio anomaly detection directly on-device using "
        "quantized edge ML models, so ambient microphone audio is never streamed to servers. Cloud inference "
        "and bandwidth are only engaged during high-probability distress spikes. With Basic at ₹199/month and "
        "Premium at ₹399/month, our compute cost is approximately ₹25 per active user, ensuring an operating "
        "gross margin exceeding 70%. Furthermore, compute-heavy 24/7 video and emergency dispatch are gated "
        "to our ₹399/month Premium tier."
    )
    print(f"\n[A1 - Strong Answer]: {a1}")
    res1 = post_json("/api/practice/answer", {
        "session_id": session_id,
        "answer": a1
    })
    eval1 = res1["evaluation"]
    print(f"[Turn 1 Score]: {eval1['score']}/10")
    print(f"  Strengths: {eval1.get('strengths')}")
    print(f"  Weaknesses: {eval1.get('weaknesses')}")
    print(f"  Missed Points: {eval1.get('missed_points')}")
    print(f"  Better Answer Snippet: {eval1.get('better_answer')[:120]}...")
    
    current_q = res1.get("next_question")
    print(f"\n[Q2]: {current_q}")
    
    # Turn 2: Deliberately weak, vague answer
    a2 = (
        "We just feel really passionate about female empowerment and making people feel good and safe. "
        "We will use synergistic machine learning and everyone loves safety, so it will go viral on TikTok "
        "without any CAC. We haven't looked at the unit economics or numbers yet because AI is the future."
    )
    print(f"\n[A2 - Weak Answer]: {a2}")
    res2 = post_json("/api/practice/answer", {
        "session_id": session_id,
        "answer": a2
    })
    eval2 = res2["evaluation"]
    print(f"[Turn 2 Score]: {eval2['score']}/10")
    print(f"  Strengths: {eval2.get('strengths')}")
    print(f"  Weaknesses: {eval2.get('weaknesses')}")
    print(f"  Missed Points: {eval2.get('missed_points')}")
    print(f"  Better Answer Snippet: {eval2.get('better_answer')[:120]}...")
    
    current_q = res2.get("next_question")
    print(f"\n[Q3]: {current_q}")
    
    # Turn 3: Strong answer citing GTM, CAC, Cap Table, and Risk mitigations
    a3 = (
        "Our go-to-market targets 18-45 urban women and college students in Chennai and Bengaluru transit corridors. "
        "We maintain a CAC of ₹150 through direct university partnerships and women's hostel safety programs. "
        "On our ₹150,000 initial cash reserves and our current $60,000 seed ask at a $1.5M pre-money valuation, "
        "40% is dedicated to engineering and edge model safety calibration, while 25% fuels customer acquisition. "
        "We project 1,000 users in Year 1 with 100% annual growth, scaling subscription and service commission revenue."
    )
    print(f"\n[A3 - Strong Answer]: {a3}")
    res3 = post_json("/api/practice/answer", {
        "session_id": session_id,
        "answer": a3
    })
    eval3 = res3["evaluation"]
    print(f"[Turn 3 Score]: {eval3['score']}/10")
    print(f"  Strengths: {eval3.get('strengths')}")
    print(f"  Weaknesses: {eval3.get('weaknesses')}")
    
    summary = res3.get("summary")
    print(f"\n[Session Finished] finished: {res3.get('finished')}")
    print(f"Overall Score: {summary.get('overall_score')}")
    print(f"Scores Per Turn: {summary.get('scores_per_turn')}")
    print(f"Top Strengths: {summary.get('top_strengths')}")
    print(f"Top Weaknesses: {summary.get('top_weaknesses')}")
    print(f"Key Improvements: {summary.get('key_improvements')}")
    
    # Verify GET /api/practice/session/{session_id}
    session_data = get_json(f"/api/practice/session/{session_id}")
    print(f"[GET /session] Status: {session_data['status']}, Turn count: {len(session_data['turns'])}, Overall: {session_data['overall_score']}")
    
    # Verify GET /api/practice/transcript/{session_id}
    transcript = get_json(f"/api/practice/transcript/{session_id}")
    print(f"[GET /transcript] Loaded successfully. Session ID: {transcript.get('session_id')}, Turns in transcript: {len(transcript.get('turns', []))}")
    
    return {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "session_id": session_id,
        "q1": start_res["question"],
        "eval1_score": eval1['score'],
        "q2": res1.get("next_question"),
        "eval2_score": eval2['score'],
        "q3": res2.get("next_question"),
        "eval3_score": eval3['score'],
        "overall_score": summary.get('overall_score'),
        "scores_per_turn": summary.get('scores_per_turn'),
        "top_strengths": summary.get('top_strengths'),
        "top_weaknesses": summary.get('top_weaknesses'),
        "key_improvements": summary.get('key_improvements'),
        "transcript_url": session_data.get("transcript_url")
    }

if __name__ == "__main__":
    results = []
    personas = [
        ("aggressive_vc", "Aggressive VC (Marcus Vance)"),
        ("technical_angel", "Technical Angel (Dr. Elena Chen)"),
        ("academic_examiner", "Academic Examiner (Prof. Jonathan Croft)")
    ]
    for pid, pname in personas:
        res = run_simulation(pid, pname)
        results.append(res)
    
    print("\n================ FINAL SUMMARY OF ALL RUNS ================")
    for r in results:
        print(f"Persona: {r['persona_name']} ({r['persona_id']})")
        print(f"  Scores: {r['scores_per_turn']} (Weak turn 2 score: {r['eval2_score']}) -> Overall: {r['overall_score']}")
        print(f"  Transcript: {r['transcript_url']}")
    
    with open("live_pitch_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nWrote live_pitch_results.json successfully!")
