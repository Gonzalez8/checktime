# Sistema de Fichaje Automático

Sistema automatizado para gestionar fichajes laborales a través de CheckJC con integración de Telegram.

## Características

- Fichaje automático de entrada y salida
- Gestión de días festivos mediante bot de Telegram
- Notificaciones en tiempo real
- Modo headless para ejecución en servidor
- Sistema de logging para seguimiento de errores

## Requisitos

- Python 3.8+
- Chrome/Chromium
- Cuenta en CheckJC
- Bot de Telegram

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/tu-usuario/fichar.git
cd fichar
```

2. Crear entorno virtual:
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
cp config/.env.example config/.env
# Editar config/.env con tus credenciales
```

## Estructura del Proyecto

```
fichar/
├── src/
│   ├── autofichar.py
│   └── bot_listener.py
├── tests/
├── config/
│   └── .env
├── logs/
├── requirements.txt
└── README.md
```

## Uso

### Fichaje Automático

Para realizar un fichaje de entrada:
```bash
python src/autofichar.py entrada
```

Para realizar un fichaje de salida:
```bash
python src/autofichar.py salida
```

### Bot de Telegram

Iniciar el bot:
```bash
python src/bot_listener.py
```

Comandos disponibles:
- `/addfestivo YYYY-MM-DD`: Añadir día festivo
- `/delfestivo YYYY-MM-DD`: Eliminar día festivo
- `/listfestivos`: Listar días festivos

## Contribuir

1. Fork el proyecto
2. Crear una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir un Pull Request

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles. 