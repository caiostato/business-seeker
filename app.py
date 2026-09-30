import streamlit as st
import requests
import os
import time
import io
import csv
from dotenv import load_dotenv

# Load environment variables (like API keys) from a .env file if it exists
load_dotenv()

# Configure the Streamlit page
st.set_page_config(page_title="Business Seeker", layout="wide")

st.title("Business Seeker")
st.markdown("Discover local businesses lacking a dedicated website on Google Maps.")

# --- 1. API Key Configuration ---
api_key = os.getenv("GOOGLE_PLACES_API_KEY")
if not api_key:
    st.error("API Key not found. Add GOOGLE_PLACES_API_KEY to your .env file.")
    st.stop()

# --- 2. Search Interface ---
st.subheader("Search")
query = st.text_input("Target Query", placeholder="Plumbers in Austin, TX")

col1, col2, col3 = st.columns(3)
with col1:
    negative_keywords = st.text_input("Exclude Keywords", placeholder="Drogasil, Starbucks")
with col2:
    max_results = st.selectbox("Result Limit", options=[20, 40, 60, 80], index=1)
with col3:
    st.markdown("<div style='margin-top: 32px;'></div>", unsafe_allow_html=True) # alignment hack
    require_phone = st.checkbox("Require Phone Number", value=True, help="Skip leads that do not have a phone number listed.")

if st.button("Find Leads", type="primary"):
    if not query:
        st.error("Enter a target query.")
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
                        st.error(f"API Error: {response.json().get('error', {}).get('message', 'Unknown Error')}")
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
                    st.info("No businesses found for this query.")
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
                        
                        if not website_uri or is_social:
                            leads.append({
                                "Business Name": business_name,
                                "Category": categories,
                                "Status": status.replace("_", " ").title(),
                                "Phone": place.get("nationalPhoneNumber", "N/A"),
                                "Website": website_uri if is_social else "None",
                                "Google Maps": maps_uri,
                                "Rating": f"{place.get('rating', 'N/A')}⭐ ({place.get('userRatingCount', 0)})",
                                "Address": place.get("formattedAddress", "N/A")
                            })

                    # --- 4. Results Display ---
                    st.divider()
                    st.subheader("Lead Results")
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Places Scanned", len(results))
                    col2.metric("Qualified Leads", len(leads))
                    conversion = round((len(leads) / len(results) * 100), 1) if results else 0
                    col3.metric("Conversion Rate", f"{conversion}%")

                    if leads:
                        st.info(f"Found {len(leads)} leads out of {len(results)} places scanned.")
                        
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
                                if h in ["Website", "Google Maps"] and str(val).startswith("http"):
                                    html_table += f'<td><a href="{val}" target="_blank">Open ↗</a></td>'
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
                        
                        st.download_button(
                            label="📥 Download Leads as CSV",
                            data=csv_data,
                            file_name=f'leads_{query.replace(" ", "_")}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.info(f"Searched {len(results)} businesses, but all of them have dedicated websites!")

            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
