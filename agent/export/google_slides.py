import os

def export_to_google_slides(plan_id: str, plan_data: dict):
    # Return the actual local endpoint to download the generated PPTX instead of a fake Google Docs URL.
    return "/api/download_ppt/" + plan_id
