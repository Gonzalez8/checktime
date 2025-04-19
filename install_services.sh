#!/bin/bash

# Función para manejar errores
handle_error() {
    echo "Error: $1"
    exit 1
}

# Verificar que se está ejecutando como root
if [ "$EUID" -ne 0 ]; then
    handle_error "Este script debe ejecutarse como root"
fi

# Directorio base del proyecto
PROJECT_DIR="/root/fichar"
VENV_DIR="$PROJECT_DIR/venv"

# Verificar que el directorio del proyecto existe
if [ ! -d "$PROJECT_DIR" ]; then
    handle_error "No se encontró el directorio del proyecto en $PROJECT_DIR"
fi

# Verificar que el entorno virtual existe
if [ ! -d "$VENV_DIR" ]; then
    handle_error "No se encontró el entorno virtual en $VENV_DIR"
fi

# Crear el archivo de servicio para el bot
cat > /etc/systemd/system/checktime-bot.service << EOL
[Unit]
Description=CheckTime Telegram Bot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python -m src.checktime.bot.listener
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=checktime-bot

[Install]
WantedBy=multi-user.target
EOL

# Crear el archivo de servicio para el fichaje
cat > /etc/systemd/system/checktime-fichar.service << EOL
[Unit]
Description=CheckTime Automatic Check-in/Check-out Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python -m src.checktime.main
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=checktime-fichar

[Install]
WantedBy=multi-user.target
EOL

# Recargar configuración de systemd
echo "Recargando configuración de systemd..."
systemctl daemon-reload || handle_error "No se pudo recargar la configuración de systemd"

# Habilitar servicios
echo "Habilitando servicios..."
systemctl enable checktime-bot.service || handle_error "No se pudo habilitar checktime-bot.service"
systemctl enable checktime-fichar.service || handle_error "No se pudo habilitar checktime-fichar.service"

# Iniciar servicios
echo "Iniciando servicios..."
systemctl start checktime-bot.service || handle_error "No se pudo iniciar checktime-bot.service"
systemctl start checktime-fichar.service || handle_error "No se pudo iniciar checktime-fichar.service"

# Verificar estado
echo "Verificando estado de los servicios..."
systemctl status checktime-bot.service
systemctl status checktime-fichar.service

echo "Instalación completada. Los servicios están activos y configurados para iniciarse al arrancar el sistema." 