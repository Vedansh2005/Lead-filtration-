# LinkedIn Prospect Filter & Lead Qualifier

## Overview
This web application automates the process of filtering LinkedIn prospects from a CSV file and identifying valid business leads based on specific product categories (e.g., sports goods). It reduces manual workload by validating LinkedIn profiles, checking company relevance, and classifying leads.

## Features
- Upload CSV of prospects (name, LinkedIn URL, job title, company name, etc.)
- Automated LinkedIn profile validation (photo, job title, connections)
- Company enrichment and classification (scraping, APIs, NLP)
- Product category tagging (e.g., sports goods, fitness)
- Clean, modern React.js + Tailwind CSS frontend
- Python FastAPI backend for processing, scraping, enrichment, and classification
- Download filtered, tagged CSV of qualified leads

## Tech Stack
- **Frontend:** React.js, Tailwind CSS
- **Backend:** Python, FastAPI, Selenium, spaCy/HuggingFace, SerpAPI/Google Custom Search

## Setup
1. `cd frontend` and run `npm install && npm start` for the React app
2. `cd backend` and run `pip install -r requirements.txt && uvicorn main:app --reload` for the API

## Usage
- Upload your CSV, review results, filter, and download the cleaned file.

---

This project is modular and can be adapted for different product categories and lead criteria. 