# Configuración
IMAGE_NAME=ghcr.io/gonzalez8/checktime
PLATFORM=linux/amd64

# Si quieres especificar otra ruta o Dockerfile puedes extender aquí
DOCKERFILE=Dockerfile

# Obtiene automáticamente el último tag
TAG=$(shell git describe --tags --abbrev=0)

# 🔵 Build para develop
publish-develop:
	docker-compose -f docker-compose.develop.yml down && docker-compose -f docker-compose.develop.yml build --no-cache && docker-compose -f docker-compose.develop.yml up

# 🔵 Build para latest
build-latest:
	docker buildx build --platform $(PLATFORM) -t $(IMAGE_NAME):latest .

# 🔵 Push para latest
push-latest:
	docker push $(IMAGE_NAME):latest

# 🔵 Build para release con el último tag (por ejemplo v1.0.0)
build-release:
	docker buildx build --platform $(PLATFORM) -t $(IMAGE_NAME):$(TAG) .

# 🔵 Push para release
push-release:
	docker push $(IMAGE_NAME):$(TAG)

# 🔵 Build + Push de latest de un tirón
publish-latest: build-latest push-latest

# 🔵 Build + Push de release (etiquetado por tag) de un tirón
publish-release: build-release push-release
