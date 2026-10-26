"""
smart_filters.py - Smart Filters and Fuzzy Deduplication for Business Seeker.

Provides intelligent algorithms to:
1. Detect chains, franchises, and multi-unit networks to filter out corporate
   branches from lead lists.
2. Normalize Brazilian addresses (expanding abbreviations, handling CEPs, UFs, and street numbers).
3. Normalize business names (stripping legal entity markers, unit identifiers, and accents).
4. Perform fuzzy deduplication on places lists using difflib.SequenceMatcher.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

# Common Brazilian corporate and legal entity suffixes
LEGAL_ENTITY_PATTERN = re.compile(
    r"\b(?:ltda|eireli|epp|m\.e\.?|me|s[\./]?a|s[\./]?s|s\/c|cia)\b",
    re.IGNORECASE,
)

# Common words representing generic business types (used to prevent false brand matching)
GENERIC_CATEGORY_WORDS = {
    "oficina", "mecanica", "auto", "eletrica", "pecas", "centro", "funilaria",
    "padaria", "panificadora", "restaurante", "bar", "lanchonete", "choperia",
    "pizzaria", "hamburgueria", "sorveteria", "cafeteria", "cafe", "rotisseria",
    "salao", "beleza", "barbearia", "esmalteria", "estetica", "cabeleireiro",
    "clinica", "consultorio", "hospital", "laboratorio", "medica", "odontologia",
    "farmacia", "drogaria", "droga",
    "otica", "oticas",
    "supermercado", "mercado", "mercearia", "minimercado", "acougue", "hortifruti",
    "pet", "shop", "petshop", "veterinaria", "banho", "tosa",
    "lavanderia", "estacionamento", "hotel", "pousada", "hostel",
    "academia", "escola", "colegio", "curso", "instituto", "treinamento",
    "papelaria", "grafica", "imobiliaria", "corretora", "advocacia", "contabilidade",
    "borracharia", "vidracaria", "marcenaria", "serralheria", "serralharia",
    "deposito", "materiais", "construcao", "chaveiro", "loja", "bazar", "distribuidora"
}

# Portuguese stopwords and prepositions
STOPWORDS = {
    "do", "da", "dos", "das", "de", "di", "del", "d", "e", "em", "no", "na",
    "nos", "nas", "com", "para", "pra", "pro", "a", "o", "as", "os"
}

# Common Brazilian neighborhood/district names frequently appended as unit identifiers
COMMON_DISTRICT_NAMES = {
    "moema", "jardins", "itaim", "bibi", "pinheiros", "morumbi", "paulista",
    "santana", "tatuape", "perdizes", "brooklin", "centro", "barra", "copacabana",
    "ipanema", "leblon", "tijuca", "savassi", "batel", "vila", "mariana", "madalena",
    "olimpia", "leopoldina", "consolacao", "bela", "vista", "bras", "se", "interlagos",
    "butanta", "alphaville", "tambore", "lapa", "cambuci", "aclimacao", "pompeia"
}

# Curated catalog of widely recognized Brazilian and multinational chains / franchises
KNOWN_FRANCHISE_BRANDS = [
    # Fast-food & Food Franchises
    "mcdonalds", "mc donald", "burger king", "subway", "bobs", "giraffas", "spoleto",
    "cacau show", "kopenhagen", "brasil cacau", "habibs", "ragazzo", "outback",
    "madero", "jeronymo", "starbucks", "dominos", "pizza hut", "popeyes", "kfc",
    "casa do pao de queijo", "rei do mate", "chiquinho sorvetes", "oakberry",
    "the coffee", "bullguer", "madeiro", "seletti", "divino fogao", "griletto",
    "montana grill", "vivenda do camarao", "china in box", "gendai",
    # Pharmacies & Drugstores
    "drogasil", "droga raia", "pague menos", "ultrafarma", "drogaria sao paulo",
    "drogaria venancio", "panvel", "farmacia pacheco", "drogaria pacheco", "drogal",
    "drogaria araujo", "extrafarma", "farmacias associadas",
    # Fitness & Gyms
    "smart fit", "bluefit", "bio ritmo", "selfit", "skyfit", "just fit", "bodytech",
    # Eyewear & Optics
    "oticas carol", "oticas diniz", "chilli beans", "grandvision", "fototica", "otica gassi",
    # Retail & Department Stores
    "lojas americanas", "americanas", "magazine luiza", "magalu", "casas bahia",
    "ponto frio", "riachuelo", "renner", "c&a", "marisa", "kalunga", "hering",
    "arezzo", "havanna", "centauro", "decathlon", "leroy merlin", "telhanorte", "c&c",
    # Supermarkets & Wholesale
    "carrefour", "extra", "pao de acucar", "assai", "atacadao", "sams club",
    "roldao", "tenda atacado", "st marche", "mambo", "dia%", "supermercados dia",
    # Beauty & Cosmetics
    "o boticario", "boticario", "quem disse berenice", "espacolaser", "sobrancelhas design",
    "giovanna baby", "sephora", "loccitane", "natura",
    # Healthcare & Dental
    "sorridents", "odontoclinic", "sorrifacil", "dr consulta", "lavoisier", "fleury", "delboni",
    # Education & Languages
    "wizard", "fisk", "cna", "ccaa", "kumon", "microlins", "yes idiomas", "wise up",
    # Automotive, Gas & Maintenance
    "posto ipiranga", "posto shell", "posto br", "petrobras", "lubrax", "porto seguro auto",
    "impacto prime", "dpaschoal", "autozone",
    # Services & Hospitality
    "cvc", "5asec", "dryclean usa", "lavanderia 60 minutos", "localiza", "movida", "unidas"
]


def strip_accents(text: str) -> str:
    """Remove accents and diacritics from text, preserving plain ASCII."""
    if not text:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(text))
        if not unicodedata.combining(c)
    )


def calculate_text_similarity(s1: str, s2: str) -> float:
    """
    Calculate similarity between two strings using difflib.SequenceMatcher.
    Combines direct character sequence ratio and token-sorted ratio to be robust
    against word-order inversions (e.g. 'Oficina Mecânica São José' vs 'Oficina São José Mecânica').
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    # 1. Direct character ratio
    seq_ratio = difflib.SequenceMatcher(None, s1, s2).ratio()

    # 2. Token-sorted ratio (handles reordered words)
    tok1 = " ".join(sorted(s1.split()))
    tok2 = " ".join(sorted(s2.split()))
    tok_ratio = difflib.SequenceMatcher(None, tok1, tok2).ratio()

    return max(seq_ratio, tok_ratio)


