"""
enrichment.py - Zero-token Lead Enrichment & Site Health Analyzer for Business Seeker

Provides:
1. Brazilian Web Presence Classifier (detects custom domains vs linktree/social/directories/none).
2. Brazilian Phone Formatter & WhatsApp 1-Click Link Generator.
3. Zero-Token Lead Enrichment (contact extraction, site health checks).
4. Lead Scoring (0-100 points, temperature, and priority reasons).
5. Multi-threaded Parallel Batch Enrichment.
"""

import concurrent.futures
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple
import requests

from parked_detector import detect_parked_or_abandoned_site
from responsiveness_auditor import audit_website_modernity

# ---------------------------------------------------------------------------
# Constants & Configuration
# ---------------------------------------------------------------------------

# Valid Brazilian area codes (DDDs)
VALID_BRAZILIAN_DDDS = {
    11, 12, 13, 14, 15, 16, 17, 18, 19,  # SP
    21, 22, 24,                          # RJ
    27, 28,                              # ES
    31, 32, 33, 34, 35, 37, 38,          # MG
    41, 42, 43, 44, 45, 46,              # PR
    47, 48, 49,                          # SC
    51, 53, 54, 55,                      # RS
    61,                                  # DF
    62, 64,                              # GO
    63,                                  # TO
    65, 66,                              # MT
    67,                                  # MS
    68,                                  # AC
    69,                                  # RO
    71, 73, 74, 75, 77,                  # BA
    79,                                  # SE
    81, 87,                              # PE
    82,                                  # AL
    83,                                  # PB
    84,                                  # RN
    85, 88,                              # CE
    86, 89,                              # PI
    91, 93, 94,                          # PA
    92, 97,                              # AM
    95,                                  # RR
    96,                                  # AP
    98, 99                               # MA
}

# Domain classification categories
WHATSAPP_DOMAINS = {
    "wa.me",
    "api.whatsapp.com",
    "whatsapp.com",
    "whats.link",
    "chat.whatsapp.com",
}

SOCIAL_DOMAINS = {
    "facebook.com",
    "fb.com",
    "fb.me",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "linkedin.com",
    "youtube.com",
}

LINKTREE_FREE_DOMAINS = {
    "linktr.ee",
    "bio.site",
    "beacons.ai",
    "linklist.bio",
    "carrd.co",
    "bento.me",
    "taplink.cc",
    "solo.to",
    "bit.ly",
    "canva.site",
    "sites.google.com",
    "wixsite.com",
    "weebly.com",
    "wordpress.com",
    "blogspot.com",
    "meu.negocio",
}

DIRECTORY_DOMAINS = {
    "ifood.com.br",
    "guiamais.com.br",
    "solutudo.com.br",
    "telelistas.net",
    "apontador.com.br",
    "kekanto.com.br",
    "doctoralia.com.br",
}

# Junk email domains/extensions to ignore during scraping
JUNK_EMAIL_DOMAINS = {
    "sentry.io",
    "wixpress.com",
    "example.com",
    "domain.com",
    "github.com",
    "google.com",
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "cloudflare.com",
    "wordpress.org",
    "wordpress.com",
    "gravatar.com",
    "akamaized.net",
    "schema.org",
    "w3.org",
    "w3schools.com",
    "adobe.com",
    "apple.com",
    "mysite.com",
    "yourdomain.com",
    "name.com",
    "wix.com",
    "canva.com",
    "linktr.ee",
    "beacons.ai",
    "sentry-next.wixpress.com",
}

JUNK_EMAIL_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".css", ".js", ".ico", ".woff", ".woff2"
}

# Instagram and Facebook paths to ignore as non-profile links
INSTAGRAM_JUNK_HANDLES = {
    "p", "reel", "reels", "explore", "stories", "tv", "accounts",
    "about", "legal", "help", "developer", "directory", "terms",
    "privacy", "contact", "blog", "press", "jobs", "api"
}

FACEBOOK_JUNK_HANDLES = {
    "sharer", "sharer.php", "policies", "login", "help", "pages",
    "share", "groups", "watch", "profile.php", "tr", "plugins",
    "dialog", "events", "photo.php"
}

