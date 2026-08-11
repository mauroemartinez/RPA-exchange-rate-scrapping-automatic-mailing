# ── base ──────────────────────────────────────────────────────────────────────
# 3.14 para que coincida con el entorno de desarrollo (venv en 3.14.5).
# Se fija la MINOR, no la patch: así entran parches de seguridad sin tocar el
# Dockerfile, y la minor es la que realmente importa para compatibilidad.
FROM python:3.14-slim

# PYTHONUNBUFFERED: que los print salgan al log al instante y no en bloques.
# PYTHONDONTWRITEBYTECODE: no generar .pyc, son basura en una imagen efímera.
# PLAYWRIGHT_BROWSERS_PATH: ruta fija y compartida, para que el navegador quede
#   accesible cuando el proceso deje de correr como root.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# ── dependencias ──────────────────────────────────────────────────────────────
# requirements.txt se copia SOLO (antes que el código) a propósito: Docker cachea
# cada paso, y este es el más lento. Si copiáramos todo junto, cambiar una línea
# de un .py invalidaría la caché y reinstalaría las 100 dependencias de nuevo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --with-deps instala también las librerías de sistema que Chromium necesita.
# Va en su propia capa porque pesa ~400MB y cambia mucho menos que el código.
RUN playwright install --with-deps chromium

# ── usuario sin privilegios ───────────────────────────────────────────────────
# Por defecto un contenedor corre como root. Si alguien logra ejecutar código
# acá adentro, tenerlo como usuario común limita bastante el daño.
RUN useradd --create-home --shell /bin/bash appuser \
 && mkdir -p /app/Previews \
 && chmod -R a+rX /ms-playwright \
 && chown -R appuser:appuser /app

# ── código del proyecto ───────────────────────────────────────────────────────
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Docker reinicia el contenedor si /health deja de responder.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