def normalize_business_name(name: str) -> str:
    """
    Normalize a business name by:
    - Removing accents and converting to lowercase.
    - Stripping parenthesized descriptors.
    - Removing corporate/legal entity suffixes (Ltda, ME, EPP, S/A, Eireli).
    - Removing unit markers (e.g., ' - Unidade ...', ' - Loja ...', ' - Moema').
    - Removing trailing unit words (e.g., 'Loja 02', 'Unidade Jardins', 'Moema').
    - Cleaning non-alphanumeric punctuation and collapsing whitespace.

    Examples:
        'Óticas Carol Moema' -> 'oticas carol'
        'Óticas Carol - Moema' -> 'oticas carol'
        'Oficina Mecânica São José ME' -> 'oficina mecanica sao jose'
        'Smart Fit - Unidade Jardins' -> 'smart fit'
    """
    if not name:
        return ""

    text = strip_accents(str(name)).lower()

    # Remove parenthetical notes e.g. "(Moema)", "(Loja 02)"
    text = re.sub(r"\(.*?\)", " ", text)

    # Remove corporate/legal suffixes
    text = LEGAL_ENTITY_PATTERN.sub(" ", text)

    # Remove unit patterns separated by hyphens, pipes, or slashes:
    # e.g. " - Moema", " - Unidade 2", " - Loja 14", " | Morumbi"
    text = re.sub(
        r"\s+[-–—/|]\s+(?:unidade|unid|loja|lj|filial|shopping|shop\b|[a-z0-9\s]+)$",
        " ",
        text,
    )

    # Remove trailing explicit unit tags without hyphens: "unidade X", "loja 12", "filial 01"
    text = re.sub(r"\b(?:unidade|unid\.?|loja|lj\.?|filial)\s+[a-z0-9]+", " ", text)

    # Remove common trailing district/neighborhood markers: e.g. "Moema", "de Moema"
    districts_re = "|".join(sorted(COMMON_DISTRICT_NAMES, key=len, reverse=True))
    text = re.sub(rf"\b(?:de\s+)?(?:{districts_re})\s*$", " ", text)

    # Remove punctuation, keep letters and digits
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    return " ".join(text.split())


