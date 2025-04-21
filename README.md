# CheckTime

Una aplicación para automatizar el fichaje de entrada y salida en el sistema CheckJC.

## Características

- Automatización del fichaje de entrada y salida en días laborables
- Detección automática de fines de semana y días festivos
- Integración con Telegram para recibir notificaciones
- Interfaz web para configurar horarios y días festivos

## Arquitectura de Servicios

CheckTime está organizado en tres servicios independientes, cada uno con una única responsabilidad:

1. **Servicio Web**: Proporciona la interfaz de usuario web para administrar el sistema
2. **Servicio de Fichaje**: Realiza los fichajes automáticos según los horarios configurados
3. **Servicio de Bot**: Maneja la integración con Telegram para notificaciones y comandos

Esta separación garantiza mayor estabilidad, mantenibilidad y escalabilidad del sistema.

## Interfaz Web

La interfaz web permite:

- Gestionar días festivos
- Configurar diferentes periodos de horarios (ej. horario de verano, horario de invierno)
- Establecer horarios de fichaje diferentes para cada día de la semana
- Ver un resumen de la configuración actual

## Requisitos

- Python 3.8+
- Google Chrome
- ChromeDriver (compatible con la versión de Chrome instalada)
- Docker y Docker Compose (recomendado para despliegue)

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

## Instalación y Ejecución

### Con Docker Compose (recomendado)

1. Construye y ejecuta todos los servicios:
   ```
   docker compose up -d
   ```

2. Accede a la interfaz web en: http://localhost:5000

3. Para iniciar servicios específicos:
   ```
   docker compose up -d web    # Solo la interfaz web
   docker compose up -d fichar # Solo el servicio de fichaje
   docker compose up -d bot    # Solo el bot de Telegram
   ```

### Sin Docker (Desarrollo)

1. Crea un entorno virtual e instala las dependencias:
   ```
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .
   ```

2. Ejecuta cada servicio por separado:
   ```
   # Interfaz web
   python -m src.checktime.web.server
   
   # Servicio de fichaje
   python -m src.checktime.fichaje.service
   
   # Bot de Telegram
   python -m src.checktime.bot.listener
   ```

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