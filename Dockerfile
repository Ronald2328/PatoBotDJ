FROM eclipse-temurin:17-jre-focal

# Instalar Python y dependencias
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Descargar Lavalink
ENV LAVALINK_VERSION=4.0.7
RUN curl -L https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink.jar -o Lavalink.jar

# Copiar archivos de configuración
COPY application.yml .
COPY requirements.txt .
COPY musicbot.py .
COPY start.sh .

# Instalar dependencias de Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Hacer ejecutable el script
RUN chmod +x start.sh

# Puerto para health checks (opcional)
EXPOSE 2333

# Ejecutar el script de inicio
CMD ["./start.sh"]