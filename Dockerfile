FROM python:3.11-alpine

# Set environment variables for real-time logging and Chrome
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium-browser
ENV CHROME_PATH=/usr/lib/chromium/

WORKDIR /app

# Install Chromium, Driver, and essential fonts for Alpine
RUN apk add --no-cache \
    chromium \
    chromium-chromedriver \
    dumb-init \
    freetype \
    harfbuzz \
    nss \
    ttf-freefont

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "drednot_mover.py"]
