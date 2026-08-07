import os
import sqlite3
import uuid

def generate_voice_narration(plan_id: str, plan_data: dict):
    # Ensure audio dir exists
    os.makedirs("./data/audio", exist_ok=True)
    
    # Mock generation (creates an empty file)
    audio_path = f"./data/audio/{plan_id}_narration.mp3"
    with open(audio_path, "wb") as f:
        f.write(b"Mock Audio Data")
        
    # Log to DB
    conn = sqlite3.connect("./data/startup_history.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audio_generations (id, plan_id, file_path, status) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), plan_id, audio_path, "completed")
    )
    conn.commit()
    conn.close()
    
    return audio_path