DEFAULT_WHATSAPP_TEMPLATE = (
    "Olá! Vi a {business_name} no Google Maps ao pesquisar por {niche}. "
    "Notei que vocês ainda não possuem um site próprio e gostaria de saber se estão atendendo novos clientes pela internet."
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# 1. Brazilian Web Presence Classifier
# ---------------------------------------------------------------------------

def _extract_hostname(url: str) -> str:
    """Extract clean lowercase hostname without port from a URL string."""
    if not url:
        return ""
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url
    try:
        parsed = urllib.parse.urlparse(clean_url)
        hostname = (parsed.hostname or parsed.netloc or "").lower().strip()
        if ":" in hostname:
            hostname = hostname.split(":")[0]
        return hostname
    except Exception:
        return ""


def _domain_matches(hostname: str, target: str) -> bool:
    """Check if hostname matches target domain or is a subdomain of target."""
    if not hostname or not target:
        return False
    target = target.lower().strip()
    return hostname == target or hostname.endswith("." + target)


def classify_web_presence(url: Optional[str]) -> Dict[str, Any]:
    """
    Classify a website URL to determine whether it is a custom website,
    a social media profile, a link aggregator, a directory, or non-existent.

    Returns dict with:
        - status: Human-readable status (e.g. 'Sem Site', 'Rede Social', 'Domínio Próprio')
        - kind: 'NONE', 'WHATSAPP', 'SOCIAL', 'LINKTREE_FREE', 'DIRECTORY', or 'CUSTOM_DOMAIN'
        - label: UI label with emoji
        - url: Cleaned URL string
        - is_custom: bool (True only if CUSTOM_DOMAIN)
        - is_lead_candidate: bool (True if not a custom domain)
    """
    if not url or not str(url).strip():
        return {
            "status": "Sem Site",
            "kind": "NONE",
            "label": "🚫 Sem Site",
            "url": "",
            "is_custom": False,
            "is_lead_candidate": True,
        }

    clean_url = str(url).strip()
    # Normalize common placeholders
    if clean_url.lower() in {"nenhum", "n/a", "none", "-", "null", "undefined"}:
        return {
            "status": "Sem Site",
            "kind": "NONE",
            "label": "🚫 Sem Site",
            "url": "",
            "is_custom": False,
            "is_lead_candidate": True,
        }

    hostname = _extract_hostname(clean_url)
    if not hostname:
        return {
            "status": "Sem Site",
            "kind": "NONE",
            "label": "🚫 Sem Site",
            "url": clean_url,
            "is_custom": False,
            "is_lead_candidate": True,
        }

    # 1. WhatsApp links
    if any(_domain_matches(hostname, d) for d in WHATSAPP_DOMAINS):
        return {
            "status": "WhatsApp",
            "kind": "WHATSAPP",
            "label": "💬 WhatsApp Link",
            "url": clean_url,
            "is_custom": False,
            "is_lead_candidate": True,
        }

    # 2. Social media
    if any(_domain_matches(hostname, d) for d in SOCIAL_DOMAINS):
        return {
            "status": "Rede Social",
            "kind": "SOCIAL",
            "label": "📱 Rede Social",
            "url": clean_url,
            "is_custom": False,
            "is_lead_candidate": True,
        }

    # 3. Link in bio & Free builders
    if any(_domain_matches(hostname, d) for d in LINKTREE_FREE_DOMAINS):
        return {
            "status": "Link na Bio",
            "kind": "LINKTREE_FREE",
            "label": "🔗 Link na Bio / Construtor Grátis",
            "url": clean_url,
            "is_custom": False,
            "is_lead_candidate": True,
        }

    # 4. Food delivery & Local directories
    if any(_domain_matches(hostname, d) for d in DIRECTORY_DOMAINS):
        return {
            "status": "Guia / Diretório",
            "kind": "DIRECTORY",
            "label": "📂 Guia / Plataforma Externa",
            "url": clean_url,
            "is_custom": False,
            "is_lead_candidate": True,
        }

    # 5. Dedicated custom domain
    return {
        "status": "Domínio Próprio",
        "kind": "CUSTOM_DOMAIN",
        "label": "🌐 Domínio Próprio",
        "url": clean_url,
        "is_custom": True,
        "is_lead_candidate": False,
    }


# ---------------------------------------------------------------------------
# 2. Brazilian Phone Formatter & WhatsApp 1-Click Link Generator
# ---------------------------------------------------------------------------

def parse_brazilian_phone(phone: Optional[str]) -> Dict[str, Any]:
    """
    Cleans and validates any Brazilian phone number string.

    Recognizes:
    - Mobile: 11 digits (2 DDD + 9 digits starting with '9')
    - Landline: 10 digits (2 DDD + 8 digits starting with '2', '3', '4', or '5')

    Returns dict with:
        - raw: original string
        - clean: digits only
        - e164: e.g. '5511987654321'
        - ddd: 2-digit DDD string e.g. '11'
        - number: local number string e.g. '987654321'
        - formatted: e.g. '(11) 98765-4321' or '(11) 3344-5566'
        - type: '📱 Celular / WhatsApp', '☎️ Fixo', or 'Invalido'
        - is_mobile: bool
        - is_valid: bool
    """
    invalid_result = {
        "raw": phone or "",
        "clean": "",
        "e164": "",
        "ddd": "",
        "number": "",
        "formatted": (phone or "").strip(),
        "type": "Invalido",
        "is_mobile": False,
        "is_valid": False,
    }

    if not phone or not str(phone).strip():
        return invalid_result

    digits = re.sub(r"\D", "", str(phone))
    if not digits:
        return invalid_result

    # Strip national trunk prefix '0' (e.g. 011987654321 -> 11987654321)
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]

    # Strip country code '55' if present
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    # Validate length and DDD
    if len(digits) == 11:
        # 2 DDD + 9 digits (Mobile)
        ddd_str = digits[:2]
        num_str = digits[2:]
        try:
            ddd_int = int(ddd_str)
        except ValueError:
            return invalid_result

        if ddd_int in VALID_BRAZILIAN_DDDS and num_str.startswith("9"):
            return {
                "raw": phone,
                "clean": digits,
                "e164": f"55{digits}",
                "ddd": ddd_str,
                "number": num_str,
                "formatted": f"({ddd_str}) {num_str[:5]}-{num_str[5:]}",
                "type": "📱 Celular / WhatsApp",
                "is_mobile": True,
                "is_valid": True,
            }

    elif len(digits) == 10:
        # 2 DDD + 8 digits (Landline)
        ddd_str = digits[:2]
        num_str = digits[2:]
        try:
            ddd_int = int(ddd_str)
        except ValueError:
            return invalid_result

        if ddd_int in VALID_BRAZILIAN_DDDS and num_str[0] in "2345":
            return {
                "raw": phone,
                "clean": digits,
                "e164": f"55{digits}",
                "ddd": ddd_str,
                "number": num_str,
                "formatted": f"({ddd_str}) {num_str[:4]}-{num_str[4:]}",
                "type": "☎️ Fixo",
                "is_mobile": False,
                "is_valid": True,
            }

    return invalid_result


