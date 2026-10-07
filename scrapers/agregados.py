"""Series macro del BCRA (agregados, inflación, deuda), con su fecha, frecuencia y unidad originales.

Fase 3 del roadmap. Usa la misma API que scrapers/bcra.py (estadísticas v4.0) y
devuelve cada serie tal cual la publica el BCRA: no convierte unidades ni completa
días. La base monetaria viene en millones de ARS y el M3 en miles de ARS porque así
salen de la fuente; cualquier conversión es cosa del gráfico, no del dato guardado.
Lo mismo con la deuda: el BCRA la publica en millones de ARS y el pasaje a dólares
(con el tipo de cambio mayorista de cada día, que también se guarda) es del gráfico.

Endeudamiento, según la definición elegida (docs/fase-3-agregados-y-deuda.md):
C, la deuda del BCRA y su financiamiento al Tesoro, y D, los préstamos al sector
privado. De C quedó afuera la posición neta de pases (variable 1261): está en
cero desde que el BCRA dejó de tomar pases pasivos en 2024. La deuda bruta del
Tesoro (opción A) no sale de esta API sino de un Excel de la Secretaría de
Finanzas: scrapers/finanzas.py. Su descripción vive acá (DEUDA_BRUTA) para que
CATALOGO tenga todas las series que se guardan en Fact_Series_Macro.

Por qué estas series y no otras (detalle en docs/fase-3-agregados-y-deuda.md):
las M1, M2 y M3 diarias del Informe Monetario Diario (ids 1232 a 1234) están sin
datos desde el 7 de mayo de 2026, así que el M2 diario sale de la variable 109 y
el M3 de la serie mensual 1624, que llega con unos dos meses de rezago.
"""

import asyncio
from dataclasses import dataclass
from datetime import date

import httpx

from scrapers.bcra import API_BASE, TIMEOUT
from scrapers.utils import ScraperError, retry_http, run_async

# La API devuelve hasta 1000 puntos si no se le pide otra cosa; con limit se
# pueden pedir más por página (3000 probado) y paginar con offset.
PAGINA = 3000


@dataclass(frozen=True)
class Serie:
    clave: str
    id_bcra: int | None  # None para las series que no salen de la API del BCRA
    nombre: str
    frecuencia: str  # "D" diaria o "M" mensual, como la informa la fuente
    unidad: str  # tal cual la publica la fuente
    positiva: bool = True  # un stock no puede ser <= 0; una variación de precios sí
    fuente: str = "BCRA"
    referencia: str | None = None  # dónde está el dato en una fuente sin ids (hoja y fila de un Excel)

    @property
    def id_fuente(self) -> str:
        """Lo que se guarda en la columna id_fuente: el id del BCRA o la referencia."""
        return self.referencia or str(self.id_bcra)


SERIES = (
    Serie("base_monetaria", 15, "Base monetaria", "D", "millones de ARS"),
    Serie("circulacion_monetaria", 16, "Circulación monetaria", "D", "millones de ARS"),
    Serie("billetes_publico", 17, "Billetes y monedas en poder del público", "D", "millones de ARS"),
    Serie("m2", 109, "M2", "D", "millones de ARS"),
    Serie("m2_transaccional_privado", 197, "M2 transaccional del sector privado", "D", "millones de ARS"),
    Serie("m3", 1624, "M3 en moneda local", "M", "miles de ARS"),
    # La inflación ya se descarga todos los días para el reporte. Guardarla permitirá
    # que el reenvío manual y los gráficos no dependan de la API, cuando lean
    # Fact_Series_Macro (docs/evaluacion-cache.md)
    Serie("inflacion_mensual", 27, "Inflación mensual", "M", "porcentaje", positiva=False),
    Serie("inflacion_interanual", 28, "Inflación interanual", "M", "porcentaje", positiva=False),
    # Endeudamiento, opción C: deuda del BCRA y financiamiento al Tesoro
    Serie("letras_bcra_pesos", 1258, "Letras del BCRA en pesos", "D", "millones de ARS"),
    Serie("letras_bcra_moneda_extranjera", 1259, "Letras del BCRA en moneda extranjera", "D", "millones de ARS"),
    Serie("adelantos_transitorios", 1268, "Adelantos transitorios del BCRA al Tesoro", "D", "millones de ARS"),
    # Endeudamiento, opción D: lo que familias y empresas les deben a los bancos
    Serie("prestamos_sector_privado", 26, "Préstamos al sector privado", "D", "millones de ARS"),
    # Para pasar a dólares las series en pesos, fecha por fecha
    Serie("tipo_cambio_mayorista", 5, "Tipo de cambio mayorista de referencia (Com. A 3500)", "D", "ARS por USD"),
)
POR_CLAVE = {s.clave: s for s in SERIES}

