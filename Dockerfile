FROM debian:trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    HOME=/tmp \
    RECOLL_CONFDIR=/home/uiharu/.recoll-novel \
    RECOLL_WEBUI_DB_PATH=/var/lib/recoll-webui/app.sqlite3 \
    RECOLL_TMPDIR=/tmp

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates python3 python3-venv python3-recoll recollcmd \
       file unzip poppler-utils 7zip libreoffice-writer tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv --system-site-packages /opt/venv

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && python -c "from recoll import recoll, rclextract, rclconfig"

COPY . .
RUN chmod -R a+rX /app \
    && install -d -o 1000 -g 1000 -m 700 /var/lib/recoll-webui

USER 1000:1000
EXPOSE 8080
CMD ["python", "webui-standalone.py", "-a", "0.0.0.0", "-p", "8080"]
