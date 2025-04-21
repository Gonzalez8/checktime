# CheckTime

Una aplicación para automatizar el fichaje de entrada y salida en el sistema CheckJC.

## Características

- Automatización del fichaje de entrada y salida en días laborables
- Detección automática de fines de semana y días festivos
- Integración con Telegram para recibir notificaciones
- **Nuevo**: Interfaz web para configurar horarios y días festivos

## Interfaz Web

La nueva interfaz web permite:

- Gestionar días festivos
- Configurar diferentes periodos de horarios (ej. horario de verano, horario de invierno)
- Establecer horarios de fichaje diferentes para cada día de la semana
- Ver un resumen de la configuración actual

## Requisitos

- Python 3.8+
- Google Chrome
- ChromeDriver (compatible con la versión de Chrome instalada)
- Docker (opcional, recomendado para despliegue)

## Configuración

1. Copia el archivo `.env.example` a `.env` y configura las variables de entorno:
   ```
   cp .env.example .env
   ```

2. Edita el archivo `.env` con tus credenciales y configuración:
   ```
   # Credenciales
   CHECKJC_USERNAME=tu_usuario
   CHECKJC_PASSWORD=tu_contraseña
   
   # Telegram (opcional)
   TELEGRAM_BOT_TOKEN=tu_token
   TELEGRAM_CHAT_ID=tu_chat_id
   
   # Configuración Web
   FLASK_SECRET_KEY=clave_secreta_para_flask
   ADMIN_PASSWORD=contraseña_administrador
   ```

## Instalación

### Con Docker (recomendado)

1. Construye y ejecuta los contenedores:
   ```
   docker-compose up -d
   ```

2. Accede a la interfaz web en: http://localhost:5000

### Sin Docker

1. Crea un entorno virtual e instala las dependencias:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

2. Ejecuta la aplicación:
   ```
   python -m src.checktime.main
   ```

3. Accede a la interfaz web en: http://localhost:5000

## Modos de ejecución

Puedes configurar el modo de ejecución utilizando la variable `RUN_MODE` en el archivo `.env`:

- `RUN_MODE=web_only`: Ejecuta solo la interfaz web
- `RUN_MODE=checker_only`: Ejecuta solo el servicio de fichaje automático
- Sin valor: Ejecuta ambos servicios (interfaz web y fichaje automático)

## Uso de la interfaz web

1. Accede a http://localhost:5000
2. Inicia sesión con el usuario `admin` y la contraseña configurada en `ADMIN_PASSWORD`
3. Desde el panel de control podrás:
   - Ver resumen de la configuración actual
   - Gestionar días festivos
   - Configurar periodos de horarios
   - Establecer horarios de fichaje por día de la semana

## Licencia

Este proyecto está licenciado bajo la licencia MIT. 