import os

def export_to_notion(plan_id: str, plan_data: dict):
    # In a real app, this would use notion-client
    # For now, we mock the success response.
    return "https://notion.so/mock-workspace-id-for-" + plan_id
