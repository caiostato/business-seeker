"""
parked_detector.py - Heuristics for Parked, Abandoned, Default Server, Under Construction, and Blank Websites.

Detects HTTP 200 websites that appear technically operational but do not provide
a functional digital presence (e.g., parked domains, default server pages,
WordPress default posts, under construction notices, suspended accounts, or blank pages).

Part of the Business Seeker zero-token lead enrichment pipeline.
"""

import html as html_module
import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Categories Constants
# ---------------------------------------------------------------------------

CATEGORY_NONE = "NONE"
CATEGORY_PARKED_DOMAIN = "PARKED_DOMAIN"
CATEGORY_SERVER_DEFAULT = "SERVER_DEFAULT"
CATEGORY_UNDER_CONSTRUCTION = "UNDER_CONSTRUCTION"
CATEGORY_CMS_DEFAULT = "CMS_DEFAULT"
CATEGORY_SUSPENDED = "SUSPENDED"
CATEGORY_BLANK_PAGE = "BLANK_PAGE"

ALL_CATEGORIES = {
    CATEGORY_NONE,
    CATEGORY_PARKED_DOMAIN,
    CATEGORY_SERVER_DEFAULT,
    CATEGORY_UNDER_CONSTRUCTION,
    CATEGORY_CMS_DEFAULT,
    CATEGORY_SUSPENDED,
    CATEGORY_BLANK_PAGE,
}


# ---------------------------------------------------------------------------
# Signatures & Regular Expressions
# ---------------------------------------------------------------------------

# Signatures for SUSPENDED accounts & expired domains
SUSPENDED_SIGNATURES: List[Tuple[str, str, float, str]] = [
    # (Regex pattern, Reason PT-BR, Confidence, Target field: "text" | "title" | "html")
    (r"\bdom[ií]nio\s+expirado\b", "Domínio Expirado", 0.98, "text"),
    (r"\bdomain\s+expired\b", "Domínio Expirado", 0.98, "text"),
    (r"\bthis\s+domain\s+has\s+expired\b", "Domínio Expirado", 0.98, "text"),
    (r"\bdom[ií]nio\s+congelado\b", "Domínio Expirado", 0.98, "text"),
    (r"\bthis\s+account\s+has\s+been\s+suspended\b", "Conta de Hospedagem Suspensa", 0.98, "text"),
    (r"\baccount\s+suspended\b", "Conta de Hospedagem Suspensa", 0.98, "text"),
    (r"\bconta\s+suspensa\b", "Conta de Hospedagem Suspensa", 0.98, "text"),
    (r"\besta\s+conta\s+foi\s+suspensa\b", "Conta de Hospedagem Suspensa", 0.98, "text"),
    (r"\bsua\s+conta\s+de\s+hospedagem\s+foi\s+suspensa\b", "Conta de Hospedagem Suspensa", 0.98, "text"),
    (r"\bsite\s+suspenso\b", "Site Suspenso pelo Provedor", 0.95, "text"),
    (r"\bservi[çc]o\s+suspenso\b", "Site Suspenso pelo Provedor", 0.95, "text"),
    (r"\bwebsite\s+temporarily\s+unavailable\b", "Site Temporariamente Indisponível (Suspenso)", 0.92, "text"),
    (r"\bbandwidth\s+limit\s+exceeded\b", "Limite de Banda Excedido (Site Fora do Ar)", 0.95, "text"),
]

