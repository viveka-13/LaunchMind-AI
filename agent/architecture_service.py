import base64
import urllib.request
import os

async def generate_architecture(idea: str, asset_llm_invoke, extract_code_block) -> str:
    prompt = f"""
You are a Cloud Software Architect.
Design a simple system architecture for this startup:
"{idea}"

Requirements:
- Output a valid Mermaid.js flowchart using graph TD syntax.
- Include only 6-8 nodes maximum: Frontend, Backend/API, Database, AI/ML Service, and 1-2 External APIs.
- Keep node labels SHORT (max 3 words each).
- Use simple arrow connections (-->).
- Do NOT use special characters, parentheses in labels, or subgraphs.
- Output ONLY the raw Mermaid code inside a ```mermaid code block.

Example format:
graph TD
    A[Mobile App] --> B[API Gateway]
    B --> C[Auth Service]
    B --> D[Core API]
    D --> E[PostgreSQL]
    D --> F[AI Engine]
    F --> G[Cloud Storage]
"""
    system = "You are a software architect. Output ONLY valid Mermaid syntax. Keep it simple."
    text = await asset_llm_invoke(system, prompt, max_tokens=500)
    mermaid_code = extract_code_block(text, "mermaid").strip()
    
    if not mermaid_code or len(mermaid_code) < 10:
        mermaid_code = extract_code_block(text, "").strip()
    
    if not mermaid_code.startswith("graph ") and not mermaid_code.startswith("flowchart "):
        mermaid_code = "graph TD\n" + mermaid_code

    # Try Kroki API
    try:
        import zlib
        compressed = zlib.compress(mermaid_code.encode("utf-8"), 9)
        base64_string = base64.urlsafe_b64encode(compressed).decode("ascii")
        url = f"https://kroki.io/mermaid/svg/{base64_string}"
        
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            svg_data = response.read().decode("utf-8")
            if "<svg" in svg_data:
                return svg_data
    except Exception as e:
        print(f"[ArchitectureService] Kroki failed: {e}")

    # Fallback: generate a beautiful static architecture SVG template
    return _fallback_architecture_svg(idea)


