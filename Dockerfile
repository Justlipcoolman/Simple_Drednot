FROM python:3.11-slim

WORKDIR /app

# Install chromium, driver, and dumb-init
# rm -rf cleans cache to reduce image size
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    dumb-init \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# dumb-init prevents zombie processes
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["python", "drednot_mover.py"]