# Signatures for PARKED_DOMAIN (Registrars, Parking Services, Domain Marketplaces)
PARKED_DOMAIN_SIGNATURES: List[Tuple[str, str, float, str]] = [
    # GoDaddy
    (r"parked\s+free,?\s+courtesy\s+of\s+godaddy", "Domínio Estacionado (GoDaddy)", 0.98, "text"),
    (r"this\s+web\s+page\s+is\s+parked\s+free", "Domínio Estacionado (GoDaddy)", 0.98, "text"),
    (r"godaddy\.com/park", "Domínio Estacionado (GoDaddy)", 0.98, "html"),
    (r"domain\s+was\s+registered\s+with\s+godaddy", "Domínio Estacionado (GoDaddy)", 0.98, "text"),
    (r"godaddy\s+parked\s+page", "Domínio Estacionado (GoDaddy)", 0.98, "text"),
    (r"godaddy\s+domain\s+parking", "Domínio Estacionado (GoDaddy)", 0.98, "text"),
    # Hostinger
    (r"default\s+web\s+site\s+page\s*[-–]\s*hostinger", "Domínio Estacionado (Hostinger)", 0.98, "text"),
    (r"hostinger\s+domain\s+parking", "Domínio Estacionado (Hostinger)", 0.98, "text"),
    (r"este\s+dom[ií]nio\s+est[aá]\s+hospedado\s+na\s+hostinger", "Domínio Estacionado (Hostinger)", 0.98, "text"),
    (r"hostinger\.com/park", "Domínio Estacionado (Hostinger)", 0.98, "html"),
    (r"dom[ií]nio\s+registrado\s+na\s+hostinger", "Domínio Estacionado (Hostinger)", 0.98, "text"),
    # Registro.br
    (r"registro\.br\s*[-–]\s*dom[ií]nio\s+registrado", "Domínio Estacionado (Registro.br)", 0.98, "text"),
    (r"este\s+dom[ií]nio\s+est[aá]\s+registrado\s+no\s+registro\.br", "Domínio Estacionado (Registro.br)", 0.98, "text"),
    (r"dom[ií]nio\s+aguardando\s+publica[çc][ãa]o", "Domínio Estacionado (Registro.br)", 0.98, "text"),
    (r"registro\.br/dominio", "Domínio Estacionado (Registro.br)", 0.98, "html"),
    (r"dom[ií]nio\s+registrado\s+por\s+registro\.br", "Domínio Estacionado (Registro.br)", 0.98, "text"),
    # Locaweb
    (r"site\s+em\s+constru[çc][ãa]o\s*[-–]\s*locaweb", "Domínio Estacionado (Locaweb)", 0.98, "text"),
    (r"p[aá]gina\s+em\s+constru[çc][ãa]o\s*[-–]\s*hospedagem\s+locaweb", "Domínio Estacionado (Locaweb)", 0.98, "text"),
    (r"locaweb\.com\.br/painel", "Domínio Estacionado (Locaweb)", 0.98, "html"),
    (r"p[aá]gina\s+padr[ãa]o\s+locaweb", "Domínio Estacionado (Locaweb)", 0.98, "text"),
    (r"hospedado\s+na\s+locaweb", "Domínio Estacionado (Locaweb)", 0.95, "text"),
    # HostGator
    (r"hostgator\s*[-–]\s*p[aá]gina\s+de\s+espera", "Domínio Estacionado (HostGator)", 0.98, "text"),
    (r"hostgator\s+domain\s+parking", "Domínio Estacionado (HostGator)", 0.98, "text"),
    (r"aguardando\s+publica[çc][ãa]o\s+no\s+hostgator", "Domínio Estacionado (HostGator)", 0.98, "text"),
    (r"p[aá]gina\s+padr[ãa]o\s+hostgator", "Domínio Estacionado (HostGator)", 0.98, "text"),
    # KingHost
    (r"p[aá]gina\s+padr[ãa]o\s+da\s+kinghost", "Domínio Estacionado (KingHost)", 0.98, "text"),
    (r"dom[ií]nio\s+registrado\s+na\s+kinghost", "Domínio Estacionado (KingHost)", 0.98, "text"),
    # UOL Host
    (r"p[aá]gina\s+padr[ãa]o\s+uol\s+host", "Domínio Estacionado (UOL Host)", 0.98, "text"),
    (r"dom[ií]nio\s+registrado\s+no\s+uol\s+host", "Domínio Estacionado (UOL Host)", 0.98, "text"),
    # Namecheap
    (r"parked\s+by\s+namecheap", "Domínio Estacionado (Namecheap)", 0.98, "text"),
    (r"namecheap\.com/domains", "Domínio Estacionado (Namecheap)", 0.98, "html"),
    (r"this\s+domain\s+was\s+registered\s+with\s+namecheap", "Domínio Estacionado (Namecheap)", 0.98, "text"),
    # Sedo
    (r"sedoparking\.com", "Domínio Estacionado (Sedo)", 0.98, "html"),
    (r"sedo\s+domain\s+parking", "Domínio Estacionado (Sedo)", 0.98, "text"),
    (r"this\s+page\s+is\s+provided\s+by\s+sedo", "Domínio Estacionado (Sedo)", 0.98, "text"),
    # Dan.com
    (r"dan\.com/buy-domain", "Domínio Estacionado (Dan.com)", 0.98, "html"),
    (r"this\s+domain\s+is\s+available\s+on\s+dan\.com", "Domínio Estacionado (Dan.com)", 0.98, "text"),
    (r"compre\s+este\s+dom[ií]nio\s+no\s+dan\.com", "Domínio Estacionado (Dan.com)", 0.98, "text"),
    # Other Marketplaces
    (r"hugedomains\.com", "Domínio Estacionado para Venda (HugeDomains)", 0.98, "html"),
    (r"afternic\.com", "Domínio Estacionado para Venda (Afternic)", 0.98, "html"),
    (r"bodis\.com", "Domínio Estacionado para Venda (Bodis)", 0.98, "html"),
    (r"parkingcrew\.net", "Domínio Estacionado (ParkingCrew)", 0.98, "html"),
    # Generic Domain For Sale / Parking
    (r"\b(?:this\s+domain|este\s+dom[ií]nio)\s+(?:is|est[aá])\s+(?:for\s+sale|[aà]\s+venda)\b", "Domínio Estacionado para Venda", 0.95, "text"),
    (r"\bbuy\s+this\s+domain\b", "Domínio Estacionado para Venda", 0.95, "text"),
    (r"\bdomain\s+(?:is\s+)?available\s+for\s+sale\b", "Domínio Estacionado para Venda", 0.95, "text"),
    (r"\binquire\s+about\s+this\s+domain\b", "Domínio Estacionado para Venda", 0.95, "text"),
    (r"\bdomain\s+parking\b", "Domínio Estacionado", 0.90, "text"),
    (r"\bdom[ií]nio\s+estacionado\b", "Domínio Estacionado", 0.90, "text"),
]

