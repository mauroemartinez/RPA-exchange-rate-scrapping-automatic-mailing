"""Servicio HTTP que dispara la corrida del reporte.

Expone /health para el healthcheck del contenedor y /run para ejecutar el
notebook. /run está protegido por API key y no admite corridas simultáneas.
"""

import logging
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Se deriva del archivo, no se hardcodea "/app": así el servicio corre igual
# dentro del contenedor y en local para probar.
BASE_DIR = Path(__file__).resolve().parent
NOTEBOOK = BASE_DIR / "Argentinian_Macroeconomic_Automatic_Mailing.ipynb"

TIMEOUT_NOTEBOOK = 3600
TIMEOUT_PROCESO = TIMEOUT_NOTEBOOK + 100

app = FastAPI(title="Seguimiento Macroeconómico", version="2.0")

# Una corrida a la vez. Sin esto, dos POST simultáneos ejecutan el notebook dos
# veces en paralelo: doble scraping, doble mail y dos INSERT compitiendo por la
# misma fecha. El lock se toma sin bloquear y se rechaza con 409 si está ocupado.
_lock = threading.Lock()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run_notebook(x_api_key: str | None = Header(default=None)):
    # Falla cerrado: si no hay API key configurada, el endpoint no se habilita.
    # La versión anterior hacía `if API_KEY and ...`, o sea que un .env sin la
    # variable dejaba /run abierto a cualquiera.
    if settings.api_key_easy_panel is None:
        logger.error("API_KEY_EASY_PANEL no está configurada; /run deshabilitado")
        raise HTTPException(status_code=503, detail="Servicio no configurado")

    if x_api_key != settings.api_key_easy_panel.get_secret_value():
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not _lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Ya hay una corrida en curso")

    try:
        logger.info("Iniciando ejecución del notebook")
        result = subprocess.run(
            [
                "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                # Se escribe a /tmp en vez de --inplace: el notebook del repo no
                # se modifica, y así la imagen puede ser de solo lectura.
                "--output", "/tmp/ejecutado.ipynb",
                f"--ExecutePreprocessor.timeout={TIMEOUT_NOTEBOOK}",
                str(NOTEBOOK),
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_PROCESO,
            cwd=BASE_DIR,
        )
        exito = result.returncode == 0

        if exito:
            logger.info("Notebook ejecutado correctamente")
        else:
            # El detalle va al log del servidor, no a la respuesta HTTP: un
            # traceback puede arrastrar la connection string o una API key.
            logger.error("Falló la ejecución (rc=%s): %s", result.returncode, result.stderr[-3000:])

        return {"success": exito, "returncode": result.returncode}

    except subprocess.TimeoutExpired:
        logger.error("Timeout: el notebook superó %s segundos", TIMEOUT_PROCESO)
        raise HTTPException(status_code=504, detail="Timeout: el notebook tardó más de una hora")

    except Exception as exc:
        logger.exception("Error inesperado ejecutando el notebook")
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}") from exc

    finally:
        _lock.release()
