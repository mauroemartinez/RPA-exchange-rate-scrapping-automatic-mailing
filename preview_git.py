"""Commit y push de los gráficos de Previews/ (celda 49 del notebook) y publicación del PowerPoint.

La celda corría git sin mirar el código de salida: si el commit o el push fallaban,
igual imprimía "Previews actualizado en GitHub", y en el contenedor (sin .git ni
git instalado) informaba "No hubo cambios". Acá cada comando se chequea.

El PowerPoint no se commitea en main: cada versión diaria quedaría para siempre en
el historial. Va solo, en su propia rama, que se reemplaza entera cada día.
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
# Rama de GitHub que guarda solo el último PowerPoint. Se pisa en cada publicación.
RAMA_PRESENTACION = "reporte-ejecutivo"


class GitError(RuntimeError):
    """Un comando de git terminó con código distinto de cero."""


def _git(repo: Path, *args: str, entrada: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], input=entrada, capture_output=True, text=True, timeout=120
    )
    if proc.returncode != 0:
        salida = (proc.stderr or proc.stdout).strip()
        raise GitError(f"git {' '.join(args)} terminó con código {proc.returncode}: {salida}")
    return proc.stdout


def _motivo_para_no_tocar_git(repo: Path, rama: str) -> str | None:
    """Por qué no corresponde usar git acá (sin git, sin repo, otra rama), o None si corresponde."""
    try:
        _git(repo, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return "git no está instalado: se omite"
    except GitError:
        return f"{repo} no es un repo git (por ejemplo, el contenedor): se omite"

    actual = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if actual != rama:
        return f"la rama actual es '{actual}' y no '{rama}': no se commitea"
    return None


def actualizar_previews(
    repo: Path, archivos: list[str] | None = None, carpeta: str = CARPETA, rama: str = RAMA
) -> tuple[bool, str]:
    """Commitea y pushea los cambios de `archivos` dentro de `carpeta`. Devuelve (hizo_algo, detalle).

    Con `archivos`, solo esos: el repo es público y un archivo que cayó en la
    carpeta por error (una vista previa del mail, por ejemplo) no tiene que
    publicarse. Sin `archivos`, toda la carpeta, como la celda 49.

    Levanta GitError si falla un comando cuando sí correspondía correrlo. Los casos
    en que no corresponde (sin git, sin repo, otra rama, sin cambios) no son error.
    """
    motivo = _motivo_para_no_tocar_git(repo, rama)
    if motivo:
        return False, motivo

    # Solo los que existen: `git add` de una ruta inexistente y sin trackear sale con
    # error, y el primer día de un gráfico nuevo que falla pondría la etapa en rojo
    rutas = [f"{carpeta}/{a}" for a in archivos if (Path(repo) / carpeta / a).exists()] if archivos else [carpeta]
    if not rutas:
        return False, f"ninguno de los archivos está en {carpeta}"
    if not _git(repo, "status", "--porcelain", "--", *rutas).strip():
        return False, f"sin cambios en {carpeta}"

    _git(repo, "add", "--", *rutas)
    # Con las rutas al final, el commit lleva solo esos archivos aunque haya otras
    # cosas en el stage. La celda hacía un `git commit` a secas.
    _git(repo, "commit", "-m", MENSAJE, "--", *rutas)
    _git(repo, "push")
    log.info("Previews actualizado en GitHub")
    return True, "Previews actualizado en GitHub"


def publicar_presentacion(
    repo: Path, archivo: Path, mensaje: str = "Reporte ejecutivo",
    rama_destino: str = RAMA_PRESENTACION, rama: str = RAMA,
) -> tuple[bool, str]:
    """Deja `archivo` como único contenido de la rama `rama_destino` en GitHub. Devuelve (hizo_algo, detalle).

    Arma un commit sin padres que tiene solo ese archivo y lo pushea con --force:
    la rama queda siempre con un único commit, así que el PowerPoint se reemplaza
    y las versiones viejas no se acumulan en el historial del repo. No toca la
    carpeta de trabajo, el stage ni main. Mismas condiciones que actualizar_previews.
    """
    motivo = _motivo_para_no_tocar_git(repo, rama)
    if motivo:
        return False, motivo

    blob = _git(repo, "hash-object", "-w", "--", str(archivo)).strip()
    # -z: la entrada se separa con NUL. Con un salto de línea, Windows lo escribe
    # como CRLF y el nombre del archivo en la rama terminaría con un retorno de carro
    arbol = _git(repo, "mktree", "-z", entrada=f"100644 blob {blob}\t{archivo.name}\0").strip()
    commit = _git(repo, "commit-tree", arbol, "-m", mensaje).strip()
    _git(repo, "push", "--force", "origin", f"{commit}:refs/heads/{rama_destino}")
    log.info("%s publicado en la rama %s", archivo.name, rama_destino)
    return True, f"{archivo.name} publicado en la rama {rama_destino}"
