import os

def export_to_notion(plan_id: str, plan_data: dict):
    # Return the actual local endpoint to download the generated PDF
    return "/api/download_pdf/" + plan_id
