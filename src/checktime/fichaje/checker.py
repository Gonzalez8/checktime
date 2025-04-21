import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils.logger import autofichar_logger
from ..utils.telegram import TelegramClient
from ..config.settings import (
    CHECKJC_USERNAME,
    CHECKJC_PASSWORD,
    CHECKJC_LOGIN_URL
)
import time

# Intentar importar chromedriver_autoinstaller
try:
    import chromedriver_autoinstaller
    CHROMEDRIVER_AVAILABLE = True
except ImportError:
    CHROMEDRIVER_AVAILABLE = False
    autofichar_logger.warning("chromedriver_autoinstaller no disponible. Asegúrese de tener chromedriver instalado manualmente.")

# Logger del módulo
logger = autofichar_logger

class CheckJCClient:
    """Cliente para interactuar con el sistema de fichaje CheckJC."""
    
    def __init__(self, options, timeout, telegram_client=None):
        """Inicializa el cliente con las opciones de Selenium."""
        self.driver = None
        self.options = options
        self.timeout = timeout
        self.wait = None
        self.telegram = telegram_client or TelegramClient()
    
    def __enter__(self):
        """Inicializa el driver al entrar en el contexto."""
        if CHROMEDRIVER_AVAILABLE:
            chromedriver_autoinstaller.install()
        self.driver = webdriver.Chrome(options=self.options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra el driver al salir del contexto."""
        if self.driver:
            self.driver.quit()
    
    def login(self):
        """Realiza el proceso de login en el sistema."""
        try:
            logger.info(f"Accediendo a la página de login: {CHECKJC_LOGIN_URL}")
            self.driver.get(CHECKJC_LOGIN_URL)
            
            logger.info(f"Realizando login con usuario: {CHECKJC_USERNAME}")
            
            # Encontrar e interactuar con el campo de usuario
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='username'], input#username, input[type='text'], input[type='email']"))
            )
            username_field.clear()
            username_field.send_keys(CHECKJC_USERNAME)
            logger.info("Campo de usuario rellenado")
            
            # Encontrar e interactuar con el campo de contraseña
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='password'], input#password, input[type='password']"))
            )
            password_field.clear()
            password_field.send_keys(CHECKJC_PASSWORD)
            logger.info("Campo de contraseña rellenado")
            
            # Encontrar y hacer clic en el botón de login
            login_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']"))
            )
            login_button.click()
            logger.info("Botón de login pulsado")
            
            # Esperar a que desaparezca el formulario de login o aparezca un elemento post-login
            self.wait.until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, "#btn-login, button[type='submit'], input[type='submit']")) or
                EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard, .main-content, #btn-check"))
            )
            
            logger.info("Login completado")
            return True
            
        except Exception as e:
            logger.error(f"Error durante el proceso de login: {str(e)}")
            raise
    
    def perform_check(self, check_type: str):
        """Realiza el fichaje de entrada o salida según el tipo especificado."""
        try:
            logger.info(f"Buscando botón de fichaje de {check_type}")
            
            # Buscar el botón con selectores comunes para fichaje
            btn_fichar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#btn-check, button.btn-check, button[id*='check'], button[class*='check']"))
            )
            
            logger.info("Botón de fichaje encontrado, realizando clic")
            
            # Usar JavaScript para hacer clic (más confiable)
            self.driver.execute_script("arguments[0].click();", btn_fichar)
            
            # Esperar a que aparezca un mensaje de confirmación o cambie algún elemento de la interfaz
            self.wait.until(
                EC.any_of(
                    EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".alert, .message, .notification"), "registrado"),
                    EC.staleness_of(btn_fichar),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".success, .confirm"))
                )
            )
            
            # Enviar mensaje de éxito
            message = f"✅ Fichaje de {check_type} registrado correctamente"
            self.telegram.send_message(message)
            
            logger.info(f"Fichaje de {check_type} registrado correctamente")
            return True
            
        except Exception as e:
            error_msg = f"Error durante el fichaje de {check_type}: {str(e)}"
            logger.error(error_msg)
            self.telegram.send_message(f"❌ {error_msg}")
            raise

    def check_in(self):
        """Realiza el fichaje de entrada."""
        return self.perform_check("entrada")

    def check_out(self):
        """Realiza el fichaje de salida."""
        return self.perform_check("salida") 