#!/usr/bin/env python
"""
Entry point for the web application.
This script only starts the Flask web server.
"""

import os
import logging
from pathlib import Path
from checktime.web import create_app
from checktime.shared.config import get_port

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/var/log/checktime/web.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Crear el objeto Flask app para Gunicorn
app = create_app()

def main():
    """Start only the web server."""
    logger.info("Starting the web server...")
    
    # app ya está creado arriba
    port = get_port()
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Web server started on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == "__main__":
    main() 