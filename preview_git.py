"""Commit y push de los gráficos de Previews/ (celda 49 del notebook).

La celda corría git sin mirar el código de salida: si el commit o el push fallaban,
igual imprimía "Previews actualizado en GitHub", y en el contenedor (sin .git ni
git instalado) informaba "No hubo cambios". Acá cada comando se chequea.
"""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

CARPETA = "Previews"
# Solo se commitea desde main: corriendo el pipeline en otra rama para probarla,
# los gráficos del día no tienen que terminar mezclados en esa rama.
RAMA = "main"
MENSAJE = "Automatic previews update"


class GitError(RuntimeError):
    """Un comando de git terminó con código distinto de cero."""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        salida = (proc.stderr or proc.stdout).strip()
        raise GitError(f"git {' '.join(args)} terminó con código {proc.returncode}: {salida}")
    return proc.stdout


def actualizar_previews(repo: Path, carpeta: str = CARPETA, rama: str = RAMA) -> tuple[bool, str]:
    """Commitea y pushea los cambios de `carpeta`. Devuelve (hizo_algo, detalle).

    Levanta GitError si falla un comando cuando sí correspondía correrlo. Los casos
    en que no corresponde (sin git, sin repo, otra rama, sin cambios) no son error.
    """
    try:
        _git(repo, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return False, "git no está instalado: se omite"
    except GitError:
        return False, f"{repo} no es un repo git (por ejemplo, el contenedor): se omite"

    actual = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if actual != rama:
        return False, f"la rama actual es '{actual}' y no '{rama}': no se commitea"

    if not _git(repo, "status", "--porcelain", "--", carpeta).strip():
        return False, f"sin cambios en {carpeta}"

    _git(repo, "add", "--", carpeta)
    # Con la ruta al final, el commit lleva solo Previews/ aunque haya otras cosas
    # en el stage. La celda hacía un `git commit` a secas.
    _git(repo, "commit", "-m", MENSAJE, "--", carpeta)
    _git(repo, "push")
    log.info("Previews actualizado en GitHub")
    return True, "Previews actualizado en GitHub"
