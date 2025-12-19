FROM python:3.11-slim

# Set environment variable for real-time logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Chromium and the specific libraries needed for stable headless operation
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    dumb-init \
    libnss3 \
    libgconf-2-4 \
    fonts-liberation \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
# Increase the memory limit for the container if possible in Render settings
CMD ["python", "drednot_mover.py"]
