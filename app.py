import streamlit as st
import requests
import os
import time
import io
import csv
import re
import concurrent.futures
import textwrap
from dotenv import load_dotenv

from enrichment import (
    classify_web_presence,
    parse_brazilian_phone,
    generate_whatsapp_url,
    check_website_health,
    calculate_lead_score,
    enrich_leads_parallel,
    DEFAULT_WHATSAPP_TEMPLATE,
)
from history import (
    load_history,
    save_history,
    mark_leads_as_seen,
    is_lead_seen,
    clear_history,
)
from scraper_connector import dedupe_places
from smart_filters import detect_chain_or_franchise, fuzzy_dedupe_places

# Load environment variables (like API keys) from a .env file if it exists
load_dotenv()

# Configure the Streamlit page
st.set_page_config(page_title="Business Seeker", layout="wide")

# Place types that are NEVER valid business leads
BLACKLISTED_TYPES = [
    'atm', 'transit_station', 'park', 'parking', 'bus_station', 
    'subway_station', 'light_rail_station', 'train_station', 'airport',
    'taxi_stand', 'tourist_attraction', 'museum', 'cemetery', 'church',
    'hindu_temple', 'mosque', 'synagogue', 'local_government_office',
    'city_hall', 'courthouse', 'embassy', 'police', 'fire_station'
]

