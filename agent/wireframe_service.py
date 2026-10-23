import html
from agent.sanitizer import sanitize_svg

async def generate_wireframes(idea: str, asset_llm_invoke, extract_code_block) -> str:
    """Generate a premium mobile wireframe SVG using a parameterized template."""

    # Use LLM only for text content
    prompt = f"""For this startup idea: "{idea}"
Give me exactly 4 short mobile app screen labels (e.g., "Dashboard", "Profile", "Search", "Settings").
And for each, one short 3-5 word description.
Output ONLY a JSON array like: [{{"screen":"Dashboard","desc":"View your daily stats"}}, ...]"""
    
    system = "Output ONLY valid JSON array. No markdown, no explanation."
    text = await asset_llm_invoke(system, prompt, max_tokens=300)
    
    import json
    try:
        clean = extract_code_block(text, "json") if "```" in text else text.strip()
        screens = json.loads(clean)
    except:
        screens = [
            {"screen": "Home", "desc": "Main dashboard view"},
            {"screen": "Search", "desc": "Find what you need"},
            {"screen": "Profile", "desc": "Your account details"},
            {"screen": "Settings", "desc": "App preferences"}
        ]

    # Ensure we have exactly 4 and escape them
    while len(screens) < 4:
        screens.append({"screen": f"Screen {len(screens)+1}", "desc": "Feature view"})
    screens = [
        {"screen": html.escape(str(s.get("screen", ""))), "desc": html.escape(str(s.get("desc", "")))}
        for s in screens[:4]
    ]
    safe_idea = html.escape(str(idea))

    # Build premium wireframe SVG
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 900" width="800" height="900">
  <defs>
    <linearGradient id="phoneGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#1e293b"/>
      <stop offset="100%" style="stop-color:#0f172a"/>
    </linearGradient>
    <linearGradient id="screenGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6366f1"/>
      <stop offset="100%" style="stop-color:#8b5cf6"/>
    </linearGradient>
    <linearGradient id="btnGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#6366f1"/>
      <stop offset="100%" style="stop-color:#06b6d4"/>
    </linearGradient>
    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#1e293b"/>
      <stop offset="100%" style="stop-color:#334155"/>
    </linearGradient>
    <filter id="dropShadow">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000" flood-opacity="0.3"/>
    </filter>
    <clipPath id="screenClip">
      <rect x="28" y="65" width="294" height="580" rx="5"/>
    </clipPath>
  </defs>

  <!-- Title -->
  <text x="400" y="40" font-family="Inter,system-ui,sans-serif" font-size="22" font-weight="700" fill="#e2e8f0" text-anchor="middle" letter-spacing="2">MVP WIREFRAMES</text>
  <line x1="300" y1="55" x2="500" y2="55" stroke="url(#btnGrad)" stroke-width="2" stroke-linecap="round"/>

  <!-- Phone 1 -->
  <g transform="translate(30, 70)" filter="url(#dropShadow)">
    <rect width="350" height="700" rx="35" fill="url(#phoneGrad)" stroke="#334155" stroke-width="2"/>
    <!-- Notch -->
    <rect x="110" y="8" width="130" height="28" rx="14" fill="#0f172a"/>
    <circle cx="175" cy="22" r="5" fill="#334155"/>
    <!-- Screen -->
    <g clip-path="url(#screenClip)">
      <rect x="28" y="65" width="294" height="580" fill="#0f172a"/>
      <!-- Status bar -->
      <rect x="28" y="65" width="294" height="35" fill="url(#screenGrad)"/>
      <text x="175" y="88" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="600" fill="#fff" text-anchor="middle">{screens[0]["screen"]}</text>
      <!-- Hero card -->
      <rect x="45" y="115" width="260" height="100" rx="16" fill="url(#cardGrad)" stroke="#475569" stroke-width="0.5"/>
      <text x="65" y="148" font-family="Inter,system-ui,sans-serif" font-size="16" font-weight="700" fill="#e2e8f0">{screens[0]["screen"]}</text>
      <text x="65" y="172" font-family="Inter,system-ui,sans-serif" font-size="11" fill="#94a3b8">{screens[0]["desc"]}</text>
      <rect x="65" y="188" width="80" height="14" rx="7" fill="url(#btnGrad)" opacity="0.7"/>
      <!-- List items -->
      <rect x="45" y="230" width="260" height="55" rx="12" fill="#1e293b" stroke="#334155" stroke-width="0.5"/>
      <circle cx="72" cy="257" r="14" fill="#6366f1" opacity="0.2"/><circle cx="72" cy="257" r="8" fill="#6366f1"/>
      <rect x="96" y="248" width="120" height="8" rx="4" fill="#475569"/>
      <rect x="96" y="262" width="80" height="6" rx="3" fill="#334155"/>
      <rect x="45" y="295" width="260" height="55" rx="12" fill="#1e293b" stroke="#334155" stroke-width="0.5"/>
      <circle cx="72" cy="322" r="14" fill="#06b6d4" opacity="0.2"/><circle cx="72" cy="322" r="8" fill="#06b6d4"/>
      <rect x="96" y="313" width="140" height="8" rx="4" fill="#475569"/>
      <rect x="96" y="327" width="90" height="6" rx="3" fill="#334155"/>
      <rect x="45" y="360" width="260" height="55" rx="12" fill="#1e293b" stroke="#334155" stroke-width="0.5"/>
      <circle cx="72" cy="387" r="14" fill="#f59e0b" opacity="0.2"/><circle cx="72" cy="387" r="8" fill="#f59e0b"/>
      <rect x="96" y="378" width="100" height="8" rx="4" fill="#475569"/>
      <rect x="96" y="392" width="70" height="6" rx="3" fill="#334155"/>
      <!-- FAB button -->
      <circle cx="280" cy="580" r="28" fill="url(#btnGrad)"/>
      <line x1="268" y1="580" x2="292" y2="580" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
      <line x1="280" y1="568" x2="280" y2="592" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>
      <!-- Bottom nav -->
      <rect x="28" y="615" width="294" height="30" fill="#1e293b"/>
      <circle cx="100" cy="630" r="4" fill="#6366f1"/>
      <circle cx="175" cy="630" r="4" fill="#475569"/>
      <circle cx="250" cy="630" r="4" fill="#475569"/>
    </g>
    <!-- Home indicator -->
    <rect x="125" y="665" width="100" height="5" rx="2.5" fill="#475569"/>
  </g>

  <!-- Phone 2 -->
  <g transform="translate(420, 70)" filter="url(#dropShadow)">
    <rect width="350" height="700" rx="35" fill="url(#phoneGrad)" stroke="#334155" stroke-width="2"/>
    <rect x="110" y="8" width="130" height="28" rx="14" fill="#0f172a"/>
    <circle cx="175" cy="22" r="5" fill="#334155"/>
    <g clip-path="url(#screenClip)">
      <rect x="28" y="65" width="294" height="580" fill="#0f172a"/>
      <rect x="28" y="65" width="294" height="35" fill="url(#screenGrad)"/>
      <text x="175" y="88" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="600" fill="#fff" text-anchor="middle">{screens[1]["screen"]}</text>
      <!-- Search bar -->
      <rect x="45" y="115" width="260" height="42" rx="21" fill="#1e293b" stroke="#475569" stroke-width="1"/>
      <circle cx="70" cy="136" r="9" fill="none" stroke="#6366f1" stroke-width="1.5"/>
      <line x1="77" y1="143" x2="82" y2="148" stroke="#6366f1" stroke-width="1.5" stroke-linecap="round"/>
      <text x="95" y="140" font-family="Inter,system-ui,sans-serif" font-size="12" fill="#64748b">{screens[1]["desc"]}</text>
      <!-- Grid cards -->
      <rect x="45" y="175" width="123" height="120" rx="16" fill="url(#cardGrad)" stroke="#475569" stroke-width="0.5"/>
      <circle cx="106" cy="220" r="20" fill="#6366f1" opacity="0.15"/><circle cx="106" cy="220" r="12" fill="#6366f1"/>
      <rect x="70" y="260" width="72" height="8" rx="4" fill="#475569"/>
      <rect x="80" y="274" width="52" height="6" rx="3" fill="#334155"/>
      <rect x="182" y="175" width="123" height="120" rx="16" fill="url(#cardGrad)" stroke="#475569" stroke-width="0.5"/>
      <circle cx="243" cy="220" r="20" fill="#06b6d4" opacity="0.15"/><circle cx="243" cy="220" r="12" fill="#06b6d4"/>
      <rect x="207" y="260" width="72" height="8" rx="4" fill="#475569"/>
      <rect x="217" y="274" width="52" height="6" rx="3" fill="#334155"/>
      <rect x="45" y="310" width="123" height="120" rx="16" fill="url(#cardGrad)" stroke="#475569" stroke-width="0.5"/>
      <circle cx="106" cy="355" r="20" fill="#f59e0b" opacity="0.15"/><circle cx="106" cy="355" r="12" fill="#f59e0b"/>
      <rect x="70" y="395" width="72" height="8" rx="4" fill="#475569"/>
      <rect x="80" y="409" width="52" height="6" rx="3" fill="#334155"/>
      <rect x="182" y="310" width="123" height="120" rx="16" fill="url(#cardGrad)" stroke="#475569" stroke-width="0.5"/>
      <circle cx="243" cy="355" r="20" fill="#ec4899" opacity="0.15"/><circle cx="243" cy="355" r="12" fill="#ec4899"/>
      <rect x="207" y="395" width="72" height="8" rx="4" fill="#475569"/>
      <rect x="217" y="409" width="52" height="6" rx="3" fill="#334155"/>
      <!-- Bottom nav -->
      <rect x="28" y="615" width="294" height="30" fill="#1e293b"/>
      <circle cx="100" cy="630" r="4" fill="#475569"/>
      <circle cx="175" cy="630" r="4" fill="#6366f1"/>
      <circle cx="250" cy="630" r="4" fill="#475569"/>
    </g>
    <rect x="125" y="665" width="100" height="5" rx="2.5" fill="#475569"/>
  </g>

  <!-- Screen labels -->
  <text x="205" y="810" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="600" fill="#94a3b8" text-anchor="middle">📱 {screens[0]["screen"]}</text>
  <text x="595" y="810" font-family="Inter,system-ui,sans-serif" font-size="14" font-weight="600" fill="#94a3b8" text-anchor="middle">📱 {screens[1]["screen"]}</text>

  <!-- Idea label -->
  <text x="400" y="870" font-family="Inter,system-ui,sans-serif" font-size="13" fill="#64748b" text-anchor="middle">{safe_idea}</text>
</svg>'''
    return sanitize_svg(svg)