# Signatures for SERVER_DEFAULT (Web server placeholder / test pages)
SERVER_DEFAULT_SIGNATURES: List[Tuple[str, str, float, str]] = [
    # Nginx
    (r"welcome\s+to\s+nginx!?", "Página Padrão Nginx", 0.98, "text"),
    (r"if\s+you\s+see\s+this\s+page,?\s+the\s+nginx\s+web\s+server", "Página Padrão Nginx", 0.98, "text"),
    (r"thank\s+you\s+for\s+using\s+nginx", "Página Padrão Nginx", 0.98, "text"),
    # Apache
    (r"apache2\s+(?:ubuntu|debian)\s+default\s+page", "Página Padrão Apache", 0.98, "text"),
    (r"it\s+works!\s*[-–]?\s*apache", "Página Padrão Apache", 0.98, "text"),
    (r"apache\s+http\s+server\s+test\s+page", "Página Padrão Apache", 0.98, "text"),
    (r"default\s+welcome\s+page\s+used\s+to\s+test.*apache2", "Página Padrão Apache", 0.98, "text"),
    # cPanel / WHM
    (r"cpanel\s+(?:&amp;|&)\s+whm\s+default\s+page", "Página Padrão cPanel / WHM", 0.98, "text"),
    (r"cpanel\s+default\s+page", "Página Padrão cPanel / WHM", 0.98, "text"),
    (r"cgi-sys/defaultwebpage\.cgi", "Página Padrão cPanel / WHM", 0.98, "html"),
    (r"a\s+new\s+cpanel\s+(?:&amp;|&)\s+whm\s+server\s+has\s+been\s+successfully\s+set\s+up", "Página Padrão cPanel / WHM", 0.98, "text"),
    (r"default\s+web\s+site\s+page.*cpanel", "Página Padrão cPanel / WHM", 0.98, "text"),
    # IIS (Windows Server)
    (r"iis\s+windows\s+server", "Página Padrão IIS (Windows Server)", 0.98, "text"),
    (r"internet\s+information\s+services", "Página Padrão IIS (Windows Server)", 0.95, "text"),
    (r"iis\.net", "Página Padrão IIS (Windows Server)", 0.90, "html"),
    # LiteSpeed
    (r"proudly\s+powered\s+by\s+litespeed\s+web\s+server", "Página Padrão LiteSpeed", 0.98, "text"),
    (r"litespeed\s+web\s+server", "Página Padrão LiteSpeed", 0.95, "text"),
    # Open Directory Listing (Index of /)
    (r"^index\s+of\s+/", "Listagem de Diretório Aberta (Index of /)", 0.98, "title"),
]