@st.cache_data(show_spinner=False, ttl=86400)
def lookup_cep(cep_raw: str):
    """Fetch address details from ViaCEP API with caching."""
    clean = re.sub(r"\D", "", cep_raw or "")
    if len(clean) != 8:
        return None, "O CEP deve conter 8 dígitos (ex: 01310-100)."
    try:
        resp = requests.get(f"https://viacep.com.br/ws/{clean}/json/", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("erro") in [True, "true"]:
                return None, "CEP não encontrado."
            return data, None
        return None, f"ViaCEP retornou status {resp.status_code}."
    except Exception as e:
        return None, f"Erro de conexão: {e}"


def get_diagnosis_badge(lead: dict) -> str:
    """Return modern, soft-toned HTML badge pill indicating lead diagnosis."""
    site_health = lead.get("site_health") or {}
    h_status = site_health.get("status", "")
    if h_status == "⚠️ Site Fora do Ar":
        return '<span class="pill-badge pill-danger">⚠️ Site Fora do Ar</span>'
    if h_status == "🔓 Sem HTTPS (Inseguro)":
        return '<span class="pill-badge pill-warning">🔓 Sem HTTPS</span>'
    if site_health.get("is_parked") or any(k in h_status for k in ("Estacionado", "Construção", "Padrão", "Branco", "Instalação")):
        clean_name = h_status.replace("⚠️ ", "").strip()
        return f'<span class="pill-badge pill-danger">⚠️ {clean_name}</span>'
    if site_health.get("is_redesign_candidate") or "Não Responsivo" in h_status:
        return '<span class="pill-badge pill-warning">📱 Não Responsivo</span>'

    web_pres = lead.get("web_presence") or {}
    kind = web_pres.get("kind", "NONE")
    url = (lead.get("Site / Rede Social") or lead.get("websiteUri") or "").lower()

    if kind == "NONE":
        return '<span class="pill-badge pill-neutral">🚫 Sem Site</span>'
    if kind == "SOCIAL":
        if "instagram.com" in url:
            return '<span class="pill-badge pill-pink">📸 Apenas Instagram</span>'
        return '<span class="pill-badge pill-blue">📱 Rede Social</span>'
    if kind == "LINKTREE_FREE":
        return '<span class="pill-badge pill-emerald">🔗 Linktree</span>'
    if kind == "WHATSAPP":
        return '<span class="pill-badge pill-teal">💬 Link WhatsApp</span>'
    if kind == "DIRECTORY":
        return '<span class="pill-badge pill-purple">📂 Guia Comercial</span>'
    return f'<span class="pill-badge pill-neutral">{web_pres.get("label", "N/A")}</span>'


def get_diagnosis_text(lead: dict) -> str:
    """Return plain-text diagnosis string for CSV export."""
    site_health = lead.get("site_health") or {}
    h_status = site_health.get("status", "")
    if h_status == "⚠️ Site Fora do Ar":
        return "⚠️ Site Fora do Ar"
    if h_status == "🔓 Sem HTTPS (Inseguro)":
        return "🔓 Sem HTTPS"
    if site_health.get("is_parked") or any(k in h_status for k in ("Estacionado", "Construção", "Padrão", "Branco", "Instalação")):
        return h_status.replace("⚠️ ", "").strip()
    if site_health.get("is_redesign_candidate") or "Não Responsivo" in h_status:
        return "Site Não Responsivo (Redesign)"

    web_pres = lead.get("web_presence") or {}
    kind = web_pres.get("kind", "NONE")
    url = (lead.get("Site / Rede Social") or lead.get("websiteUri") or "").lower()

    if kind == "NONE":
        return "Sem Site"
    if kind == "SOCIAL":
        if "instagram.com" in url:
            return "Apenas Instagram"
        return "Rede Social"
    if kind == "LINKTREE_FREE":
        return "Linktree"
    if kind == "WHATSAPP":
        return "Link WhatsApp"
    if kind == "DIRECTORY":
        return "Guia Comercial"
    return web_pres.get("label", "Outro")


def generate_lead_row_html(lead: dict) -> str:
    """Generate a single formatted, clean <tr> for the redesigned data table."""
    score = lead.get("Score", 0)
    temp = lead.get("Temperatura", "❄️ Frio")
    if "Quente" in temp:
        score_html = f'<div class="score-pill score-hot"><span class="score-icon">🔥</span> <b>{score} pts</b> · Quente</div>'
    elif "Médio" in temp:
        score_html = f'<div class="score-pill score-medium"><span class="score-icon">⚡</span> <b>{score} pts</b> · Médio</div>'
    else:
        score_html = f'<div class="score-pill score-cold"><span class="score-icon">❄️</span> <b>{score} pts</b> · Frio</div>'

    disp = lead.get("displayName")
    name = disp.get("text", "") if isinstance(disp, dict) else (lead.get("displayName") or lead.get("Nome da Empresa") or lead.get("title") or "Empresa")
    is_seen = lead.get("is_seen", False)
    if is_seen:
        hist_badge = '<span class="hist-badge hist-seen">✅ Já visto</span>'
    else:
        hist_badge = '<span class="hist-badge hist-new">🆕 Novo</span>'

    reasons = lead.get("Motivos Prioridade", "")
    reasons_html = f'<div class="lead-reasons">{reasons}</div>' if reasons else ''
    empresa_cell = f'<div class="lead-company-wrap">{hist_badge} <span class="lead-name">{name}</span></div>{reasons_html}'

    diag_badge = get_diagnosis_badge(lead)

    p_info = lead.get("phone_info") or {}
    p_formatted = p_info.get("formatted") or lead.get("Telefone") or "N/A"
    is_mobile = p_info.get("is_mobile", False)
    e164 = p_info.get("e164") or ""

    phone_parts = []
    if p_formatted and p_formatted != "N/A":
        if is_mobile:
            if e164:
                phone_parts.append(f'<div class="contact-item"><span class="contact-phone">📱 <b>{p_formatted}</b></span> <a href="https://wa.me/{e164}" target="_blank" class="contact-wa-link" title="Abrir conversa no WhatsApp">💬 WhatsApp</a></div>')
            else:
                phone_parts.append(f'<div class="contact-item"><span class="contact-phone">📱 <b>{p_formatted}</b></span></div>')
        elif p_info.get("type") == "☎️ Fixo":
            phone_parts.append(f'<div class="contact-item"><span class="contact-phone">☎️ {p_formatted}</span></div>')
        else:
            phone_parts.append(f'<div class="contact-item"><span class="contact-phone">{p_formatted}</span></div>')

    contacts = lead.get("extracted_contacts") or {}
    ig = lead.get("Instagram Extraído")
    email = lead.get("Email Extraído")
    if ig and ig != "N/A":
        ig_obj = contacts.get("instagram")
        ig_url = ig_obj.get("url") if isinstance(ig_obj, dict) else f"https://instagram.com/{ig.replace('@', '')}"
        phone_parts.append(f'<div class="contact-item"><a href="{ig_url}" target="_blank" class="contact-ig-link">📸 {ig}</a></div>')
    if email and email != "N/A":
        phone_parts.append(f'<div class="contact-item"><a href="mailto:{email}" class="contact-email-link">✉️ {email}</a></div>')

    contact_cell = "".join(phone_parts) if phone_parts else '<span class="text-muted">-</span>'

    rating_val = lead.get("Avaliação")
    if not rating_val:
        r_num = lead.get('rating', 'N/A')
        r_count = lead.get('userRatingCount', 0)
        rating_html = f'<div class="rating-box"><span class="rating-stars">⭐ {r_num}</span> <span class="rating-count">({r_count})</span></div>'
    else:
        rating_html = f'<div class="rating-box">{rating_val}</div>'

    addr = lead.get("Endereço") or lead.get("formattedAddress") or "N/A"
    maps_uri = lead.get("Google Maps") or lead.get("googleMapsUri") or ""
    if maps_uri and str(maps_uri).startswith("http"):
        maps_link = f'<a href="{maps_uri}" target="_blank" class="maps-btn">Maps ↗</a>'
    else:
        maps_link = ""

    location_cell = f'<div class="location-text">{addr}</div>{maps_link}'

    return f"<tr><td>{score_html}</td><td>{empresa_cell}</td><td>{diag_badge}</td><td>{contact_cell}</td><td style='white-space: nowrap;'>{rating_html}</td><td>{location_cell}</td></tr>"


# --- Configuration & Local History ---
api_key = os.getenv("GOOGLE_PLACES_API_KEY")

# --- Main Header ---
st.title("🔍 Business Seeker")
st.markdown("Descubra empresas locais no Google Maps que **não possuem site**, estão com **site fora do ar / sem SSL** ou usam apenas redes sociais.")

with st.expander("📚 Histórico de Leads Salvos", expanded=False):
    current_history = load_history()
    col_hist1, col_hist2 = st.columns([3, 1])
    with col_hist1:
        st.metric("Total no Histórico", f"{len(current_history)} leads")
        st.caption("Empresas marcadas como já vistas são lembradas para evitar prospecção duplicada.")
    with col_hist2:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️ Limpar Histórico", use_container_width=True):
            clear_history()
            st.success("Histórico limpo com sucesso!")
            time.sleep(0.4)
            st.rerun()

# --- Guia de Formatos de Busca ---
with st.expander("💡 Guia de Formatos de Busca: Como usar CEP, Endereço, Bairro e Sintaxe", expanded=False):
    st.markdown("""
    Esta tabela explica **quais formatos são permitidos**, **como o Google Maps interpreta cada entrada** e as melhores práticas de busca:
    """)
    st.markdown("""
| Tipo de Entrada | Exemplo de Sintaxe | O CEP/Endereço é Válido? | Como o Google Maps se Comporta & Dica de Uso |
| :--- | :--- | :---: | :--- |
| **Nicho + CEP Direto** | `Oficina Mecânica 04538-133` | ✅ **Permitido** | O Google Maps reconhece o CEP brasileiro como âncora geográfica e busca o nicho no quarteirão ou raio imediato daquele CEP. Funciona com ou sem hífen (`04538-133` ou `04538133`). |
| **Nicho + Bairro + Cidade** | `Vidraçaria em Moema, São Paulo` | ✅ **Recomendado** | **Melhor volume e conversão.** Bairros cobrem uma área comercial densa (500m–2km) sem ficar restrito a uma única rua, retornando mais empresas sem site. |
| **Múltiplos Bairros em Lote** | `Oficina em Moema, Oficina no Itaim Bibi` | ✅ **Recomendado** | **Busca em lote.** Processa cada bairro e deduplica empresas automaticamente evitando registros repetidos. |
| **Nicho + Endereço / Rua** | `Dentista na Av. Paulista, 1000` | ✅ **Permitido** | Ótimo para avenidas e corredores comerciais densos. Busca consultórios e comércios instalados naquele logradouro ou na mesma via. |
| **Nicho + Prefixo CEP (5 dígitos)** | `Marcenaria CEP 04500` | ✅ **Permitido** | Busca na sub-região postal inteira (engloba vários quarteirões vizinhos) em vez de uma única rua de 8 dígitos. |
| **Nicho + "Perto de" / "Próximo a"**| `Pizzaria perto de 01310-100` | ✅ **Permitido** | O motor de busca semântica do Google Maps localiza comércios ao redor do ponto de referência, cruzamento ou CEP informado. |
| **Apenas o CEP (Sem Nicho)** | `01310-100` | ⚠️ **Evitar** | O Google retornará qualquer comércio genérico daquela rua (bancos, farmácias, padarias), sem focar no nicho de clientes que você quer prospectar. |
| **Apenas Cidade Ampla** | `Advogados em São Paulo` | ❌ **Não Recomendado** | Esgota o limite de 60 resultados da API trazendo apenas grandes empresas do centro que já têm site próprio e agência contratada. |
    """)
    st.markdown("""
    #### 📌 Regras Práticas de Sintaxe:
    1. **Busca em Lote:** Na Busca Livre, separe múltiplos bairros ou nichos por vírgula (ex: `Oficina em Moema, Oficina no Itaim Bibi`).
    2. **CEP com ou sem hífen:** Ambos funcionam perfeitamente (`01310-100` ou `01310100`).
    3. **Modo Automático:** Se não quiser digitar manualmente, use a aba **"🎯 Busca por CEP (Brasil)"** abaixo para detecção via ViaCEP.
    """)

# --- Search Interface ---
st.subheader("Busca")

search_mode = st.radio(
    "Modo de Busca",
    options=["🎯 Busca por CEP (Brasil)", "🔍 Busca Livre"],
    horizontal=True,
    help="Use a busca por CEP para detecção automática de bairro via ViaCEP, ou busca livre para digitar qualquer termo."
)

query_input = ""
target_niche_clean = "Serviços Locais"

if search_mode == "🎯 Busca por CEP (Brasil)":
    cep_input = st.text_input(
        "CEP (Código Postal)",
        placeholder="01310-100",
        help="Digite um CEP com 8 dígitos (ex: 01310-100 ou 01310100)"
    )
    st.caption("Exemplos: `01310-100` (Bela Vista, SP) • `04538-133` (Itaim Bibi, SP) • `30140-071` (Savassi, BH)")

    if cep_input.strip():
        cep_data, err_msg = lookup_cep(cep_input)
        if cep_data:
            bairro = cep_data.get("bairro", "").strip()
            cidade = cep_data.get("localidade", "").strip()
            uf = cep_data.get("uf", "").strip()
            logradouro = cep_data.get("logradouro", "").strip()

            address_badge = f"📍 **{bairro or 'Região Central'}**, {cidade} - {uf}"
            if logradouro:
                address_badge += f" *({logradouro})*"
            st.success(address_badge)

            suggested_query = f"{bairro}, {cidade} - {uf}" if bairro else f"{cidade} - {uf}"
            query_input = st.text_input("Termo de Busca Gerado (Editável)", value=suggested_query)
        else:
            st.warning(f"⚠️ {err_msg}")
else:
    query_input = st.text_input(
        "Termo de Busca (ou múltiplos termos separados por vírgula)",
        placeholder="ex: Oficina em Moema, Oficina no Itaim Bibi, Oficina nos Jardins",
        help="Permite buscar termos únicos ou múltiplos bairros/nichos separados por vírgula para processamento em lote."
    )

# --- Filtros e Opções de Busca ---
col1, col2, col3 = st.columns(3)
with col1:
    negative_keywords = st.text_input(
        "Palavras-chave a Excluir",
        placeholder="Drogasil, Raia, McDonald's, O Boticário, Subway, Casas Bahia",
        help="Nomes de grandes franquias ou termos separados por vírgula para ignorar."
    )
with col2:
    max_results = st.selectbox(
        "Limite de Resultados por Busca",
        options=[20, 40, 60, 100, 150, 200, 300, 500],
        index=2,
        help="Limite máximo de empresas a buscar. O Google Places API retorna até ~60 resultados por termo único; para limites maiores (100+), use múltiplos bairros na Busca Livre."
    )
with col3:
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True)
    require_phone = st.checkbox(
        "Exigir Telefone",
        value=True,
        help="Ignora leads que não possuem telefone cadastrado no Google Maps."
    )

