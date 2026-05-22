FROM python:3.11-slim

# Dependencias del sistema para Chromium (lo lanza Playwright).
# CheckJC v7.4 detecta clientes HTTP "ligeros" (urllib, curl, curl_cffi)
# y los rechaza en silencio, por eso volvemos a un navegador real.
RUN apt-get update && apt-get install -y --no-install-recommends \
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

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir supervisor
# Descarga Chromium gestionado por Playwright (~330 MB)
RUN python -m playwright install chromium

ENV PYTHONPATH=/app

RUN mkdir -p /var/log/checktime && chmod 777 /var/log/checktime
RUN mkdir -p /app/config && chmod 777 /app/config

EXPOSE 5000

COPY supervisord.conf /etc/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