# Signatures for CMS_DEFAULT (Fresh / unconfigured CMS installations)
CMS_DEFAULT_SIGNATURES: List[Tuple[str, str, float, str]] = [
    # WordPress
    (r"just\s+another\s+wordpress\s+site", "Instalação Padrão do WordPress (Tagline Padrão)", 0.98, "text"),
    (r"s[oó]\s+mais\s+um\s+site\s+wordpress", "Instalação Padrão do WordPress (Tagline Padrão)", 0.98, "text"),
    (r"mais\s+um\s+site\s+wordpress", "Instalação Padrão do WordPress (Tagline Padrão)", 0.98, "text"),
    (r"um\s+novo\s+site\s+wordpress", "Instalação Padrão do WordPress (Tagline Padrão)", 0.98, "text"),
    (r"hello\s+world!?\s*welcome\s+to\s+wordpress", "Instalação Padrão do WordPress (Hello World)", 0.98, "text"),
    (r"ol[aá],?\s*mundo!?\s*bem-vindo\s+ao\s+wordpress", "Instalação Padrão do WordPress (Hello World)", 0.98, "text"),
    (r"bem-vindo\s+ao\s+wordpress\.?\s*este\s+[eé]\s+o\s+seu\s+primeiro\s+post", "Instalação Padrão do WordPress (Hello World)", 0.98, "text"),
    (r"welcome\s+to\s+wordpress\.?\s*this\s+is\s+your\s+first\s+post", "Instalação Padrão do WordPress (Hello World)", 0.98, "text"),
    # Joomla
    (r"joomla!\s+is\s+free\s+software\s+released\s+under\s+the\s+gnu", "Instalação Padrão do Joomla", 0.95, "text"),
    (r"welcome\s+to\s+your\s+new\s+joomla\s+site", "Instalação Padrão do Joomla", 0.95, "text"),
    # Drupal
    (r"welcome\s+to\s+your\s+new\s+drupal\s+website", "Instalação Padrão do Drupal", 0.95, "text"),
    (r"no\s+front\s+page\s+content\s+has\s+been\s+created\s+yet", "Instalação Padrão do Drupal", 0.95, "text"),
]

# Patterns for UNDER_CONSTRUCTION
UNDER_CONSTRUCTION_TITLE_REGEX = re.compile(
    r"^(?:(?:site|p[aá]gina|portal)\s+)?(?:em|sob)\s+(?:constru[çc][ãa]o|manuten[çc][ãa]o|desenvolvimento)\s*(?:[-–|].*)?$"
    r"|^(?:under\s+construction|coming\s+soon|em\s+breve)\s*(?:[-–|].*)?$"
    r"|^(?:site|p[aá]gina)\s+em\s+(?:manuten[çc][ãa]o|constru[çc][ãa]o)\b",
    re.IGNORECASE,
)

UNDER_CONSTRUCTION_HEADING_REGEX = re.compile(
    r"^(?:(?:(?:este\s+|o\s+)?(?:site|portal|website|p[aá]gina)\s+(?:est[aá]\s+)?)|estamos\s+)?(?:em|sob)\s+(?:constru[çc][ãa]o|manuten[çc][ãa]o|desenvolvimento|obras)$"
    r"|^(?:under\s+construction|coming\s+soon|voltaremos\s+em\s+breve|novidades\s+em\s+breve)$",
    re.IGNORECASE,
)

