#!/bin/bash

# Función para manejar errores
handle_error() {
    echo "Error: $1"
    exit 1
}

# Verificar que Docker está instalado
if ! command -v docker &> /dev/null; then
    handle_error "Docker no está instalado. Por favor, instale Docker primero."
fi

# Verificar que Docker Compose está instalado
if ! command -v docker-compose &> /dev/null; then
    handle_error "Docker Compose no está instalado. Por favor, instale Docker Compose primero."
fi

# Verificar que el archivo .env existe
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creando archivo .env a partir de .env.example..."
        cp .env.example .env
        echo "Por favor, edite el archivo .env con sus credenciales antes de continuar."
        exit 0
    else
        handle_error "No se encontró el archivo .env ni .env.example"
    fi
fi

# Construir y levantar los contenedores
echo "Construyendo y levantando los contenedores..."
docker-compose up -d --build || handle_error "Error al construir y levantar los contenedores"

# Verificar que los contenedores están corriendo
echo "Verificando estado de los contenedores..."
docker-compose ps

echo "Instalación completada. Los servicios están activos y configurados para iniciarse automáticamente."
echo "Para ver los logs, use: docker-compose logs -f"
echo "Para detener los servicios, use: docker-compose down" 