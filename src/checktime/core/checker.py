import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from typing import Optional
from ..utils.logger import autofichar_logger, error_logger
from ..utils.telegram import TelegramClient
from ..config.settings import (
    CHECKJC_USERNAME,
    CHECKJC_PASSWORD,
    CHECKJC_LOGIN_URL,
    SELENIUM_TIMEOUT,
    SELENIUM_OPTIONS
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
            logger.info("Accediendo a la página de login...")
            self.driver.get(CHECKJC_LOGIN_URL)
            
            # Esperar a que el formulario de login esté presente
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            # Introducir credenciales
            username_field.send_keys(CHECKJC_USERNAME)
            password_field.send_keys(CHECKJC_PASSWORD)
            
            # Hacer click en el botón de login
            login_button = self.driver.find_element(By.ID, "login-button")
            login_button.click()
            
            # Esperar a que se complete el login
            self.wait.until(
                EC.presence_of_element_located((By.ID, "dashboard"))
            )
            logger.info("Login completado exitosamente.")
            
        except TimeoutException:
            logger.error("Timeout esperando elementos de la página de login.")
            raise
        except NoSuchElementException as e:
            logger.error(f"Elemento no encontrado durante el login: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error durante el proceso de login: {str(e)}")
            raise
    
    def check_in(self):
        """Realiza el fichaje de entrada."""
        try:
            logger.info("Iniciando proceso de fichaje de entrada...")
            check_in_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "check-in-button"))
            )
            check_in_button.click()
            
            # Esperar confirmación
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "success-message"))
            )
            logger.info("Fichaje de entrada registrado correctamente.")
            
        except TimeoutException:
            logger.error("Timeout durante el proceso de fichaje de entrada.")
            raise
        except NoSuchElementException as e:
            logger.error(f"Elemento no encontrado durante el fichaje de entrada: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error durante el proceso de fichaje de entrada: {str(e)}")
            raise
    
    def check_out(self):
        """Realiza el fichaje de salida."""
        try:
            logger.info("Iniciando proceso de fichaje de salida...")
            check_out_button = self.wait.until(
                EC.element_to_be_clickable((By.ID, "check-out-button"))
            )
            check_out_button.click()
            
            # Esperar confirmación
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "success-message"))
            )
            logger.info("Fichaje de salida registrado correctamente.")
            
        except TimeoutException:
            logger.error("Timeout durante el proceso de fichaje de salida.")
            raise
        except NoSuchElementException as e:
            logger.error(f"Elemento no encontrado durante el fichaje de salida: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error durante el proceso de fichaje de salida: {str(e)}")
            raise

    def check_in_type(self, check_type: str) -> bool:
        """
        Realiza el fichaje.
        
        Args:
            check_type (str): Tipo de fichaje ('entrada' o 'salida')
        
        Returns:
            bool: True si el fichaje fue exitoso, False en caso contrario
        """
        try:
            logger.info(f"Iniciando fichaje de {check_type}")
            
            if not self.login():
                return False
            
            logger.info(f"Esperando botón de fichaje de {check_type}")
            btn_fichar = self.wait.until(
                EC.element_to_be_clickable((By.ID, f"btn-{check_type}"))
            )
            btn_fichar.click()
            
            logger.info(f"Fichaje de {check_type} realizado correctamente")
            return True
            
        except Exception as e:
            logger.error(f"Error al fichar ({check_type}): {str(e)}")
            return False
        
        finally:
            if self.driver:
                logger.info("Cerrando navegador")
                self.driver.quit() 