# Endeudamiento, opción A: la deuda bruta del Tesoro, que publica la Secretaría de
# Finanzas en un Excel mensual (scrapers/finanzas.py), en millones de USD
DEUDA_BRUTA = Serie(
    "deuda_bruta_tesoro", None, "Deuda bruta de la Administración Central", "M", "millones de USD",
    fuente="Secretaría de Finanzas", referencia="A.1, A- DEUDA BRUTA",
)
# Todas las series que se guardan en Fact_Series_Macro, por clave
CATALOGO = {**POR_CLAVE, DEUDA_BRUTA.clave: DEUDA_BRUTA}


@retry_http
async def _pagina(client: httpx.AsyncClient, id_variable: int, params: dict) -> dict:
    response = await client.get(f"{API_BASE}/{id_variable}", params=params)
    response.raise_for_status()
    return response.json()


async def fetch(serie: Serie, client: httpx.AsyncClient, desde: date | None = None) -> list[tuple[date, float]]:
    """Puntos (fecha, valor) de la serie, ordenados de más viejo a más nuevo.

    Con `desde`, todos los puntos desde esa fecha; sin él, la historia completa.
    """
    params: dict = {"limit": PAGINA}
    if desde is not None:
        params["desde"] = desde.isoformat()

    puntos: list[tuple[date, float]] = []
    offset = 0
    while True:
        datos = await _pagina(client, serie.id_bcra, {**params, "offset": offset})
        resultados = datos.get("results") or [{}]
        detalle = resultados[0].get("detalle") or []
        puntos.extend((date.fromisoformat(d["fecha"]), float(d["valor"])) for d in detalle)
        offset += len(detalle)
        total = datos.get("metadata", {}).get("resultset", {}).get("count", offset)
        if not detalle or offset >= total:
            break

    puntos.sort(key=lambda par: par[0])
    return puntos


async def fetch_todas(
    client: httpx.AsyncClient | None = None, desde: date | None = None, claves: list[str] | None = None
) -> dict[str, list[tuple[date, float]]]:
    """Todas las series (o las de `claves`) en paralelo, por clave."""
    series = [POR_CLAVE[c] for c in claves] if claves else list(SERIES)
    # Hasta 4 variables a la vez: la API del BCRA limita a quien le pega muy seguido
    limite = asyncio.Semaphore(4)

    async def una(serie: Serie, cliente: httpx.AsyncClient):
        async with limite:
            return await fetch(serie, cliente, desde)

    if client is not None:
        resultados = await asyncio.gather(*(una(s, client) for s in series), return_exceptions=True)
    else:
        async with httpx.AsyncClient(timeout=TIMEOUT) as propio:
            resultados = await asyncio.gather(*(una(s, propio) for s in series), return_exceptions=True)

    # Una variable que falla (un 404, una caída puntual) no se lleva puestas a las demás:
    # se devuelven las que llegaron y quien llama ve cuáles faltan. Solo si no llegó
    # ninguna es un error.
    llegaron = {s.clave: r for s, r in zip(series, resultados) if not isinstance(r, BaseException)}
    if not llegaron:
        primero = next(r for r in resultados if isinstance(r, BaseException))
        raise ScraperError("BCRA", "leer agregados monetarios", primero) from primero
    return llegaron


def descargar(desde: date | None = None, claves: list[str] | None = None) -> dict[str, list[tuple[date, float]]]:
    """Versión sincrónica de fetch_todas, para el pipeline y los scripts."""
    return run_async(fetch_todas(desde=desde, claves=claves))