def normalize_brazilian_address(address: str) -> str:
    r"""
    Normalize a Brazilian address to ensure stable comparisons:
    - Removes accents and converts to lowercase ('São Paulo' -> 'sao paulo').
    - Standardizes common Brazilian street type abbreviations:
        'av.' / 'av' -> 'avenida'
        'r.' / 'r' -> 'rua'
        'rod.' / 'rod' -> 'rodovia'
        'al.' / 'al' -> 'alameda'
        'pça.' / 'pca' -> 'praca'
        'dr.' -> 'doutor'
        'est.' -> 'estrada'
        'trav.' / 'tv.' -> 'travessa'
    - Removes CEPs (\d{5}-?\d{3}).
    - Removes trailing country (', Brasil').
    - Removes Brazilian state codes (- SP, / SP) and common city suffixes.
    - Extracts and standardizes street name and number.

    Examples:
        'Av. Paulista, 1000 - SP' -> 'avenida paulista, 1000'
        'Avenida Paulista, 1000, São Paulo' -> 'avenida paulista, 1000'
        'Av. Santo Amaro, 1200' -> 'avenida santo amaro, 1200'
        'Avenida Santo Amaro, 1200 - Vila Nova Conceição, São Paulo - SP' -> 'avenida santo amaro, 1200'
    """
    if not address:
        return ""

    text = strip_accents(str(address)).lower()

    # 1. Standardize abbreviations (using word boundaries or dots)
    abbrev_map = [
        (r"\b(?:av\.|av\b)", "avenida"),
        (r"\b(?:r\.|r\b)", "rua"),
        (r"\b(?:rod\.|rod\b)", "rodovia"),
        (r"\b(?:al\.|al\b)", "alameda"),
        (r"\b(?:p[cç]a\.|p[cç]a\b|pca)", "praca"),
        (r"\b(?:dr\.|dr\b)", "doutor"),
        (r"\b(?:dra\.|dra\b)", "doutora"),
        (r"\b(?:est\.|est\b)", "estrada"),
        (r"\b(?:trav\.|tv\.|trav\b|tv\b)", "travessa"),
        (r"\b(?:prof\.|prof\b)", "professor"),
        (r"\b(?:cel\.|cel\b)", "coronel"),
        (r"\b(?:gen\.|gen\b)", "general"),
        (r"\b(?:sto\.|sto\b)", "santo"),
        (r"\b(?:sta\.|sta\b)", "santa"),
        (r"\b(?:pres\.|pres\b)", "presidente"),
        (r"\b(?:gov\.|gov\b)", "governador"),
    ]
    for pattern, rep in abbrev_map:
        text = re.sub(pattern, rep, text)

    # 2. Remove CEP (\d{5}-?\d{3})
    text = re.sub(r"\b\d{5}-?\d{3}\b", " ", text)

    # 3. Remove country
    text = re.sub(r"[, -]+\b(?:brasil|brazil)\b", " ", text)

    # 4. Remove state suffixes e.g. ' - sp', ' / sp', ', sp' at end of address
    ufs = (
        r"(?:ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)"
    )
    text = re.sub(rf"[-/,\s]+{ufs}\s*$", " ", text)

    # 5. Remove common metropolitan city suffixes
    cities = (
        r"(?:sao paulo|rio de janeiro|belo horizonte|curitiba|porto alegre|salvador|"
        r"fortaleza|recife|brasilia|campinas|santo andre|sao bernardo|sao caetano|osasco|guarulhos)"
    )
    text = re.sub(rf"[, -]+\b{cities}\b", " ", text)

    text = " ".join(text.split()).strip(" ,-")

    # 6. Extract street and address number:
    # Pattern: <street_name>, <number> or <street_name> <number>
    # where number is followed by end of string or complement/neighborhood
    m = re.match(
        r"^([^,0-9]+?)[,\s]+(?:n[º°.]?\s*|no\.\s*)?(\d+[a-z]?)(?:[,\s-]+.*)?$",
        text,
    )
    if m:
        street = m.group(1).strip()
        num = m.group(2).strip()
        street = re.sub(r"[^a-z0-9\s]", " ", street)
        street = " ".join(street.split())
        return f"{street}, {num}"

    # Fallback if no explicit number identified
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _extract_brand_tokens(name: str) -> list[str]:
    """Helper to extract clean brand tokens without legal markers or district tags."""
    clean = strip_accents(name).lower()
    clean = re.sub(r"\(.*?\)", " ", clean)
    clean = LEGAL_ENTITY_PATTERN.sub(" ", clean)
    clean = re.sub(
        r"\s+[-–—/|]\s+(?:unidade|unid|loja|lj|filial|shopping|shop|[a-z0-9\s]+)$",
        " ",
        clean,
    )
    clean = re.sub(r"\b(?:unidade|unid\.?|loja|lj\.?|filial)\s+[a-z0-9]+", " ", clean)
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    return [w for w in clean.split() if w]


