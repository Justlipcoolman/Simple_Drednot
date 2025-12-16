# Use Alpine Linux (Tiny OS) to save RAM
FROM python:3.11-alpine

WORKDIR /app

# Install Chromium and dependencies on Alpine
# Alpine's chromium package is highly optimized
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    dumb-init \
    libstdc++

# Copy requirements
COPY requirements.txt .

# Install python deps
# We don't need compilation tools for these specific packages
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use dumb-init to handle signals
ENTRYPOINT ["dumb-init", "--"]

CMD ["python", "drednot_mover.py"]