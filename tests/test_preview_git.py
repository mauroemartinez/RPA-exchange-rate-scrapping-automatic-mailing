"""preview_git contra repos de git reales en carpetas temporales (con un remoto bare)."""

import shutil
import subprocess

import pytest

import preview_git

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    remoto = tmp_path / "remoto.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(remoto)], check=True, capture_output=True)
    local = tmp_path / "local"
    subprocess.run(["git", "clone", str(remoto), str(local)], check=True, capture_output=True)
    _git(local, "config", "user.name", "Test")
    _git(local, "config", "user.email", "test@example.com")
    (local / "Previews").mkdir()
    (local / "Previews" / "grafico.jpg").write_bytes(b"v1")
    (local / "otro.txt").write_text("v1")
    _git(local, "add", ".")
    _git(local, "commit", "-m", "inicial")
    _git(local, "branch", "-M", "main")
    _git(local, "push", "-u", "origin", "main")
    return local, remoto


def test_sin_cambios_no_hace_nada(repo):
    local, _ = repo
    assert preview_git.actualizar_previews(local) == (False, "sin cambios en Previews")


def test_commitea_y_pushea_solo_previews(repo):
    local, remoto = repo
    (local / "Previews" / "grafico.jpg").write_bytes(b"v2")
    (local / "otro.txt").write_text("v2")
    _git(local, "add", "otro.txt")  # algo ajeno en el stage

    hecho, detalle = preview_git.actualizar_previews(local)

    assert hecho is True
    assert _git(remoto, "log", "-1", "--format=%s").strip() == preview_git.MENSAJE
    assert _git(remoto, "show", "--name-only", "--format=", "HEAD").split() == ["Previews/grafico.jpg"]
    assert "otro.txt" in _git(local, "diff", "--cached", "--name-only")  # sigue en el stage, sin commitear


def test_en_otra_rama_no_commitea(repo):
    local, _ = repo
    _git(local, "checkout", "-b", "roadmap")
    (local / "Previews" / "grafico.jpg").write_bytes(b"v2")
    hecho, detalle = preview_git.actualizar_previews(local)
    assert hecho is False and "roadmap" in detalle


def test_fuera_de_un_repo_se_omite(tmp_path):
    hecho, detalle = preview_git.actualizar_previews(tmp_path)
    assert hecho is False and "no es un repo" in detalle


def test_un_push_que_falla_levanta(repo, tmp_path):
    local, _ = repo
    _git(local, "remote", "set-url", "origin", str(tmp_path / "no-existe.git"))
    (local / "Previews" / "grafico.jpg").write_bytes(b"v3")
    with pytest.raises(preview_git.GitError):
        preview_git.actualizar_previews(local)


def test_con_archivos_solo_commitea_esos(repo):
    local, remoto = repo
    (local / "Previews" / "grafico.jpg").write_bytes(b"v2")
    (local / "Previews" / "mail.eml").write_text("vista previa del mail")

    hecho, _ = preview_git.actualizar_previews(local, archivos=["grafico.jpg"])

    assert hecho is True
    assert _git(remoto, "show", "--name-only", "--format=", "HEAD").split() == ["Previews/grafico.jpg"]
    assert "mail.eml" in _git(local, "status", "--porcelain")  # quedó afuera del commit
