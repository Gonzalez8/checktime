"""
CheckJC client for automatically performing check-in and check-out operations.
"""

import logging
import time
import os
import platform
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

from checktime.shared.config import get_selenium_timeout
from checktime.utils.telegram import TelegramClient

# Create logger
logger = logging.getLogger(__name__)

# Telegram client for notifications
telegram_client = TelegramClient()

# Check if we're running on Apple Silicon or in a Docker container where Chrome might not be available
SIMULATION_MODE = platform.machine() == 'arm64' or os.environ.get('SIMULATION_MODE', 'false').lower() == 'true'

class CheckJCClient:
    """Client for interacting with the CheckJC system for check-in and check-out."""
    
    def __init__(self, username=None, password=None):
        """
        Initialize the CheckJC client.
        
        Args:
            username (str, optional): The username for CheckJC. Required.
            password (str, optional): The password for CheckJC. Required.
        """
        if not username or not password:
            raise ValueError("CheckJC username and password must be provided")
            
        self.username = username
        self.password = password
        self.timeout = get_selenium_timeout()
        self.login_url = "https://trainingbnetwork.checkjc.com/login"
        self.driver = None
        
    def __enter__(self):
        """Set up the Chrome driver when entering context."""
        if SIMULATION_MODE:
            logger.info(f"Running in simulation mode (Chrome not available) for user {self.username}")
            return self
            
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info(f"Chrome driver initialized successfully for user {self.username}")
        except Exception as e:
            error_msg = f"Error initializing Chrome driver for user {self.username}: {e}"
            logger.error(error_msg)
            telegram_client.send_message(f"❌ {error_msg}")
            raise
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up the Chrome driver when exiting context."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info(f"Chrome driver closed successfully for user {self.username}")
            except Exception as e:
                logger.error(f"Error closing Chrome driver for user {self.username}: {e}")
    
    def wait_for_element(self, by, value):
        """Wait for an element to be present in the DOM."""
        if SIMULATION_MODE:
            logger.info(f"Simulation for user {self.username}: Wait for element {by}={value}")
            time.sleep(0.5)  # Simulate wait
            return MockElement()
            
        try:
            return WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            error_msg = f"Timeout waiting for element: {by}={value} for user {self.username}"
            logger.error(error_msg)
            raise TimeoutException(error_msg)
    
    def login(self):
        """Log in to the CheckJC system."""
        logger.info(f"Attempting to login to CheckJC for user {self.username}")
        
        if SIMULATION_MODE:
            logger.info(f"Simulation: Login with {self.username}")
            time.sleep(1)  # Simulate operation
            telegram_client.send_message(f"✅ Simulation: Login to CheckJC successful for {self.username}")
            return
        
        try:
            self.driver.get(self.login_url)
            logger.info(f"Navigated to login page for user {self.username}")
            
            # Find and fill username field
            username_field = self.wait_for_element(By.ID, "username")
            username_field.clear()
            username_field.send_keys(self.username)
            logger.info(f"Username entered for {self.username}")
            
            # Find and fill password field
            password_field = self.wait_for_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("Password entered")
            
            # Click login button
            login_button = self.wait_for_element(By.ID, "login-button")
            login_button.click()
            logger.info("Login button clicked")
            
            # Wait for dashboard to load
            self.wait_for_element(By.ID, "dashboard")
            logger.info(f"Login successful for user {self.username}")
            telegram_client.send_message(f"✅ Login to CheckJC successful for {self.username}")
            
        except Exception as e:
            error_msg = f"Error during login for user {self.username}: {e}"
            logger.error(error_msg)
            telegram_client.send_message(f"❌ {error_msg}")
            raise
    
    def check_in(self):
        """Perform check-in operation."""
        logger.info(f"Performing check-in for user {self.username}")
        
        if SIMULATION_MODE:
            # Simulate successful check-in
            time.sleep(1)
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Simulation: Check-in at {current_time} for user {self.username}")
            telegram_client.send_message(f"✅ Simulation: Check-in completed at {current_time} for user {self.username}")
            return
        
        try:
            # Navigate to check-in page
            check_button = self.wait_for_element(By.ID, "check-in-button")
            check_button.click()
            logger.info(f"Check-in button clicked for user {self.username}")
            
            # Confirm check-in
            confirm_button = self.wait_for_element(By.ID, "confirm-check")
            confirm_button.click()
            logger.info(f"Confirm button clicked for user {self.username}")
            
            # Wait for success message
            self.wait_for_element(By.CLASS_NAME, "success-message")
            logger.info(f"Check-in successful for user {self.username}")
            
            # Get current time for the message
            current_time = datetime.now().strftime("%H:%M:%S")
            telegram_client.send_message(f"✅ Check-in completed at {current_time} for user {self.username}")
            
        except Exception as e:
            error_msg = f"Error during check-in for user {self.username}: {e}"
            logger.error(error_msg)
            telegram_client.send_message(f"❌ {error_msg}")
            raise
    
    def check_out(self):
        """Perform check-out operation."""
        logger.info(f"Performing check-out for user {self.username}")
        
        if SIMULATION_MODE:
            # Simulate successful check-out
            time.sleep(1)
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.info(f"Simulation: Check-out at {current_time} for user {self.username}")
            telegram_client.send_message(f"✅ Simulation: Check-out completed at {current_time} for user {self.username}")
            return
        
        try:
            # Navigate to check-out page
            check_button = self.wait_for_element(By.ID, "check-out-button")
            check_button.click()
            logger.info(f"Check-out button clicked for user {self.username}")
            
            # Confirm check-out
            confirm_button = self.wait_for_element(By.ID, "confirm-check")
            confirm_button.click()
            logger.info(f"Confirm button clicked for user {self.username}")
            
            # Wait for success message
            self.wait_for_element(By.CLASS_NAME, "success-message")
            logger.info(f"Check-out successful for user {self.username}")
            
            # Get current time for the message
            current_time = datetime.now().strftime("%H:%M:%S")
            telegram_client.send_message(f"✅ Check-out completed at {current_time} for user {self.username}")
            
        except Exception as e:
            error_msg = f"Error during check-out for user {self.username}: {e}"
            logger.error(error_msg)
            telegram_client.send_message(f"❌ {error_msg}")
            raise

# Mock element for simulation mode
class MockElement:
    def clear(self):
        pass
        
    def send_keys(self, *args, **kwargs):
        pass
        
    def click(self):
        pass 