UNDER_CONSTRUCTION_TEXT_SIGNATURES: List[Tuple[str, str, float]] = [
    (r"\b(?:este\s+|o\s+)?(?:site|portal|website|p[aá]gina)\s+(?:est[aá]\s+)?(?:em|sob)\s+(?:constru[çc][ãa]o|manuten[çc][ãa]o|desenvolvimento|obras)\b", "Site em Construção", 0.95),
    (r"\b(?:estamos\s+)?em\s+obras\s+para\s+melhor\s+atend[eê]-lo\b", "Site em Obras / Construção", 0.95),
    (r"\bvoltaremos\s+em\s+breve\b", "Site em Manutenção (Voltaremos em Breve)", 0.92),
    (r"\bestaremos\s+de\s+volta\s+em\s+breve\b", "Site em Manutenção", 0.92),
    (r"\bunder\s+construction\b", "Site em Construção (Under Construction)", 0.95),
    (r"\bcoming\s+soon\b", "Em Breve (Coming Soon)", 0.92),
    (r"\bsite\s+(?:temporariamente\s+)?indispon[ií]vel\s+(?:para|em)\s+manuten[çc][ãa]o\b", "Site em Manutenção", 0.95),
    (r"\bdesculpe\s+(?:o|pelo)\s+transtorno,?\s+(?:estamos|site)\s+(?:em|sob)\s+manuten[çc][ãa]o\b", "Site em Manutenção", 0.95),
    (r"\bnovidades\s+em\s+breve\s*[,.!]?\s*(?:aguarde|acompanhe)\b", "Em Breve / Em Desenvolvimento", 0.90),
    (r"\bem\s+breve\s+(?:um\s+)?novo\s+site\b", "Em Breve (Novo Site)", 0.92),
]

# Legitimate business keywords that should NEVER be falsely flagged as UNDER_CONSTRUCTION
# (e.g. construction companies, auto mechanics, HVAC maintenance, etc.)
LEGITIMATE_BUSINESS_TERMS = [
    "construção civil",
    "materiais de construção",
    "material de construção",
    "loja de materiais de construção",
    "serviços de construção",
    "serviço de construção",
    "empresa de construção",
    "artigos para construção",
    "construção residencial",
    "construção comercial",
    "construção predial",
    "construção e reforma",
    "construções e reformas",
    "alvenaria e construção",
    "projetos e construção",
    "manutenção de carros",
    "manutenção automotiva",
    "manutenção de veículos",
    "manutenção preventiva",
    "manutenção corretiva",
    "manutenção predial",
    "manutenção industrial",
    "manutenção de ar condicionado",
    "manutenção de computadores",
    "manutenção de celulares",
    "oficina mecânica",
    "auto mecânica",
    "reparação automotiva",
]


# ---------------------------------------------------------------------------
# HTML Parsing & Text Normalization Helpers
# ---------------------------------------------------------------------------

