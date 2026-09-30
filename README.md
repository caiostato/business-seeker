# 🔍 Business Seeker MVP

**Business Seeker** is a lead-generation tool designed for web development agencies and freelancers. Its primary goal is to automate the discovery of local businesses that either completely lack a website or have a severely outdated web presence (relying solely on social media or free site builders). 

By leveraging the new Google Places API, this tool filters out bad leads (like massive franchises or businesses that already have custom domains) and gives you a clean, actionable list of prospects to pitch web development services to.

## ✨ Features
- **Smart Filtering:** Automatically skips businesses that have an existing custom website.
- **Social Media Detection:** Flags businesses using `facebook.com`, `linktr.ee`, `sites.google.com`, etc. as highly qualified leads.
- **Actionable UI:** A sleek, high-contrast dashboard to view, filter, and export leads.
- **Customizable:** Exclude specific keywords (like franchises) or useless place types directly from the search bar.
- **CSV Export:** Download your generated lead list with one click.

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
- **Be Specific:** Instead of searching `"Restaurants in New York"`, search `"Restaurants near Broadway, NY"` to bypass Google's 60-result limit and find smaller, local businesses.
- **Use Exclude Keywords:** If franchises keep popping up, add them to the "Exclude Keywords" input (e.g., `McDonalds, Starbucks`).
- **Phone Numbers:** Leave "Require Phone Number" checked so you don't end up with dead-end leads.
