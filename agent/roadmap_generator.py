"""
roadmap_generator.py — Generates a professional, graphical Business Roadmap Workflow
as a downloadable SVG file.  No external rendering engines required.

The output is a vertical timeline infographic with 15 milestone stages,
styled with rounded boxes, colored connectors, and modern startup aesthetics.
"""
import os
import html as html_mod


# ── Design tokens ──
INDIGO       = "#4f46e5"
INDIGO_DARK  = "#312e81"
CYAN         = "#06b6d4"
EMERALD      = "#10b981"
AMBER        = "#f59e0b"
ROSE         = "#f43f5e"
PURPLE       = "#a855f7"
SKY          = "#0ea5e9"
TEAL         = "#14b8a6"
SLATE_50     = "#f8fafc"
SLATE_100    = "#f1f5f9"
SLATE_700    = "#334155"
SLATE_900    = "#0f172a"
WHITE        = "#ffffff"

# 15 stages – each gets a colour and icon
STAGES = [
    ("Business Idea",               "💡", INDIGO),
    ("Business Analysis",           "📊", PURPLE),
    ("Market Research",             "🔍", CYAN),
    ("Target Customers",            "👥", SKY),
    ("Business Strategy",           "🎯", INDIGO_DARK),
    ("Marketing Plan",              "📣", ROSE),
    ("Financial Planning",          "💰", AMBER),
    ("Product / Service Development","⚙️", TEAL),
    ("Launch Strategy",             "🚀", EMERALD),
    ("Growth Plan",                 "📈", INDIGO),
    ("Next 30 Days",                "📅", CYAN),
    ("Next 3 Months",               "🗓️", SKY),
    ("Next 6 Months",               "📆", PURPLE),
    ("Long-Term Goals",             "🏔️", INDIGO_DARK),
    ("Expected Business Outcome",   "🏆", EMERALD),
]

# Layout constants
SVG_W       = 900
BOX_W       = 520
BOX_H       = 54
BOX_R       = 14          # border-radius
GAP_Y       = 26          # gap between boxes
ARROW_LEN   = GAP_Y       # connector height
LEFT_X      = (SVG_W - BOX_W) // 2
TOP_PAD     = 130          # space for title area
BOTTOM_PAD  = 60


def _escape(text: str) -> str:
    return html_mod.escape(str(text))


def generate_roadmap_svg(plan_data: dict, file_path: str) -> str:
    """
    Generates a professional vertical-timeline roadmap SVG.
    Returns the file path written, or None on failure.
    """
    try:
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else ".", exist_ok=True)
        title = _escape(plan_data.get("startup_title", "Your Startup"))

        num = len(STAGES)
        row_h   = BOX_H + GAP_Y
        svg_h   = TOP_PAD + num * row_h + BOTTOM_PAD

        parts = []
        # ── SVG open ──
        parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {svg_h}" '
            f'width="{SVG_W}" height="{svg_h}" '
            f'font-family="Segoe UI, Roboto, Arial, sans-serif">\n'
        )

        # ── Defs: drop-shadow filter, arrow marker ──
        parts.append("""
<defs>
  <filter id="shadow" x="-4%" y="-4%" width="108%" height="116%">
    <feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="#0f172a" flood-opacity="0.10"/>
  </filter>
  <marker id="arrowhead" markerWidth="10" markerHeight="8" refX="5" refY="4" orient="auto">
    <polygon points="0 0, 10 4, 0 8" fill="#94a3b8"/>
  </marker>
  <linearGradient id="bgGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#f8fafc"/>
    <stop offset="100%" stop-color="#e2e8f0"/>
  </linearGradient>
  <linearGradient id="headerGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="#4f46e5"/>
    <stop offset="100%" stop-color="#06b6d4"/>
  </linearGradient>
</defs>
""")

        # ── Background ──
        parts.append(f'<rect width="{SVG_W}" height="{svg_h}" rx="20" fill="url(#bgGrad)"/>\n')

        # ── Title bar ──
        parts.append(
            f'<rect x="0" y="0" width="{SVG_W}" height="100" rx="20" fill="url(#headerGrad)"/>\n'
            f'<rect x="0" y="20" width="{SVG_W}" height="80" fill="url(#headerGrad)"/>\n'
            f'<text x="{SVG_W//2}" y="45" text-anchor="middle" '
            f'font-size="22" font-weight="700" fill="{WHITE}">{title}</text>\n'
            f'<text x="{SVG_W//2}" y="72" text-anchor="middle" '
            f'font-size="13" fill="rgba(255,255,255,0.75)">Business Execution Roadmap</text>\n'
        )

        # ── Vertical timeline spine ──
        spine_x = SVG_W // 2
        spine_top = TOP_PAD
        spine_bot = TOP_PAD + (num - 1) * row_h + BOX_H // 2
        parts.append(
            f'<line x1="{spine_x}" y1="{spine_top}" x2="{spine_x}" y2="{spine_bot}" '
            f'stroke="#cbd5e1" stroke-width="3" stroke-dasharray="8 6"/>\n'
        )

        # ── Stage boxes ──
        for i, (label, icon, color) in enumerate(STAGES):
            y = TOP_PAD + i * row_h
            cx = LEFT_X
            cy = y

            # Box shadow + rounded rect
            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{BOX_W}" height="{BOX_H}" '
                f'rx="{BOX_R}" fill="{WHITE}" filter="url(#shadow)" '
                f'stroke="{color}" stroke-width="2"/>\n'
            )

            # Left color accent bar
            parts.append(
                f'<rect x="{cx}" y="{cy}" width="6" height="{BOX_H}" '
                f'rx="3" fill="{color}"/>\n'
            )

            # Step number badge (circle)
            badge_x = cx + 30
            badge_cy = cy + BOX_H // 2
            parts.append(
                f'<circle cx="{badge_x}" cy="{badge_cy}" r="14" fill="{color}"/>\n'
                f'<text x="{badge_x}" y="{badge_cy + 5}" text-anchor="middle" '
                f'font-size="12" font-weight="700" fill="{WHITE}">{i+1}</text>\n'
            )

            # Icon
            icon_x = cx + 58
            parts.append(
                f'<text x="{icon_x}" y="{cy + BOX_H // 2 + 6}" font-size="18">{icon}</text>\n'
            )

            # Label text
            text_x = cx + 82
            parts.append(
                f'<text x="{text_x}" y="{cy + BOX_H // 2 + 5}" '
                f'font-size="15" font-weight="600" fill="{SLATE_700}">{_escape(label)}</text>\n'
            )

            # Connector arrow to next box
            if i < num - 1:
                arr_x = spine_x
                arr_y1 = cy + BOX_H
                arr_y2 = cy + BOX_H + GAP_Y
                parts.append(
                    f'<line x1="{arr_x}" y1="{arr_y1}" x2="{arr_x}" y2="{arr_y2}" '
                    f'stroke="{color}" stroke-width="2" marker-end="url(#arrowhead)"/>\n'
                )

        # ── Footer credit ──
        foot_y = svg_h - 30
        parts.append(
            f'<text x="{SVG_W//2}" y="{foot_y}" text-anchor="middle" '
            f'font-size="11" fill="#94a3b8">Generated by AutoStartup AI</text>\n'
        )

        parts.append("</svg>\n")

        svg_content = "".join(parts)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        print(f"[Roadmap] SVG saved: {file_path}")
        return file_path

    except Exception as e:
        print(f"[Roadmap] Generation failed: {e}")
        return None
