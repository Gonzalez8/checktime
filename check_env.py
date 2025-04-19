#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def check_environment():
    """Verifica las variables de entorno y la configuración del sistema."""
    print("\n=== VERIFICACIÓN DE VARIABLES DE ENTORNO ===")
    
    # Variables de Telegram
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
    print(f"TELEGRAM_BOT_TOKEN: {'✅ Configurado' if telegram_token else '❌ No configurado'}")
    print(f"TELEGRAM_CHAT_ID: {'✅ Configurado' if telegram_chat else '❌ No configurado'}")
    
    # Variables de CheckJC
    checkjc_user = os.getenv('CHECKJC_USERNAME')
    checkjc_pass = os.getenv('CHECKJC_PASSWORD')
    print(f"CHECKJC_USERNAME: {'✅ Configurado' if checkjc_user else '❌ No configurado'}")
    print(f"CHECKJC_PASSWORD: {'✅ Configurado' if checkjc_pass else '❌ No configurado'}")
    
    # Variables de horario
    check_in = os.getenv('CHECK_IN_TIME')
    check_out = os.getenv('CHECK_OUT_TIME')
    print(f"CHECK_IN_TIME: {'✅ Configurado' if check_in else '❌ No configurado'}")
    print(f"CHECK_OUT_TIME: {'✅ Configurado' if check_out else '❌ No configurado'}")
    
    print("\n=== INFORMACIÓN DEL SISTEMA ===")
    print(f"Directorio actual: {os.getcwd()}")
    print(f"Directorio del script: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"Python path: {sys.executable}")
    print(f"Python version: {sys.version}")
    
    print("\n=== MÓDULOS INSTALADOS ===")
    import pkg_resources
    installed_packages = [f"{dist.key} {dist.version}" for dist in pkg_resources.working_set]
    print("\n".join(installed_packages))

if __name__ == "__main__":
    check_environment() 