def classify_phone_type(phone: Optional[str]) -> str:
    """Helper returning phone classification label ('📱 Celular / WhatsApp', '☎️ Fixo', 'Invalido')."""
    return parse_brazilian_phone(phone)["type"]


def generate_whatsapp_url(
    phone: Optional[str],
    business_name: str = "",
    niche: str = "",
    custom_template: Optional[str] = None
) -> str:
    """
    Generates a WhatsApp 1-Click universal URL (https://wa.me/55...)
    with a customized, URL-encoded Portuguese pitch message.

    Returns empty string if phone cannot be resolved to a valid Brazilian number.
    """
    parsed = parse_brazilian_phone(phone)
    if not parsed["is_valid"] or not parsed["e164"]:
        return ""

    biz = (business_name or "").strip() or "sua empresa"
    niche_clean = (niche or "").strip() or "seus serviços"

    template = (custom_template or "").strip() or DEFAULT_WHATSAPP_TEMPLATE
    try:
        message = template.format(business_name=biz, niche=niche_clean)
    except Exception:
        message = template.replace("{business_name}", biz).replace("{niche}", niche_clean)

    encoded_text = urllib.parse.quote(message)
    return f"https://wa.me/{parsed['e164']}?text={encoded_text}"


# ---------------------------------------------------------------------------
# 3. Zero-Token Multi-threaded Lead Enrichment
# ---------------------------------------------------------------------------