def _fallback_architecture_svg(idea: str) -> str:
    """Premium fallback architecture diagram when API rendering fails."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 600" width="900" height="600">
  <defs>
    <linearGradient id="ag1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#6366f1"/>
      <stop offset="100%" style="stop-color:#8b5cf6"/>
    </linearGradient>
    <linearGradient id="ag2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#06b6d4"/>
      <stop offset="100%" style="stop-color:#0ea5e9"/>
    </linearGradient>
    <linearGradient id="ag3" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f59e0b"/>
      <stop offset="100%" style="stop-color:#f97316"/>
    </linearGradient>
    <linearGradient id="ag4" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#10b981"/>
      <stop offset="100%" style="stop-color:#34d399"/>
    </linearGradient>
    <linearGradient id="ag5" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#ec4899"/>
      <stop offset="100%" style="stop-color:#f472b6"/>
    </linearGradient>
    <filter id="nodeShadow">
      <feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#000" flood-opacity="0.25"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="900" height="600" fill="#0f172a" rx="16"/>

  <!-- Title -->
  <text x="450" y="40" font-family="Inter,system-ui,sans-serif" font-size="18" font-weight="700" fill="#e2e8f0" text-anchor="middle" letter-spacing="2">SYSTEM ARCHITECTURE</text>
  <line x1="350" y1="52" x2="550" y2="52" stroke="url(#ag1)" stroke-width="2" stroke-linecap="round"/>

  <!-- Row 1: Client Layer -->
  <g filter="url(#nodeShadow)">
    <rect x="350" y="75" width="200" height="50" rx="12" fill="url(#ag1)"/>
    <text x="450" y="105" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="700" fill="#fff" text-anchor="middle">📱 Mobile / Web App</text>
  </g>

  <!-- Arrow down -->
  <line x1="450" y1="125" x2="450" y2="165" stroke="#475569" stroke-width="2" marker-end="url(#arrowhead)"/>
  <polygon points="445,160 450,170 455,160" fill="#475569"/>

  <!-- Row 2: API Gateway -->
  <g filter="url(#nodeShadow)">
    <rect x="350" y="175" width="200" height="50" rx="12" fill="url(#ag2)"/>
    <text x="450" y="205" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="700" fill="#fff" text-anchor="middle">🔗 API Gateway</text>
  </g>

  <!-- Arrows to Row 3 -->
  <line x1="380" y1="225" x2="180" y2="275" stroke="#475569" stroke-width="1.5"/>
  <polygon points="175,272 185,278 180,268" fill="#475569"/>
  <line x1="450" y1="225" x2="450" y2="275" stroke="#475569" stroke-width="1.5"/>
  <polygon points="445,270 450,280 455,270" fill="#475569"/>
  <line x1="520" y1="225" x2="720" y2="275" stroke="#475569" stroke-width="1.5"/>
  <polygon points="715,272 725,278 720,268" fill="#475569"/>

  <!-- Row 3: Services -->
  <g filter="url(#nodeShadow)">
    <rect x="80" y="280" width="200" height="50" rx="12" fill="url(#ag4)"/>
    <text x="180" y="310" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="700" fill="#fff" text-anchor="middle">🔐 Auth Service</text>
  </g>
  <g filter="url(#nodeShadow)">
    <rect x="350" y="280" width="200" height="50" rx="12" fill="url(#ag3)"/>
    <text x="450" y="310" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="700" fill="#fff" text-anchor="middle">⚙️ Core Business API</text>
  </g>
  <g filter="url(#nodeShadow)">
    <rect x="620" y="280" width="200" height="50" rx="12" fill="url(#ag5)"/>
    <text x="720" y="310" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="700" fill="#fff" text-anchor="middle">🤖 AI/ML Engine</text>
  </g>

  <!-- Arrows to Row 4 -->
  <line x1="450" y1="330" x2="300" y2="395" stroke="#475569" stroke-width="1.5"/>
  <polygon points="295,392 305,398 300,388" fill="#475569"/>
  <line x1="450" y1="330" x2="600" y2="395" stroke="#475569" stroke-width="1.5"/>
  <polygon points="595,392 605,398 600,388" fill="#475569"/>
  <line x1="720" y1="330" x2="720" y2="395" stroke="#475569" stroke-width="1.5"/>
  <polygon points="715,390 720,400 725,390" fill="#475569"/>

  <!-- Row 4: Data Layer -->
  <g filter="url(#nodeShadow)">
    <rect x="180" y="400" width="200" height="50" rx="12" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
    <text x="280" y="430" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="600" fill="#e2e8f0" text-anchor="middle">🗄️ PostgreSQL / DB</text>
  </g>
  <g filter="url(#nodeShadow)">
    <rect x="500" y="400" width="200" height="50" rx="12" fill="#1e293b" stroke="#334155" stroke-width="1.5"/>
    <text x="600" y="430" font-family="Inter,system-ui,sans-serif" font-size="13" font-weight="600" fill="#e2e8f0" text-anchor="middle">☁️ Cloud Storage</text>
  </g>

  <!-- Row 5: External -->
  <g filter="url(#nodeShadow)">
    <rect x="620" y="480" width="200" height="45" rx="10" fill="#1e293b" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>
    <text x="720" y="507" font-family="Inter,system-ui,sans-serif" font-size="12" font-weight="600" fill="#94a3b8" text-anchor="middle">🌐 External APIs</text>
  </g>
  <line x1="720" y1="450" x2="720" y2="480" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>

  <!-- Idea label -->
  <text x="450" y="560" font-family="Inter,system-ui,sans-serif" font-size="12" fill="#475569" text-anchor="middle">{idea}</text>
</svg>'''
