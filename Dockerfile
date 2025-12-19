FROM python:3.11-slim

WORKDIR /app

# Install chromium and deps
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    dumb-init \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "drednot_mover.py"]
