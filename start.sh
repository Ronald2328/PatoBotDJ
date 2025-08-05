#!/bin/bash

echo "[SISTEMA] Iniciando servicios..."

java -Xmx400m -jar Lavalink.jar &
LAVALINK_PID=$!

check_lavalink() {
    curl -s http://localhost:2333/version > /dev/null 2>&1
}

echo "[LAVALINK] Esperando que esté listo..."
COUNTER=0
while ! check_lavalink; do
    sleep 2
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt 30 ]; then
        echo "[ERROR] Lavalink no inició después de 60 segundos"
        exit 1
    fi
done

echo "[LAVALINK] ¡Servidor listo!"

export LAVALINK_HOST=localhost
export LAVALINK_PORT=2333

echo "[BOT] Iniciando bot de Discord..."
python3 musicbot.py &
BOT_PID=$!

cleanup() {
    echo "[SISTEMA] Cerrando servicios..."
    kill $BOT_PID 2>/dev/null
    kill $LAVALINK_PID 2>/dev/null
    exit
}

trap cleanup SIGINT SIGTERM

echo "[SISTEMA] Todos los servicios iniciados"
wait $BOT_PID