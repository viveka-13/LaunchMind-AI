async def generate_logo(idea: str, brand_kit: dict, asset_llm_invoke, extract_code_block) -> str:
    """Generate a premium SVG logo using a parameterized template."""
    brand_name = brand_kit.get("brand_name", "Startup")
    primary = brand_kit.get("colors", {}).get("primary", "#6366f1")
    secondary = brand_kit.get("colors", {}).get("secondary", "#06b6d4")
    accent = brand_kit.get("colors", {}).get("accent", "#f59e0b")

    # Get the first letter for the logo mark
    letter = brand_name[0].upper() if brand_name else "S"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="400" height="400">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{primary};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{secondary};stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="shineGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#ffffff;stop-opacity:0.3"/>
      <stop offset="50%" style="stop-color:#ffffff;stop-opacity:0.05"/>
      <stop offset="100%" style="stop-color:#ffffff;stop-opacity:0.15"/>
    </linearGradient>
    <radialGradient id="glowGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" style="stop-color:{primary};stop-opacity:0.4"/>
      <stop offset="100%" style="stop-color:{primary};stop-opacity:0"/>
    </radialGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="{primary}" flood-opacity="0.35"/>
    </filter>
    <filter id="innerGlow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="3" result="blur"/>
      <feFlood flood-color="#ffffff" flood-opacity="0.15"/>
      <feComposite in2="blur" operator="in"/>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="400" height="400" rx="40" fill="#0f172a"/>

  <!-- Ambient glow -->
  <circle cx="200" cy="160" r="140" fill="url(#glowGrad)"/>

  <!-- Main logo shape - rounded hexagon -->
  <g filter="url(#shadow)">
    <path d="M200 60 L290 110 L290 210 L200 260 L110 210 L110 110 Z" 
          fill="url(#bgGrad)" 
          stroke="rgba(255,255,255,0.15)" 
          stroke-width="1.5"
          rx="20"/>
    <path d="M200 60 L290 110 L290 210 L200 260 L110 210 L110 110 Z" 
          fill="url(#shineGrad)"/>
  </g>

  <!-- Letter mark -->
  <text x="200" y="185" 
        font-family="'Inter', 'Segoe UI', system-ui, sans-serif" 
        font-size="100" 
        font-weight="800" 
        fill="#ffffff" 
        text-anchor="middle" 
        dominant-baseline="central"
        filter="url(#innerGlow)">{letter}</text>

  <!-- Decorative dots -->
  <circle cx="140" cy="90" r="4" fill="{accent}" opacity="0.7"/>
  <circle cx="260" cy="90" r="3" fill="{secondary}" opacity="0.5"/>
  <circle cx="130" cy="230" r="3" fill="{accent}" opacity="0.5"/>
  <circle cx="270" cy="230" r="4" fill="{secondary}" opacity="0.7"/>

  <!-- Brand name -->
  <text x="200" y="315" 
        font-family="'Inter', 'Segoe UI', system-ui, sans-serif" 
        font-size="32" 
        font-weight="700" 
        fill="#e2e8f0" 
        text-anchor="middle" 
        letter-spacing="3">{brand_name.upper()}</text>

  <!-- Tagline line -->
  <line x1="130" y1="340" x2="270" y2="340" stroke="url(#bgGrad)" stroke-width="2" stroke-linecap="round"/>

  <!-- Subtle corner accents -->
  <path d="M30 60 Q30 30 60 30" stroke="{primary}" stroke-width="2" fill="none" opacity="0.3"/>
  <path d="M340 30 Q370 30 370 60" stroke="{secondary}" stroke-width="2" fill="none" opacity="0.3"/>
  <path d="M30 340 Q30 370 60 370" stroke="{secondary}" stroke-width="2" fill="none" opacity="0.3"/>
  <path d="M340 370 Q370 370 370 340" stroke="{primary}" stroke-width="2" fill="none" opacity="0.3"/>
</svg>'''
    return svg
