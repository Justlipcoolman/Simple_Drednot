# Use minimal Python on Debian Bullseye
FROM python:3.9-slim-bullseye

# No cache to keep image small
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Chromium and Driver manually
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY drednot_mover.py .

# Healthcheck for Render
HEALTHCHECK CMD curl --fail http://localhost:8080/ || exit 1

CMD ["python", "drednot_mover.py"]
