import os
import subprocess
from fastapi import FastAPI, HTTPException, Header
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
API_KEY = os.getenv("API_KEY_EASY_PANEL", "")

NOTEBOOK = "Argentinian_Macroeconomic_Automatic_Mailing.ipynb"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/run")
def run_notebook(x_api_key: str = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        result = subprocess.run(
            [
                "jupyter", "nbconvert",
                "--to", "notebook",
                "--execute",
                "--inplace",
                "--ExecutePreprocessor.timeout=3600",
                NOTEBOOK,
            ],
            capture_output=True,
            text=True,
            timeout=3700,
            cwd="/app",
        )
        success = result.returncode == 0
        return {
            "success": success,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-3000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timeout: el notebook tardó más de 1 hora")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
