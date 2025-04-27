import logging
import os
import platform
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from checktime.shared.config import get_selenium_timeout

logger = logging.getLogger(__name__)

class CheckJCClient:
    """Cliente para interactuar con CheckJC."""
    
    def __init__(self, username, password):
        if not username or not password:
            raise ValueError("CheckJC username and password must be provided.")
            

        self.username = username
        self.password = password
        self.driver = None
        self.wait = None
        self.timeout = get_selenium_timeout()
        self.login_url = "https://trainingbnetwork.checkjc.com/login"
    
    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        options = webdriver.ChromeOptions()
        options.binary_location = os.getenv('CHROME_BIN', '/usr/bin/chromium')
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")

        service = Service(executable_path=os.getenv('CHROMEDRIVER_BIN', '/usr/bin/chromedriver'))
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        logger.info(f"Driver de Chrome inicializado correctamente para {self.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            logger.info(f"Driver de Chrome cerrado para {self.username}")
    
    def login(self):
        """Realiza el login en CheckJC."""
        if SIMULATION_MODE:
            logger.info(f"Simulation: Login successful for {self.username}")
            time.sleep(1)
            return True

        try:
            logger.info(f"Navigating to login page: {self.login_url}")
            self.driver.get(self.login_url)
            
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username'], input#username, input[type='text'], input[type='email']"))
            )
            username_field.clear()
            username_field.send_keys(self.username)
            logger.info(f"Username entered for {self.username}")
            
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password'], input#password, input[type='password']"))
            )
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("Password entered")
            
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']"))
            )
            login_button.click()
            logger.info("Login button clicked")
            
            self.wait.until(
                EC.any_of(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .main-content, #btn-check")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.alert-danger"))
                )
            )
            try:
                error_div = self.driver.find_element(By.CSS_SELECTOR, "div.alert-danger")
                error_text = error_div.text.strip()

                if error_text:
                    raise Exception(f"Error during login for {self.username}: {error_text}")

            except NoSuchElementException:
                logger.info(f"Login successful for {self.username}")
                
            return True
        
        except Exception as e:
            error_msg = f"❌ Error during login for {self.username}: {e}"
            raise

    def perform_check(self, check_type: str):
        """Check in or check out."""
        if SIMULATION_MODE:
            time.sleep(1)
            now = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Simulation: Check {check_type} completed at {now} for {self.username}")
            return True

        try:
            logger.info(f"Searching for Check {check_type} button")
            btn_fichar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-check, button.btn-check, button[id*='check'], button[class*='check']"))
            )
            self.driver.execute_script("arguments[0].click();", btn_fichar)
            
            self.wait.until(
                EC.any_of(
                    EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".alert, .message, .notification"), "registrado"),
                    EC.staleness_of(btn_fichar),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".success, .confirm"))
                )
            )
            
            now = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Check {check_type} completed for {self.username} successfully")
            return True
        
        except Exception as e:
            error_msg = f"❌ Error during Check {check_type} for {self.username}: {e}"
            logger.error(error_msg)
            raise

    def check_in(self):
        """Perform check in."""
        return self.perform_check("in")
    
    def check_out(self):
        """Perform check out."""
        return self.perform_check("out")

