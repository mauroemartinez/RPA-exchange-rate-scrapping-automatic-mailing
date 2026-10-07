"""Servicio HTTP que dispara la corrida del reporte.

Expone /health para el healthcheck del contenedor y /run para ejecutar el
pipeline. /run está protegido por API key y no admite corridas simultáneas.
"""

import json
import logging
import os
import secrets
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Se deriva del archivo, no se hardcodea "/app": así el servicio corre igual
# dentro del contenedor y en local para probar.
BASE_DIR = Path(__file__).resolve().parent
PIPELINE = BASE_DIR / "pipeline.py"

TIMEOUT_CORRIDA = 3600

# Sin /docs ni /openapi.json: el servicio solo lo llama un programador, y la
# documentación interactiva le mostraba /run a cualquiera que encontrara la URL.
app = FastAPI(title="Seguimiento Macroeconómico", version="3.0", docs_url=None, redoc_url=None, openapi_url=None)

# Una corrida a la vez. Sin esto, dos POST simultáneos ejecutan el pipeline dos
# veces en paralelo: doble scraping, doble mail y dos INSERT compitiendo por la
# misma fecha. El lock se toma sin bloquear y se rechaza con 409 si está ocupado.
# El pipeline además toma un advisory lock en Supabase, que cubre disparadores
# que no pasan por este proceso.
_lock = threading.Lock()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run_pipeline(x_api_key: str | None = Header(default=None), dry_run: bool = False):
    """Corre pipeline.py y devuelve el estado de cada etapa.

    Con ?dry_run=true scrapea y arma el reporte sin escribir en Supabase, sin
    llamar a Gemini, sin mandar el mail y sin pushear: sirve para probar el
    despliegue de punta a punta.
    """
    # Falla cerrado: si no hay API key configurada, el endpoint no se habilita.
    # La versión anterior hacía `if API_KEY and ...`, o sea que un .env sin la
    # variable dejaba /run abierto a cualquiera.
    # config.py ya convierte una key vacía en None; se chequea igual, porque una
    # key vacía con un header vacío pasaría compare_digest.
    if settings.api_key_easy_panel is None or not settings.api_key_easy_panel.get_secret_value().strip():
        logger.error("API_KEY_EASY_PANEL no está configurada; /run deshabilitado")
        raise HTTPException(status_code=503, detail="Servicio no configurado")

    # compare_digest tarda lo mismo acierte o no, así el tiempo de respuesta no
    # deja adivinar la key de a un carácter.
    esperada = settings.api_key_easy_panel.get_secret_value().encode()
    if x_api_key is None or not secrets.compare_digest(x_api_key.encode(), esperada):
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not _lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Ya hay una corrida en curso")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            archivo_json = Path(tmp) / "resultado.json"
            comando = [sys.executable, str(PIPELINE), "--origen", "api", "--json", str(archivo_json)]
            if dry_run:
                # La vista previa queda adentro de la carpeta temporal y se borra con ella
                comando += ["--dry-run", "--salida", str(Path(tmp) / "vista-previa")]

            logger.info("Iniciando la corrida%s", " (dry-run)" if dry_run else "")
            # Proceso aparte y no una llamada en este mismo proceso, por dos motivos:
            # el timeout puede matar una corrida colgada (a un hilo no se lo puede
            # matar) y cada corrida arranca limpia, sin estado de matplotlib ni
            # memoria de la anterior, igual que cuando se ejecutaba el notebook.
            # La salida no se captura: el log del pipeline va directo al del contenedor.
            result = subprocess.run(
                comando,
                timeout=TIMEOUT_CORRIDA,
                cwd=BASE_DIR,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            resultado = json.loads(archivo_json.read_text(encoding="utf-8")) if archivo_json.exists() else None

        exito = result.returncode == 0
        if exito:
            logger.info("Corrida terminada: %s", resultado["estado"] if resultado else "sin resumen")
        else:
            # El detalle queda en el log del pipeline, no en la respuesta HTTP: un
            # mensaje de error puede arrastrar la connection string o una API key.
            logger.error("La corrida terminó con código %s", result.returncode)

        respuesta = {"success": exito, "returncode": result.returncode}
        if resultado:
            respuesta["estado"] = resultado["estado"]
            respuesta["etapas"] = [
                {"nombre": e["nombre"], "estado": e["estado"], "segundos": e["segundos"]}
                for e in resultado["etapas"]
            ]
        return respuesta

    except subprocess.TimeoutExpired:
        logger.error("Timeout: la corrida superó %s segundos", TIMEOUT_CORRIDA)
        raise HTTPException(status_code=504, detail="Timeout: la corrida tardó más de una hora") from None

    except Exception as exc:
        logger.exception("Error inesperado ejecutando la corrida")
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}") from exc

    finally:
        _lock.release()
