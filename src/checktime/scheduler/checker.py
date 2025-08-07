import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import tempfile
import shutil

from checktime.shared.config import get_selenium_timeout, get_chrome_options_args, get_simulation_mode, get_chrome_bin, get_chromedriver_bin

SIMULATION_MODE = get_simulation_mode()

logger = logging.getLogger(__name__)

class CheckJCClient:
    """Cliente para interactuar con CheckJC."""
    
    def __init__(self, username, password, subdomain):
        if not username or not password or not subdomain:
            raise ValueError("CheckJC username, password, and subdomain must be provided.")

        self.username = username
        self.password = password
        self.subdomain = subdomain
        self.driver = None
        self.wait = None
        self.timeout = get_selenium_timeout()
        self.login_url = f"https://{self.subdomain}.checkjc.com/login"
    
    def __enter__(self):
        if SIMULATION_MODE:
            logger.info(f"Simulation mode enabled for {self.username}")
            return self

        options = webdriver.ChromeOptions()
        options.binary_location = get_chrome_bin()
        for arg in get_chrome_options_args():
            options.add_argument(arg)
        # Aislar perfil temporal único por usuario
        self._tmp_profile = tempfile.mkdtemp(prefix=f"chrome_{self.username}_")
        options.add_argument(f"--user-data-dir={self._tmp_profile}")

        service = Service(executable_path=get_chromedriver_bin())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        logger.info(f"Driver de Chrome inicializado correctamente para {self.username}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
            logger.info(f"Driver de Chrome cerrado para {self.username}")
        # Limpia el perfil temporal
        if hasattr(self, "_tmp_profile"):
            shutil.rmtree(self._tmp_profile, ignore_errors=True)
    
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
        """Performs a check-in or check-out by clicking the check button and waiting for the page to reload."""
        if SIMULATION_MODE:
            time.sleep(1)
            now = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Simulation: Check {check_type} completed at {now} for {self.username}")
            return True

        try:
            logger.info(f"Attempting to perform Check {check_type} for {self.username}")

            # 1. Find the check button
            check_button_selector = (By.CSS_SELECTOR, "#btn-check, button.btn-check, button[id*='check'], button[class*='check']")
            check_button = self.wait.until(EC.element_to_be_clickable(check_button_selector))

            # 2. Click the button
            self.driver.execute_script("arguments[0].click();", check_button)
            logger.info(f"Clicked Check {check_type} button")

            # 3. Wait for the page to reload by waiting for the old button to go stale.
            # This confirms the navigation to the temporary result page has started.
            logger.info("Waiting for page to start reloading (button to go stale)...")
            WebDriverWait(self.driver, 15).until(EC.staleness_of(check_button))
            logger.info("Page has started reloading.")

            # 4. Wait for the new page to load (after the 5s redirect) and the button to be available again.
            logger.info("Waiting for new page to load and check button to be ready...")
            self.wait.until(EC.element_to_be_clickable(check_button_selector))
            logger.info(f"Check {check_type} for {self.username} completed successfully.")

            return True

        except TimeoutException:
            logger.error(f"Timeout occurred during Check {check_type} for {self.username}. The page did not reload as expected.")
            # Re-read the page source to provide more context in the error log
            page_source = self.driver.page_source
            logger.error(f"Current page source on timeout:\n{page_source[:2000]}")
            raise Exception(f"Timeout during Check {check_type}")
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

