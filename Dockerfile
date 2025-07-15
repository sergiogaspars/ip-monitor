FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY main.py .

# Crear directorio para datos persistentes
RUN mkdir -p /data

# Crear usuario no privilegiado
RUN useradd --create-home --shell /bin/bash app \
  && chown -R app:app /app /data

# Cambiar a usuario no privilegiado
USER app

# Configurar variables de entorno por defecto
ENV CHECK_INTERVAL=300
ENV PYTHONUNBUFFERED=1

# Comando por defecto
CMD ["python", "main.py"]
