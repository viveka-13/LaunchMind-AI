import os
from fpdf import FPDF
import json

class InvestorPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()
        
    def header(self):
        self.set_font("helvetica", "B", 15)
        self.cell(80)
        self.cell(30, 10, "Investor Readiness Report", border=0, align="C")
        self.ln(20)
        
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")
        
    def chapter_title(self, title):
        self.set_font("helvetica", "B", 16)
        self.set_fill_color(220, 20, 60) # Crimson red
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, title, fill=True, align="L", border=0)
        self.ln(12)
        
    def chapter_body(self, body):
        self.set_font("helvetica", "", 11)
        self.set_text_color(31, 41, 55)
        self.multi_cell(0, 7, body)
        self.ln()

async def generate_investor_report(idea: str, critique: str, plan_id: str) -> str:
    """
    Generates a PDF Investor Readiness Report based on the VC critique JSON.
    Returns the file path.
    """
    pdf = InvestorPDF()
    
    try:
        data = json.loads(critique) if isinstance(critique, str) else critique
    except:
        data = {}

    scores = data.get("scores", {})
    action_plan = data.get("action_plan", {})
    verdict = data.get("final_verdict", {})

    pdf.chapter_title("1. Investment Overview")
    body = f"Startup Idea: {idea}\n\n"
    body += f"Final Verdict: {verdict.get('verdict', 'N/A')}\n"
    body += f"Why: {verdict.get('why', 'N/A')}\n"
    pdf.chapter_body(body)

    pdf.chapter_title("2. Score Breakdown")
    body = f"Overall Feasibility Score: {scores.get('overall_feasibility_score', 'N/A')}/100\n"
    body += f"- Problem Validation: {scores.get('problem_validation', 'N/A')}/10\n"
    body += f"- Market Opportunity: {scores.get('market_opportunity', 'N/A')}/10\n"
    body += f"- Revenue Model: {scores.get('revenue_model', 'N/A')}/10\n"
    pdf.chapter_body(body)

    pdf.chapter_title("3. Priority 1 Actions (Critical Risks)")
    p1 = action_plan.get("priority_1", [])
    if not p1:
        pdf.chapter_body("No critical risks identified.")
    else:
        body = ""
        for idx, action in enumerate(p1):
            body += f"[{idx+1}] Problem: {action.get('problem', '')}\n"
            body += f"    Solution: {action.get('solution', '')}\n"
            body += f"    Impact: {action.get('expected_impact', '')}\n\n"
        pdf.chapter_body(body)

    # Save PDF
    export_dir = "./data/documents"
    os.makedirs(export_dir, exist_ok=True)
    file_path = os.path.join(export_dir, f"investor_report_{plan_id}.pdf")
    pdf.output(file_path)
    
    return file_path
