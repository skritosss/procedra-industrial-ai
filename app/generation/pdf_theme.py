"""Print tokens mirrored from the interface stylesheet.

The exported document is what a customer takes away, so it has to read as the
same product as the screen. These values are the light-theme half of
`app/static/tokens.css`; changing one without the other is what let the two
drift apart in the first place.
"""

from reportlab.lib import colors

INK = colors.HexColor("#1A1719")
MUTED = colors.HexColor("#6E6763")
LINE = colors.HexColor("#E2DEDB")
LINE_STRONG = colors.HexColor("#8F8883")
SURFACE = colors.HexColor("#FFFFFF")
SURFACE_SUNKEN = colors.HexColor("#EFEDEB")

BRAND = colors.HexColor("#7A2E3C")
BRAND_SURFACE = colors.HexColor("#F5ECEE")
BRAND_SURFACE_SOFT = colors.HexColor("#FCF7F8")

# Risk, provenance and workflow status share these pairs, exactly as on screen:
# meaning stays tied to the reserved colours and never to the brand tone.
SEMANTIC = {
    "low": (colors.HexColor("#15653A"), colors.HexColor("#E8F0EA")),
    "medium": (colors.HexColor("#7A5A12"), colors.HexColor("#F5EFDF")),
    "high": (colors.HexColor("#8A3D0F"), colors.HexColor("#F7EADF")),
    "critical": (colors.HexColor("#A8201A"), colors.HexColor("#FAE9E7")),
    "neutral": (MUTED, SURFACE_SUNKEN),
}

BADGE_VARIANTS = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
    "confirmed": "low",
    "approved": "low",
    "local": "low",
    "requires_local_check": "high",
    "hypothesis": "neutral",
    "hypothesis_pending_review": "medium",
    "ai_draft": "neutral",
    "draft": "neutral",
    "public": "neutral",
    "expert_review": "medium",
    "in_review": "medium",
    "in_execution": "medium",
    "rejected": "critical",
}


def semantic_pair(value: str) -> tuple[colors.Color, colors.Color]:
    """Text and background for a value, falling back to the neutral pair."""
    return SEMANTIC[BADGE_VARIANTS.get(value, "neutral")]


def score_band(score: int) -> str:
    """Same banding as the on-screen criterion bar."""
    if score >= 90:
        return "low"
    if score >= 75:
        return "medium"
    if score >= 50:
        return "high"
    return "critical"
