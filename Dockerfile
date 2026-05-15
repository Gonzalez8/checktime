FROM python:3.11-slim

# Dependencias mínimas (sin Chromium: Playwright se usa solo como cliente HTTP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir supervisor

ENV PYTHONPATH=/app

RUN mkdir -p /var/log/checktime && chmod 777 /var/log/checktime
RUN mkdir -p /app/config && chmod 777 /app/config

EXPOSE 5000

COPY supervisord.conf /etc/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
