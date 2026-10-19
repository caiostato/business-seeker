import streamlit as st
import requests
import os
import time
import io
import csv
import re
from dotenv import load_dotenv

# Load environment variables (like API keys) from a .env file if it exists
load_dotenv()

# Configure the Streamlit page
st.set_page_config(page_title="Business Seeker", layout="wide")

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

st.title("🔍 Business Seeker")
st.markdown("Descubra empresas locais no Google Maps que **não possuem site** ou usam apenas redes sociais.")

# --- 1. API Key Configuration ---
api_key = os.getenv("GOOGLE_PLACES_API_KEY")
if not api_key:
    st.error("Chave de API não encontrada. Adicione GOOGLE_PLACES_API_KEY ao seu arquivo .env.")
    st.stop()

# --- 2. Guia de Uso: Formatos Aceitos (CEP, Endereço e Bairro) ---
with st.expander("💡 Guia de Formatos de Busca: Como usar CEP, Endereço, Bairro e Sintaxe", expanded=False):
    st.markdown("""
    Esta tabela explica **quais formatos são permitidos**, **como o Google Maps interpreta cada entrada** e as melhores práticas de busca:
    """)
    
    st.markdown("""
| Tipo de Entrada | Exemplo de Sintaxe | O CEP/Endereço é Válido? | Como o Google Maps se Comporta & Dica de Uso |
| :--- | :--- | :---: | :--- |
| **Nicho + CEP Direto** | `Oficina Mecânica 04538-133` | ✅ **Permitido** | O Google Maps reconhece o CEP brasileiro como âncora geográfica e busca o nicho no quarteirão ou raio imediato daquele CEP. Funciona com ou sem hífen (`04538-133` ou `04538133`). |
| **Nicho + Bairro + Cidade** | `Vidraçaria em Moema, São Paulo` | ✅ **Recomendado** | **Melhor volume e conversão.** Bairros cobrem uma área comercial densa (500m–2km) sem ficar restrito a uma única rua, retornando mais empresas sem site. |
| **Nicho + Endereço / Rua** | `Dentista na Av. Paulista, 1000` | ✅ **Permitido** | Ótimo para avenidas e corredores comerciais densos. Busca consultórios e comércios instalados naquele logradouro ou na mesma via. |
| **Nicho + Prefixo CEP (5 dígitos)** | `Marcenaria CEP 04500` | ✅ **Permitido** | Busca na sub-região postal inteira (engloba vários quarteirões vizinhos) em vez de uma única rua de 8 dígitos. |
| **Nicho + "Perto de" / "Próximo a"**| `Pizzaria perto de 01310-100` | ✅ **Permitido** | O motor de busca semântica do Google Maps localiza comércios ao redor do ponto de referência, cruzamento ou CEP informado. |
| **Apenas o CEP (Sem Nicho)** | `01310-100` | ⚠️ **Evitar** | O Google retornará qualquer comércio genérico daquela rua (bancos, farmácias, padarias), sem focar no nicho de clientes que você quer prospectar. |
| **Apenas Cidade Ampla** | `Advogados em São Paulo` | ❌ **Não Recomendado** | Esgota o limite de 60 resultados da API trazendo apenas grandes empresas do centro que já têm site próprio e agência contratada. |
    """)

    st.markdown("""
    #### 📌 Regras Práticas de Sintaxe:
    1. **CEP com ou sem hífen:** Ambos funcionam perfeitamente (`01310-100` ou `01310100`).
    2. **Preposições e Conectores:** Você pode usar `em`, `na`, `perto de`, `no CEP` ou simplesmente espaço (ex: `Mecânica Moema SP` ou `Mecânica 04538-133`).
    3. **Modo Automático:** Se não quiser digitar manualmente, use a aba **"🎯 Busca por CEP (Brasil)"** abaixo. Ela consulta o ViaCEP em tempo real e monta a sintaxe do bairro ideal para você.
    """)