def _find_shared_brand_prefix(t1: list[str], t2: list[str]) -> str | None:
    """
    Find common prefix words between two token lists and verify if it contains
    at least one distinctive brand word (i.e. not purely generic categories or stopwords).
    """
    prefix: list[str] = []
    for w1, w2 in zip(t1, t2):
        if w1 == w2:
            prefix.append(w1)
        else:
            break

    if not prefix:
        return None

    # Check if the prefix has at least one distinctive token of length >= 3
    distinctive = [
        w for w in prefix
        if w not in GENERIC_CATEGORY_WORDS and w not in STOPWORDS and len(w) >= 3
    ]
    if distinctive:
        return " ".join(prefix)
    return None


def detect_chain_or_franchise(
    place_name: str,
    types: list[str] | None = None,
    all_batch_names: list[str] | None = None,
) -> dict[str, Any]:
    """
    Detect whether a business is likely a corporate chain, franchise, or multi-unit network.

    Checks:
    1. Batch network frequency (all_batch_names):
       If 2 or more businesses in the batch share the same root brand prefix,
       both are automatically identified as part of a multi-unit network.
    2. Structural unit and branch patterns via regex:
       - 'Shopping \\w+' (e.g. 'Shopping Morumbi')
       - 'Loja \\d+' (e.g. 'Loja 04')
       - 'Filial \\d+' or 'Filial \\w+' (e.g. 'Filial 02')
       - 'Unidade \\w+' (e.g. 'Unidade Moema')
       - 'Express\\b', 'Outlet\\b', 'Drive Thru\\b'
       - 'Auto Posto\\b'
       - 'Rede \\w+'
       - 'Supermercado(s)?', 'Hipermercado', 'Atacadista', 'Atacadão'
       - 'Drogaria \\w+'
    3. Known national and international franchise brands (e.g. Subway, Smart Fit, Óticas Carol).

    Args:
        place_name: Name of the business.
        types: Optional list of Google Places types.
        all_batch_names: Optional list of all business names in the current search batch.

    Returns:
        dict: {
            "is_likely_chain": bool,
            "confidence": float,  # 0.0 to 1.0
            "matched_pattern": str,
            "reason": str,
        }
    """
    if not place_name or not str(place_name).strip():
        return {
            "is_likely_chain": False,
            "confidence": 0.0,
            "matched_pattern": "",
            "reason": "Nome do estabelecimento não fornecido.",
        }

    raw_name = str(place_name).strip()
    norm_name = strip_accents(raw_name).lower()

    # -------------------------------------------------------------------------
    # 1. Check Batch Frequency (all_batch_names)
    # -------------------------------------------------------------------------
    batch_matches: list[str] = []
    batch_brand_prefix: str = ""

    if all_batch_names and len(all_batch_names) >= 2:
        target_tokens = _extract_brand_tokens(raw_name)
        target_found_count = 0
        for other_name in all_batch_names:
            if not other_name or not str(other_name).strip():
                continue
            if str(other_name).strip() == raw_name:
                target_found_count += 1
                if target_found_count > 1:
                    batch_matches.append(str(other_name).strip())
                    batch_brand_prefix = " ".join(target_tokens)
                continue

            other_tokens = _extract_brand_tokens(other_name)
            shared = _find_shared_brand_prefix(target_tokens, other_tokens)
            if shared:
                batch_matches.append(str(other_name).strip())
                batch_brand_prefix = shared

    if batch_matches:
        total_units = len(batch_matches) + 1
        brand_display = batch_brand_prefix.title()
        return {
            "is_likely_chain": True,
            "confidence": 0.95,
            "matched_pattern": f"Rede com múltiplas unidades ('{brand_display}')",
            "reason": (
                f"Detectadas {total_units} unidades compartilhando a marca "
                f"'{brand_display}' no lote de busca."
            ),
        }

    # -------------------------------------------------------------------------
    # 2. Structural Name Pattern Checks (Shopping, Loja, Unidade, Filial, etc.)
    # -------------------------------------------------------------------------
    # A. Shopping Mall location
    shopping_match = re.search(
        r"\b(?:shopping|center\s+shopping)\s+([a-z0-9à-ÿ\s\-]+?)(?:\s*[-–—|/]|$)",
        norm_name,
    )
    if shopping_match or re.search(r"\b(?:no\s+shopping|do\s+shopping)\b", norm_name):
        mall_text = shopping_match.group(0).strip() if shopping_match else "Shopping"
        return {
            "is_likely_chain": True,
            "confidence": 0.90,
            "matched_pattern": f"Padrão de Shopping ('{mall_text.title()}')",
            "reason": "Estabelecimento situado em shopping center ou centro comercial, padrão típico de franquias.",
        }

    # B. Loja numerada (e.g. "Loja 04", "Loja 102", "Lj 03")
    loja_match = re.search(r"\b(?:loja|lj\.?)\s*(\d+)\b", norm_name)
    if loja_match:
        num = loja_match.group(1)
        return {
            "is_likely_chain": True,
            "confidence": 0.92,
            "matched_pattern": f"Padrão de Filial ('Loja {num}')",
            "reason": f"Identificador de loja numerada ('Loja {num}'), característico de filiais de grandes redes.",
        }

    # C. Filial identificada (e.g. "Filial 02", "Filial Centro")
    filial_match = re.search(r"\b(?:filial|fil\.?)\s*(\d+|[a-z0-9à-ÿ]+)\b", norm_name)
    if filial_match:
        f_id = filial_match.group(1)
        return {
            "is_likely_chain": True,
            "confidence": 0.90,
            "matched_pattern": f"Padrão de Filial ('Filial {f_id.title()}')",
            "reason": f"Identificador de filial ('Filial {f_id}'), característico de redes de negócios.",
        }

    # D. Unidade explícita (e.g. "Unidade Moema", "Unidade 01")
    unidade_match = re.search(r"\b(?:unidade|unid\.?)\s+([a-z0-9à-ÿ]+)", norm_name)
    if unidade_match:
        u_name = unidade_match.group(1)
        return {
            "is_likely_chain": True,
            "confidence": 0.88,
            "matched_pattern": f"Padrão de Unidade ('Unidade {u_name.title()}')",
            "reason": f"Indicação explícita de unidade corporativa ('Unidade {u_name.title()}').",
        }

    # E. Express, Outlet, Drive Thru
    express_match = re.search(r"\b(express|outlet|drive\s*thru)\b", norm_name)
    if express_match:
        fmt = express_match.group(1).title()
        return {
            "is_likely_chain": True,
            "confidence": 0.85,
            "matched_pattern": f"Padrão Express/Formato ('{fmt}')",
            "reason": f"Formato '{fmt}' comumente operado por redes e modelos de franquia.",
        }

    # F. Auto Posto
    posto_match = re.search(r"\b(auto\s+posto|posto\s+(?:ipiranga|shell|br|petrobras|ale))\b", norm_name)
    if posto_match:
        matched_str = posto_match.group(1).title()
        return {
            "is_likely_chain": True,
            "confidence": 0.85,
            "matched_pattern": f"Padrão de Auto Posto ('{matched_str}')",
            "reason": "Posto de combustíveis associado a distribuidora ou bandeira nacional.",
        }

    # G. Rede explícita
    rede_match = re.search(r"\brede\s+([a-z0-9à-ÿ]+)", norm_name)
    if rede_match:
        net_name = rede_match.group(1).title()
        return {
            "is_likely_chain": True,
            "confidence": 0.90,
            "matched_pattern": f"Padrão de Rede ('Rede {net_name}')",
            "reason": f"Identificado formalmente como parte de uma rede ('Rede {net_name}').",
        }

    # H. Supermercados, Hipermercados, Atacadistas, Atacadão
    retail_match = re.search(r"\b(supermercados?|hipermercado|atacadista|atacadao)\b", norm_name)
    if retail_match:
        r_type = retail_match.group(1).title()
        return {
            "is_likely_chain": True,
            "confidence": 0.85,
            "matched_pattern": f"Grande Varejista / Atacado ('{r_type}')",
            "reason": f"Segmento de grande porte ('{r_type}'), fora do perfil de pequenas empresas locais.",
        }

    # I. Drogaria com especificação de rede
    drogaria_match = re.search(r"\bdrogaria\s+([a-z0-9à-ÿ]+)", norm_name)
    if drogaria_match:
        d_name = drogaria_match.group(1).title()
        if types and any(t in types for t in ["pharmacy", "health"]):
            return {
                "is_likely_chain": True,
                "confidence": 0.80,
                "matched_pattern": f"Drogaria ('Drogaria {d_name}')",
                "reason": f"Rede ou drogaria comercial ('Drogaria {d_name}').",
            }

    # -------------------------------------------------------------------------
    # 3. Known Franchise Brands Catalog
    # -------------------------------------------------------------------------
    for brand in KNOWN_FRANCHISE_BRANDS:
        brand_clean = strip_accents(brand).lower()
        if re.search(rf"\b{re.escape(brand_clean)}\b", norm_name):
            return {
                "is_likely_chain": True,
                "confidence": 0.98,
                "matched_pattern": f"Franquia Reconhecida ('{brand.title()}')",
                "reason": (
                    f"Marca identificada no catálogo de redes e franquias nacionais ('{brand.title()}')."
                ),
            }

    # -------------------------------------------------------------------------
    # 4. Default: Appears to be an Independent Local Business
    # -------------------------------------------------------------------------
    return {
        "is_likely_chain": False,
        "confidence": 0.0,
        "matched_pattern": "",
        "reason": "Negócio aparentemente independente.",
    }


