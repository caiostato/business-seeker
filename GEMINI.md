# 🧠 Gemini AI Context: Business Seeker

Welcome! If you are an AI assistant (like Gemini/Antigravity) reading this file, this is your core context for the **Business Seeker** project. Please adhere to these product guidelines and technical constraints when assisting the user.

## 1. Project Vision
**Business Seeker** is a lead-generation tool designed for web development agencies and freelancers. Its primary goal is to automate the discovery of local businesses that either completely lack a website or have a severely outdated web presence. By providing ready-to-contact lead lists, this tool saves hours of manual prospecting.

## 2. Current Scope: The MVP (Version 1.0)
We are currently operating strictly within the MVP scope.
* **Core Logic:** We only flag businesses that have absolutely **no website** attached to their Google Places profile. (No deep scraping or performance checks yet).
* **Data Source:** Google Places API (specifically the New API endpoint `places:searchText`).
* **User Interface:** A local web app built entirely in Streamlit.
* **Output:** Visual data table + CSV download.

## 3. Tech Stack
* **Language:** Python 3.x
* **Frontend/UI:** Streamlit (`streamlit`)
* **Data Handling:** Pandas (`pandas`)
* **API Requests:** Requests (`requests`)
* **Environment:** `python-dotenv` for managing the `GOOGLE_PLACES_API_KEY`.

## 4. AI Assistant Directives (Product & Engineering Rules)

When contributing to this project, follow these guidelines:

### A. Prevent Over-Engineering (The MVP Rule)
* **Stick to Streamlit:** Do not suggest migrating to complex frontend frameworks (React, Vue, Next.js) or full backend frameworks (Django/FastAPI) unless the user explicitly requests a pivot for Phase 3. Streamlit is perfect for our current data-driven MVP.
* **Simple is Better:** Prioritize Pythonic, readable code. Avoid unnecessary abstractions.

### B. API Cost & Performance Awareness
* **Always Use Field Masks:** The Google Places API charges based on the data requested. Whenever you write or modify API calls, ensure you are using the `X-Goog-FieldMask` header to request *only* the specific fields needed (e.g., `places.displayName,places.formattedAddress,places.websiteUri`). Do not request full place details unless required.

### C. Maintain Product Focus
* **The Goal is Leads:** Every feature suggestion or code change should tie back to the core metric: *Does this help the user find better web-dev leads faster?*
* **False Positives:** Be mindful of edge cases in the data (e.g., a business using a Facebook page as a website). If modifying the filtering logic, prioritize accuracy.

### D. Documentation
* If the user makes a significant pivot to the product scope (e.g., deciding to build an automated email outreach feature), ensure you remind them to update the `PRD_Business_Seeker.md` artifact and this `GEMINI.md` file.

---
*Created by the Senior Product Manager AI for future context alignment.*