# Advanced Lead Intelligence Toggles
st.markdown("##### ⚙️ Filtros Avançados e Inteligência")
col_opt1, col_opt2, col_opt3, col_opt4 = st.columns(4)
with col_opt1:
    check_site_health_toggle = st.checkbox(
        "⚠️ Checar Saúde & Responsividade",
        value=True,
        help="Testa sites com domínio próprio. Identifica sites fora do ar, sem HTTPS, domínios estacionados/em construção e sites não adaptados para celular (redesign)!"
    )
with col_opt2:
    enrich_contacts_toggle = st.checkbox(
        "🔍 Enriquecer Links Sociais da Bio",
        value=True,
        help="Acessa as páginas de redes sociais/linktree para extrair WhatsApp comercial, Instagram e emails de contato."
    )
with col_opt3:
    filter_chains_toggle = st.checkbox(
        "🏢 Ocultar Redes & Franquias",
        value=True,
        help="Identifica e oculta automaticamente filiais de grandes redes (Subway, Óticas Carol, Drogasil, lojas de shopping) para priorizar comércios locais independentes."
    )
with col_opt4:
    hide_seen_leads_toggle = st.checkbox(
        "🆕 Ocultar Já Vistos no Histórico",
        value=False,
        help="Oculta automaticamente empresas que já constam no arquivo leads_vistos.json."
    )

