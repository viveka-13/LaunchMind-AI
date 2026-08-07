import os

def export_to_google_slides(plan_id: str, plan_data: dict):
    # In a real app, this would use google-api-python-client and oauth2client
    # For now, we mock the success response.
    return "https://docs.google.com/presentation/d/mock-slides-id-for-" + plan_id
