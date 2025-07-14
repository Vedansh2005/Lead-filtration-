import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from dotenv import load_dotenv
import logging
from selenium.webdriver.chrome.service import Service

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "chromedriver")

# Log in once and reuse session for efficiency (simple singleton pattern)
driver = None
def get_driver():
    global driver
    if driver is not None:
        return driver
    try:
        options = Options()
        # options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        logger.info(f"Initializing Chrome driver with path: {CHROMEDRIVER_PATH}")
        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        logger.info("Navigating to LinkedIn login page")
        driver.get("https://www.linkedin.com/login")
        time.sleep(2)
        
        logger.info("Attempting to log in to LinkedIn")
        driver.find_element(By.ID, "username").send_keys(LINKEDIN_EMAIL)
        driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)
        
        return driver
    except WebDriverException as e:
        logger.error(f"WebDriver error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during driver initialization: {str(e)}")
        raise

def validate_linkedin_profile(profile_url="https://www.linkedin.com/in/ahssin-iqbal-a7a159286"):
    try:
        logger.info(f"Validating LinkedIn profile: {profile_url}")
        d = get_driver()
        d.get(profile_url)
        time.sleep(3)
        
        # Check for profile photo
        try:
            # Try multiple selectors for profile photo
            selectors = ["img.profile-photo", "img.pv-top-card-profile-picture__image", ".pv-top-card__photo"]
            has_photo = False
            for selector in selectors:
                try:
                    photo = d.find_element(By.CSS_SELECTOR, selector)
                    has_photo = True
                    break
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.warning(f"Error checking profile photo: {str(e)}")
            has_photo = False
        
        # Check for job title
        try:
            # Try multiple selectors for job title
            selectors = [".text-body-medium.break-words", ".pv-text-details__left-panel", ".pv-top-card--list"]
            job_title = ""
            for selector in selectors:
                try:
                    job_title = d.find_element(By.CSS_SELECTOR, selector).text
                    if job_title:
                        break
                except NoSuchElementException:
                    continue
        except Exception as e:
            logger.warning(f"Error checking job title: {str(e)}")
            job_title = ""
        
        # Check for connections
        try:
            connections = d.find_element(By.XPATH, "//*[contains(text(),'connections')]").text
        except NoSuchElementException:
            connections = ""
        except Exception as e:
            logger.warning(f"Error checking connections: {str(e)}")
            connections = ""
        
        logger.info(f"Profile validation complete: has_photo={has_photo}, job_title={job_title != ''}, connections={connections != ''}")
        return {
            "has_photo": has_photo,
            "job_title": job_title,
            "connections": connections
        }
    except Exception as e:
        logger.error(f"Error validating profile {profile_url}: {str(e)}")
        return {
            "has_photo": False,
            "job_title": "",
            "connections": ""
        }