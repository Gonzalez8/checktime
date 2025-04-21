#!/usr/bin/env python
"""
Punto de entrada específico para la aplicación web.
Este script solo inicia el servidor web Flask.
"""

import os
import logging
from pathlib import Path
from checktime.web import create_app
from checktime.config.settings import LOG_DIR

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "web.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Iniciar solo el servidor web."""
    logger.info("Iniciando el servidor web...")
    
    # Crear la aplicación Flask
    app = create_app()
    
    # Ejecutar la aplicación web
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Servidor web iniciado en el puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == "__main__":
    main() 