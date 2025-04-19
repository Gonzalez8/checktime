# Sistema de Fichaje Automático

Este proyecto implementa un sistema automatizado de fichaje que realiza automáticamente los registros de entrada y salida en el sistema CheckJC.

## Características

- Fichaje automático de entrada y salida en horarios configurados
- Detección automática de días laborables (excluye fines de semana)
- Sistema de logging detallado
- Notificaciones por Telegram
- Gestión de días festivos
- Interfaz web para configuración y monitoreo

## Requisitos

- Python 3.8+
- Chrome/Chromium
- ChromeDriver compatible con la versión de Chrome instalada
- Cuenta en CheckJC
- Bot de Telegram (opcional, para notificaciones)

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/checktime.git
cd checktime
```

2. Crear y activar un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus credenciales y configuración
```

## Configuración

El archivo `.env` debe contener las siguientes variables:

```env
CHECKJC_USERNAME=tu_usuario
CHECKJC_PASSWORD=tu_contraseña
CHECK_IN_TIME=09:00
CHECK_OUT_TIME=18:00
TELEGRAM_BOT_TOKEN=tu_token  # Opcional
TELEGRAM_CHAT_ID=tu_chat_id  # Opcional
```

## Uso

1. Iniciar el servicio:
```bash
python src/checktime/main.py
```

2. El servicio se ejecutará en segundo plano y realizará los fichajes automáticamente en los horarios configurados.

## Estructura del Proyecto

```
checktime/
├── src/
│   └── checktime/
│       ├── core/
│       │   ├── checker.py      # Cliente de CheckJC
│       │   └── holidays.py     # Gestión de festivos
│       ├── utils/
│       │   ├── logger.py       # Configuración de logging
│       │   └── telegram.py     # Cliente de Telegram
│       ├── config/
│       │   └── settings.py     # Configuración general
│       └── main.py            # Punto de entrada
├── logs/                      # Directorio de logs
├── requirements.txt
└── README.md
```

## Logging

Los logs se almacenan en el directorio `logs/`:
- `fichar.log`: Log general del sistema
- `error.log`: Log específico de errores

## Contribuir

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo [LICENSE](LICENSE) para más detalles. 