def extract_contact_info(html_content: str) -> Dict[str, Any]:
    """
    Extracts emails, Instagram handles, Facebook links, and embedded WhatsApp links
    from raw HTML content. Filters junk domains and tracking assets.
    """
    result: Dict[str, Any] = {
        "emails": [],
        "primary_email": None,
        "instagram": None,
        "facebook": None,
        "whatsapp_links": [],
        "whatsapp_phones": [],
    }

    if not html_content or not isinstance(html_content, str):
        return result

    # 1. Emails: mailto links first, then regex text search
    found_emails: List[str] = []

    # Mailto links
    mailto_matches = re.findall(
        r'href=["\']mailto:([^"?\'>\s]+)', html_content, re.IGNORECASE
    )
    for m in mailto_matches:
        email = m.strip().lower()
        if email and "@" in email:
            found_emails.append(email)

    # General email regex
    regex_matches = re.findall(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", html_content
    )
    for r_email in regex_matches:
        found_emails.append(r_email.strip().lower())

    # Filter out junk emails
    clean_emails: List[str] = []
    seen_emails = set()
    for email in found_emails:
        if email in seen_emails:
            continue
        seen_emails.add(email)

        # Check domain and file extensions
        domain = email.split("@")[-1].lower() if "@" in email else ""
        if domain in JUNK_EMAIL_DOMAINS:
            continue
        if any(domain.endswith("." + jd) for jd in JUNK_EMAIL_DOMAINS):
            continue
        if any(email.endswith(ext) for ext in JUNK_EMAIL_EXTENSIONS):
            continue
        clean_emails.append(email)

    result["emails"] = clean_emails
    result["primary_email"] = clean_emails[0] if clean_emails else None

    # 2. Instagram: handle and link
    ig_matches = re.findall(
        r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9_.]+)/?",
        html_content,
        re.IGNORECASE,
    )
    for handle in ig_matches:
        h_clean = handle.strip().strip("/").lower()
        if h_clean and h_clean not in INSTAGRAM_JUNK_HANDLES:
            # Check length and avoid filenames
            if not any(h_clean.endswith(ext) for ext in JUNK_EMAIL_EXTENSIONS):
                result["instagram"] = {
                    "handle": f"@{h_clean}",
                    "url": f"https://instagram.com/{h_clean}",
                }
                break

    # 3. Facebook link
    fb_matches = re.findall(
        r"https?://(?:www\.)?(?:facebook\.com|fb\.com)/([A-Za-z0-9_.-]+)/?",
        html_content,
        re.IGNORECASE,
    )
    for handle in fb_matches:
        h_clean = handle.strip().strip("/").lower()
        if h_clean and h_clean not in FACEBOOK_JUNK_HANDLES:
            if not any(h_clean.endswith(ext) for ext in JUNK_EMAIL_EXTENSIONS):
                result["facebook"] = f"https://facebook.com/{h_clean}"
                break

    # 4. Embedded WhatsApp links and phones
    extracted_wa_links: List[str] = []
    extracted_wa_phones: List[str] = []

    # Matches https://wa.me/5511...
    for m in re.finditer(r"https?://wa\.me/(\d+)", html_content, re.IGNORECASE):
        phone_num = m.group(1)
        full_wa = f"https://wa.me/{phone_num}"
        if full_wa not in extracted_wa_links:
            extracted_wa_links.append(full_wa)
            extracted_wa_phones.append(phone_num)

    # Matches https://api.whatsapp.com/send?phone=5511...
    for m in re.finditer(
        r"https?://api\.whatsapp\.com/send\?[^\"'\s>]*phone=(\d+)",
        html_content,
        re.IGNORECASE,
    ):
        phone_num = m.group(1)
        full_wa = f"https://wa.me/{phone_num}"
        if full_wa not in extracted_wa_links:
            extracted_wa_links.append(full_wa)
            extracted_wa_phones.append(phone_num)

    # Matches short links: chat.whatsapp.com/..., whats.link/...
    for m in re.finditer(
        r"https?://(?:chat\.whatsapp\.com|whats\.link)/[A-Za-z0-9_-]+",
        html_content,
        re.IGNORECASE,
    ):
        sw = m.group(0)
        if sw not in extracted_wa_links:
            extracted_wa_links.append(sw)

    result["whatsapp_links"] = extracted_wa_links
    result["whatsapp_phones"] = extracted_wa_phones

    return result


