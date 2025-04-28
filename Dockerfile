FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para Selenium y Chromium
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
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Crear y establecer el directorio de trabajo
WORKDIR /app

# Copiar el resto del código
COPY . .

# Instalar el paquete en modo editable (y todas las dependencias)
RUN pip install --no-cache-dir -e .

# Asegurarse de que el módulo está en el PYTHONPATH
ENV PYTHONPATH=/app

# Variables de entorno para Chrome y Chromedriver
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Crear directorios necesarios
RUN mkdir -p /var/log/checktime && chmod 777 /var/log/checktime
RUN mkdir -p /app/config && chmod 777 /app/config

# Exponer el puerto para la aplicación web
EXPOSE 5000

# Comando por defecto
CMD ["python", "-m", "src.checktime.web.server"]
