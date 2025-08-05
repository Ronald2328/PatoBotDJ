FROM eclipse-temurin:17-jre-focal

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV LAVALINK_VERSION=4.0.7
RUN curl -L https://github.com/lavalink-devs/Lavalink/releases/download/${LAVALINK_VERSION}/Lavalink.jar -o Lavalink.jar

COPY application.yml .
COPY requirements.txt .
COPY musicbot.py .
COPY start.sh .

RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install --no-cache-dir -r requirements.txt

RUN chmod +x start.sh

EXPOSE 2333 8080

CMD ["./start.sh"]