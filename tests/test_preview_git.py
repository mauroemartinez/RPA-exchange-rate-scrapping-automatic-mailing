"""preview_git contra repos de git reales en carpetas temporales (con un remoto bare)."""

import os
import shutil
import subprocess

import pytest

import preview_git

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture(autouse=True)
def git_aislado(monkeypatch):
    """Sin la config global ni la del sistema: un commit.gpgsign o un hook del desarrollador no cuentan."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


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


def test_sin_git_instalado_se_omite(monkeypatch, tmp_path):
    def run(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(preview_git.subprocess, "run", run)
    assert preview_git.actualizar_previews(tmp_path) == (False, "git no está instalado: se omite")


def test_publicar_presentacion_deja_un_solo_commit_con_el_ultimo(repo):
    local, remoto = repo
    deck = local / "Previews" / "Reporte Ejecutivo.pptx"
    rama = preview_git.RAMA_PRESENTACION

    deck.write_bytes(b"deck del lunes")
    assert preview_git.publicar_presentacion(local, deck, mensaje="Reporte ejecutivo del 05/10/2026")[0] is True
    deck.write_bytes(b"deck del martes")
    hecho, detalle = preview_git.publicar_presentacion(local, deck, mensaje="Reporte ejecutivo del 06/10/2026")

    assert hecho is True and rama in detalle
    # Un solo commit, sin historia: el de ayer no quedó acumulado
    assert _git(remoto, "rev-list", "--count", rama).strip() == "1"
    assert _git(remoto, "ls-tree", "--name-only", rama).splitlines() == ["Reporte Ejecutivo.pptx"]
    assert _git(remoto, "show", f"{rama}:Reporte Ejecutivo.pptx") == "deck del martes"
    assert _git(remoto, "log", "-1", "--format=%s|%an", rama).strip() == "Reporte ejecutivo del 06/10/2026|Test"
    # main, la carpeta de trabajo y el stage no se tocaron
    assert _git(remoto, "log", "-1", "--format=%s", "main").strip() == "inicial"
    # (git entrecomilla las rutas con espacios)
    assert _git(local, "status", "--porcelain", "--", "Previews").strip() == '?? "Previews/Reporte Ejecutivo.pptx"'


def test_publicar_presentacion_fuera_de_main_no_publica(repo):
    local, remoto = repo
    _git(local, "checkout", "-b", "roadmap")
    deck = local / "Previews" / "Reporte Ejecutivo.pptx"
    deck.write_bytes(b"deck")
    hecho, detalle = preview_git.publicar_presentacion(local, deck)
    assert hecho is False and "roadmap" in detalle
    assert preview_git.RAMA_PRESENTACION not in _git(remoto, "branch", "--list")


def test_publicar_presentacion_con_push_fallido_levanta(repo, tmp_path):
    local, _ = repo
    _git(local, "remote", "set-url", "origin", str(tmp_path / "no-existe.git"))
    deck = local / "Previews" / "Reporte Ejecutivo.pptx"
    deck.write_bytes(b"deck")
    with pytest.raises(preview_git.GitError):
        preview_git.publicar_presentacion(local, deck)


def test_un_grafico_que_no_existe_no_rompe_el_commit(repo):
    local, remoto = repo
    (local / "Previews" / "grafico.jpg").write_bytes(b"v2")

    hecho, _ = preview_git.actualizar_previews(local, archivos=["grafico.jpg", "nuevo_que_fallo.jpg"])

    assert hecho is True
    assert _git(remoto, "show", "--name-only", "--format=", "HEAD").split() == ["Previews/grafico.jpg"]


def test_si_main_avanzo_durante_la_corrida_se_trae_y_se_reintenta(repo, tmp_path):
    local, remoto = repo
    # Otro clon pushea a main mientras corre el reporte (un merge, por ejemplo)
    otro = tmp_path / "otro"
    subprocess.run(["git", "clone", str(remoto), str(otro)], check=True, capture_output=True)
    _git(otro, "config", "user.name", "Otro")
    _git(otro, "config", "user.email", "otro@example.com")
    (otro / "otro.txt").write_text("cambio de otro lado")
    _git(otro, "commit", "-am", "cambio de otro lado")
    _git(otro, "push")

    (local / "Previews" / "grafico.jpg").write_bytes(b"v2")
    hecho, _ = preview_git.actualizar_previews(local)

    assert hecho is True
    asuntos = _git(remoto, "log", "--format=%s", "-3").splitlines()
    assert asuntos[:2] == [preview_git.MENSAJE, "cambio de otro lado"]


def test_la_fecha_de_un_grafico_es_la_de_su_commit_salvo_que_tenga_cambios(repo):
    import datetime as dt
    import os as so

    local, _ = repo
    ruta = local / "Previews" / "grafico.jpg"
    # Commiteado y sin cambios: la fecha del commit, aunque el archivo se haya tocado hoy (como hace git pull)
    _git(local, "commit", "--allow-empty", "-m", "x")
    hoy = dt.date.today()
    so.utime(ruta, (dt.datetime(2020, 1, 1).timestamp(),) * 2)
    assert preview_git.fecha_del_archivo(local, ruta) == hoy
    # Con cambios sin commitear: la fecha de modificación
    ruta.write_bytes(b"generado en esta PC")
    so.utime(ruta, (dt.datetime(2026, 1, 15, 12).timestamp(),) * 2)
    assert preview_git.fecha_del_archivo(local, ruta) == dt.date(2026, 1, 15)
