"""Corrige series históricas de Fact_Mercado_Macro contra su API de origen.

Dos bugs de captura, ya arreglados en el código, dejaron datos mal en la base:

  riesgo_pais  El scraper leía la primera fila de la tabla histórica de Ámbito,
               que es el último cierre PUBLICADO, y la guardaba contra la fecha
               de hoy. La serie quedaba corrida un día hábil.

  bcra_tea     La API del BCRA devuelve el detalle de más nuevo a más viejo. El
               notebook tomaba .iloc[-1] sin invertir, o sea el registro MÁS
               VIEJO de la ventana de 1000 puntos: guardaba la BADLAR de junio
               de 2022 como si fuera la de hoy.

Sigue haciendo falta mientras el servicio de producción corra código viejo:
cada corrida con la versión anterior vuelve a escribir los valores malos.

Uso:
    python backfill.py                    # dry-run de las dos series
    python backfill.py --serie bcra_tea   # dry-run de una sola
    python backfill.py --apply            # aplica los UPDATE
"""

import argparse

import pandas as pd
from sqlalchemy import create_engine, text

from config import settings
from scrapers import bcra, riesgo_pais
from scrapers.utils import run_async

TABLA = "Fact_Mercado_Macro"

SERIES = {
    "riesgo_pais": lambda: run_async(riesgo_pais.fetch_historico()),
    "bcra_tea": lambda: run_async(bcra.fetch_historico_tea()),
}

# Tolerancia al comparar floats: la TEA viene con 4 decimales.
EPS = 1e-6


def corregir(engine, columna: str, apply: bool) -> None:
    print(f"\n{'=' * 60}\n{columna}\n{'=' * 60}")

    db = pd.read_sql(f'SELECT "Fecha", "{columna}" FROM "{TABLA}" ORDER BY "Fecha"', engine)
    db["Fecha"] = pd.to_datetime(db["Fecha"]).dt.date

    api = pd.DataFrame(SERIES[columna](), columns=["fecha", "valor"])

    print(f"Supabase : {len(db)} filas  ({db['Fecha'].min()} → {db['Fecha'].max()})")
    print(f"API      : {len(api)} filas  ({api['fecha'].min()} → {api['fecha'].max()})")

    m = db.merge(api, left_on="Fecha", right_on="fecha", how="inner")
    difieren = m[(m[columna] - m["valor"]).abs() > EPS].copy()

    print(f"\nFechas en común : {len(m)}")
    print(f"Coinciden       : {len(m) - len(difieren)}")
    print(f"A corregir      : {len(difieren)}")

    if difieren.empty:
        print("Nada que hacer.")
        return

    print(f"Rango           : {difieren['Fecha'].min()} → {difieren['Fecha'].max()}")
    print("\nPrimeras 10 (actual → API):")
    for _, r in difieren.head(10).iterrows():
        print(f"  {r['Fecha']}  {r[columna]:>10.4f} → {r['valor']:>10.4f}")

    if not apply:
        print(f"\n[DRY-RUN] Sin escribir. Usá --apply para las {len(difieren)} correcciones.")
        return

    filas = [{"f": r["Fecha"], "v": float(r["valor"])} for _, r in difieren.iterrows()]
    with engine.begin() as conn:
        result = conn.execute(
            text(f'UPDATE "{TABLA}" SET "{columna}" = :v WHERE "Fecha" = :f'), filas
        )
    print(f"\n✅ Aplicado. Filas afectadas: {result.rowcount}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serie", choices=list(SERIES), help="Solo esta serie (por defecto, todas)")
    parser.add_argument("--apply", action="store_true", help="Escribe (por defecto es dry-run)")
    args = parser.parse_args()

    engine = create_engine(settings.supabase_db_url.get_secret_value())
    for columna in [args.serie] if args.serie else SERIES:
        corregir(engine, columna, args.apply)
