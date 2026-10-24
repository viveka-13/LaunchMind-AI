# agent/sanitizer.py
# HTML and SVG Sanitization using nh3 (allowlist) and defusedxml

import re
import html
import logging
from typing import Optional
import nh3
import defusedxml.minidom

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# HTML Sanitization
# ─────────────────────────────────────────────

# Safe tags and attributes allowlist
SAFE_HTML_TAGS = {
    "a", "b", "blockquote", "br", "code", "div", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "i", "li", "ol", "p", "pre", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "ul"
}

SAFE_HTML_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "div": {"class", "style"},
    "span": {"class", "style"},
    "p": {"class", "style"},
    "td": {"class", "style", "colspan", "rowspan"},
    "th": {"class", "style", "colspan", "rowspan"},
    "pre": {"class", "style"},
    "code": {"class"},
}


def sanitize_html(raw_html: str) -> str:
    """
    Sanitize raw HTML using nh3 allowlist.
    Strips <script>, on* event handlers, javascript: URLs, iframes, and external form actions.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    try:
        cleaned = nh3.clean(
            raw_html,
            tags=SAFE_HTML_TAGS,
            attributes=SAFE_HTML_ATTRIBUTES,
            url_schemes={"http", "https", "mailto"},
        )
        return cleaned
    except Exception as e:
        logger.warning(f"[Sanitizer] HTML sanitization error: {e}")
        return html.escape(raw_html)


# ─────────────────────────────────────────────
# SVG Sanitization
# ─────────────────────────────────────────────

SAFE_SVG_ELEMENTS = {
    "svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
    "text", "tspan", "defs", "linearGradient", "radialGradient", "stop", "filter",
    "feDropShadow", "feGaussianBlur", "feFlood", "feComposite", "feMerge", "feMergeNode",
    "clipPath", "mask", "use", "image"
}

SAFE_SVG_ATTRIBUTES = {
    "xmlns", "xmlns:xlink", "viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "d", "fill", "fill-opacity", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "stroke-opacity", "opacity",
    "transform", "font-family", "font-size", "font-weight", "text-anchor", "offset",
    "stop-color", "stop-opacity", "id", "class", "style", "clip-path", "filter",
    "stdDeviation", "dx", "dy", "flood-color", "flood-opacity", "operator", "in", "in2",
    "result", "preserveAspectRatio", "href", "xlink:href"
}

DISALLOWED_ATTR_PREFIXES = ("on",)


def sanitize_svg(raw_svg: str) -> str:
    """
    Parse SVG with defusedxml, filter against element and attribute allowlist,
    strip <script>, <foreignObject>, on* event handlers, and javascript: links.
    Rejects malformed SVG.
    """
    if not raw_svg or not isinstance(raw_svg, str):
        return ""

    raw_svg = raw_svg.strip()
    if not raw_svg.startswith("<") or "<svg" not in raw_svg.lower():
        raise ValueError("Invalid SVG: missing <svg> root element")

    try:
        dom = defusedxml.minidom.parseString(raw_svg)
    except Exception as e:
        raise ValueError(f"Failed to parse SVG: {e}") from e

    def clean_node(node):
        to_remove = []
        for child in list(node.childNodes):
            if child.nodeType == child.ELEMENT_NODE:
                tag_name = child.tagName.split(":")[-1]  # strip namespace prefix
                if tag_name not in SAFE_SVG_ELEMENTS:
                    to_remove.append(child)
                    continue

                # Clean attributes
                attrs_to_remove = []
                if child.attributes:
                    for i in range(child.attributes.length):
                        attr = child.attributes.item(i)
                        attr_name = attr.name.split(":")[-1]
                        val = attr.value.strip().lower()

                        # Check disallowed prefixes (like onclick, onload)
                        if any(attr_name.startswith(p) for p in DISALLOWED_ATTR_PREFIXES):
                            attrs_to_remove.append(attr.name)
                            continue

                        # Check safe attribute names
                        if attr_name not in SAFE_SVG_ATTRIBUTES:
                            attrs_to_remove.append(attr.name)
                            continue

                        # Check dangerous URLs
                        if attr_name in ("href", "xlink:href", "src") and (
                            val.startswith("javascript:") or val.startswith("data:text/html")
                        ):
                            attrs_to_remove.append(attr.name)
                            continue

                for a in attrs_to_remove:
                    child.removeAttribute(a)

                # Recursively clean children
                clean_node(child)

        for rm in to_remove:
            node.removeChild(rm)

    clean_node(dom)
    return dom.toxml()
