"""Arma Assets/Presentacion.jpg, la vista del deck en el README: las nueve diapositivas en una grilla de 3 x 3.

Exporta cada diapositiva con PowerPoint (por COM, así que necesita Windows con
PowerPoint instalado) y las monta sobre el azul del reporte, con esquinas
redondeadas y sombra. PowerPoint es lo único que dibuja los gráficos nativos tal
como los ve quien abre el archivo.

Uso, desde la raíz del repo:
    python scripts/presentacion_ejecutiva.py --salida tmp_deck      # el deck con la última fila de Supabase
    python Assets/arquitectura/montaje_presentacion.py "tmp_deck/Reporte Ejecutivo.pptx"
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

DESTINO = Path(__file__).resolve().parent.parent / "Presentacion.jpg"
FONDO_ARRIBA, FONDO_ABAJO = (8, 30, 64), (22, 58, 107)  # los azules del reporte
ANCHO_SLIDE, ALTO_SLIDE = 560, 315
MARGEN, ESPACIO, RADIO = 40, 28, 12


def exportar(pptx: Path, carpeta: Path) -> list[Path]:
    """Cada diapositiva a PNG con PowerPoint, al doble del tamaño final para que la reducción quede nítida."""
    script = (
        "$pp = New-Object -ComObject PowerPoint.Application; "
        "try { "
        f"$p = $pp.Presentations.Open('{pptx}', -1, 0, 0); "
        f"for ($i = 1; $i -le $p.Slides.Count; $i++) {{ $p.Slides.Item($i).Export('{carpeta}\\slide' + $i + '.png', 'PNG', {ANCHO_SLIDE * 2}, {ALTO_SLIDE * 2}) }}; "
        "$p.Close() } finally { $pp.Quit() }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)
    return sorted(carpeta.glob("slide*.png"), key=lambda r: int(r.stem.removeprefix("slide")))


def montar(diapositivas: list[Path]) -> Image.Image:
    columnas, filas = 3, (len(diapositivas) + 2) // 3
    ancho = 2 * MARGEN + columnas * ANCHO_SLIDE + (columnas - 1) * ESPACIO
    alto = 2 * MARGEN + filas * ALTO_SLIDE + (filas - 1) * ESPACIO
    lienzo = Image.new("RGB", (ancho, alto))
    for y in range(alto):  # degradé vertical, como el encabezado de las diapositivas
        t = y / max(alto - 1, 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(FONDO_ARRIBA, FONDO_ABAJO))
        ImageDraw.Draw(lienzo).line([(0, y), (ancho, y)], fill=color)

    mascara = Image.new("L", (ANCHO_SLIDE, ALTO_SLIDE), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, ANCHO_SLIDE - 1, ALTO_SLIDE - 1], RADIO, fill=255)
    sombra = Image.new("L", (ANCHO_SLIDE + 40, ALTO_SLIDE + 40), 0)
    ImageDraw.Draw(sombra).rounded_rectangle([20, 26, ANCHO_SLIDE + 19, ALTO_SLIDE + 25], RADIO, fill=150)
    sombra = sombra.filter(ImageFilter.GaussianBlur(10))

    for i, ruta in enumerate(diapositivas):
        x = MARGEN + (i % columnas) * (ANCHO_SLIDE + ESPACIO)
        y = MARGEN + (i // columnas) * (ALTO_SLIDE + ESPACIO)
        lienzo.paste((0, 0, 0), (x - 20, y - 20), sombra)
        with Image.open(ruta) as im:
            slide = im.convert("RGB").resize((ANCHO_SLIDE, ALTO_SLIDE), Image.LANCZOS)
        lienzo.paste(slide, (x, y), mascara)
    return lienzo


def main(argv: list[str]) -> None:
    if len(argv) != 1:
        sys.exit(__doc__)
    pptx = Path(argv[0]).resolve()
    with tempfile.TemporaryDirectory() as temporal:
        imagen = montar(exportar(pptx, Path(temporal)))
    imagen.save(DESTINO, quality=90, optimize=True)
    print(f"{DESTINO}: {imagen.width} x {imagen.height}, {DESTINO.stat().st_size / 1024:,.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
