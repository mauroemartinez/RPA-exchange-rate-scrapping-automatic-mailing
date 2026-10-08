"""Genera los íconos PNG de la presentación (reporte/recursos/) a partir de SVG, con Chromium.

PowerPoint no muestra bien los SVG en todas sus versiones, así que la presentación
usa PNG. Se corren una sola vez y quedan en el repo; volver a correrlo solo hace
falta para cambiar un ícono.

Uso: python iconos_presentacion.py

El de Globalaize es provisorio (una G sobre el degradé de la marca) hasta tener
el logo: si existe reporte/recursos/globalaize_logo.png, la presentación usa ese.
"""

import re
from pathlib import Path

DIR = Path(__file__).resolve().parent
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
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F39C12"/>'
        '<stop offset="1" stop-color="#E67E22"/></linearGradient></defs>'
        '<circle cx="50" cy="50" r="50" fill="url(#g)"/>'
        '<text x="50" y="70" text-anchor="middle" font-family="Arial, sans-serif" font-weight="700" '
        'font-size="58" fill="#1A252F">G</text></svg>'
    ),
    # Comercio exterior: un globo con una ruta entre dos puertos, en los colores de Globalaize
    "comex.png": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<circle cx="50" cy="50" r="48" fill="#FFFFFF"/>'
        '<g fill="none" stroke="#081E40" stroke-width="2.6" stroke-linecap="round">'
        '<circle cx="50" cy="50" r="34"/><ellipse cx="50" cy="50" rx="14" ry="34"/>'
        '<path d="M16 50H84M21 33H79M21 67H79"/></g>'
        '<path d="M24 64 C 34 22, 66 22, 77 38" fill="none" stroke="#F39C12" stroke-width="4" '
        'stroke-dasharray="6 4" stroke-linecap="round"/>'
        '<path d="M70 33 L79 39 L69 42 Z" fill="#F39C12"/>'
        '<circle cx="24" cy="64" r="5" fill="#F39C12" stroke="#FFFFFF" stroke-width="2"/>'
        '<circle cx="79" cy="40" r="3" fill="#081E40"/></svg>'
    ),
    "bitcoin.png": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<circle cx="50" cy="50" r="48" fill="#F7931A"/><circle cx="50" cy="50" r="42" fill="none" '
        'stroke="#FFFFFF" stroke-opacity=".35" stroke-width="2"/>'
        '<text x="50" y="70" text-anchor="middle" font-family="Segoe UI Symbol, Segoe UI, Arial, sans-serif" '
        'font-weight="700" font-size="58" fill="#FFFFFF" transform="rotate(14 50 50)">₿</text></svg>'
    ),
}


def main() -> None:
    from playwright.sync_api import sync_playwright

    DESTINO.mkdir(parents=True, exist_ok=True)
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
        finally:
            navegador.close()


if __name__ == "__main__":
    main()