# Session state initialization for persistent search results
if "search_leads" not in st.session_state:
    st.session_state["search_leads"] = None
if "raw_count" not in st.session_state:
    st.session_state["raw_count"] = 0
if "query_used" not in st.session_state:
    st.session_state["query_used"] = ""


# --- Action: Search Leads ---
if st.button("Buscar Leads", type="primary"):
    # Parse individual queries (supports batch comma-separated)
    if search_mode == "🎯 Busca por CEP (Brasil)":
        queries = [query_input.strip()] if query_input.strip() else []
    else:
        queries = [q.strip() for q in query_input.split(",") if q.strip()]
        if queries:
            target_niche_clean = queries[0].split(" em ")[0].split(" no ")[0].split(" na ")[0].strip()

    if not queries:
        st.error("Por favor, informe ao menos um termo de busca ou um CEP válido.")
    elif not api_key:
        st.error("Chave de API não encontrada. Adicione GOOGLE_PLACES_API_KEY ao seu arquivo .env para buscar pela Google Places API.")
    else:
        try:
            all_raw_places = []
            
            # 1. Fetch places across all queries via Google Places API
            for q in queries:
                with st.spinner(f"Coletando empresas para '{q}' via Google Places API..."):
                    url = "https://places.googleapis.com/v1/places:searchText"
                    headers = {
                        "Content-Type": "application/json",
                        "X-Goog-Api-Key": api_key,
                        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.businessStatus,places.types,nextPageToken"
                    }
                    page_token = None
                    max_pages = (max_results + 19) // 20

                    for page in range(max_pages):
                        data = {
                            "textQuery": q,
                            "pageSize": 20
                        }
                        if page_token:
                            data["pageToken"] = page_token

                        response = requests.post(url, headers=headers, json=data)
                        if response.status_code != 200:
                            st.error(f"Erro na API para '{q}': {response.json().get('error', {}).get('message', 'Erro desconhecido')}")
                            break

                        resp_json = response.json()
                        page_results = resp_json.get("places", [])
                        all_raw_places.extend(page_results)

                        page_token = resp_json.get("nextPageToken")
                        if not page_token:
                            break
                        time.sleep(1.5)

            # 2. Cascading Deduplication across all pages and queries
            all_raw_places, _ = fuzzy_dedupe_places(all_raw_places)

            if not all_raw_places:
                st.info("Nenhuma empresa encontrada para os termos informados.")
                st.session_state["search_leads"] = []
                st.session_state["raw_count"] = 0
                st.session_state["query_used"] = ", ".join(queries)
            else:
                # 3. Skip Filter: Negative keywords, closed permanently, blacklisted types, require phone, and chain/franchise detection
                neg_words = [w.strip().lower() for w in negative_keywords.split(",")] if negative_keywords else []
                filtered_candidates = []

                all_raw_names = [
                    (p.get("displayName", {}).get("text") if isinstance(p.get("displayName"), dict) else (p.get("displayName") or p.get("title") or p.get("Nome da Empresa") or ""))
                    for p in all_raw_places
                ]

                for place in all_raw_places:
                    disp = place.get("displayName")
                    name = disp.get("text", "") if isinstance(disp, dict) else (place.get("displayName") or place.get("title") or place.get("Nome da Empresa") or "")
                    status = place.get("businessStatus", "UNKNOWN")
                    phone = place.get("nationalPhoneNumber") or place.get("phone") or place.get("Telefone")
                    types = place.get("types", [])

                    if neg_words and any(nw in name.lower() for nw in neg_words if nw):
                        continue
                    if status == "CLOSED_PERMANENTLY":
                        continue
                    if any(t in BLACKLISTED_TYPES for t in types):
                        continue
                    if require_phone and not phone:
                        continue
                    if filter_chains_toggle:
                        chain_info = detect_chain_or_franchise(name, types=types, all_batch_names=all_raw_names)
                        if chain_info.get("is_likely_chain"):
                            continue

                    filtered_candidates.append(place)

                # 4. Lead Qualification & Site Health Check
                qualified_candidates = []
                custom_domain_candidates = []

                for place in filtered_candidates:
                    website_uri = place.get("websiteUri") or place.get("web_site") or place.get("website") or ""
                    web_pres = classify_web_presence(website_uri)
                    place["web_presence"] = web_pres

                    if web_pres["kind"] != "CUSTOM_DOMAIN":
                        # No website, WhatsApp, social, linktree, directory -> Immediately qualified!
                        qualified_candidates.append(place)
                    elif check_site_health_toggle:
                        # Dedicated custom domain -> candidate for health check
                        custom_domain_candidates.append(place)

                # Parallel Website Health Check for Custom Domains
                if custom_domain_candidates and check_site_health_toggle:
                    with st.spinner(f"Verificando saúde de {len(custom_domain_candidates)} sites com domínio próprio em paralelo..."):
                        def _check_p(p):
                            u = p.get("websiteUri") or p.get("web_site") or p.get("website") or ""
                            h = check_website_health(u)
                            return p, h

                        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                            health_results = list(executor.map(_check_p, custom_domain_candidates))

                        for p, health in health_results:
                            p["site_health"] = health
                            # Offline, insecure, parked/under construction, or non-responsive redesign sites qualify!
                            h_status = health.get("status", "")
                            if (
                                health.get("is_parked")
                                or health.get("is_redesign_candidate")
                                or h_status.startswith("⚠️ ")
                                or h_status in ("⚠️ Site Fora do Ar", "🔓 Sem HTTPS (Inseguro)")
                                or "Não Responsivo" in h_status
                            ):
                                qualified_candidates.append(p)

                # 5. Parallel Lead Enrichment & Scoring
                with st.spinner(f"Enriquecendo dados e calculando score de {len(qualified_candidates)} leads qualificados..."):
                    enriched_leads = enrich_leads_parallel(
                        qualified_candidates,
                        max_workers=10,
                        niche=target_niche_clean,
                        custom_pitch_template=None,
                        enrich_contacts=enrich_contacts_toggle,
                    )

                # Sort qualified leads by commercial score descending
                enriched_leads.sort(key=lambda x: x.get("Score", 0), reverse=True)

                st.session_state["search_leads"] = enriched_leads
                st.session_state["raw_count"] = len(all_raw_places)
                st.session_state["query_used"] = ", ".join(queries)

        except Exception as exc:
            st.error(f"Ocorreu um erro inesperado durante a busca: {exc}")


