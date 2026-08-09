import os

def export_to_google_docs(plan_id: str, plan_data: dict):
    # Return the actual local endpoint to download the generated Word doc
    return "/api/download_word/" + plan_id
