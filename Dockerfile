FROM python:3.11-slim

# Instalar dependencias del sistema Y SUPERVISOR
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    unzip \
    curl \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    xdg-utils \
    supervisor `# <-- AÑADIDO: Instalar supervisor` \
    && rm -rf /var/lib/apt/lists/*

# Instalar Google Chrome (última versión disponible)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Ya no necesitamos especificar una versión fija de ChromeDriver
# webdriver-manager se encargará de descargar la versión compatible

# Crear y establecer el directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Instalar el paquete en modo desarrollo
RUN pip install -e .

# Asegurarse de que el módulo está en el PYTHONPATH
ENV PYTHONPATH=/app

# Crear directorios necesarios
RUN mkdir -p /app/logs
RUN mkdir -p /app/config

# Copiar la configuración de Supervisor dentro de la imagen
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Exponer el puerto para la aplicación web
EXPOSE 5000

# Ejecutar Supervisor (este es el proceso principal del contenedor)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]