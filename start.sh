#!/bin/bash

# Colores para los logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}[SISTEMA] Iniciando servicios...${NC}"

# Iniciar Lavalink en background
echo -e "${YELLOW}[LAVALINK] Iniciando servidor...${NC}"
java -Xmx400m -jar Lavalink.jar &
LAVALINK_PID=$!

# Función para verificar si Lavalink está listo
check_lavalink() {
    curl -s http://localhost:2333/version > /dev/null 2>&1
}

# Esperar hasta que Lavalink responda
echo -e "${YELLOW}[LAVALINK] Esperando que esté listo...${NC}"
COUNTER=0
while ! check_lavalink; do
    sleep 2
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt 30 ]; then
        echo -e "${RED}[ERROR] Lavalink no inició después de 60 segundos${NC}"
        exit 1
    fi
done

echo -e "${GREEN}[LAVALINK] ¡Servidor listo!${NC}"

# Configurar variables para conexión local
export LAVALINK_HOST=localhost
export LAVALINK_PORT=2333

# Iniciar el bot de Discord
echo -e "${YELLOW}[BOT] Iniciando bot de Discord...${NC}"
python3 musicbot.py &
BOT_PID=$!

# Función para manejar el cierre
cleanup() {
    echo -e "${RED}[SISTEMA] Recibida señal de cierre...${NC}"
    kill $BOT_PID 2>/dev/null
    kill $LAVALINK_PID 2>/dev/null
    exit
}

# Capturar señales de cierre
trap cleanup SIGINT SIGTERM

# Mantener el script corriendo
echo -e "${GREEN}[SISTEMA] Todos los servicios iniciados${NC}"
wait $BOT_PID