def fetch_page_sample(
    url: str,
    timeout: int = 6,
    max_bytes: int = 400 * 1024
) -> Optional[str]:
    """
    Fetches the beginning of a web page using a streamed GET request.
    Restricts download to max_bytes (default 400KB) to prevent network bloat.
    """
    if not url or not str(url).strip():
        return None

    clean_url = str(url).strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = "https://" + clean_url

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        response = requests.get(
            clean_url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=True,
        )
        content = bytearray()
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content.extend(chunk)
                if len(content) >= max_bytes:
                    break
        return content.decode("utf-8", errors="replace")
    except Exception:
        return None


def check_website_health(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Performs a fast health check on a custom website URL.

    Detects:
    - Offline: ConnectionError, Timeout, DNS failure, HTTP status >= 400 -> '⚠️ Site Fora do Ar'
    - Insecure / No HTTPS: HTTP only or SSL certificate error -> '🔓 Sem HTTPS (Inseguro)'
    - Operational: Healthy HTTPS response (2xx/3xx) -> '✅ Site Operacional'
    """
    result: Dict[str, Any] = {
        "status": "🚫 Sem Site",
        "is_healthy": False,
        "has_https": False,
        "status_code": None,
        "error": None,
        "url": url or "",
    }

    if not url or not str(url).strip():
        result["error"] = "URL não fornecida"
        return result

    clean_url = str(url).strip()
    if clean_url.lower() in {"nenhum", "n/a", "none", "-", "null"}:
        result["error"] = "URL não fornecida"
        return result

    # Standardize initial target URL
    has_explicit_http = clean_url.startswith("http://")
    if not clean_url.startswith(("http://", "https://")):
        target_url = "https://" + clean_url
    else:
        target_url = clean_url

    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
    }

    session = requests.Session()
    try:
        # Try HEAD first for minimal latency
        try:
            resp = session.head(
                target_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=True,
            )
            # If server forbids HEAD (common with Cloudflare or Nginx), fallback to GET
            if resp.status_code in (403, 405):
                resp = session.get(
                    target_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,
                    stream=True,
                    verify=True,
                )
        except requests.exceptions.RequestException:
            # Try GET if HEAD failed unexpectedly
            resp = session.get(
                target_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                stream=True,
                verify=True,
            )

        final_url = resp.url or target_url
        result["status_code"] = resp.status_code

        # Offline check: HTTP error codes
        if resp.status_code >= 400:
            result["status"] = "⚠️ Site Fora do Ar"
            result["is_healthy"] = False
            result["error"] = f"HTTP {resp.status_code}"
            return result

        # Check HTTPS security
        final_is_https = final_url.lower().startswith("https://")
        result["has_https"] = final_is_https

        if not final_is_https:
            result["status"] = "🔓 Sem HTTPS (Inseguro)"
            result["is_healthy"] = False
            result["error"] = "Site sem certificado HTTPS ou redirecionamento inseguro"
            return result

        # Check Content for Parked / Abandoned / Default pages / Responsiveness
        html_sample = fetch_page_sample(final_url, timeout=timeout)
        if html_sample:
            parked_res = detect_parked_or_abandoned_site(html_sample, status_code=resp.status_code, url=final_url)
            if parked_res.get("is_parked_or_abandoned"):
                result["status"] = f"⚠️ {parked_res['reason']}"
                result["is_healthy"] = False
                result["is_parked"] = True
                result["parked_info"] = parked_res
                return result

            modernity_res = audit_website_modernity(html_sample, latency_seconds=0.0, url=final_url)
            result["modernity_info"] = modernity_res
            if not modernity_res.get("is_mobile_friendly"):
                result["status"] = "📱 Site Não Responsivo (Redesign)"
                result["is_healthy"] = False
                result["is_redesign_candidate"] = True
                return result
            elif modernity_res.get("is_outdated_or_problematic"):
                result["is_redesign_candidate"] = True

        # Healthy site
        result["status"] = "✅ Site Operacional"
        result["is_healthy"] = True
        return result

    except requests.exceptions.SSLError as ssl_err:
        result["status"] = "🔓 Sem HTTPS (Inseguro)"
        result["is_healthy"] = False
        result["has_https"] = False
        result["error"] = f"Erro de Certificado SSL: {ssl_err}"
        return result

    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.RequestException,
    ) as req_err:
        result["status"] = "⚠️ Site Fora do Ar"
        result["is_healthy"] = False
        result["error"] = str(req_err)
        return result


# ---------------------------------------------------------------------------
# 4. Lead Scoring (0 to 100 Points & Temperature)
# ---------------------------------------------------------------------------

def calculate_lead_score(
    place: Dict[str, Any],
    enriched_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculates a commercial lead score from 0 to 100 points based on:
    - Review count (up to +35 pts)
    - Rating (up to +20 pts)
    - Quick contact availability (up to +35 pts)
    - Digital pain (no site, broken site, linktree) (up to +15 pts)

    Returns:
        - score: int (0 to 100)
        - temperature: '🔥 Quente', '⚡ Médio', or '❄️ Frio'
        - reasons: list of human-readable priority reasons
        - breakdown: dict of points by category
    """
    enriched = enriched_info or {}
    reasons: List[str] = []

    # 1. Review Count extraction
    reviews = place.get("userRatingCount")
    if reviews is None and "Avaliação" in place:
        m = re.search(r"\((\d+)\)", str(place["Avaliação"]))
        if m:
            try:
                reviews = int(m.group(1))
            except ValueError:
                reviews = 0
    try:
        reviews = int(reviews) if reviews is not None else 0
    except (ValueError, TypeError):
        reviews = 0

    review_pts = 0
    if reviews >= 50:
        review_pts = 35
        reasons.append(f"Alto volume de avaliações ({reviews})")
    elif reviews >= 15:
        review_pts = 25
        reasons.append(f"Bom volume de avaliações ({reviews})")
    elif reviews >= 5:
        review_pts = 15
        reasons.append(f"Volume moderado de avaliações ({reviews})")
    elif reviews >= 1:
        review_pts = 5
        reasons.append(f"Poucas avaliações ({reviews})")

    # 2. Rating extraction
    rating = place.get("rating")
    if rating is None and "Avaliação" in place:
        m = re.search(r"(\d+(?:\.\d+)?)", str(place["Avaliação"]))
        if m:
            try:
                rating = float(m.group(1))
            except ValueError:
                rating = 0.0
    try:
        rating = float(rating) if rating is not None else 0.0
    except (ValueError, TypeError):
        rating = 0.0

    rating_pts = 0
    if rating >= 4.2:
        rating_pts = 20
        reasons.append(f"Excelente reputação ({rating:.1f}⭐)")
    elif rating >= 3.8:
        rating_pts = 10
        reasons.append(f"Boa reputação ({rating:.1f}⭐)")

    # 3. Quick Contact evaluation
    phone_info = enriched.get("phone_info")
    if not phone_info:
        raw_phone = place.get("nationalPhoneNumber") or place.get("Telefone") or ""
        phone_info = parse_brazilian_phone(raw_phone)

    contact_pts = 0
    if phone_info.get("is_mobile"):
        contact_pts += 25
        reasons.append("WhatsApp / Celular verificado")
    elif phone_info.get("type") == "☎️ Fixo":
        contact_pts += 10
        reasons.append("Telefone fixo disponível")

    # Extracted contact boost (email or Instagram)
    has_extracted_email = bool(
        enriched.get("extracted_email")
        or enriched.get("extracted_contacts", {}).get("primary_email")
    )
    has_extracted_ig = bool(
        enriched.get("extracted_instagram")
        or enriched.get("extracted_contacts", {}).get("instagram")
    )
    if has_extracted_email or has_extracted_ig:
        contact_pts += 10
        reasons.append("Canal adicional extraído (Email / Instagram)")

    # 4. Digital Pain evaluation
    web_pres = enriched.get("web_presence")
    if not web_pres:
        raw_web = place.get("websiteUri") or place.get("Site / Rede Social") or ""
        web_pres = classify_web_presence(raw_web)

    pain_pts = 0
    kind = web_pres.get("kind", "NONE")
    health = enriched.get("site_health") or {}
    health_status = health.get("status", "")

    if health_status == "⚠️ Site Fora do Ar":
        pain_pts = 15
        reasons.append("Site fora do ar (Dor urgente)")
    elif health.get("is_parked") or any(k in health_status for k in ("Estacionado", "Construção", "Padrão", "Branco", "Instalação")):
        pain_pts = 20
        clean_desc = health_status.replace("⚠️ ", "").strip()
        reasons.append(f"Site inativo / {clean_desc} (Dor urgente)")
    elif health.get("is_redesign_candidate") or "Não Responsivo" in health_status:
        pain_pts = 15
        reasons.append("Site não adaptado para celular (Oportunidade de Redesign)")
    elif kind == "NONE":
        pain_pts = 10
        reasons.append("Não possui site cadastrado")
    elif kind in ("LINKTREE_FREE", "SOCIAL", "WHATSAPP"):
        pain_pts = 10
        reasons.append("Utiliza agregador / rede social em vez de site próprio")
    elif health_status == "🔓 Sem HTTPS (Inseguro)":
        pain_pts = 10
        reasons.append("Site inseguro sem certificado HTTPS")

    # Total score calculation & clamping
    total_score = min(100, max(0, review_pts + rating_pts + contact_pts + pain_pts))

    if total_score >= 70:
        temperature = "🔥 Quente"
    elif total_score >= 40:
        temperature = "⚡ Médio"
    else:
        temperature = "❄️ Frio"

    return {
        "score": total_score,
        "temperature": temperature,
        "reasons": reasons,
        "breakdown": {
            "reviews": review_pts,
            "rating": rating_pts,
            "contact": contact_pts,
            "digital_pain": pain_pts,
        },
    }


# ---------------------------------------------------------------------------
# 5. Parallel Batch Lead Enrichment
# ---------------------------------------------------------------------------

def enrich_single_lead(
    lead: Dict[str, Any],
    niche: str = "",
    custom_pitch_template: Optional[str] = None,
    enrich_contacts: bool = True,
) -> Dict[str, Any]:
    """
    Enriches a single lead dictionary with:
    - Web presence classification
    - Phone number validation and E.164 normalization
    - WhatsApp 1-Click link generation
    - Contact extraction (if linktree / social) OR Site health check (if custom domain)
    - Commercial lead score and temperature
    """
    enriched = dict(lead)

    try:
        # Extract name
        name = (
            lead.get("Nome da Empresa")
            or (lead.get("displayName", {}).get("text") if isinstance(lead.get("displayName"), dict) else lead.get("displayName"))
            or "Empresa"
        )
        if isinstance(name, dict):
            name = name.get("text", "Empresa")

        # Extract website
        raw_web = lead.get("Site / Rede Social") or lead.get("websiteUri") or lead.get("website") or ""
        web_pres = classify_web_presence(raw_web)

        # Extract phone
        raw_phone = lead.get("Telefone") or lead.get("nationalPhoneNumber") or lead.get("phone") or ""
        phone_info = parse_brazilian_phone(raw_phone)

        # Site Health or Contact Extraction
        site_health: Optional[Dict[str, Any]] = lead.get("site_health")
        extracted_contacts: Dict[str, Any] = {
            "emails": [],
            "primary_email": None,
            "instagram": None,
            "facebook": None,
            "whatsapp_links": [],
            "whatsapp_phones": [],
        }

        if web_pres["kind"] == "CUSTOM_DOMAIN" and web_pres["url"]:
            if not site_health:
                site_health = check_website_health(web_pres["url"])
        elif enrich_contacts and web_pres["kind"] in ("LINKTREE_FREE", "SOCIAL", "WHATSAPP") and web_pres["url"]:
            page_sample = fetch_page_sample(web_pres["url"])
            if page_sample:
                extracted_contacts = extract_contact_info(page_sample)
                # If lead lacked mobile phone but page had embedded WhatsApp phone, adopt it
                if (not phone_info["is_valid"] or not phone_info["is_mobile"]) and extracted_contacts.get("whatsapp_phones"):
                    embedded_phone = extracted_contacts["whatsapp_phones"][0]
                    parsed_embedded = parse_brazilian_phone(embedded_phone)
                    if parsed_embedded["is_valid"]:
                        phone_info = parsed_embedded

        # Generate WhatsApp 1-Click Link
        wa_url = generate_whatsapp_url(
            phone_info["e164"] if phone_info["is_valid"] else None,
            business_name=name,
            niche=niche,
            custom_template=custom_pitch_template,
        )

        # Calculate Lead Score
        enrichment_meta = {
            "phone_info": phone_info,
            "web_presence": web_pres,
            "site_health": site_health,
            "extracted_contacts": extracted_contacts,
            "is_mobile": phone_info.get("is_mobile", False),
            "phone_type": phone_info.get("type", "Invalido"),
            "extracted_email": extracted_contacts.get("primary_email"),
            "extracted_instagram": extracted_contacts.get("instagram"),
        }
        score_info = calculate_lead_score(lead, enrichment_meta)

        # Attach technical metadata
        enriched["web_presence"] = web_pres
        enriched["phone_info"] = phone_info
        enriched["site_health"] = site_health
        enriched["extracted_contacts"] = extracted_contacts
        enriched["whatsapp_url"] = wa_url
        enriched["lead_score"] = score_info

        # Attach UI-ready formatted fields
        enriched["Tipo Presença"] = web_pres["label"]
        enriched["Tipo Telefone"] = phone_info["type"]
        enriched["WhatsApp 1-Clique"] = wa_url
        enriched["Score"] = score_info["score"]
        enriched["Temperatura"] = score_info["temperature"]
        enriched["Motivos Prioridade"] = " • ".join(score_info["reasons"])
        enriched["Email Extraído"] = extracted_contacts.get("primary_email") or "N/A"

        ig = extracted_contacts.get("instagram")
        enriched["Instagram Extraído"] = ig.get("handle") if isinstance(ig, dict) else (ig or "N/A")

        if site_health:
            enriched["Saúde do Site"] = site_health.get("status", "N/A")

    except Exception as exc:
        # Graceful fallback: lead is not dropped if any step fails
        enriched["enrichment_error"] = str(exc)

    return enriched


def enrich_leads_parallel(
    leads: List[Dict[str, Any]],
    max_workers: int = 10,
    niche: str = "",
    custom_pitch_template: Optional[str] = None,
    enrich_contacts: bool = True,
) -> List[Dict[str, Any]]:
    """
    Enriches a list of leads concurrently using ThreadPoolExecutor.
    Preserves input order while maximizing I/O performance.
    """
    if not leads:
        return []

    workers = min(max_workers, max(1, len(leads)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(enrich_single_lead, lead, niche, custom_pitch_template, enrich_contacts)
            for lead in leads
        ]
        return [f.result() for f in futures]
