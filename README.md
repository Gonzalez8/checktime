# CheckTime - Sistema de Fichaje Automático

Sistema automatizado para realizar fichajes de entrada y salida en CheckJC, con integración de Telegram para notificaciones.

## Características

- Fichaje automático de entrada y salida en CheckJC
- Notificaciones en tiempo real a través de Telegram
- Configuración flexible de horarios
- Sistema de servicios gestionado por systemd
- Manejo de errores y reintentos automáticos
- Logs detallados para monitoreo
- Gestión de días festivos a través de Telegram

## Requisitos

- Python 3.8+
- pip (gestor de paquetes de Python)
- Credenciales de CheckJC
- Token de bot de Telegram
- ID de chat de Telegram

## Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd fichar
```

2. Crear y activar entorno virtual:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
Crear un archivo `.env` en la raíz del proyecto con:
```
TELEGRAM_BOT_TOKEN=tu_token_de_bot
TELEGRAM_CHAT_ID=tu_chat_id
CHECKJC_USERNAME=tu_usuario
CHECKJC_PASSWORD=tu_contraseña
CHECK_IN_TIME=09:00
CHECK_OUT_TIME=18:00
```

## Configuración de Servicios

El sistema utiliza systemd para gestionar los servicios. Se incluyen dos servicios:

1. `checktime-fichar.service`: Gestiona el fichaje automático
2. `checktime-bot.service`: Gestiona el bot de Telegram

Para instalar los servicios:
```bash
chmod +x install_services.sh
./install_services.sh
```

## Uso

### Iniciar los Servicios

```bash
systemctl start checktime-fichar.service
systemctl start checktime-bot.service
```

### Verificar Estado

```bash
systemctl status checktime-fichar.service
systemctl status checktime-bot.service
```

### Ver Logs

```bash
journalctl -u checktime-fichar.service
journalctl -u checktime-bot.service
```

### Gestión de Festivos

El bot de Telegram permite gestionar los días festivos mediante los siguientes comandos:

- `/addfestivo YYYY-MM-DD`: Añade un nuevo día festivo
- `/delfestivo YYYY-MM-DD`: Elimina un día festivo
- `/listfestivos`: Muestra la lista de días festivos configurados

Ejemplos:
```
/addfestivo 2024-12-25
/delfestivo 2024-12-25
/listfestivos
```

> **Nota**: Los festivos se almacenan en el archivo `/root/fichar/config/festivos.txt`. No debe existir otro archivo con el mismo nombre en otra ubicación.

## Notificaciones de Telegram

El sistema envía notificaciones en los siguientes casos:
- Inicio del servicio de fichaje
- Fichaje de entrada realizado
- Fichaje de salida realizado
- Errores durante el proceso de fichaje
- Gestión de festivos (añadir/eliminar/listar)

## Estructura del Proyecto

```
fichar/
├── src/
│   └── checktime/
│       ├── bot/
│       │   └── listener.py
│       ├── utils/
│       │   └── telegram.py
│       ├── config/
│       │   └── settings.py
│       ├── checker.py
│       └── main.py
├── config/
│   └── festivos.txt
├── requirements.txt
├── .env
└── install_services.sh
```

## Mantenimiento

### Actualizar el Sistema

1. Detener los servicios:
```bash
systemctl stop checktime-fichar.service checktime-bot.service
```

2. Actualizar el código:
```bash
git pull
```

3. Actualizar dependencias si es necesario:
```bash
pip install -r requirements.txt
```

4. Reiniciar los servicios:
```bash
systemctl start checktime-fichar.service checktime-bot.service
```

### Solución de Problemas

1. Verificar logs:
```bash
journalctl -u checktime-fichar.service -n 50
journalctl -u checktime-bot.service -n 50
```

2. Verificar variables de entorno:
```bash
python3 check_env.py
```

3. Verificar estado de los servicios:
```bash
systemctl status checktime-fichar.service
systemctl status checktime-bot.service
```

4. Verificar archivo de festivos:
```bash
cat config/festivos.txt
```

## Contribuir

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 