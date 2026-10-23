import html

async def generate_poster(idea: str, brand_kit: dict, images: list, asset_llm_invoke, extract_code_block) -> str:
    """Generate a premium marketing poster using a parameterized HTML/CSS template."""
    raw_name = brand_kit.get("brand_name", "Startup")
    brand_name = html.escape(str(raw_name))
    tagline = html.escape(str(brand_kit.get("tagline", "Innovate today.")))
    primary = html.escape(str(brand_kit.get("colors", {}).get("primary", "#6366f1")))
    secondary = html.escape(str(brand_kit.get("colors", {}).get("secondary", "#06b6d4")))
    bg = html.escape(str(brand_kit.get("colors", {}).get("background", "#0f172a")))
    accent = html.escape(str(brand_kit.get("colors", {}).get("accent", "#f59e0b")))
    safe_idea = html.escape(str(idea))

    html_content = f'''<div style="
      width: 600px;
      min-height: 800px;
      background: linear-gradient(160deg, {bg} 0%, #1e293b 40%, {primary}15 100%);
      border-radius: 24px;
      padding: 48px;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      color: #e2e8f0;
      position: relative;
      overflow: hidden;
      box-sizing: border-box;
    ">
      <!-- Background decorative elements -->
      <div style="
        position: absolute;
        top: -60px;
        right: -60px;
        width: 250px;
        height: 250px;
        background: radial-gradient(circle, {primary}30, transparent 70%);
        border-radius: 50%;
      "></div>
      <div style="
        position: absolute;
        bottom: -40px;
        left: -40px;
        width: 200px;
        height: 200px;
        background: radial-gradient(circle, {secondary}25, transparent 70%);
        border-radius: 50%;
      "></div>
      <div style="
        position: absolute;
        top: 50%;
        right: 10%;
        width: 120px;
        height: 120px;
        background: radial-gradient(circle, {accent}15, transparent 70%);
        border-radius: 50%;
      "></div>

      <!-- Content -->
      <div style="position: relative; z-index: 1;">
        <!-- Badge -->
        <div style="
          display: inline-block;
          background: {primary}20;
          border: 1px solid {primary}40;
          color: {primary};
          padding: 6px 16px;
          border-radius: 99px;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 2px;
          text-transform: uppercase;
          margin-bottom: 32px;
        ">✨ {brand_name}</div>

        <!-- Headline -->
        <h1 style="
          font-size: 48px;
          font-weight: 800;
          line-height: 1.1;
          margin-bottom: 16px;
          background: linear-gradient(135deg, #ffffff, {secondary});
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        ">{tagline}</h1>

        <!-- Subheadline -->
        <p style="
          font-size: 16px;
          color: #94a3b8;
          line-height: 1.7;
          margin-bottom: 40px;
          max-width: 440px;
        ">{safe_idea} — Powered by cutting-edge AI technology for a smarter tomorrow.</p>

        <!-- Feature bullets -->
        <div style="margin-bottom: 40px;">
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
            <div style="width: 36px; height: 36px; background: {primary}20; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;">🚀</div>
            <span style="font-size: 15px; color: #cbd5e1;">AI-Powered Intelligence & Automation</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
            <div style="width: 36px; height: 36px; background: {secondary}20; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;">⚡</div>
            <span style="font-size: 15px; color: #cbd5e1;">Lightning-Fast Real-Time Processing</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 36px; height: 36px; background: {accent}20; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0;">🔒</div>
            <span style="font-size: 15px; color: #cbd5e1;">Enterprise-Grade Security & Privacy</span>
          </div>
        </div>

        <!-- CTA Button -->
        <div style="
          display: inline-block;
          background: linear-gradient(135deg, {primary}, {secondary});
          color: #ffffff;
          padding: 14px 36px;
          border-radius: 12px;
          font-size: 16px;
          font-weight: 700;
          letter-spacing: 0.5px;
          box-shadow: 0 4px 20px {primary}40;
          margin-bottom: 48px;
        ">Get Started Free →</div>

        <!-- Stats -->
        <div style="
          display: flex;
          gap: 32px;
          padding-top: 32px;
          border-top: 1px solid #334155;
        ">
          <div>
            <div style="font-size: 28px; font-weight: 800; color: {primary};">10K+</div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Users</div>
          </div>
          <div>
            <div style="font-size: 28px; font-weight: 800; color: {secondary};">98%</div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Satisfaction</div>
          </div>
          <div>
            <div style="font-size: 28px; font-weight: 800; color: {accent};">4.9★</div>
            <div style="font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">Rating</div>
          </div>
        </div>
      </div>
    </div>'''
    return html_content

