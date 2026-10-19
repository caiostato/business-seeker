# 🔍 Business Seeker MVP

**Business Seeker** is a lead-generation tool designed for web development agencies and freelancers. Its primary goal is to automate the discovery of local businesses that either completely lack a website or have a severely outdated web presence (relying solely on social media or free site builders). 

By leveraging the new Google Places API, this tool filters out bad leads (like massive franchises or businesses that already have custom domains) and gives you a clean, actionable list of prospects to pitch web development services to.

## ✨ Features
- **Smart Filtering:** Automatically skips businesses that have an existing custom website.
- **Social Media Detection:** Flags businesses using `facebook.com`, `linktr.ee`, `sites.google.com`, etc. as highly qualified leads.
- **🎯 Brazilian CEP Search:** Integrated with ViaCEP to automatically resolve 8-digit postal codes into neighborhoods, cities, and formatted queries.
- **💡 In-App Playbook & Examples:** Collapsible table featuring high-converting niches, sample queries, and franchise filters.
- **Actionable UI:** A sleek, high-contrast dashboard to view, filter, and export leads.
- **Customizable:** Exclude specific keywords (like franchises) or useless place types directly from the search bar.
- **CSV Export:** Download your generated lead list with sanitized filenames in one click.

---

## 🚀 Getting Started

Follow these instructions to get the project running on your local machine.

### 1. Prerequisites
You will need Python 3.8+ installed on your computer.

### 2. Install Dependencies
Open your terminal or command prompt in the project directory and run the following command to install the required Python libraries:

```bash
pip install -r requirements.txt
```

*(This will install `streamlit`, `requests`, and `python-dotenv`.)*

### 3. Get a Google Places API Key
This app uses the Google Places API (New) to fetch data.
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and **Enable Billing** (required by Google, but you get $200 free credit monthly).
3. Enable the **Places API (New)**.
4. Generate an API Key under Credentials.

### 4. Configure Environment Variables
Create a file named `.env` in the root of the project directory. Add your Google API key to it like this:

```env
GOOGLE_PLACES_API_KEY=your_api_key_here
```

### 5. Run the Application
Start the Streamlit dashboard by running:

```bash
streamlit run app.py
```

The application will open automatically in your default web browser at `http://localhost:8501`.

---

## 💡 Usage Tips
- **Use CEP Search (Brazil):** Switch to the CEP Search mode, type an 8-digit CEP (e.g., `01310-100`), select your niche, and let the app build the optimal hyper-local query.
- **Target Neighborhoods (Bairros):** Searching by neighborhood (`Bairro`) offers the best balance of business density without being restricted to a single block.
- **Use Exclude Keywords:** Filter out national franchises that pollute the results (e.g., `Drogasil, Raia, McDonald's, O Boticário, Subway, Casas Bahia`).
- **Phone Numbers:** Leave "Require Phone Number" checked so you only retrieve actionable leads ready for direct cold outreach via phone or WhatsApp.
