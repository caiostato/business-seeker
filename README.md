# 🔍 Business Seeker 2.0 (Brasil)

**Business Seeker** is a lead-generation tool designed for web development agencies and freelancers. Its primary goal is to automate the discovery of local businesses in Brazil that either completely lack a website, rely solely on social media / bio link builders, or have a broken / outdated web presence.

By leveraging the new Google Places API (or an optional local Docker scraping engine) and zero-token enrichment, this tool filters out bad leads (like massive franchises or businesses that already have operational websites) and gives you an actionable list of prospects ready for 1-click cold outreach via WhatsApp.

---

## ✨ Features

- **Smart Filtering:** Automatically skips businesses that already have an operational custom website.
- **Social Media & Bio Detection:** Flags businesses using `facebook.com`, `instagram.com`, `linktr.ee`, `bio.site`, `canva.site`, `sites.google.com`, `ifood.com.br`, etc. as highly qualified leads.
- **💬 1-Click WhatsApp Cold Outreach:** Formats Brazilian phones into E.164 (`55 + DDD + Número`), detects `📱 Celular` vs `☎️ Fixo`, and generates direct `wa.me/55...` links with customizable, pre-filled cold pitch templates.
- **⚠️ Broken, Parked & Outdated Site Detection:** Audits custom domains in parallel with `ThreadPoolExecutor` to capture high-converting leads whose website is down (DNS/404/500 error), insecure (`http://` without SSL), parked/abandoned (GoDaddy, Hostinger, cPanel, "Em Construção"), or completely non-responsive on mobile devices (prime redesign leads).
- **🏢 Smart Chain & Franchise Filter:** Automatically recognizes corporate franchise branches (Subway, Drogasil, Óticas Carol, shopping mall units, store numbers like "Loja 02") and multi-location repetitions to focus exclusively on independent local business owners.
- **⚡ Fuzzy Cascading Deduplication:** Normalizes Brazilian street abbreviations (`Av.` -> `Avenida`, `R.` -> `Rua`, door numbers) and uses fuzzy token matching so batch searches in adjacent neighborhoods never return duplicate prospects.
- **🔍 Zero-Token Bio & Social Enrichment:** Automatically visits Linktree, Canva, and social pages to extract email addresses, Instagram handles, and hidden WhatsApp numbers without consuming LLM tokens.
- **🔥 Lead Scoring (Temperatura):** Rates each lead from 0 to 100 points (`🔥 Quente`, `⚡ Médio`, `❄️ Frio`) based on review volume, customer ratings, quick contact channels, and digital pain points.
- **🆕 Seen-Leads History (`leads_vistos.json`):** Tracks previously discovered and contacted businesses so you don't pitch the same company twice when searching adjacent neighborhoods.
- **🎯 Brazilian CEP & Multi-Bairro Batch Search:** Integrated with ViaCEP for automatic neighborhood detection, plus comma-separated batch queries (e.g. `Oficina em Moema, Oficina no Itaim Bibi`) with automatic cascading deduplication (`places.id` > Maps URI > Nome+Endereço).
- **🐳 Dual Engine Support:** Use the official **Google Places API (New)** by default, or connect seamlessly to a local **`gosom/google-maps-scraper`** Docker instance on `http://localhost:8080` for $0 unlimited scraping.
- **CSV Export:** Download your qualified leads with 17 enriched columns ready for sales outreach and CRM import.

---

## 🚀 Getting Started

Follow these instructions to get the project running on your local machine.

### 1. Prerequisites
You will need Python 3.8+ installed on your computer.

### 2. Install Dependencies
Open your terminal or command prompt in the project directory and run:

```bash
pip install -r requirements.txt
```

*(Installs `streamlit`, `requests`, and `python-dotenv`.)*

### 3. Choose Your Search Engine

#### Option A: Google Places API (New) — Default & Recommended
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Places API (New)**.
3. Generate an API Key under Credentials.
4. Create a `.env` file in the root of the project:
   ```env
   GOOGLE_PLACES_API_KEY=your_api_key_here
   ```

#### Option B: Local Scraper (Docker) — $0 Unlimited Scraping
If you prefer not using an API key, run the open-source scraper container locally:
```bash
docker run -d --name gmaps-scraper -p 8080:8080 gosom/google-maps-scraper:v1.18.1 -web
```
Then select **"🐳 Scraper Local Docker"** in the Streamlit sidebar.

### 4. Run the Application
Start the Streamlit dashboard by running:

```bash
streamlit run app.py
```

The application will open automatically in your browser at `http://localhost:8501`.

---

## 🧪 Testing

Run the automated test suite (160 unit tests):

```bash
python -m unittest discover -v
```

---

## 💡 Usage Tips for Cold Outreach in Brazil
- **Target Neighborhoods (Bairros):** Searching by neighborhood (`Bairro`) offers the best balance of business density without being restricted to a single block.
- **Multi-Query Batching:** Enter multiple bairros separated by comma in "Busca Livre" (e.g., `Marmoraria em Moema, Marmoraria no Itaim Bibi, Marmoraria em Pinheiros`) to prospect multiple areas in a single run.
- **WhatsApp 1-Click:** Look for `🔥 Quente` leads with `📱 Celular` numbers. Click **"💬 Chamar no WhatsApp"** to open WhatsApp Web with your pitch already typed.
- **History Tracking:** After completing a batch, click **"💾 Marcar Leads desta Busca como Já Vistos"** to prevent duplicate outreach in the future.
