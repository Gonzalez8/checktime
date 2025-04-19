#!/usr/bin/env python3
import logging
import sys
import os
from pathlib import Path

# Añadir el directorio raíz al path para poder importar los módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from src.checktime.utils.telegram import TelegramClient
from src.checktime.config.settings import LOG_DIR

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "test_telegram.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def test_telegram():
    """Prueba el envío de mensajes a Telegram."""
    try:
        # Crear instancia del cliente
        client = TelegramClient()
        
        # Probar envío de mensaje de prueba
        print("\n=== PRUEBA DE ENVÍO DE MENSAJES A TELEGRAM ===")
        
        # Mensaje de prueba
        test_message = "🔔 Mensaje de prueba desde el script de verificación"
        print(f"Enviando mensaje de prueba: {test_message}")
        success = client.send_message(test_message)
        
        if success:
            print("✅ Mensaje enviado correctamente")
        else:
            print("❌ Error al enviar el mensaje")
        
        # Probar mensaje de check-in
        checkin_message = "✅ Check-in realizado correctamente"
        print(f"\nEnviando mensaje de check-in: {checkin_message}")
        success = client.send_message(checkin_message)
        
        if success:
            print("✅ Mensaje de check-in enviado correctamente")
        else:
            print("❌ Error al enviar el mensaje de check-in")
        
        # Probar mensaje de check-out
        checkout_message = "🚪 Check-out realizado correctamente"
        print(f"\nEnviando mensaje de check-out: {checkout_message}")
        success = client.send_message(checkout_message)
        
        if success:
            print("✅ Mensaje de check-out enviado correctamente")
        else:
            print("❌ Error al enviar el mensaje de check-out")
        
    except Exception as e:
        logger.error(f"Error en la prueba de Telegram: {str(e)}")
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_telegram() 