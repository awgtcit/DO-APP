"""
Jinja2 custom filters and template utilities.
Registered in the application factory via ``register_filters(app)``.
"""

import re
import xml.etree.ElementTree as ET

from markupsafe import Markup

# ── Allowlist-based SVG sanitizer ──────────────────────────────
# Only these elements and attributes are kept; everything else is stripped.

_ALLOWED_ELEMENTS = frozenset({
    "svg", "path", "circle", "ellipse", "line", "polyline", "polygon",
    "rect", "g", "defs", "clipPath", "use", "title", "desc",
})

_ALLOWED_ATTRIBUTES = frozenset({
    "xmlns", "viewBox", "viewbox", "fill", "stroke", "stroke-width",
    "stroke-linecap", "stroke-linejoin", "d", "cx", "cy", "r", "rx", "ry",
    "x", "y", "x1", "y1", "x2", "y2", "width", "height", "points",
    "transform", "opacity", "fill-opacity", "stroke-opacity",
    "clip-path", "clip-rule", "fill-rule", "id", "class",
})

_NS = "{http://www.w3.org/2000/svg}"


def _sanitize_svg(raw: str) -> str:
    """Parse SVG and rebuild with only allowed elements/attributes."""
    # Register namespace so ET doesn't produce ns0: prefixes
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return ""  # Malformed SVG → drop entirely

    def _clean(el):
        # Strip namespace prefix for comparison
        tag = el.tag.replace(_NS, "")
        if tag not in _ALLOWED_ELEMENTS:
            return None

        # Keep only allowed attributes
        attribs = {}
        for k, v in el.attrib.items():
            clean_k = k.replace(_NS, "")
            if clean_k in _ALLOWED_ATTRIBUTES:
                attribs[clean_k] = v
        el.attrib.clear()
        el.attrib.update(attribs)

        # Recursively clean children
        for child in list(el):
            cleaned = _clean(child)
            if cleaned is None:
                el.remove(child)

        # Strip text/tail that could contain scripts
        el.text = None
        el.tail = None
        return el

    cleaned = _clean(root)
    if cleaned is None:
        return ""

    # Re-serialize
    return ET.tostring(cleaned, encoding="unicode", method="html")


def _safe_svg_filter(value):
    """Render SVG markup through allowlist-based sanitizer."""
    if not value:
        return ""
    return Markup(_sanitize_svg(str(value)))


def register_filters(app):
    """Register all custom Jinja2 filters on the Flask app."""
    app.template_filter("safe_svg")(_safe_svg_filter)