# --- Results Section ---
if st.session_state["search_leads"] is not None:
    enriched_leads = st.session_state["search_leads"]
    raw_count = st.session_state["raw_count"]
    query_used = st.session_state["query_used"]

    # 1. Update seen history status for each lead
    history_dict = load_history()
    for lead in enriched_leads:
        lead["is_seen"] = is_lead_seen(lead, history=history_dict)
        lead["Status Histórico"] = "Já visto" if lead["is_seen"] else "Novo"

    # 2. Filter out seen leads if requested
    if hide_seen_leads_toggle:
        displayed_leads = [l for l in enriched_leads if not l["is_seen"]]
    else:
        displayed_leads = enriched_leads

    # Sort displayed leads by score descending
    displayed_leads.sort(key=lambda x: x.get("Score", 0), reverse=True)

    st.divider()
    st.subheader("Resultados dos Leads")

    # Metrics
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Empresas Mapeadas", raw_count)
    col_m2.metric("Leads Qualificados", len(enriched_leads))
    conversion = round((len(enriched_leads) / raw_count * 100), 1) if raw_count else 0
    col_m3.metric("Taxa de Conversão", f"{conversion}%")
    hot_count = sum(1 for l in displayed_leads if l.get("Temperatura") == "🔥 Quente")
    col_m4.metric("Leads Quentes 🔥", hot_count)

    if hide_seen_leads_toggle:
        hidden_count = len(enriched_leads) - len(displayed_leads)
        if hidden_count > 0:
            st.info(f"ℹ️ {hidden_count} empresas já vistas no histórico foram ocultadas nesta visualização.")

    if not displayed_leads:
        if enriched_leads:
            st.warning("Todas as empresas encontradas já foram vistas anteriormente! Desmarque 'Ocultar Empresas Já Vistas no Histórico' para visualizá-las.")
        else:
            st.info(f"Foram analisadas {raw_count} empresas, mas todas já possuem site seguro e operacional!")
    else:
        # History Action Bar
        col_btn1, col_btn2 = st.columns([1, 2])
        with col_btn1:
            if st.button("💾 Marcar Leads desta Busca como Já Vistos", type="secondary", help="Salva os leads atualmente exibidos no histórico para marcá-los como já vistos em buscas futuras."):
                marked_count = mark_leads_as_seen(displayed_leads)
                st.success(f"{marked_count} novos leads gravados no histórico!")
                time.sleep(0.4)
                st.rerun()

        # Render Modern High-Clarity HTML Table
        table_rows_html = "".join(generate_lead_row_html(lead) for lead in displayed_leads)
        html_table = textwrap.dedent(f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
            
            .table-container {{
                width: 100%;
                overflow-x: auto;
                border-radius: 12px;
                box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
                border: 1px solid #E2E8F0;
                margin: 18px 0;
                background: #FFFFFF;
            }}
            
            .data-table {{
                border-collapse: separate;
                border-spacing: 0;
                width: 100%;
                font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
                font-size: 13px;
            }}
            
            .data-table thead tr {{
                background-color: #0F172A;
                color: #F8FAFC;
            }}
            
            .data-table th {{
                padding: 13px 15px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                font-size: 11px;
                border-bottom: 2px solid #1E293B;
                white-space: nowrap;
                text-align: left;
            }}
            
            .data-table td {{
                padding: 13px 15px;
                border-bottom: 1px solid #F1F5F9;
                color: #1E293B;
                vertical-align: middle;
                line-height: 1.5;
            }}
            
            .data-table tbody tr {{
                transition: background-color 0.15s ease;
            }}
            
            .data-table tbody tr:nth-of-type(even) {{
                background-color: #F8FAFC;
            }}
            
            .data-table tbody tr:hover {{
                background-color: #F0F7FF;
            }}
            
            .data-table tbody tr:last-of-type td {{
                border-bottom: none;
            }}

            /* Score Badges */
            .score-pill {{
                display: inline-flex;
                align-items: center;
                gap: 5px;
                padding: 4px 10px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 600;
                white-space: nowrap;
            }}
            .score-hot {{
                background-color: #FEF2F2;
                color: #DC2626;
                border: 1px solid #FECACA;
            }}
            .score-medium {{
                background-color: #FFFBEB;
                color: #D97706;
                border: 1px solid #FDE68A;
            }}
            .score-cold {{
                background-color: #EFF6FF;
                color: #2563EB;
                border: 1px solid #BFDBFE;
            }}

            /* History Badges */
            .hist-badge {{
                display: inline-block;
                padding: 2px 7px;
                border-radius: 9999px;
                font-size: 10px;
                font-weight: 700;
                margin-right: 6px;
                vertical-align: middle;
            }}
            .hist-new {{
                background-color: #ECFDF5;
                color: #059669;
                border: 1px solid #A7F3D0;
            }}
            .hist-seen {{
                background-color: #F1F5F9;
                color: #64748B;
                border: 1px solid #CBD5E1;
            }}

            /* Company Name & Reasons */
            .lead-company-wrap {{
                display: flex;
                align-items: center;
                flex-wrap: wrap;
                gap: 6px;
            }}
            .lead-name {{
                font-size: 14px;
                font-weight: 700;
                color: #0F172A;
            }}
            .lead-reasons {{
                font-size: 11px;
                color: #64748B;
                margin-top: 4px;
                line-height: 1.4;
            }}

            /* Diagnosis Pill Badges */
            .pill-badge {{
                display: inline-flex;
                align-items: center;
                gap: 5px;
                padding: 4px 10px;
                border-radius: 9999px;
                font-size: 11px;
                font-weight: 600;
                white-space: nowrap;
            }}
            .pill-danger {{
                background-color: #FEF2F2;
                color: #DC2626;
                border: 1px solid #FECACA;
            }}
            .pill-warning {{
                background-color: #FFFBEB;
                color: #D97706;
                border: 1px solid #FDE68A;
            }}
            .pill-neutral {{
                background-color: #F1F5F9;
                color: #475569;
                border: 1px solid #CBD5E1;
            }}
            .pill-pink {{
                background-color: #FDF2F8;
                color: #DB2777;
                border: 1px solid #FBCFE8;
            }}
            .pill-blue {{
                background-color: #EFF6FF;
                color: #2563EB;
                border: 1px solid #BFDBFE;
            }}
            .pill-emerald {{
                background-color: #ECFDF5;
                color: #059669;
                border: 1px solid #A7F3D0;
            }}
            .pill-teal {{
                background-color: #F0FDFA;
                color: #0D9488;
                border: 1px solid #99F6E4;
            }}
            .pill-purple {{
                background-color: #F5F3FF;
                color: #7C3AED;
                border: 1px solid #DDD6FE;
            }}

            /* Contacts */
            .contact-item {{
                margin: 2px 0;
                font-size: 12px;
            }}
            .contact-phone {{
                font-weight: 600;
                color: #1E293B;
            }}
            .contact-wa-link {{
                display: inline-block;
                margin-left: 4px;
                color: #059669 !important;
                font-weight: 600;
                text-decoration: none !important;
                background: #ECFDF5;
                padding: 1px 6px;
                border-radius: 4px;
                border: 1px solid #A7F3D0;
                font-size: 10px;
            }}
            .contact-wa-link:hover {{
                background: #D1FAE5;
            }}
            .contact-ig-link {{
                color: #DB2777 !important;
                text-decoration: none !important;
                font-weight: 500;
            }}
            .contact-ig-link:hover {{
                text-decoration: underline !important;
            }}
            .contact-email-link {{
                color: #2563EB !important;
                text-decoration: none !important;
                font-size: 11px;
            }}
            .contact-email-link:hover {{
                text-decoration: underline !important;
            }}

            /* Rating */
            .rating-box {{
                font-size: 12px;
                white-space: nowrap;
            }}
            .rating-stars {{
                font-weight: 700;
                color: #D97706;
            }}
            .rating-count {{
                color: #64748B;
                font-size: 11px;
            }}

            /* Location & Maps */
            .location-text {{
                font-size: 12px;
                color: #475569;
                max-width: 220px;
                line-height: 1.3;
            }}
            .maps-btn {{
                display: inline-block;
                margin-top: 4px;
                font-size: 11px;
                font-weight: 600;
                color: #2563EB !important;
                text-decoration: none !important;
                padding: 2px 6px;
                border-radius: 4px;
                background: #EFF6FF;
                border: 1px solid #BFDBFE;
            }}
            .maps-btn:hover {{
                background: #DBEAFE;
            }}
            .text-muted {{
                color: #94A3B8;
                font-size: 11px;
            }}

            /* Dark Mode Theme */
            @media (prefers-color-scheme: dark) {{
                .table-container {{
                    background: #111827;
                    border-color: #374151;
                    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
                }}
                .data-table thead tr {{
                    background-color: #030712;
                }}
                .data-table th {{
                    border-bottom-color: #1F2937;
                    color: #E2E8F0;
                }}
                .data-table td {{
                    border-bottom-color: #1F2937;
                    color: #E2E8F0;
                }}
                .data-table tbody tr:nth-of-type(even) {{
                    background-color: rgba(255, 255, 255, 0.02);
                }}
                .data-table tbody tr:hover {{
                    background-color: rgba(59, 130, 246, 0.08);
                }}
                .lead-name {{
                    color: #F8FAFC;
                }}
                .lead-reasons {{
                    color: #94A3B8;
                }}
                .contact-phone {{
                    color: #F8FAFC;
                }}
                .location-text {{
                    color: #CBD5E1;
                }}
                .score-hot {{
                    background-color: rgba(220, 38, 38, 0.15);
                    color: #F87171;
                    border-color: rgba(220, 38, 38, 0.3);
                }}
                .score-medium {{
                    background-color: rgba(217, 119, 6, 0.15);
                    color: #FBBF24;
                    border-color: rgba(217, 119, 6, 0.3);
                }}
                .score-cold {{
                    background-color: rgba(37, 99, 235, 0.15);
                    color: #60A5FA;
                    border-color: rgba(37, 99, 235, 0.3);
                }}
                .pill-danger {{
                    background-color: rgba(220, 38, 38, 0.15);
                    color: #F87171;
                    border-color: rgba(220, 38, 38, 0.3);
                }}
                .pill-warning {{
                    background-color: rgba(217, 119, 6, 0.15);
                    color: #FBBF24;
                    border-color: rgba(217, 119, 6, 0.3);
                }}
                .pill-neutral {{
                    background-color: rgba(100, 116, 139, 0.15);
                    color: #CBD5E1;
                    border-color: rgba(100, 116, 139, 0.3);
                }}
                .pill-pink {{
                    background-color: rgba(219, 39, 119, 0.15);
                    color: #F472B6;
                    border-color: rgba(219, 39, 119, 0.3);
                }}
                .pill-blue {{
                    background-color: rgba(37, 99, 235, 0.15);
                    color: #60A5FA;
                    border-color: rgba(37, 99, 235, 0.3);
                }}
                .pill-emerald {{
                    background-color: rgba(5, 150, 105, 0.15);
                    color: #34D399;
                    border-color: rgba(5, 150, 105, 0.3);
                }}
                .pill-teal {{
                    background-color: rgba(13, 148, 136, 0.15);
                    color: #2DD4BF;
                    border-color: rgba(13, 148, 136, 0.3);
                }}
                .pill-purple {{
                    background-color: rgba(124, 58, 237, 0.15);
                    color: #A78BFA;
                    border-color: rgba(124, 58, 237, 0.3);
                }}
                .hist-seen {{
                    background-color: rgba(100, 116, 139, 0.15);
                    color: #94A3B8;
                    border-color: rgba(100, 116, 139, 0.3);
                }}
                .maps-btn {{
                    background-color: rgba(37, 99, 235, 0.15);
                    color: #93C5FD !important;
                    border-color: rgba(37, 99, 235, 0.3);
                }}
                .maps-btn:hover {{
                    background-color: rgba(37, 99, 235, 0.25);
                }}
            }}
        </style>
        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Qualificação</th>
                        <th>Empresa & Oportunidade</th>
                        <th>Diagnóstico Web</th>
                        <th>Contatos</th>
                        <th>Avaliação</th>
                        <th>Localização & Maps</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </div>
        """).strip()
        st.html(html_table)

        # CSV Download Generation (Focused on Lead Qualification)
        csv_rows = []
        for lead in displayed_leads:
            disp = lead.get("displayName")
            name = disp.get("text", "") if isinstance(disp, dict) else (lead.get("displayName") or lead.get("Nome da Empresa") or lead.get("title") or "")
            p_info = lead.get("phone_info") or {}
            s_health = lead.get("site_health") or {}

            csv_rows.append({
                "Score": lead.get("Score", 0),
                "Temperatura": lead.get("Temperatura", "Frio"),
                "Empresa": name,
                "Status Histórico": "Já visto" if lead.get("is_seen") else "Novo",
                "Diagnóstico": get_diagnosis_text(lead),
                "Telefone": p_info.get("formatted") or lead.get("Telefone") or "",
                "Tipo Telefone": p_info.get("type") or "",
                "Email Extraído": lead.get("Email Extraído") or "",
                "Instagram Extraído": lead.get("Instagram Extraído") or "",
                "Site / Rede Social": lead.get("Site / Rede Social") or lead.get("websiteUri") or "Nenhum",
                "Saúde do Site": s_health.get("status") or "N/A",
                "Avaliação": lead.get("Avaliação") or (f"{lead.get('rating', 'N/A')}⭐ ({lead.get('userRatingCount', 0)})"),
                "Endereço": lead.get("Endereço") or lead.get("formattedAddress") or "",
                "Google Maps": lead.get("Google Maps") or lead.get("googleMapsUri") or "",
                "Motivos Prioridade": lead.get("Motivos Prioridade") or "",
                "ID do Lead": lead.get("id") or lead.get("place_id") or ""
            })

        csv_buffer = io.StringIO()
        if csv_rows:
            fieldnames = list(csv_rows[0].keys())
            writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        csv_data = csv_buffer.getvalue().encode('utf-8')
        safe_filename = re.sub(r'[^\w\-]', '_', query_used).strip('_')

        st.download_button(
            label="📥 Baixar Leads Qualificados em CSV",
            data=csv_data,
            file_name=f'leads_{safe_filename or "busca"}.csv',
            mime='text/csv',
        )
