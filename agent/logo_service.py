async def generate_logo(idea: str, brand_kit: dict, images: list, asset_llm_invoke, extract_code_block) -> str:
    """Generate a premium SVG logo using a parameterized template, dynamic emoji, and optional image background."""
    brand_name = brand_kit.get("brand_name", "Startup")
    primary = brand_kit.get("colors", {}).get("primary", "#6366f1")
    secondary = brand_kit.get("colors", {}).get("secondary", "#06b6d4")
    accent = brand_kit.get("colors", {}).get("accent", "#f59e0b")

    # Ask the LLM for a single relevant emoji
    system = "You are a designer. Return ONLY a SINGLE emoji that best represents the given startup idea. Do not return any text, explanation, or quotes."
    emoji = await asset_llm_invoke(system, idea, max_tokens=10)
    emoji = emoji.strip().replace("'", "").replace('"', "")
    
    if len(emoji) > 5 or not emoji:
        emoji = brand_name[0].upper() if brand_name else "S"

    # Use a background image if available
    bg_image_html = ""
    if images and len(images) > 0:
        bg_img = images[0]
        bg_image_html = f'''
        <image href="{bg_img}" x="0" y="0" width="400" height="400" preserveAspectRatio="xMidYMid slice" opacity="0.3"/>
        <rect width="400" height="400" fill="url(#bgGrad)" opacity="0.85"/>
        '''
    else:
        bg_image_html = f'<rect width="400" height="400" rx="40" fill="#0f172a"/>'

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
      <stop offset="0%" style="stop-color:{primary};stop-opacity:0.5"/>
      <stop offset="100%" style="stop-color:{primary};stop-opacity:0"/>
    </radialGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="4" stdDeviation="8" flood-color="{primary}" flood-opacity="0.45"/>
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
    <clipPath id="circleClip">
       <rect width="400" height="400" rx="40" />
    </clipPath>
  </defs>

  <g clip-path="url(#circleClip)">
      {bg_image_html}
      <!-- Ambient glow -->
      <circle cx="200" cy="160" r="140" fill="url(#glowGrad)"/>
  </g>

  <!-- Main logo shape - modern rounded squircle -->
  <g filter="url(#shadow)">
    <path d="M 120,60 C 120,60 280,60 280,60 C 340,60 340,120 340,120 C 340,120 340,220 340,220 C 340,280 280,280 280,280 C 280,280 120,280 120,280 C 60,280 60,220 60,220 C 60,220 60,120 60,120 C 60,60 120,60 120,60 Z"
          fill="url(#bgGrad)" 
          stroke="rgba(255,255,255,0.25)" 
          stroke-width="2"/>
    <path d="M 120,60 C 120,60 280,60 280,60 C 340,60 340,120 340,120 C 340,120 340,220 340,220 C 340,280 280,280 280,280 C 280,280 120,280 120,280 C 60,280 60,220 60,220 C 60,220 60,120 60,120 C 60,60 120,60 120,60 Z"
          fill="url(#shineGrad)"/>
  </g>

  <!-- Icon/Emoji -->
  <text x="200" y="185" 
        font-family="'Inter', 'Segoe UI', system-ui, sans-serif" 
        font-size="90" 
        font-weight="800" 
        fill="#ffffff" 
        text-anchor="middle" 
        dominant-baseline="central"
        filter="url(#innerGlow)">{emoji}</text>

  <!-- Decorative dots -->
  <circle cx="100" cy="80" r="6" fill="{accent}" opacity="0.8"/>
  <circle cx="280" cy="90" r="4" fill="{secondary}" opacity="0.6"/>
  <circle cx="110" cy="250" r="5" fill="{accent}" opacity="0.6"/>
  <circle cx="290" cy="260" r="6" fill="{secondary}" opacity="0.8"/>

  <!-- Brand name -->
  <text x="200" y="340" 
        font-family="'Inter', 'Segoe UI', system-ui, sans-serif" 
        font-size="34" 
        font-weight="800" 
        fill="#ffffff" 
        text-anchor="middle" 
        letter-spacing="4">{brand_name.upper()}</text>
</svg>'''
    return svg
