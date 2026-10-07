"""Agregados monetarios del BCRA: resumen, gráfico de prueba y carga histórica (fase 3).

Las series todavía no van en el mail: este script sirve para revisarlas antes de
sumarlas al reporte y para cargar su historia completa en Supabase una vez creada
la tabla (scripts/sql/06_series_macro.sql). Sin --guardar no escribe nada en ningún lado
salvo el gráfico, que va a una carpeta temporal y nunca a Previews/.

Uso:
    python scripts/agregados_monetarios.py               # resumen y gráfico de prueba
    python scripts/agregados_monetarios.py --salida DIR  # el gráfico en DIR
    python scripts/agregados_monetarios.py --guardar     # además carga toda la historia en Fact_Series_Macro
"""

import argparse
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pandas as pd

import charts
import data_access
import fechas
import transformations
from scrapers import agregados

# Para el gráfico alcanzan dos años de variación interanual, o sea tres de datos
ANIOS_GRAFICO = 3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", type=Path, help="Carpeta para el gráfico (por defecto, una temporal)")
    parser.add_argument("--guardar", action="store_true", help="Carga la historia completa en Fact_Series_Macro")
    args = parser.parse_args()

    hoy = fechas.hoy()
    desde = None if args.guardar else (pd.Timestamp(hoy) - pd.DateOffset(years=ANIOS_GRAFICO)).date()
    print(f"Descargando {len(agregados.SERIES)} series del BCRA {'(historia completa)' if desde is None else f'desde {desde}'}...")
    series = agregados.descargar(desde=desde)

    print(f"\n{'serie':26s} {'frec':4s} {'unidad':16s} {'último dato':>11s} {'valor':>20s} {'i.a.':>8s}")
    avisos = []
    for serie in agregados.SERIES:
        puntos = series[serie.clave]
        avisos += transformations.validar_serie(serie, puntos, hoy)
        fecha, valor = puntos[-1]
        interanual = transformations.variacion_interanual(puntos)
        ia = f"{interanual:7.1f}%" if interanual is not None and serie.positiva else "      -"
        print(f"{serie.clave:26s} {serie.frecuencia:4s} {serie.unidad:16s} {fecha!s:>11s} {valor:>20,.1f} {ia}")
    for aviso in avisos:
        print(f"⚠️ {aviso}")

    salida = args.salida or Path(tempfile.mkdtemp(prefix="agregados_"))
    salida.mkdir(parents=True, exist_ok=True)
    niveles, interanual = charts.preparar_agregados(series, hoy)
    ruta = charts.grafico_agregados(niveles, interanual, salida)
    print(f"\nGráfico: {ruta}")

    if args.guardar:
        engine = data_access.crear_engine()
        if not data_access.tabla_existe(engine):
            raise SystemExit(f"❌ No existe {data_access.TABLA_SERIES}. Aplicá scripts/sql/06_series_macro.sql en Supabase primero.")
        total = sum(data_access.guardar_series(engine, agregados.POR_CLAVE[c], p) for c, p in series.items())
        engine.dispose()
        print(f"✅ {data_access.TABLA_SERIES}: {total} puntos nuevos o revisados")


if __name__ == "__main__":
    main()