# --- 3. Search Interface ---
st.subheader("Busca")

search_mode = st.radio(
    "Modo de Busca",
    options=["🎯 Busca por CEP (Brasil)", "🔍 Busca Livre"],
    horizontal=True,
    help="Use a busca por CEP para detecção automática de bairro via ViaCEP, ou busca livre para digitar qualquer termo."
)

query = ""

if search_mode == "🎯 Busca por CEP (Brasil)":
    col_cep, col_niche = st.columns([1, 2])
    with col_cep:
        cep_input = st.text_input(
            "CEP (Código Postal)",
            placeholder="01310-100",
            help="Digite um CEP com 8 dígitos (ex: 01310-100 ou 01310100)"
        )
        st.caption("Exemplos: `01310-100` (Bela Vista, SP) • `04538-133` (Itaim Bibi, SP) • `30140-071` (Savassi, BH)")
    with col_niche:
        niche_options = [
            "Desentupidora 24h",
            "Oficina Mecânica",
            "Marcenaria Sob Medida",
            "Marmoraria",
            "Vidraçaria",
            "Guincho 24h",
            "Clínica de Estética",
            "Consultório Odontológico",
            "Serralheria",
            "Estética Automotiva",
            "Contabilidade",
            "Chaveiro 24h",
            "Outro / Digitar nicho..."
        ]
        selected_niche = st.selectbox("Nicho / Serviço Alvo", options=niche_options)
        if selected_niche == "Outro / Digitar nicho...":
            target_niche = st.text_input("Digite o nicho personalizado", placeholder="ex: Martelinho de Ouro, Pilates")
        else:
            target_niche = selected_niche

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

            # Granularity selection
            scope_choices = []
            if bairro:
                scope_choices.append("Bairro (Recomendado)")
            if logradouro:
                scope_choices.append("Rua / Logradouro")
            scope_choices.append("Cidade Inteira")

            selected_scope = st.radio(
                "Granularidade da Busca",
                options=scope_choices,
                horizontal=True,
                help="Bairro oferece a melhor concentração de empresas locais sem restringir demais a busca."
            )

            if "Bairro" in selected_scope:
                suggested_query = f"{target_niche} em {bairro}, {cidade} - {uf}"
            elif "Rua" in selected_scope:
                suggested_query = f"{target_niche} {logradouro}, {cidade} - {uf}"
            else:
                suggested_query = f"{target_niche} em {cidade} - {uf}"

            query = st.text_input("Termo de Busca Gerado (Editável)", value=suggested_query)
        else:
            st.warning(f"⚠️ {err_msg}")
else:
    query = st.text_input(
        "Termo de Busca",
        placeholder="ex: Dentistas em Santana, São Paulo ou Oficinas em Curitiba"
    )

col1, col2, col3 = st.columns(3)
with col1:
    negative_keywords = st.text_input(
        "Palavras-chave a Excluir",
        placeholder="Drogasil, Raia, McDonald's, O Boticário, Subway, Casas Bahia",
        help="Nomes de grandes franquias ou termos separados por vírgula para ignorar."
    )
with col2:
    max_results = st.selectbox("Limite de Resultados", options=[20, 40, 60, 80], index=1)
with col3:
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True) # alignment hack
    require_phone = st.checkbox(
        "Exigir Telefone",
        value=True,
        help="Ignora leads que não possuem telefone cadastrado no Google Maps."
    )

