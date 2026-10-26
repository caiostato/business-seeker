"""
responsiveness_auditor.py - Web Redesign Heuristic Engine for Business Seeker

Audits website modernity and responsiveness to detect golden redesign opportunities:
1. Mobile Responsiveness / Viewport configuration (missing viewport, fixed desktop widths).
2. Obsolete / Legacy Technologies (Framesets, Flash, Marquee/Blink, nested layout tables).
3. Stale / Abandoned Copyright years.
4. High Latency (> 5.0s load time).
5. Lead Opportunity Score for Web Redesign (0-30 points).
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants & Regex Patterns
# ---------------------------------------------------------------------------

# Meta tag matching: handles attributes in any order, quoted or unquoted
META_TAG_REGEX = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
VIEWPORT_NAME_REGEX = re.compile(r'\bname\s*=\s*["\']?viewport["\']?', re.IGNORECASE)
CONTENT_ATTR_REGEX = re.compile(
    r'\bcontent\s*=\s*(?:["\']([^"\']*)["\']|([^>\s]+))', re.IGNORECASE
)

# Copyright extraction regex
# Matches: © 2016, &copy; 2014-2018, Copyright 2010, Copyright &copy; 2015, (c) 2012
COPYRIGHT_REGEX = re.compile(
    r"(?:©|&copy;|copyright|\(c\))(?:\s*(?:©|&copy;|\(c\)|copyright))?[\s:]*(?:[0-9]{4}\s*[-–/]\s*)?([12][0-9]{3})",
    re.IGNORECASE,
)

# Legacy technology patterns
FRAMESET_REGEX = re.compile(r"<\s*frameset\b", re.IGNORECASE)
FRAME_REGEX = re.compile(r"<\s*(?<!i)frame[\s>]", re.IGNORECASE)
MARQUEE_REGEX = re.compile(r"<\s*marquee\b", re.IGNORECASE)
BLINK_REGEX = re.compile(r"<\s*blink\b", re.IGNORECASE)
FLASH_REGEX = re.compile(
    r"(?:application/x-shockwave-flash|\b[a-zA-Z0-9_\-\./]+\.swf(?=[\s\"'\?#>]|$)|clsid:D27CDB6E-AE6D-11cf-96B8-444553540000)",
    re.IGNORECASE,
)
MODERN_CSS_REGEX = re.compile(
    r"(@media|display:\s*(?:flex|grid)|class=[\"'][^\"']*(?:container|row|col-|grid|flex))",
    re.IGNORECASE,
)

LATENCY_SLOW_THRESHOLD_SECONDS = 5.0
STALE_COPYRIGHT_YEARS_THRESHOLD = 4


def detect_viewport(html_content: str) -> Tuple[bool, bool, Optional[str]]:
    """
    Detects the presence and mobile friendliness of a viewport meta tag.

    Returns:
        (has_viewport, is_mobile_friendly, viewport_content)
    """
    if not html_content or not isinstance(html_content, str):
        return False, False, None

    viewport_content: Optional[str] = None
    for meta in META_TAG_REGEX.findall(html_content):
        if VIEWPORT_NAME_REGEX.search(meta):
            content_match = CONTENT_ATTR_REGEX.search(meta)
            if content_match:
                # Group 1 is quoted, group 2 is unquoted
                viewport_content = (content_match.group(1) or content_match.group(2) or "").strip()
            else:
                viewport_content = ""
            break

    if viewport_content is None:
        return False, False, None

    vp_lower = viewport_content.lower()

    # Fixed desktop width detection (e.g. width=1024, width=1200, width=960)
    fixed_width_match = re.search(r"width\s*=\s*(\d+)", vp_lower)
    is_fixed_desktop = False
    if fixed_width_match:
        val = int(fixed_width_match.group(1))
        if val >= 500:
            is_fixed_desktop = True

    has_device_width = "width=device-width" in vp_lower

    # user-scalable=no without width=device-width
    if not has_device_width and ("user-scalable=no" in vp_lower or "user-scalable=0" in vp_lower):
        is_fixed_desktop = True

    if is_fixed_desktop:
        return True, False, viewport_content

    if has_device_width or "initial-scale=1" in vp_lower:
        return True, True, viewport_content

    # If has viewport tag, but neither fixed desktop nor device-width/initial-scale recognized
    return True, False, viewport_content


def detect_legacy_technologies(html_content: str) -> Tuple[bool, List[str]]:
    """
    Detects obsolete and prehistoric web technologies in the HTML.

    Returns:
        (has_legacy_tech, detected_list)
    """
    if not html_content or not isinstance(html_content, str):
        return False, []

    detected: List[str] = []

    # 1. Frameset / Frame tags (excluding modern <iframe>)
    if FRAMESET_REGEX.search(html_content):
        detected.append("Frameset")
    elif FRAME_REGEX.search(html_content):
        detected.append("Frame")

    # 2. Obsolete Marquee & Blink tags
    if MARQUEE_REGEX.search(html_content):
        detected.append("Marquee")
    if BLINK_REGEX.search(html_content):
        detected.append("Blink")

    # 3. Flash objects / embeds
    if FLASH_REGEX.search(html_content):
        detected.append("Flash")

    # 4. Prehistoric nested table layout (repeated width="100%" and cellpadding="0" without modern CSS)
    layout_tables = re.findall(
        r'<table\b[^>]*(?:width=["\']100%["\'][^>]*cellpadding=["\']0["\']|cellpadding=["\']0["\'][^>]*width=["\']100%["\'])',
        html_content,
        re.IGNORECASE,
    )
    if len(layout_tables) >= 2 and re.search(r"<table\b[\s\S]*?<table\b", html_content, re.IGNORECASE):
        if not MODERN_CSS_REGEX.search(html_content):
            detected.append("Layout tabular aninhado")

    return len(detected) > 0, detected


def extract_copyright_year(
    html_content: str, current_year: Optional[int] = None
) -> Tuple[Optional[int], bool]:
    """
    Extracts copyright year and checks if it is stale (stagnant).

    Returns:
        (copyright_year, is_copyright_stale)
    """
    if not html_content or not isinstance(html_content, str):
        return None, False

    if current_year is None:
        current_year = datetime.date.today().year

    matches = COPYRIGHT_REGEX.findall(html_content)
    valid_years: List[int] = []
    for match in matches:
        try:
            year = int(match)
            # Realistic copyright year window (1990 up to current_year + 1)
            if 1990 <= year <= current_year + 1:
                valid_years.append(year)
        except (ValueError, TypeError):
            continue

    if not valid_years:
        return None, False

    latest_year = max(valid_years)
    is_stale = latest_year <= (current_year - STALE_COPYRIGHT_YEARS_THRESHOLD)
    return latest_year, is_stale


def audit_website_modernity(
    html_content: str,
    latency_seconds: float = 0.0,
    url: str = "",
    current_year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Comprehensive audit of website modernity, responsiveness, and performance.

    Returns:
        {
            "is_outdated_or_problematic": bool,
            "has_viewport": bool,
            "is_mobile_friendly": bool,
            "is_slow": bool,
            "latency_seconds": float,
            "has_legacy_tech": bool,
            "copyright_year": Optional[int],
            "is_copyright_stale": bool,
            "pain_points": list[str],
            "redesign_opportunity_score": int, # 0 to 30
            "url": str,
        }
    """
    if current_year is None:
        current_year = datetime.date.today().year

    latency_float = float(latency_seconds) if latency_seconds is not None else 0.0
    is_slow = latency_float >= LATENCY_SLOW_THRESHOLD_SECONDS

    pain_points: List[str] = []
    opportunity_score = 0

    # 1. Viewport & Responsiveness
    has_viewport, is_mobile_friendly, _ = detect_viewport(html_content)

    if not has_viewport:
        pain_points.append("Sem viewport para celular")
        opportunity_score += 15
    elif not is_mobile_friendly:
        pain_points.append("Viewport com largura fixa desktop")
        opportunity_score += 15

    # 2. Legacy Technologies
    has_legacy_tech, legacy_items = detect_legacy_technologies(html_content)
    if has_legacy_tech:
        opportunity_score += 10
        if "Flash" in legacy_items or "Frameset" in legacy_items or "Frame" in legacy_items:
            pain_points.append("Tecnologias legadas (Flash/Frameset)")
        elif "Marquee" in legacy_items or "Blink" in legacy_items:
            pain_points.append("Tecnologias legadas (Tags obsoletas: marquee/blink)")
        elif "Layout tabular aninhado" in legacy_items:
            pain_points.append("Tecnologias legadas (Layout baseado em tabelas)")
        else:
            pain_points.append(f"Tecnologias legadas ({'/'.join(legacy_items)})")

    # 3. Copyright year
    copyright_year, is_copyright_stale = extract_copyright_year(html_content, current_year=current_year)
    if is_copyright_stale and copyright_year is not None:
        pain_points.append(f"Copyright desatualizado ({copyright_year})")
        opportunity_score += 5

    # 4. Latency
    if is_slow:
        pain_points.append("Carregamento muito lento (> 5s)")
        opportunity_score += 5

    capped_score = min(30, opportunity_score)
    is_outdated_or_problematic = len(pain_points) > 0 or capped_score > 0

    return {
        "is_outdated_or_problematic": is_outdated_or_problematic,
        "has_viewport": has_viewport,
        "is_mobile_friendly": is_mobile_friendly,
        "is_slow": is_slow,
        "latency_seconds": latency_float,
        "has_legacy_tech": has_legacy_tech,
        "copyright_year": copyright_year,
        "is_copyright_stale": is_copyright_stale,
        "pain_points": pain_points,
        "redesign_opportunity_score": capped_score,
        "url": url or "",
    }
