# ── base ─────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── system deps + headless Chrome ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg unzip ca-certificates fonts-liberation \
    libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# ── env: Chrome sin sandbox (requerido en Docker) ────────────────────────────
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV WDM_LOCAL=1
ENV PYTHONUNBUFFERED=1

# ── dependencias Python ───────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir fastapi uvicorn nbconvert

# ── código del proyecto ───────────────────────────────────────────────────────
COPY . .

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
