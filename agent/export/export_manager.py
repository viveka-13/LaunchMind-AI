from agent.export.google_slides import export_to_google_slides
from agent.export.google_docs import export_to_google_docs
from agent.export.notion_export import export_to_notion
import sqlite3
import uuid

def log_export(plan_id: str, export_type: str, url: str):
    conn = sqlite3.connect("./data/startup_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO export_history (id, plan_id, export_type, export_url) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), plan_id, export_type, url)
    )
    conn.commit()
    conn.close()

def handle_export(plan_id: str, plan_data: dict, export_type: str):
    url = ""
    if export_type == "google_slides":
        url = export_to_google_slides(plan_id, plan_data)
    elif export_type == "google_docs":
        url = export_to_google_docs(plan_id, plan_data)
    elif export_type == "notion":
        url = export_to_notion(plan_id, plan_data)
    else:
        raise ValueError("Unknown export type")
        
    log_export(plan_id, export_type, url)
    return url