def fuzzy_dedupe_places(
    places: list[dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> tuple[list[dict[str, Any]], int]:
    """
    Perform fuzzy deduplication on a list of place dictionaries while preserving
    original encounter order.

    Cascading priority:
    1. Exact Match on 'id' (Google Place ID or Scraper cid).
    2. Exact Match on 'googleMapsUri' or 'link'.
    3. Fuzzy match comparing normalized business names and normalized Brazilian addresses:
       - Uses calculate_text_similarity (difflib.SequenceMatcher with token sorting).
       - Matches if addresses are identical and names are fuzzy-similar (>= 0.80).
       - Matches if names are identical and addresses are fuzzy-similar (>= 0.80).
       - Matches if both name similarity and address similarity meet the threshold.

    Args:
        places: List of place dictionaries.
        similarity_threshold: Float threshold for fuzzy similarity (default: 0.85).

    Returns:
        tuple[list[dict], int]: (deduped_places, removed_count)
    """
    if not places:
        return [], 0

    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_uris: set[str] = set()

    # Pre-extract normalized representations to make comparison efficient
    indexed_places: list[dict[str, Any]] = []

    for place in places:
        if not isinstance(place, dict):
            continue

        p_id = str(place.get("id") or "").strip()
        p_uri = str(place.get("googleMapsUri") or place.get("link") or place.get("url") or "").strip()

        # Extract name
        d_name = place.get("displayName")
        if isinstance(d_name, dict):
            raw_title = d_name.get("text", "")
        elif isinstance(d_name, str):
            raw_title = d_name
        else:
            raw_title = place.get("title") or place.get("name") or ""

        # Extract address
        raw_addr = (
            place.get("formattedAddress")
            or place.get("address")
            or place.get("formatted_address")
            or ""
        )

        norm_name = normalize_business_name(raw_title)
        norm_addr = normalize_brazilian_address(raw_addr)

        # 1. Exact ID check
        if p_id and p_id in seen_ids:
            continue

        # 2. Exact URI check
        if p_uri and p_uri in seen_uris:
            continue

        # 3. Fuzzy match against existing accepted places
        is_duplicate = False
        for accepted in indexed_places:
            acc_name = accepted["norm_name"]
            acc_addr = accepted["norm_addr"]

            # If both names contain digits and they differ (e.g. "Place 1" vs "Place 2"), distinct entities
            n_digits1 = re.findall(r"\b\d+\b", norm_name)
            n_digits2 = re.findall(r"\b\d+\b", acc_name)
            if n_digits1 and n_digits2 and n_digits1 != n_digits2:
                continue

            # If both addresses contain door numbers and they differ (e.g. 100 vs 200), distinct locations
            m_num1 = re.search(r",\s*(\d+[a-z]?)", norm_addr)
            m_num2 = re.search(r",\s*(\d+[a-z]?)", acc_addr)
            if m_num1 and m_num2 and m_num1.group(1) != m_num2.group(1):
                continue

            if norm_addr and acc_addr:
                # Both have addresses
                addr_sim = calculate_text_similarity(norm_addr, acc_addr)
                name_sim = calculate_text_similarity(norm_name, acc_name)

                # Case A: Same normalized address, high name similarity (handles word reorder/typos)
                if norm_addr == acc_addr and name_sim >= 0.75:
                    is_duplicate = True
                    break

                # Case B: Identical normalized name, high address similarity (handles street variations)
                if norm_name == acc_name and addr_sim >= 0.75:
                    is_duplicate = True
                    break

                # Case C: Both meet the similarity threshold
                if addr_sim >= similarity_threshold and name_sim >= similarity_threshold:
                    is_duplicate = True
                    break

                # Case D: Weighted combination exceeds threshold
                combined = (name_sim * 0.55) + (addr_sim * 0.45)
                if combined >= similarity_threshold and name_sim >= 0.70 and addr_sim >= 0.70:
                    is_duplicate = True
                    break

            else:
                # At least one has no address; rely strictly on high name similarity
                name_sim = calculate_text_similarity(norm_name, acc_name)
                if name_sim >= 0.95:
                    is_duplicate = True
                    break

        if is_duplicate:
            continue

        # Accept place
        if p_id:
            seen_ids.add(p_id)
        if p_uri:
            seen_uris.add(p_uri)

        indexed_places.append({
            "norm_name": norm_name,
            "norm_addr": norm_addr,
            "place": place,
        })
        deduped.append(place)

    removed_count = len(places) - len(deduped)
    return deduped, removed_count
