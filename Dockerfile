FROM python:3.11-slim

# Instalar dependencias del sistema
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
    && rm -rf /var/lib/apt/lists/*

# Intenta instalar Chrome, pero no falla si no es posible (para compatibilidad ARM/amd64)
RUN set -e; \
    if [ "$(uname -m)" = "x86_64" ]; then \
      wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google.gpg \
      && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google.list \
      && apt-get update \
      && apt-get install -y --no-install-recommends google-chrome-stable || true; \
    fi \
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
RUN mkdir -p /var/log/checktime && chmod 777 /var/log/checktime
RUN mkdir -p /app/config && chmod 777 /app/config

# Exponer el puerto para la aplicación web
EXPOSE 5000

# Comando por defecto
CMD ["python", "-m", "src.checktime.web.server"]