def clean_html_text(html_content: Optional[str]) -> str:
    """
    Strips script, style, svg, noscript tags, comments, and all HTML markup.
    Unescapes HTML entities and collapses whitespace into single spaces.
    Returns the real, human-visible text content of the page.
    """
    if not html_content or not isinstance(html_content, str):
        return ""

    # Remove comments
    text = re.sub(r"<!--[\s\S]*?-->", " ", html_content)
    # Remove non-rendered block tags (scripts, styles, svg, noscript, iframes)
    text = re.sub(
        r"<(?:script|style|svg|noscript|iframe)\b[^>]*>[\s\S]*?</(?:script|style|svg|noscript|iframe)>",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities
    text = html_module.unescape(text)
    # Normalize whitespaces
    return re.sub(r"\s+", " ", text).strip()


def extract_html_title(html_content: Optional[str]) -> str:
    """
    Extracts and normalizes the contents of the <title> tag.
    """
    if not html_content or not isinstance(html_content, str):
        return ""

    match = re.search(r"<title\b[^>]*>(.*?)</title>", html_content, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""

    title_text = re.sub(r"<[^>]+>", " ", match.group(1))
    title_text = html_module.unescape(title_text)
    return re.sub(r"\s+", " ", title_text).strip()


def extract_headings(html_content: Optional[str]) -> List[str]:
    """
    Extracts all clean text from <h1> and <h2> tags.
    """
    if not html_content or not isinstance(html_content, str):
        return []

    headings: List[str] = []
    for match in re.finditer(r"<h[12]\b[^>]*>(.*?)</h[12]>", html_content, flags=re.IGNORECASE | re.DOTALL):
        h_text = re.sub(r"<[^>]+>", " ", match.group(1))
        h_text = html_module.unescape(h_text)
        clean_h = re.sub(r"\s+", " ", h_text).strip()
        if clean_h:
            headings.append(clean_h)
    return headings


def _has_legitimate_business_context(text: str) -> bool:
    """
    Checks if the clean text contains explicit legitimate business terms
    (civil construction, auto repair, preventive maintenance, etc.).
    """
    text_lower = text.lower()
    return any(term in text_lower for term in LEGITIMATE_BUSINESS_TERMS)


# ---------------------------------------------------------------------------
# Core Detection Engine
# ---------------------------------------------------------------------------

def detect_parked_or_abandoned_site(
    html_content: Optional[str],
    status_code: int = 200,
    url: str = ""
) -> Dict[str, Any]:
    """
    Analyzes an HTML response (typically HTTP 200) to determine if a website
    is parked, abandoned, default webserver page, under construction, or blank.

    Parameters:
    - html_content: Raw HTML body string.
    - status_code: HTTP response status code (default 200).
    - url: The target or final redirected URL.

    Returns:
    {
        "is_parked_or_abandoned": bool,
        "category": str, # "PARKED_DOMAIN", "SERVER_DEFAULT", "UNDER_CONSTRUCTION",
                         # "CMS_DEFAULT", "SUSPENDED", "BLANK_PAGE", "NONE"
        "reason": str,   # Human-readable diagnostic in PT-BR for pitch & lead status
        "confidence": float, # 0.0 to 1.0
    }
    """
    # 1. Normalize inputs
    if html_content is None:
        html_str = ""
    elif isinstance(html_content, bytes):
        html_str = html_content.decode("utf-8", errors="replace")
    else:
        html_str = str(html_content)

    clean_text = clean_html_text(html_str)
    text_len = len(clean_text)
    title = extract_html_title(html_str)
    headings = extract_headings(html_str)
    url_clean = (url or "").lower().strip()

    # 2. Check explicit URL indicators (Redirects to parking or cgi-sys)
    if "cgi-sys/defaultwebpage.cgi" in url_clean:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_SERVER_DEFAULT,
            "reason": "Página Padrão cPanel / WHM",
            "confidence": 0.99,
        }
    if "sedoparking.com" in url_clean:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_PARKED_DOMAIN,
            "reason": "Domínio Estacionado (Sedo)",
            "confidence": 0.99,
        }
    if "dan.com" in url_clean and ("buy-domain" in url_clean or "dan.com" in url_clean):
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_PARKED_DOMAIN,
            "reason": "Domínio Estacionado (Dan.com)",
            "confidence": 0.99,
        }
    if "godaddy.com/park" in url_clean:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_PARKED_DOMAIN,
            "reason": "Domínio Estacionado (GoDaddy)",
            "confidence": 0.99,
        }
    if "hostinger.com/park" in url_clean:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_PARKED_DOMAIN,
            "reason": "Domínio Estacionado (Hostinger)",
            "confidence": 0.99,
        }

    # 3. Check SUSPENDED / Expired accounts
    for pattern, reason, conf, target in SUSPENDED_SIGNATURES:
        target_str = clean_text if target == "text" else (title if target == "title" else html_str)
        if re.search(pattern, target_str, flags=re.IGNORECASE):
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_SUSPENDED,
                "reason": reason,
                "confidence": conf,
            }

    # 4. Check PARKED_DOMAIN signatures
    for pattern, reason, conf, target in PARKED_DOMAIN_SIGNATURES:
        target_str = clean_text if target == "text" else (title if target == "title" else html_str)
        if re.search(pattern, target_str, flags=re.IGNORECASE):
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_PARKED_DOMAIN,
                "reason": reason,
                "confidence": conf,
            }

    # 5. Check SERVER_DEFAULT signatures
    for pattern, reason, conf, target in SERVER_DEFAULT_SIGNATURES:
        target_str = clean_text if target == "text" else (title if target == "title" else html_str)
        if re.search(pattern, target_str, flags=re.IGNORECASE):
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_SERVER_DEFAULT,
                "reason": reason,
                "confidence": conf,
            }

    # Special Apache "It works!" fallback when headings or title matches
    if title.strip().lower() in ("apache2 ubuntu default page: it works", "apache2 debian default page: it works", "it works!"):
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_SERVER_DEFAULT,
            "reason": "Página Padrão Apache",
            "confidence": 0.98,
        }
    for h in headings:
        if h.strip().lower() == "it works!" and text_len < 300:
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_SERVER_DEFAULT,
                "reason": "Página Padrão Apache",
                "confidence": 0.98,
            }

    # 6. Check CMS_DEFAULT signatures
    for pattern, reason, conf, target in CMS_DEFAULT_SIGNATURES:
        target_str = clean_text if target == "text" else (title if target == "title" else html_str)
        if re.search(pattern, target_str, flags=re.IGNORECASE):
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_CMS_DEFAULT,
                "reason": reason,
                "confidence": conf,
            }

    # 7. Check UNDER_CONSTRUCTION signatures (with false positive guard)
    has_legit_context = _has_legitimate_business_context(clean_text)

    # 7a. Check Title for placeholder status
    title_matches_uc = bool(UNDER_CONSTRUCTION_TITLE_REGEX.match(title.strip()))
    if title_matches_uc:
        # If title strictly says "Em Construção" and there's no extensive legitimate business content
        if not (has_legit_context and text_len > 400):
            reason_str = "Site em Manutenção" if "manuten" in title.lower() else (
                "Página em Desenvolvimento" if "desenvolv" in title.lower() else "Site em Construção"
            )
            return {
                "is_parked_or_abandoned": True,
                "category": CATEGORY_UNDER_CONSTRUCTION,
                "reason": reason_str,
                "confidence": 0.95,
            }

    # 7b. Check Headings for placeholder status
    for h in headings:
        h_clean = h.strip()
        if UNDER_CONSTRUCTION_HEADING_REGEX.match(h_clean):
            if not (has_legit_context and text_len > 400):
                reason_str = "Site em Manutenção" if "manuten" in h_clean.lower() else (
                    "Site em Obras / Construção" if "obras" in h_clean.lower() else "Site em Construção"
                )
                return {
                    "is_parked_or_abandoned": True,
                    "category": CATEGORY_UNDER_CONSTRUCTION,
                    "reason": reason_str,
                    "confidence": 0.95,
                }

    # 7c. Check Text phrases for placeholder status
    # False positive protection: If page has legitimate business terms and text_len >= 200,
    # skip generic text regex matching.
    if not (has_legit_context and text_len >= 200):
        for pattern, reason, conf in UNDER_CONSTRUCTION_TEXT_SIGNATURES:
            if re.search(pattern, clean_text, flags=re.IGNORECASE):
                return {
                    "is_parked_or_abandoned": True,
                    "category": CATEGORY_UNDER_CONSTRUCTION,
                    "reason": reason,
                    "confidence": conf,
                }

    # 8. Check BLANK_PAGE (Empty or visible clean text < 80 characters)
    if text_len == 0:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_BLANK_PAGE,
            "reason": "Página em Branco (Sem Conteúdo Textual)",
            "confidence": 1.0,
        }

    if text_len < 80:
        return {
            "is_parked_or_abandoned": True,
            "category": CATEGORY_BLANK_PAGE,
            "reason": "Página Quase Vazia (Menos de 80 caracteres de texto)",
            "confidence": 0.85,
        }

    # 9. Default: Functional, legitimate website with content
    return {
        "is_parked_or_abandoned": False,
        "category": CATEGORY_NONE,
        "reason": "",
        "confidence": 0.0,
    }
