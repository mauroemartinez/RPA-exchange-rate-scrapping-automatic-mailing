"""Genera los íconos PNG de la presentación (reporte/recursos/) a partir de SVG, con Chromium.

PowerPoint no muestra bien los SVG en todas sus versiones, así que la presentación
usa PNG. Se corren una sola vez y quedan en el repo; volver a correrlo solo hace
falta para cambiar un ícono.

Uso: python iconos_presentacion.py

El de GlobalAIze es provisorio (una G sobre el degradé de la marca) hasta tener
el logo: si existe reporte/recursos/globalaize_logo.png, la presentación usa ese.
"""

import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))  # para importar construir.py, el del diagrama
DESTINO = DIR.parent.parent / "reporte" / "recursos"
LADO = 256


def _github() -> str:
    svg = (DIR / "iconos" / "si_github.svg").read_text(encoding="utf-8")
    camino = re.search(r'<path d="([^"]+)"', svg).group(1)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-3 -3 30 30">'
        f'<circle cx="12" cy="12" r="15" fill="#24292E"/><path d="{camino}" fill="#FFFFFF"/></svg>'
    )


ICONOS = {
    "github.png": _github(),
    "linkedin.png": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<rect width="100" height="100" rx="18" fill="#0A66C2"/>'
        '<text x="50" y="74" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" '
        'font-size="62" fill="#FFFFFF">in</text></svg>'
    ),
    "globalaize.png": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs>'
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#163A6B"/>'
        '<stop offset="1" stop-color="#081E40"/></linearGradient></defs>'
        '<circle cx="50" cy="50" r="50" fill="url(#g)"/>'
        '<text x="50" y="70" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" '
        'font-size="58" fill="#FFFFFF">G</text></svg>'
    ),
    "bitcoin.png": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<circle cx="50" cy="50" r="48" fill="#F7931A"/><circle cx="50" cy="50" r="42" fill="none" '
        'stroke="#FFFFFF" stroke-opacity=".35" stroke-width="2"/>'
        '<text x="50" y="70" text-anchor="middle" font-family="Segoe UI Symbol, Segoe UI, Arial, sans-serif" '
        'font-weight="700" font-size="58" fill="#FFFFFF" transform="rotate(14 50 50)">₿</text></svg>'
    ),
}


# Las tecnologías del proyecto, para el pie de la portada: los mismos logos del diagrama
# de arquitectura (construir.py). Quedan en reporte/recursos/tecnologias/.
def _tecnologias() -> dict[str, str]:
    import construir as c

    return {
        "python": c.dev("python"), "playwright": c.dev("playwright"), "pandas": c.dev("pandas"),
        "pydantic": c.si("pydantic", "#E92063"), "sqlalchemy": c.dev("sqlalchemy"),
        "postgresql": c.dev("postgresql"), "supabase": c.dev("supabase"), "gemini": c.GEMINI,
        "matplotlib": c.dev("matplotlib"), "seaborn": c.SEABORN, "jinja": c.si("jinja", "#081E40"),
        "powerpoint": c.si("microsoftpowerpoint", "#B7472A"), "githubactions": c.dev("githubactions"),
        "pytest": c.dev("pytest"), "fastapi": c.dev("fastapi"), "docker": c.dev("docker"),
    }


def _logo_redondeado() -> None:
    """El logo de GlobalAIze con las esquinas redondeadas, como los íconos de LinkedIn, para la fila de links."""
    from PIL import Image, ImageDraw

    origen = DESTINO / "globalaize_logo.png"
    if not origen.exists():
        return
    with Image.open(origen) as im:
        logo = im.convert("RGBA").resize((LADO, LADO), Image.LANCZOS)
    mascara = Image.new("L", (LADO, LADO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, LADO - 1, LADO - 1), radius=int(LADO * 0.18), fill=255)
    logo.putalpha(mascara)
    logo.save(DESTINO / "globalaize_logo_redondeado.png")
    print("globalaize_logo_redondeado.png")


def main() -> None:
    from playwright.sync_api import sync_playwright

    DESTINO.mkdir(parents=True, exist_ok=True)
    _logo_redondeado()
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            pagina = navegador.new_page(viewport={"width": LADO, "height": LADO})
            for nombre, svg in ICONOS.items():
                svg = svg.replace("<svg ", f'<svg width="{LADO}" height="{LADO}" ', 1)
                pagina.set_content(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
                pagina.screenshot(path=str(DESTINO / nombre), omit_background=True,
                                  clip={"x": 0, "y": 0, "width": LADO, "height": LADO})
                print(nombre)
            carpeta = DESTINO / "tecnologias"
            carpeta.mkdir(exist_ok=True)
            for nombre, uri in _tecnologias().items():
                pagina.set_content(
                    f'<html><body style="margin:0;background:transparent"><img src="{uri}" '
                    f'style="width:{LADO}px;height:{LADO}px;object-fit:contain;display:block"></body></html>'
                )
                pagina.wait_for_timeout(50)
                pagina.screenshot(path=str(carpeta / f"{nombre}.png"), omit_background=True,
                                  clip={"x": 0, "y": 0, "width": LADO, "height": LADO})
                print("tecnologias/" + nombre)
        finally:
            navegador.close()


if __name__ == "__main__":
    main()