if st.button("Buscar Leads", type="primary"):
    if not query.strip():
        st.error("Por favor, informe um termo de busca ou um CEP válido.")
    else:
        with st.spinner("Scanning places..."):
            # Using the New Google Places API endpoint
            url = "https://places.googleapis.com/v1/places:searchText"
            
            # The field mask dictates exactly what data Google returns (saves money and bandwidth)
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.businessStatus,places.types,nextPageToken"
            }
            
            results = []
            page_token = None
            max_pages = max_results // 20
            
            # Social media and free site builder domains
            social_domains = [
                'facebook.com', 'instagram.com', 'yelp.com', 'twitter.com', 'x.com', 
                'linkedin.com', 'tiktok.com', 'linktr.ee', 'yellowpages.com',
                'sites.google.com', 'wixsite.com', 'weebly.com', 'wordpress.com', 'blogspot.com', 'canva.site'
            ]
            
            # Place types that are NEVER valid business leads
            blacklisted_types = [
                'atm', 'transit_station', 'park', 'parking', 'bus_station', 
                'subway_station', 'light_rail_station', 'train_station', 'airport',
                'taxi_stand', 'tourist_attraction', 'museum', 'cemetery', 'church',
                'hindu_temple', 'mosque', 'synagogue', 'local_government_office',
                'city_hall', 'courthouse', 'embassy', 'police', 'fire_station'
            ]
            
            try:
                for page in range(max_pages):
                    data = {
                        "textQuery": query,
                        "pageSize": 20  # The New API supports max 20 per request for textSearch
                    }
                    if page_token:
                        data["pageToken"] = page_token

                    response = requests.post(url, headers=headers, json=data)
                    
                    # Check if the API returned an error (e.g., invalid key, billing not enabled)
                    if response.status_code != 200:
                        st.error(f"Erro na API: {response.json().get('error', {}).get('message', 'Erro desconhecido')}")
                        break
                    
                    resp_json = response.json()
                    page_results = resp_json.get("places", [])
                    results.extend(page_results)
                    
                    page_token = resp_json.get("nextPageToken")
                    if not page_token:
                        break  # No more pages available
                        
                    # Google API sometimes requires a short delay before using nextPageToken
                    time.sleep(2)

                if not results:
                    st.info("Nenhuma empresa encontrada para este termo de busca.")
                else:
                    # --- 3. Filtering Logic ---
                    leads = []
                    
                    # Parse negative keywords
                    neg_words = [w.strip().lower() for w in negative_keywords.split(",")] if negative_keywords else []
                    
                    for place in results:
                        business_name = place.get("displayName", {}).get("text", "Unknown Name")
                        status = place.get("businessStatus", "UNKNOWN")
                        phone = place.get("nationalPhoneNumber")
                        types = place.get("types", [])
                        
                        # 1. Skip logic: negative keywords, permanently closed, or useless place types (ATM, park, etc)
                        if neg_words and any(nw in business_name.lower() for nw in neg_words if nw):
                            continue
                        if status == "CLOSED_PERMANENTLY":
                            continue
                        if any(t in blacklisted_types for t in types):
                            continue
                            
                        # 2. Skip logic: missing phone number (if user checked the box)
                        if require_phone and not phone:
                            continue
                            
                        website_uri = place.get("websiteUri")
                        maps_uri = place.get("googleMapsUri", "")
                        
                        # Format types beautifully (e.g., "auto_repair, point_of_interest" -> "Auto Repair, Point Of Interest")
                        categories = ", ".join([t.replace("_", " ").title() for t in types[:2]]) if types else "N/A"
                        
                        # A "Qualified Lead" is a business missing the websiteUri entirely,
                        # OR their website is actually a social media / directory page / free builder.
                        is_social = any(domain in website_uri.lower() for domain in social_domains) if website_uri else False
                        
                        status_br = "Operacional" if status == "OPERATIONAL" else status.replace("_", " ").title()
                        
                        if not website_uri or is_social:
                            leads.append({
                                "Nome da Empresa": business_name,
                                "Categoria": categories,
                                "Status": status_br,
                                "Telefone": phone or "N/A",
                                "Site / Rede Social": website_uri if is_social else "Nenhum",
                                "Google Maps": maps_uri,
                                "Avaliação": f"{place.get('rating', 'N/A')}⭐ ({place.get('userRatingCount', 0)})",
                                "Endereço": place.get("formattedAddress", "N/A")
                            })

                    # --- 4. Results Display ---
                    st.divider()
                    st.subheader("Resultados dos Leads")
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Empresas Mapeadas", len(results))
                    col2.metric("Leads Qualificados", len(leads))
                    conversion = round((len(leads) / len(results) * 100), 1) if results else 0
                    col3.metric("Taxa de Conversão", f"{conversion}%")

                    if leads:
                        st.info(f"Encontrados {len(leads)} leads qualificados entre as {len(results)} empresas mapeadas.")
                        
                        # Display using a highly styled native HTML Table
                        headers = list(leads[0].keys())
                        
                        # Technical, high-contrast flat CSS styling for the table
                        html_table = f"""
                        <style>
                            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                            .data-table {{
                                border-collapse: collapse;
                                margin: 15px 0;
                                font-size: 14px;
                                font-family: 'Inter', sans-serif;
                                width: 100%;
                                border: 1px solid #333;
                            }}
                            .data-table thead tr {{
                                background-color: #1A1A1A;
                                color: #FFFFFF;
                                text-align: left;
                            }}
                            .data-table th {{
                                padding: 12px 16px;
                                font-weight: 600;
                                text-transform: uppercase;
                                letter-spacing: 0.05em;
                                font-size: 11px;
                                border-bottom: 1px solid #444;
                            }}
                            .data-table td {{
                                padding: 12px 16px;
                                border-bottom: 1px solid #E0E0E0;
                                color: #111111;
                            }}
                            .data-table tbody tr:nth-of-type(even) {{
                                background-color: #F8F9FA;
                            }}
                            .data-table tbody tr:last-of-type td {{
                                border-bottom: 1px solid #333;
                            }}
                            .data-table a {{
                                color: #2E66FF;
                                text-decoration: none;
                                font-weight: 500;
                            }}
                            .data-table a:hover {{
                                text-decoration: underline;
                            }}
                            /* Dark mode support in Streamlit */
                            @media (prefers-color-scheme: dark) {{
                                .data-table {{ border: 1px solid #555; }}
                                .data-table td {{ border-bottom: 1px solid #333; color: #E0E0E0; }}
                                .data-table tbody tr:nth-of-type(even) {{ background-color: rgba(255, 255, 255, 0.03); }}
                                .data-table a {{ color: #5C8CFF; }}
                            }}
                        </style>
                        <div style="overflow-x:auto;">
                            <table class="data-table">
                                <thead>
                                    <tr>
                                        {"".join(f'<th>{h}</th>' for h in headers)}
                                    </tr>
                                </thead>
                                <tbody>
                        """
                        for lead in leads:
                            html_table += "<tr>"
                            for h in headers:
                                val = lead.get(h, "")
                                if h in ["Site / Rede Social", "Google Maps"] and str(val).startswith("http"):
                                    html_table += f'<td><a href="{val}" target="_blank">Abrir ↗</a></td>'
                                else:
                                    html_table += f'<td>{val}</td>'
                            html_table += "</tr>"
                        
                        html_table += """
                                </tbody>
                            </table>
                        </div>
                        <br>
                        """
                        
                        st.markdown(html_table, unsafe_allow_html=True)

                        # Provide a CSV download button using standard csv module
                        csv_buffer = io.StringIO()
                        writer = csv.DictWriter(csv_buffer, fieldnames=headers)
                        writer.writeheader()
                        writer.writerows(leads)
                        csv_data = csv_buffer.getvalue().encode('utf-8')
                        
                        safe_filename = re.sub(r'[^\w\-]', '_', query).strip('_')
                        st.download_button(
                            label="📥 Baixar Leads em CSV",
                            data=csv_data,
                            file_name=f'leads_{safe_filename or "busca"}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.info(f"Foram analisadas {len(results)} empresas, mas todas já possuem site dedicado!")

            except Exception as e:
                st.error(f"Ocorreu um erro inesperado: {e}")
