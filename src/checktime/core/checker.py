import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils.logger import autofichar_logger, error_logger
from ..utils.telegram import TelegramClient
from ..config.settings import (
    CHECKJC_USERNAME,
    CHECKJC_PASSWORD,
    CHECKJC_LOGIN_URL
)

# Usar el logger del módulo
logger = autofichar_logger

class CheckJCClient:
    """Cliente para interactuar con el sistema de fichaje CheckJC."""
    
    def __init__(self, options, timeout):
        """Inicializa el cliente con las opciones de Selenium."""
        self.driver = None
        self.options = options
        self.timeout = timeout
        self.wait = None
        self.telegram = TelegramClient()
    
    def __enter__(self):
        """Inicializa el driver al entrar en el contexto."""
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
            
            # Login directo usando los mismos selectores que el ejemplo
            logger.info(f"Realizando login con usuario: {CHECKJC_USERNAME} y contraseña: {CHECKJC_PASSWORD}")
            self.driver.find_element(By.NAME, "username").send_keys(CHECKJC_USERNAME)
            self.driver.find_element(By.NAME, "password").send_keys(CHECKJC_PASSWORD)
            self.driver.find_element(By.ID, "btn-login").click()
            
            # Esperar un momento para que se complete el login
            logger.info("Login completado")
            return True
            
        except Exception as e:
            logger.error(f"Error durante el proceso de login: {str(e)}")
            raise
    
    def perform_check(self, check_type: str):
        """Realiza el fichaje de entrada o salida según el tipo especificado."""
        try:
            logger.info(f"Iniciando proceso de fichaje de {check_type}...")
            
            # Realizar login una vez
            if not self.login():
                logger.error(f"No se pudo realizar el login para el fichaje de {check_type}")
                return False
            
            # Esperar que el botón esté disponible y hacer clic
            logger.info(f"Esperando botón de fichaje de {check_type}")
            btn_fichar = self.wait.until(
                EC.element_to_be_clickable((By.ID, "btn-check"))
            )
            btn_fichar.click()
            
            # Enviar mensaje a Telegram
            message = f"✅ Fichaje de {check_type} registrado correctamente"
            self.telegram.send_message(message)
            
            logger.info(f"Fichaje de {check_type} registrado correctamente")
            return True
            
        except Exception as e:
            error_msg = f"Error durante el proceso de fichaje de {check_type}: {str(e)}"
            logger.error(error_msg)
            # Enviar mensaje de error a Telegram
            self.telegram.send_message(f"❌ {error_msg}")
            raise

    def check_in(self):
        """Realiza el fichaje de entrada."""
        return self.perform_check("entrada")

    def check_out(self):
        """Realiza el fichaje de salida."""
        return self.perform_check("salida") 