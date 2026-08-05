import os
import html

async def generate_architecture(idea: str, plan_id: str, safe_json_invoke) -> str:
    prompt = f"""
You are a Cloud Software Architect.
Design a modular system architecture for this startup idea:
"{idea}"

Return exactly 4 layers:
1. Client Layer (Frontend apps, mobile, etc.)
2. Gateway Layer (API, Load Balancers, Auth)
3. Core Services (The main logic/microservices)
4. Data & External (Databases, AI models, third-party APIs)

Return ONLY valid JSON in this EXACT format:
{{
  "layers": [
    {{
      "name": "Client Layer",
      "color": "#3b82f6",
      "components": [
        {{"name": "Web App", "tech": "React"}},
        {{"name": "Mobile App", "tech": "React Native"}}
      ]
    }},
    {{
      "name": "Gateway Layer",
      "color": "#8b5cf6",
      "components": [
        {{"name": "API Gateway", "tech": "GraphQL"}},
        {{"name": "Auth Service", "tech": "Firebase"}}
      ]
    }},
    {{
      "name": "Core Services",
      "color": "#10b981",
      "components": [
        {{"name": "Matching Engine", "tech": "Python"}},
        {{"name": "User Service", "tech": "Node.js"}}
      ]
    }},
    {{
      "name": "Data & External",
      "color": "#f59e0b",
      "components": [
        {{"name": "Primary DB", "tech": "PostgreSQL"}},
        {{"name": "LLM API", "tech": "OpenAI"}}
      ]
    }}
  ]
}}
"""
    system = "You are an expert system architect. Output ONLY valid JSON. Keep components concise."
    
    arch_data = await safe_json_invoke(system, prompt, max_tokens=1000)
    
    # Generate HTML from the JSON Data
    layers = arch_data.get("layers", [])
    if not layers:
        # Fallback data if JSON fails
        layers = [
            {"name": "Client Layer", "color": "#3b82f6", "components": [{"name": "Web/Mobile App", "tech": "Frontend"}]},
            {"name": "Gateway Layer", "color": "#8b5cf6", "components": [{"name": "API Gateway", "tech": "Auth & Routing"}]},
            {"name": "Core Services", "color": "#10b981", "components": [{"name": "Business Logic", "tech": "Backend"}]},
            {"name": "Data & External", "color": "#f59e0b", "components": [{"name": "Database", "tech": "Storage"}]}
        ]

    layers_html = ""
    for i, layer in enumerate(layers):
        name = html.escape(layer.get("name", f"Layer {i}"))
        color = layer.get("color", "#6366f1")
        
        comps_html = ""
        for comp in layer.get("components", []):
            c_name = html.escape(comp.get("name", ""))
            c_tech = html.escape(comp.get("tech", ""))
            comps_html += f"""
            <div style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; margin: 8px; flex: 1; min-width: 140px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-weight: 600; font-size: 15px; margin-bottom: 4px; color: #f8fafc;">{c_name}</div>
                <div style="font-size: 12px; color: {color}; font-weight: 500;">{c_tech}</div>
            </div>
            """
            
        arrow = ""
        if i < len(layers) - 1:
            arrow = f"""
            <div style="display: flex; justify-content: center; margin: 10px 0;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>
            </div>
            """

        layers_html += f"""
        <div style="background: {color}15; border-left: 4px solid {color}; border-radius: 8px; padding: 20px; margin-bottom: 5px;">
            <h3 style="margin-top: 0; margin-bottom: 16px; color: {color}; font-size: 16px; text-transform: uppercase; letter-spacing: 1px;">{name}</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 8px; justify-content: center;">
                {comps_html}
            </div>
        </div>
        {arrow}
        """

    final_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>System Architecture</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background-color: #0f172a;
    color: #e2e8f0;
    margin: 0;
    padding: 0;
  }}
  .container {{
    max-width: 900px;
    margin: 40px auto;
    padding: 40px;
    background: #1e293b;
    border-radius: 16px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    border: 1px solid #334155;
  }}
  .header {{
    text-align: center;
    margin-bottom: 40px;
  }}
  .header h1 {{
    margin: 0 0 10px 0;
    font-size: 32px;
    color: #ffffff;
  }}
  .header p {{
    margin: 0;
    color: #94a3b8;
    font-size: 16px;
  }}
</style>
</head>
<body>
  <div class="container">
    <div class="header">
        <h1>System Architecture Map</h1>
        <p>High-level topological design for the proposed solution.</p>
    </div>
    
    <div style="display: flex; flex-direction: column;">
        {layers_html}
    </div>
  </div>
</body>
</html>"""

    # Save to disk for download endpoint
    os.makedirs("./data/architectures", exist_ok=True)
    file_path = f"./data/architectures/{plan_id}.html"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_html)
    except Exception as e:
        print(f"[Architecture] Failed to save HTML: {e}")

    return final_html
