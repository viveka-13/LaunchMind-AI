async def generate_landing_page(idea: str, features: str, brand_kit: dict, asset_llm_invoke, extract_code_block) -> str:
    """Generate a premium landing page using a parameterized HTML template."""
    brand_name = brand_kit.get("brand_name", "Startup")
    tagline = brand_kit.get("tagline", "Innovate Today")
    primary = brand_kit.get("colors", {}).get("primary", "#6366f1")
    secondary = brand_kit.get("colors", {}).get("secondary", "#06b6d4")
    accent = brand_kit.get("colors", {}).get("accent", "#f59e0b")
    bg = brand_kit.get("colors", {}).get("background", "#0f172a")

    # Extract feature lines
    feature_lines = [l.strip() for l in features.split('\n') if l.strip()][:6]
    feature_icons = ['🚀', '⚡', '🎯', '💡', '🔒', '📊']
    
    features_html = ""
    for i, feat in enumerate(feature_lines):
        icon = feature_icons[i] if i < len(feature_icons) else '✨'
        short = feat[:80] if len(feat) > 80 else feat
        features_html += f'''
        <div class="feature-card">
          <div class="feature-icon">{icon}</div>
          <p class="feature-text">{short}</p>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{brand_name}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background: {bg};
    color: #e2e8f0;
    overflow-x: hidden;
  }}

  /* Animated gradient background */
  .hero {{
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 2rem;
    position: relative;
    overflow: hidden;
  }}
  .hero::before {{
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 30% 40%, {primary}22 0%, transparent 50%),
                radial-gradient(circle at 70% 60%, {secondary}22 0%, transparent 50%),
                radial-gradient(circle at 50% 80%, {accent}15 0%, transparent 40%);
    animation: float 15s ease-in-out infinite;
  }}
  @keyframes float {{
    0%, 100% {{ transform: translate(0, 0) rotate(0deg); }}
    33% {{ transform: translate(30px, -30px) rotate(5deg); }}
    66% {{ transform: translate(-20px, 20px) rotate(-3deg); }}
  }}

  .hero-content {{ position: relative; z-index: 1; max-width: 700px; }}
  .badge {{
    display: inline-block;
    background: {primary}20;
    border: 1px solid {primary}40;
    color: {primary};
    padding: 0.4rem 1rem;
    border-radius: 99px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
  }}
  .hero h1 {{
    font-size: clamp(2.5rem, 6vw, 4rem);
    font-weight: 800;
    line-height: 1.1;
    margin-bottom: 1rem;
    background: linear-gradient(135deg, #fff 0%, {secondary} 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .hero p {{
    font-size: 1.15rem;
    color: #94a3b8;
    line-height: 1.7;
    margin-bottom: 2rem;
    max-width: 550px;
    margin-left: auto; margin-right: auto;
  }}
  .cta-group {{ display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }}
  .btn {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.85rem 2rem;
    border-radius: 12px;
    font-weight: 700;
    font-size: 1rem;
    text-decoration: none;
    transition: all 0.3s;
    cursor: pointer;
    border: none;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, {primary}, {secondary});
    color: #fff;
    box-shadow: 0 4px 20px {primary}40;
  }}
  .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px {primary}50; }}
  .btn-outline {{
    background: transparent;
    color: #e2e8f0;
    border: 1px solid #334155;
  }}
  .btn-outline:hover {{ background: #1e293b; }}

  /* Features */
  .features {{
    padding: 5rem 2rem;
    max-width: 1000px;
    margin: 0 auto;
  }}
  .section-title {{
    text-align: center;
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
  }}
  .section-sub {{
    text-align: center;
    color: #64748b;
    margin-bottom: 3rem;
    font-size: 1rem;
  }}
  .features-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
  }}
  .feature-card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2rem;
    transition: all 0.3s;
  }}
  .feature-card:hover {{
    transform: translateY(-4px);
    border-color: {primary}50;
    box-shadow: 0 8px 30px rgba(0,0,0,0.3);
  }}
  .feature-icon {{ font-size: 2rem; margin-bottom: 1rem; }}
  .feature-text {{ color: #cbd5e1; font-size: 0.95rem; line-height: 1.6; }}

  /* Social proof */
  .social {{
    padding: 4rem 2rem;
    text-align: center;
    background: linear-gradient(180deg, transparent, {primary}08, transparent);
  }}
  .stats {{
    display: flex;
    justify-content: center;
    gap: 4rem;
    flex-wrap: wrap;
    margin-top: 2rem;
  }}
  .stat-num {{
    font-size: 2.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, {primary}, {secondary});
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .stat-label {{ color: #64748b; font-size: 0.85rem; margin-top: 0.25rem; }}

  /* CTA Footer */
  .cta-footer {{
    padding: 5rem 2rem;
    text-align: center;
  }}
  .cta-footer h2 {{
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 1rem;
  }}
  .cta-footer p {{ color: #94a3b8; margin-bottom: 2rem; }}

  footer {{
    text-align: center;
    padding: 2rem;
    color: #475569;
    font-size: 0.8rem;
    border-top: 1px solid #1e293b;
  }}
</style>
</head>
<body>
  <section class="hero">
    <div class="hero-content">
      <div class="badge">✨ {brand_name}</div>
      <h1>{tagline}</h1>
      <p>{idea} — built for the future with AI-powered intelligence and seamless user experience.</p>
      <div class="cta-group">
        <a href="#" class="btn btn-primary">🚀 Get Started Free</a>
        <a href="#" class="btn btn-outline">Learn More →</a>
      </div>
    </div>
  </section>

  <section class="features">
    <h2 class="section-title">Why {brand_name}?</h2>
    <p class="section-sub">Everything you need, nothing you don't.</p>
    <div class="features-grid">
      {features_html}
    </div>
  </section>

  <section class="social">
    <h2 class="section-title">Trusted by Thousands</h2>
    <div class="stats">
      <div><div class="stat-num">10K+</div><div class="stat-label">Active Users</div></div>
      <div><div class="stat-num">98%</div><div class="stat-label">Satisfaction Rate</div></div>
      <div><div class="stat-num">4.9★</div><div class="stat-label">App Store Rating</div></div>
    </div>
  </section>

  <section class="cta-footer">
    <h2>Ready to Transform Your Experience?</h2>
    <p>Join thousands of users who trust {brand_name}.</p>
    <a href="#" class="btn btn-primary">🚀 Start Free Trial</a>
  </section>

  <footer>&copy; 2024 {brand_name}. All rights reserved.</footer>
</body>
</html>'''
    return html
