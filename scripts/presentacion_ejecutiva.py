"""Rearma a mano la presentación ejecutiva con lo que dejó la última corrida.

La corrida diaria ya la genera sola (etapa `presentacion` de pipeline.py) y la
deja en Previews/. Este script sirve para rearmarla desde Supabase: lee la última
fila de Fact_Mercado_Macro (SELECT, solo lectura), su párrafo y sus comentarios
de IA, y los gráficos de Previews/. No scrapea, no llama a Gemini y no escribe
nada salvo el .pptx, que por defecto va a una carpeta temporal.

El armado está en presentacion.py, el mismo código que usa el pipeline.

Uso:
    python scripts/presentacion_ejecutiva.py                 # .pptx en una carpeta temporal
    python scripts/presentacion_ejecutiva.py --salida DIR
    python scripts/presentacion_ejecutiva.py --graficos DIR  # otra carpeta de gráficos
"""

import argparse
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import charts
import data_access
import presentacion


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, help="Carpeta del .pptx (por defecto, una temporal)")
    parser.add_argument("--graficos", type=Path, default=RAIZ / "Previews", help="Carpeta de los .jpg")
    args = parser.parse_args(argv)

    engine = data_access.crear_engine()
    try:
        df, _ = data_access.leer_historico(engine, respaldo_csv=False)
    finally:
        engine.dispose()

    imagenes = {n: args.graficos / n for n in charts.ORDEN_EN_MAIL if (args.graficos / n).exists()}
    ruta = presentacion.armar(df, imagenes, args.salida or Path(tempfile.mkdtemp(prefix="presentacion_")))
    print(f"Presentación: {ruta}")
    return ruta


if __name__ == "__main__":
    main()
