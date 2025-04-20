# CheckTime - Bot de Fichaje Automático

Bot de Telegram para automatizar el proceso de fichaje en CheckTime.

## Características

- 🤖 Bot de Telegram para control y monitoreo
- ⏰ Fichaje automático programado
- 📊 Registro de actividad y logs
- 🔄 Reintentos automáticos en caso de fallo
- 🚀 Ejecución en contenedores Docker

## Requisitos

- Python 3.8 o superior
- Docker y Docker Compose
- Google Chrome (instalado automáticamente en el contenedor)
- Cuenta de Telegram y token de bot
- Credenciales de CheckTime

## Configuración

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/checktime.git
cd checktime
```

2. Crear archivo `.env` con las siguientes variables:
```env
TELEGRAM_BOT_TOKEN=tu_token_de_telegram
TELEGRAM_CHAT_ID=tu_chat_id
CHECKTIME_USERNAME=tu_usuario
CHECKTIME_PASSWORD=tu_contraseña
```

3. Construir y ejecutar con Docker Compose:
```bash
docker compose up -d
```

## Estructura del Proyecto

```
checktime/
├── src/
│   └── checktime/
│       ├── bot/
│       │   ├── __init__.py
│       │   ├── listener.py
│       │   └── telegram_bot.py
│       ├── __init__.py
│       └── main.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── setup.py
└── README.md
```

## Servicios Docker

El proyecto utiliza dos contenedores Docker:

1. **checktime-bot**: Ejecuta el bot de Telegram
   - Comando: `python -m src.checktime.bot.listener`
   - Reinicio automático en caso de fallo
   - Memoria compartida: 2GB

2. **checktime-fichar**: Ejecuta el servicio de fichaje
   - Comando: `python -m src.checktime.main`
   - Reinicio automático en caso de fallo
   - Memoria compartida: 2GB

## Monitoreo

- Los logs se almacenan en `/var/log/checktime/`
- El bot envía notificaciones de estado a Telegram
- Los contenedores se reinician automáticamente en caso de fallo

## Desarrollo

Para desarrollo local:

1. Instalar dependencias:
```bash
pip install -e .
```

2. Ejecutar el bot:
```bash
python -m src.checktime.bot.listener
```

3. Ejecutar el servicio de fichaje:
```bash
python -m src.checktime.main
```

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 