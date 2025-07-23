import os
import time
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging


# Load environment variables
load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "chromedriver")

# Define target keywords
TARGET_KEYWORDS = ["sports","boxing","football","cricket","tennis","basketball","hockey","athletics","sports goods", "netting","fishing","snowboard","sandboard","sail boats","golf","manufacturing","bicycle","surfboard"]
# TARGET_KEYWORDS = ["engineering", "software", "technology", "developer", "programming", "data science", "AI", "machine learning"]

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reusable Selenium driver
driver = None


def get_driver():
    global driver
    if driver:
        return driver
    try:
        options = Options()
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        logger.info(f"Starting ChromeDriver from: {CHROMEDRIVER_PATH}")
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)

        driver.get("https://www.linkedin.com/login")
        time.sleep(2)

        driver.find_element(By.ID, "username").send_keys(LINKEDIN_EMAIL)
        driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        return driver
    except WebDriverException as e:
        logger.error(f"WebDriver error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during driver init: {str(e)}")
        raise


# model="mistral"
def is_similar_with_ollama(description, keywords, threshold=0.5, model="mistral"):
    prompt = f"""
You are an intelligent assistant. Check if this company description is related to any of the following keywords:
Keywords: {', '.join(keywords)}
Description: "{description}"

Reply only with "YES" if related or "NO" if not.
"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False}
        )
        reply = response.json().get("response", "").strip().lower()
        print(f"Ollama reply: {reply}")
        return "yes" in reply
    
    except Exception as e:
        logger.error(f"Ollama similarity check failed: {e}")
        return False


def get_company_info(company_url, driver):
    try:
        # Visit company "about" page
        about_url = company_url.rstrip("/") + "/about"
        logger.info(f"Visiting: {about_url}")
        driver.get(about_url)
        time.sleep(2)  # You can replace this with WebDriverWait for robustness

        # Extract company description from the overview section
        about_text = ""
        try:
            # More robust selector targeting <p class="break-words"> inside the overview section
            about_section = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.org-about-module__margin-bottom p.break-words"))
            )
            about_text = about_section.text.strip()
        except Exception as e:
            logger.warning(f"No about section found or timed out for: {company_url} | Error: {e}")
            return None

        # Check similarity using LLM (Ollama)
        if is_similar_with_ollama(about_text, TARGET_KEYWORDS):
            logger.info(f"Company matched keywords: {company_url}")
            return {
                "company_url": company_url,
                "about": about_text
            }
        else:
            logger.info(f"Filtered out (no keyword match): {company_url}")
            return None

    except Exception as e:
        logger.error(f"Error scraping company {company_url}: {str(e)}")
        return None


def extract_company_links(driver):
    """Extracts all company profile URLs from the experience section."""
    company_links = set()
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Find all <a> tags where the href contains '/company/'a
        anchors = driver.find_elements(By.XPATH, "//a[@data-field='experience_company_logo']")

        for anchor in anchors:
            href = anchor.get_attribute("href")
            if href and "/company/" in href:
                base_url = href.split("?")[0]
                company_links.add(base_url)
        
        logger.info(f"Extracted {len(company_links)} unique company links from experience section.")
    except Exception as e:
        logger.warning(f"Failed to extract company links: {e}")
    
    return list(company_links)


def validate_linkedin_profile(profile_url=""):
    if profile_url == "":
        return None
    
    try:
        logger.info(f"Visiting profile: {profile_url}")
        d = get_driver()
        d.get(profile_url)
        time.sleep(3)

        # Check profile photo
        has_photo = False
        for selector in [
            "img.profile-photo",
            "img.pv-top-card-profile-picture__image",
            ".pv-top-card__photo",
        ]:
            try:
                d.find_element(By.CSS_SELECTOR, selector)
                has_photo = True
                break
            except NoSuchElementException:
                continue

        # Job title
        job_title = ""
        for selector in [
            ".text-body-medium.break-words",
            ".pv-text-details__left-panel",
            ".pv-top-card--list"
        ]:
            try:
                job_title = d.find_element(By.CSS_SELECTOR, selector).text.strip()
                if job_title:
                    break
            except NoSuchElementException:
                continue

        # Connections
        try:
            connections = d.find_element(By.XPATH, "//*[contains(text(),'connections')]").text.strip()
        except Exception:
            connections = ""

        # Extract company links
        company_urls = extract_company_links(d)

        # Get company info if matches keywords
        matching_companies = []
        for url in company_urls:
            info = get_company_info(url, d)
            if info:
                matching_companies.append(info)

        # Skip profiles with no matching companies
        if not matching_companies:
            return None

        return {
            "has_photo": has_photo,
            "job_title": job_title,
            "connections": connections,
            "companies": matching_companies
        }
    except Exception as e:
        logger.error(f"Failed to process profile: {e}")
        return None
