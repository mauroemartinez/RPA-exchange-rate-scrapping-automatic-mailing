"""Corrida diaria completa, sin Jupyter. Es el reemplazo operativo del notebook.

Etapas, en el mismo orden que el notebook:

  control       fin de semana o feriado: no se corre (salvo --forzar); otra corrida en curso o
                la fila de hoy ya guardada: tampoco
  historico     lee Fact_Mercado_Macro (o el CSV de contingencia si Supabase no responde)
  scraping      las seis fuentes en paralelo; si una cae, alerta y corta
  validacion    arma la fila del día y la pasa por models.FilaMacro; si no cumple, alerta y corta
  persistencia  INSERT de la fila sin duplicar la fecha
  ia            párrafo de Gemini, guardado en la misma fila; con la columna ai_secciones,
                además un comentario por gráfico, en la misma llamada (fase 4)
  indicadores   agregados monetarios, inflación y deuda del BCRA, y la deuda bruta de la
                Secretaría de Finanzas, para sus gráficos; si una fuente falla, es una advertencia
                y el mail sale sin esos gráficos
  graficos      los seis .jpg; si Yahoo no responde, el mail sale sin el de BTC
  mail          las dos variantes del reporte (con y sin CSV)
  presentacion  el PowerPoint del día (presentacion.ARCHIVO), en la carpeta de los gráficos;
                si falla, es una advertencia: el mail ya salió
  previews      commit y push de los .jpg en Previews/ (main); el .pptx, a la rama reporte-ejecutivo
  series        guarda en Fact_Series_Macro lo que bajó la etapa indicadores (fase 3)

Cada etapa queda registrada con estado y duración. Una etapa en "error" pone la
corrida en rojo (código de salida 1) y dispara un mail de alerta con el resumen.

Uso:
    python pipeline.py                     # corrida real: escribe, manda el mail y pushea
    python pipeline.py --dry-run           # scrapea y arma todo, sin escribir ni mandar nada
    python pipeline.py --dry-run --enviar-a yo@mail.com
                                           # igual, pero el mail te llega solo a vos
    python pipeline.py --sin-mail          # escribe en Supabase y genera todo, sin enviar
    python pipeline.py --forzar            # repite el día aunque la fila ya exista, o corre en un feriado
    python pipeline.py --dry-run --con-ia  # prueba los comentarios por gráfico de Gemini, sin guardarlos
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError

from reporte import (
    charts,
    data_access,
    email_report,
    fechas,
    ia_generator,
    indicadores,
    mailer,
    preview_git,
    scrapers,
    transformations,
)
from reporte.config import redactar, reemplazos_sensibles, settings
from reporte.scrapers import agregados, btc, feriados, finanzas
from reporte.scrapers.utils import ScraperError

# python-pptx puede faltar en un venv instalado antes de que entrara a requirements.txt.
# Sin este resguardo, `import pipeline` fallaría entero: ni mail ni alerta ese día.
try:
    from reporte import presentacion
except ImportError as _exc:
    presentacion = None
    FALTA_PRESENTACION = f"{type(_exc).__name__}: {_exc}"

log = logging.getLogger("pipeline")

RAIZ = Path(__file__).resolve().parent
PREVIEWS = RAIZ / "Previews"

OK, ADVERTENCIA, ERROR, OMITIDA = "ok", "advertencia", "error", "omitida"

# Ventana de las series diarias que la etapa de series vuelve a guardar cada día:
# alcanza para tomar las revisiones del BCRA. Las mensuales (el M3 sale con unos
# dos meses de rezago, la deuda bruta con uno) se guardan enteras.
DIAS_SERIES = 120


@dataclass
class Etapa:
    nombre: str
    estado: str = OK
    detalle: str = ""
    segundos: float = 0.0


@dataclass
class ResultadoCorrida:
    fecha: date
    origen: str = "cli"
    estado: str = OK
    etapas: list[Etapa] = field(default_factory=list)
    segundos: float = 0.0
    salida: Path | None = None
    alertado: bool = False

    @property
    def exitosa(self) -> bool:
        """False solo si alguna etapa terminó en error. Omitir el día no es un error."""
        return self.estado != ERROR

    def calcular_estado(self) -> None:
        estados = {e.estado for e in self.etapas}
        if ERROR in estados:
            self.estado = ERROR
        elif self.estado == OMITIDA:
            pass
        elif ADVERTENCIA in estados:
            self.estado = ADVERTENCIA
        else:
            self.estado = OK

    def resumen(self) -> str:
        lineas = [f"Corrida del {self.fecha} ({self.origen}): {self.estado.upper()} en {self.segundos:.1f}s"]
        for e in self.etapas:
            detalle = f"  {e.detalle}" if e.detalle else ""
            lineas.append(f"  {e.nombre:<13} {e.estado:<12} {e.segundos:>6.1f}s{detalle}")
        if self.salida:
            lineas.append(f"  salida: {self.salida}")
        return "\n".join(lineas)

    def como_dict(self) -> dict:
        """Serializable a JSON (--json). app.py lee de acá estado y etapas, sin el detalle."""
        datos = asdict(self)
        datos["fecha"] = self.fecha.isoformat()
        datos["salida"] = str(self.salida) if self.salida else None
        datos["exitosa"] = self.exitosa
        return datos


@dataclass
class Opciones:
    dry_run: bool = False
    enviar_mail: bool = True
    push_previews: bool = True
    forzar: bool = False
    # Reemplaza a las dos listas de destinatarios: el mail sale una sola vez, con el CSV
    enviar_a: list[str] | None = None
    # Carpeta de los gráficos y la vista previa. Por defecto Previews/, o una
    # carpeta temporal en dry-run (Previews/ se commitea sola, no es lugar de pruebas).
    salida: Path | None = None
    origen: str = "cli"
    # En dry-run, pedirle a Gemini los comentarios por gráfico (una llamada, sin guardarlos)
    probar_ia: bool = False


@dataclass
class Dependencias:
    """Todo lo que sale del proceso. Los tests lo reemplazan por dobles."""

    crear_engine: Callable = data_access.crear_engine
    leer_historico: Callable = data_access.leer_historico
    guardar_fila: Callable = data_access.guardar_fila
    candado: Callable = data_access.candado_corrida
    scrapear: Callable = scrapers.run_all_sync
    descargar_btc: Callable = btc.descargar
    generar_parrafo: Callable = ia_generator.procesar_y_guardar_parrafo
    columna_secciones: Callable = lambda engine: data_access.columna_existe(engine, "ai_secciones")
    generar_secciones: Callable = ia_generator.generar_secciones
    guardar_secciones: Callable = ia_generator.guardar_secciones
    limpiar_secciones: Callable = ia_generator.limpiar_secciones
    enviar_mail: Callable = email_report.enviar
    actualizar_previews: Callable = preview_git.actualizar_previews
    publicar_presentacion: Callable = preview_git.publicar_presentacion
    tabla_series: Callable = data_access.tabla_existe
    descargar_series: Callable = agregados.descargar
    descargar_deuda: Callable = finanzas.descargar
    guardar_series: Callable = data_access.guardar_series
    alertar: Callable = mailer.enviar_alerta
    alertar_scraper: Callable = mailer.alertar_scraper_caido
    alertar_validacion: Callable = mailer.alertar_validacion
    feriado: Callable = feriados.nombre_feriado
    hoy: Callable = fechas.hoy
    ahora: Callable = fechas.ahora


class _Corte(Exception):
    """Falló una etapa crítica: la corrida no sigue."""


class _Registro:
    def __init__(self, resultado: ResultadoCorrida):
        self.resultado = resultado

    @contextmanager
    def etapa(self, nombre: str, critica: bool = True):
        etapa = Etapa(nombre)
        inicio = time.perf_counter()
        log.info("[%s] inicio", nombre)
        try:
            yield etapa
        except _Corte:
            raise
        except Exception as exc:
            etapa.estado = ERROR
            etapa.detalle = f"{type(exc).__name__}: {exc}"
            log.exception("[%s] falló", nombre)
            if critica:
                raise _Corte(nombre) from exc
        finally:
            etapa.segundos = round(time.perf_counter() - inicio, 2)
            self.resultado.etapas.append(etapa)
            extra = f": {etapa.detalle}" if etapa.detalle else ""
            nivel = logging.ERROR if etapa.estado == ERROR else logging.WARNING if etapa.estado == ADVERTENCIA else logging.INFO
            log.log(nivel, "[%s] %s en %.1fs%s", nombre, etapa.estado, etapa.segundos, extra)

    def omitir(self, nombre: str, motivo: str) -> None:
        self.resultado.etapas.append(Etapa(nombre, OMITIDA, motivo))
        log.info("[%s] omitida: %s", nombre, motivo)


def _solo_log(*args, **kwargs) -> bool:
    log.info("dry-run: la alerta por mail no se envía")
    return False


def correr(opciones: Opciones | None = None, deps: Dependencias | None = None) -> ResultadoCorrida:
    """Ejecuta la corrida del día y devuelve qué pasó en cada etapa. No levanta."""
    opciones = opciones or Opciones()
    deps = deps or Dependencias()
    if opciones.dry_run:
        # En una prueba no sale ningún mail que no se haya pedido explícitamente
        deps = replace(deps, alertar=_solo_log, alertar_scraper=_solo_log, alertar_validacion=_solo_log)

    comienzo = time.perf_counter()
    resultado = ResultadoCorrida(fecha=deps.hoy(), origen=opciones.origen)
    registro = _Registro(resultado)
    log.info("Corrida del %s (%s)%s", resultado.fecha, opciones.origen, " [DRY-RUN]" if opciones.dry_run else "")

    engine = None
    try:
        engine = deps.crear_engine()
        with ExitStack() as pila:
            obtenido = True
            if not opciones.dry_run:
                try:
                    obtenido = pila.enter_context(deps.candado(engine))
                except Exception as exc:
                    log.warning("No se pudo tomar el candado de corrida en Supabase (%s); se sigue sin él", exc)
            if not obtenido:
                registro.omitir("control", "hay otra corrida en curso")
                resultado.estado = OMITIDA
            else:
                _etapas(opciones, deps, registro, engine, comienzo)
    except _Corte:
        pass
    except Exception as exc:
        # Algo fuera de las etapas (por ejemplo, crear el engine). Igual queda registrado.
        log.exception("Error inesperado en la corrida")
        resultado.etapas.append(Etapa("pipeline", ERROR, f"{type(exc).__name__}: {exc}"))
    finally:
        if engine is not None:
            engine.dispose()

    resultado.segundos = round(time.perf_counter() - comienzo, 2)
    resultado.calcular_estado()
    log.info("\n%s", resultado.resumen())

    if resultado.estado == ERROR and not resultado.alertado:
        deps.alertar(f"⚠️ Corrida del {resultado.fecha} con errores", resultado.resumen())
    return resultado


def _etapas(opciones: Opciones, deps: Dependencias, registro: _Registro, engine, comienzo: float) -> None:
    resultado = registro.resultado
    fecha = resultado.fecha

    if _no_es_dia_habil(opciones, deps, registro, fecha):
        return

    # ── Histórico ────────────────────────────────────────────────────────────
    with registro.etapa("historico") as e:
        historico, origen = deps.leer_historico(engine)
        e.detalle = f"{len(historico)} filas desde {origen}"
        if origen != "supabase":
            e.estado = ADVERTENCIA

    existente = historico[historico["Fecha"] == str(fecha)]
    ya_existe = not existente.empty
    parrafo_existente = _primer_valor(existente, "ai_paragraph", str)
    secciones_existentes = _primer_valor(existente, "ai_secciones", dict)
    if ya_existe:
        if not (opciones.forzar or opciones.dry_run):
            if parrafo_existente is None:
                # La fila está pero sin párrafo: la corrida que la insertó murió antes de
                # la IA y del mail (timeout, reinicio, la PC suspendida). Omitir el día
                # dejaría a la lista sin reporte y todo en verde.
                resultado.etapas.append(Etapa(
                    "control", ERROR,
                    f"la fila del {fecha} existe sin párrafo de IA: la corrida anterior no terminó. "
                    "Para rehacer el día: --forzar",
                ))
                return
            registro.omitir(
                "control",
                f"la fila del {fecha} ya existe, así que la corrida de hoy ya se hizo. "
                "Para repetirla: --forzar. Para reenviar el mail: scripts/reenvio_manual.py",
            )
            resultado.estado = OMITIDA
            return
        log.warning("La fila del %s ya existe; se rehace el día sin duplicarla", fecha)
        historico = historico[historico["Fecha"] != str(fecha)].reset_index(drop=True)

    # ── Scraping ─────────────────────────────────────────────────────────────
    with registro.etapa("scraping") as e:
        try:
            res = transformations.ResultadosScraping(*deps.scrapear())
        except ScraperError as exc:
            resultado.alertado = deps.alertar_scraper(exc)
            raise
        avisos = transformations.avisos_de_frescura(res, fecha)
        for aviso in avisos:
            log.warning(aviso)
        e.detalle = "; ".join(avisos)

    # ── Fila del día y validación ────────────────────────────────────────────
    with registro.etapa("validacion"):
        fila = transformations.armar_fila_nueva(res, fecha)
        try:
            transformations.validar_fila(fila)
        except ValidationError as exc:
            resultado.alertado = deps.alertar_validacion(exc)
            raise

    df_base = transformations.sumar_al_historico(fila, historico)
    fwd_oficial, fwd_blue = transformations.forwards_fisher(df_base)
    df = transformations.agregar_brechas_y_variaciones(df_base)

    # ── Persistencia ─────────────────────────────────────────────────────────
    persistida = conflicto = False
    if opciones.dry_run:
        registro.omitir("persistencia", "dry-run")
    else:
        with registro.etapa("persistencia", critica=False) as e:
            persistida = deps.guardar_fila(engine, fila, sobrescribir=ya_existe)
            if persistida:
                e.detalle = "fila actualizada" if ya_existe else "fila insertada"
            else:
                # Otra corrida (el notebook, o una que leyó el histórico del CSV de
                # respaldo y no vio la fila) ya hizo el día: seguir mandaría otro mail
                conflicto = True
                e.estado = OMITIDA
                e.detalle = "la fila ya estaba en la base: otra corrida hizo el día"
    if conflicto:
        resultado.estado = OMITIDA
        return

    # ── BTC ──────────────────────────────────────────────────────────────────
    # Se descarga antes de la IA porque el comentario de BTC lo necesita. Si
    # Yahoo no responde, el mail sale sin ese gráfico y sin ese comentario.
    btc_df, falla_btc = None, None
    try:
        desde, hasta = charts.rango_btc(deps.ahora())
        btc_df = charts.preparar_btc(deps.descargar_btc(desde, hasta), hasta)
    except Exception as exc:
        log.warning("Sin datos de BTC: %s", exc)
        falla_btc = f"{type(exc).__name__}: {exc}"

    parrafo, texto_ia, comentarios = _etapa_ia(
        opciones, deps, registro, engine, fecha, df_base, btc_df, fwd_oficial, persistida,
        parrafo_existente, secciones_existentes,
    )

    series, provisorios = _etapa_indicadores(deps, registro, fecha)

    inflacion = transformations.serie_inflacion(res.bcra["inflacion_mensual"])
    inflacion_12 = transformations.ultimos_meses(inflacion)
    carpeta = _carpeta_de_salida(opciones)
    if opciones.dry_run or carpeta != PREVIEWS:
        resultado.salida = carpeta
    generados = _etapa_graficos(
        registro, carpeta, df, inflacion, inflacion_12, btc_df, falla_btc, series, provisorios, fecha,
    )
    # Solo de los gráficos que se generaron: una explicación sin su gráfico no tiene sentido
    cids = email_report.cids_disponibles({nombre: b"" for nombre in generados})
    try:
        explicaciones = indicadores.explicaciones(series, provisorios, cids=cids)
    except Exception:
        # Las frases con los últimos datos son un agregado: si algo falla, van los textos fijos
        log.exception("No se pudieron armar las frases de agregados y deuda; van solo los textos fijos")
        explicaciones = indicadores.textos_fijos(cids)

    _etapa_mail(
        opciones, deps, registro, fecha, comienzo, df, df_base, inflacion_12, fwd_oficial, fwd_blue,
        parrafo, texto_ia, comentarios, generados, explicaciones,
    )
    deck = _etapa_presentacion(registro, carpeta, df_base, parrafo, comentarios, generados, explicaciones,
                               inflacion=inflacion, btc=btc_df)
    _etapa_previews(opciones, deps, registro, carpeta, deck, fecha)
    _etapa_series(opciones, deps, registro, engine, fecha, series)


def _no_es_dia_habil(opciones: Opciones, deps: Dependencias, registro: _Registro, fecha: date) -> bool:
    """Fines de semana y feriados: True si la corrida no corresponde.

    Un programador automático de lunes a viernes dispararía la corrida también
    los feriados, con las fuentes repitiendo el último dato. Si el calendario no
    responde, se sigue: es preferible un mail de más que un día sin reporte.
    """
    if fecha.weekday() >= 5:
        motivo = "fin de semana"
    else:
        try:
            nombre = deps.feriado(fecha)
        except Exception as exc:
            log.warning("No se pudo consultar el calendario de feriados (%s); se sigue como día hábil", exc)
            nombre = None
        motivo = f"feriado ({nombre})" if nombre else None

    if not motivo or opciones.forzar:
        return False
    if opciones.dry_run:
        log.warning("El %s es %s: una corrida real no se haría (dry-run sigue igual)", fecha, motivo)
        return False
    registro.omitir("control", f"el {fecha} es {motivo}; para correr igual: --forzar")
    registro.resultado.estado = OMITIDA
    return True


def _primer_valor(filas, columna: str, tipo: type):
    """El valor de `columna` en la primera fila si existe y es del tipo esperado; si no, None."""
    if filas.empty or columna not in filas.columns:
        return None
    valor = filas[columna].iloc[0]
    return valor if isinstance(valor, tipo) else None


def _etapa_ia(
    opciones: Opciones, deps: Dependencias, registro: _Registro, engine, fecha: date, df_base, btc_df,
    fwd_oficial: float, persistida: bool, parrafo_existente: str | None, secciones_existentes: dict | None,
) -> tuple[str, str | None, dict]:
    """(párrafo que muestra el mail, texto que queda guardado en la fila, comentarios por gráfico).

    Con la columna ai_secciones, una llamada estructurada (fase 4). Ante cualquier
    falla de esa llamada, o si no se pudo guardar, se vuelve al párrafo único.
    """
    if opciones.dry_run:
        parrafo = parrafo_existente or "[dry-run] Acá va el párrafo de Gemini, que en una prueba no se pide."
        comentarios = ia_generator.comentarios_por_grafico(secciones_existentes)
        if not opciones.probar_ia:
            registro.omitir("ia", "dry-run: no se llama a Gemini (--con-ia para probar los comentarios)")
            return parrafo, parrafo_existente, comentarios
        with registro.etapa("ia", critica=False) as e:
            secciones, modelo = _pedir_secciones(deps, df_base, btc_df, fwd_oficial)
            if secciones is None:
                e.estado = ADVERTENCIA
                e.detalle = "Gemini no devolvió secciones válidas"
            else:
                parrafo = secciones.resumen
                comentarios = ia_generator.comentarios_por_grafico(secciones)
                e.detalle = f"secciones de prueba con {modelo}, sin guardar"
        return parrafo, parrafo_existente, comentarios

    if not persistida:
        registro.omitir("ia", "la fila del día no quedó guardada")
        return ia_generator.MENSAJE_FALLA, None, {}

    parrafo, texto_ia, comentarios = ia_generator.MENSAJE_FALLA, None, {}
    with registro.etapa("ia", critica=False) as e:
        try:
            con_secciones = bool(deps.columna_secciones(engine))
        except Exception as exc:
            log.warning("No se pudo consultar la columna ai_secciones (%s); se usa el párrafo único", exc)
            con_secciones = False

        if con_secciones:
            secciones, modelo = _pedir_secciones(deps, df_base, btc_df, fwd_oficial)
            if secciones is not None and _guardar_secciones(deps, engine, fecha, secciones, modelo):
                e.detalle = f"resumen y comentarios por gráfico con {modelo}"
                return secciones.resumen, secciones.resumen, ia_generator.comentarios_por_grafico(secciones)
            log.warning("Sin comentarios por gráfico; se vuelve al párrafo único")
            # Una corrida anterior del día (--forzar) pudo dejar comentarios de otros valores
            try:
                deps.limpiar_secciones(engine, fecha)
            except Exception as exc:
                log.warning("No se pudieron borrar los comentarios anteriores del día: %s", exc)

        texto = deps.generar_parrafo(engine, fecha_esperada=fecha)
        if texto and texto != ia_generator.MENSAJE_FALLA:
            parrafo = texto_ia = texto
            if con_secciones:
                e.estado = ADVERTENCIA
                e.detalle = "falló la respuesta estructurada; salió el párrafo único"
        else:
            e.estado = ADVERTENCIA
            e.detalle = "Gemini no devolvió párrafo; el mail lleva el mensaje de reemplazo"
    return parrafo, texto_ia, comentarios


def _pedir_secciones(deps: Dependencias, df_base, btc_df, fwd_oficial: float):
    """(secciones, modelo) de la llamada estructurada, o (None, None) ante cualquier falla."""
    try:
        return deps.generar_secciones(ia_generator.armar_prompt_secciones(df_base, btc_df, fwd_oficial))
    except Exception:
        log.exception("Falló la llamada estructurada a Gemini")
        return None, None


def _guardar_secciones(deps: Dependencias, engine, fecha: date, secciones, modelo) -> bool:
    try:
        return bool(deps.guardar_secciones(engine, fecha, secciones, modelo))
    except Exception:
        log.exception("No se pudieron guardar las secciones de IA")
        return False


def _carpeta_de_salida(opciones: Opciones) -> Path:
    """Previews/ en una corrida real; una carpeta temporal (o --salida) en un dry-run."""
    carpeta = opciones.salida or (Path(tempfile.mkdtemp(prefix="macro_dryrun_")) if opciones.dry_run else PREVIEWS)
    if opciones.dry_run and carpeta.resolve().is_relative_to(PREVIEWS):
        # La vista previa (mail.eml, con el remitente) terminaría commiteada en el repo público
        log.warning("Un dry-run no escribe en Previews/: se usa una carpeta temporal")
        carpeta = Path(tempfile.mkdtemp(prefix="macro_dryrun_"))
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _etapa_indicadores(deps: Dependencias, registro: _Registro, fecha: date) -> tuple[dict, set]:
    """Series para los gráficos de agregados y deuda: (series por clave, meses provisorios de la deuda bruta).

    Baja las del BCRA (dos años, para tener un año de variación interanual) y la
    deuda bruta de la Secretaría de Finanzas. Cada serie se valida por separado:
    una rota se descarta y una atrasada se usa igual, con aviso. Nada de esto
    escribe: también corre en un dry-run. Si una fuente no responde, el mail sale
    sin el gráfico que la necesita, así que es una advertencia y no un error.
    """
    series: dict = {}
    provisorios: set = set()
    with registro.etapa("indicadores", critica=False) as e:
        avisos = []
        try:
            series.update(deps.descargar_series(indicadores.desde(fecha)))
        except Exception as exc:
            log.warning("Sin series del BCRA: %s", exc)
            avisos.append(f"BCRA: {type(exc).__name__}: {exc}")
        else:
            faltan = [clave for clave in agregados.POR_CLAVE if clave not in series]
            if faltan:
                avisos.append(f"BCRA: sin {', '.join(faltan)}")
        try:
            series[agregados.DEUDA_BRUTA.clave], provisorios = deps.descargar_deuda()
        except Exception as exc:
            log.warning("Sin deuda bruta de la Secretaría de Finanzas: %s", exc)
            avisos.append(f"Secretaría de Finanzas: {type(exc).__name__}: {exc}")

        for clave in list(series):
            serie = agregados.CATALOGO[clave]
            try:
                avisos += transformations.validar_serie(serie, series[clave], fecha)
            except ValueError as exc:
                log.warning("Serie %s descartada: %s", clave, exc)
                avisos.append(str(exc))
                del series[clave]

        # Historia larga solo para comparar la deuda contra hace 4, 8 y 12 años. Si no
        # llega o no valida, quedan las de dos años: la frase sale sin esas comparaciones
        if all(clave in series for clave in indicadores.CLAVES_COMPARACIONES):
            try:
                largas = deps.descargar_series(indicadores.desde_comparaciones(fecha),
                                               claves=list(indicadores.CLAVES_COMPARACIONES))
                for clave in indicadores.CLAVES_COMPARACIONES:
                    transformations.validar_serie(agregados.CATALOGO[clave], largas[clave], fecha)
            except Exception as exc:
                log.warning("Sin historia larga para comparar la deuda: %s", exc)
            else:
                series.update({clave: largas[clave] for clave in indicadores.CLAVES_COMPARACIONES})

        e.detalle = f"{len(series)} series" + "".join(f"; {a}" for a in avisos)
        if avisos:
            e.estado = ADVERTENCIA
    return series, provisorios


def _etapa_graficos(
    registro: _Registro, carpeta: Path, df, inflacion, inflacion_12, btc_df, falla_btc,
    series: dict | None = None, provisorios=frozenset(), hoy: date | None = None,
) -> dict[str, Path]:
    """Los .jpg del mail. Devuelve solo los que se generaron en esta corrida."""
    generados: dict[str, Path] = {}
    series = series or {}
    with registro.etapa("graficos", critica=False) as e:
        data = charts.preparar_datos(df)
        pendientes = [
            (charts.TIPOS_DE_CAMBIO, lambda: charts.grafico_tipos_de_cambio(data, carpeta)),
            (charts.VARIACIONES, lambda: charts.grafico_variaciones(charts.preparar_variaciones(data, inflacion), carpeta)),
            (charts.INFLACION, lambda: charts.grafico_inflacion(charts.preparar_inflacion(inflacion_12), carpeta)),
        ]
        if btc_df is not None:
            pendientes.append((charts.BTC, lambda: charts.grafico_btc(btc_df, carpeta)))

        fallas = []
        for nombre, generar in pendientes:
            try:
                generados[nombre] = generar()
            except Exception as exc:
                log.exception("No se pudo generar %s", nombre)
                fallas.append(f"{nombre}: {type(exc).__name__}: {exc}")

        # Agregados y deuda dependen de fuentes de afuera, como BTC: si faltan datos
        # o el gráfico no se puede armar con lo que llegó, el mail sale sin él
        avisos = []
        faltan = [c for c in charts.CLAVES_AGREGADOS if c not in series]
        if faltan:
            motivo = "no llegaron sus series" if len(faltan) == len(charts.CLAVES_AGREGADOS) else f"faltan {', '.join(faltan)}"
            avisos.append(f"sin gráfico de agregados ({motivo})")
        else:
            _grafico_opcional(generados, avisos, charts.AGREGADOS,
                              lambda: charts.grafico_agregados(*charts.preparar_agregados(series, hoy), carpeta))
        # El de deuda se dibuja con lo que haya: la deuda bruta sola, o las series del
        # BCRA con el tipo de cambio para pasarlas a dólares; un panel sin datos lo dice
        hay_bcra = "tipo_cambio_mayorista" in series and any(c in series for c in charts.CLAVES_DEUDA_BCRA[:-1])
        if agregados.DEUDA_BRUTA.clave not in series and not hay_bcra:
            avisos.append("sin gráfico de deuda (no llegaron sus series)")
        else:
            _grafico_opcional(generados, avisos, charts.DEUDA,
                              lambda: charts.grafico_deuda(charts.preparar_deuda(series, hoy, provisorios), carpeta))

        if btc_df is None:
            avisos.insert(0, f"sin gráfico de BTC ({falla_btc})")
        if avisos:
            e.estado = ADVERTENCIA
            e.detalle = "; ".join(avisos)
        if fallas:
            # A diferencia de BTC, estos no dependen de un tercero: si fallan, es un bug
            e.estado = ERROR
            e.detalle = "; ".join(fallas + ([e.detalle] if e.detalle else []))
    return generados


def _grafico_opcional(generados: dict, avisos: list, nombre: str, generar: Callable) -> None:
    try:
        generados[nombre] = generar()
    except Exception as exc:
        log.exception("No se pudo generar %s", nombre)
        avisos.append(f"{nombre}: {type(exc).__name__}: {exc}")


def _etapa_mail(
    opciones: Opciones, deps: Dependencias, registro: _Registro, fecha: date, comienzo: float, df, df_base,
    inflacion_12, fwd_oficial: float, fwd_blue: float, parrafo: str, texto_ia: str | None, comentarios: dict,
    generados: dict[str, Path], explicaciones: dict | None = None,
) -> None:
    resultado = registro.resultado
    with registro.etapa("mail", critica=False) as e:
        # Solo los gráficos generados en esta corrida: si uno falló, en Previews/
        # sigue el de ayer y no tiene que viajar en el mail de hoy.
        imagenes = {nombre: generados[nombre].read_bytes() for nombre in charts.ORDEN_EN_MAIL if nombre in generados}
        html = email_report.renderizar(
            df, inflacion_12, fwd_oficial, fwd_blue, parrafo,
            performance_segundos=time.perf_counter() - comienzo,
            graficos=email_report.cids_disponibles(imagenes),
            comentarios=comentarios,
            explicaciones=explicaciones,
        )
        if resultado.salida:
            _guardar_vista_previa(resultado.salida, html, imagenes, fecha)

        con_parrafo = df_base.copy()
        con_parrafo.loc[0, "ai_paragraph"] = texto_ia
        csv = email_report.csv_historico(con_parrafo)

        if opciones.enviar_a:
            errores = email_report.enviar_reporte_diario(
                html, imagenes, fecha, csv, receptores=[], receptores_csv=opciones.enviar_a,
                enviar_fn=deps.enviar_mail,
            )
        elif opciones.dry_run or not opciones.enviar_mail:
            errores = None
            e.estado = OMITIDA
            e.detalle = "dry-run" if opciones.dry_run else "--sin-mail"
        else:
            errores = email_report.enviar_reporte_diario(html, imagenes, fecha, csv, enviar_fn=deps.enviar_mail)

        if errores is not None:
            fallidos = {variante: error for variante, error in errores.items() if error}
            if fallidos:
                e.estado = ERROR
                e.detalle = "; ".join(f"{variante}: {error}" for variante, error in fallidos.items())
            else:
                e.detalle = "enviado" + (f" solo a {', '.join(opciones.enviar_a)}" if opciones.enviar_a else "")


def _etapa_presentacion(
    registro: _Registro, carpeta: Path, df_base, parrafo: str, comentarios: dict, generados: dict[str, Path],
    explicaciones: dict | None = None, inflacion=None, btc=None,
) -> Path | None:
    """El PowerPoint del día, con los datos, los textos de IA y los gráficos de esta corrida.

    Queda en la misma carpeta que los gráficos (en una corrida real, Previews/) y
    la etapa previews lo publica en su propia rama. Va después del mail, así que si
    falla el reporte ya salió: es una advertencia y no pone la corrida en rojo.
    Devuelve la ruta del archivo armado en esta corrida, o None.
    """
    with registro.etapa("presentacion", critica=False) as e:
        if presentacion is None:
            e.estado = ADVERTENCIA
            e.detalle = f"no se pudo importar presentacion ({FALTA_PRESENTACION}): pip install -r requirements.txt"
            return None
        try:
            ruta = presentacion.armar(
                df_base, generados, carpeta, parrafo=parrafo, comentarios=comentarios, explicaciones=explicaciones,
                inflacion=inflacion, btc=btc,
            )
        except Exception as exc:
            log.exception("No se pudo armar la presentación")
            e.estado = ADVERTENCIA
            e.detalle = f"{type(exc).__name__}: {exc}"
            return None
        e.detalle = f"{ruta.name}, {ruta.stat().st_size / 1024:,.0f} KB"
        faltan = [nombre for nombre in charts.ORDEN_EN_MAIL if nombre not in generados]
        if faltan:
            e.detalle += f"; sin {', '.join(faltan)}"
        return ruta


def _etapa_previews(
    opciones: Opciones, deps: Dependencias, registro: _Registro, carpeta: Path, deck: Path | None, fecha: date,
) -> None:
    """Los gráficos van a main, en Previews/; el PowerPoint, a su propia rama, que se reemplaza entera.

    Solo se publica el PowerPoint armado en esta corrida: si hoy falló, el de ayer
    no se vuelve a subir con la fecha de hoy. Si su publicación falla, es una
    advertencia: los gráficos ya quedaron y el mail ya salió.
    """
    if opciones.dry_run or not opciones.push_previews:
        registro.omitir("previews", "dry-run" if opciones.dry_run else "--sin-push")
    elif carpeta != PREVIEWS:
        registro.omitir("previews", f"los gráficos se generaron en {carpeta}, no en Previews/")
    elif Path(settings.ruta_repo).resolve() != RAIZ:
        registro.omitir("previews", f"RUTA_REPO ({settings.ruta_repo}) no es la carpeta de este código ({RAIZ})")
    else:
        with registro.etapa("previews", critica=False) as e:
            partes, hecho = [], False
            try:
                hecho, detalle = deps.actualizar_previews(RAIZ, archivos=list(charts.ORDEN_EN_MAIL))
                partes.append(detalle)
            except Exception as exc:
                # Queda en error, pero se sigue: el PowerPoint va a otra rama y no depende de este push
                log.exception("No se pudieron publicar los gráficos")
                partes.append(f"gráficos sin publicar: {type(exc).__name__}: {exc}")
                e.estado = ERROR
            if deck is not None:
                try:
                    publicado, detalle_deck = deps.publicar_presentacion(
                        RAIZ, deck, mensaje=f"Reporte ejecutivo del {fecha:%d/%m/%Y}"
                    )
                    partes.append(detalle_deck)
                    hecho = hecho or publicado
                except Exception as exc:
                    log.exception("No se pudo publicar la presentación")
                    partes.append(f"presentación sin publicar: {type(exc).__name__}: {exc}")
                    if e.estado != ERROR:
                        e.estado = ADVERTENCIA
            e.detalle = "; ".join(partes)
            if not hecho and e.estado == OK:
                e.estado = OMITIDA


def _etapa_series(
    opciones: Opciones, deps: Dependencias, registro: _Registro, engine, fecha: date, series: dict | None = None,
) -> None:
    """Guarda en Fact_Series_Macro lo que bajó la etapa indicadores, ya validado (fase 3).

    No vuelve a descargar. De las series diarias guarda los últimos DIAS_SERIES
    días, que alcanzan para tomar las revisiones del BCRA; las mensuales, enteras.
    Un problema acá queda como advertencia y no pone la corrida en rojo, y cada
    serie se guarda por separado: una que falla no frena a las demás.
    """
    if opciones.dry_run:
        registro.omitir("series", "dry-run")
        return
    with registro.etapa("series", critica=False) as e:
        try:
            if not deps.tabla_series(engine):
                e.estado = OMITIDA
                e.detalle = f"falta la tabla {data_access.TABLA_SERIES} (sql/06_series_macro.sql)"
                return
        except Exception as exc:
            log.exception("No se pudo consultar la tabla de series")
            e.estado = ADVERTENCIA
            e.detalle = f"{type(exc).__name__}: {exc}"
            return
        if not series:
            e.estado = OMITIDA
            e.detalle = "no hay series para guardar (ver la etapa indicadores)"
            return

        corte = fecha - timedelta(days=DIAS_SERIES)
        avisos, escritos = [], 0
        for clave, puntos in series.items():
            serie = agregados.CATALOGO[clave]
            recientes = [(f, v) for f, v in puntos if f >= corte] if serie.frecuencia == "D" else puntos
            try:
                escritos += deps.guardar_series(engine, serie, recientes)
            except Exception as exc:
                log.warning("Serie %s sin guardar: %s", clave, exc)
                avisos.append(f"{clave}: {type(exc).__name__}: {exc}")
        e.detalle = f"{escritos} puntos nuevos o revisados" + "".join(f"; {a}" for a in avisos)
        if avisos:
            e.estado = ADVERTENCIA


def _guardar_vista_previa(carpeta: Path, html: str, imagenes: dict[str, bytes], fecha: date) -> None:
    """mail.eml para abrir en un cliente de correo y mail_preview.html para el navegador."""
    mensaje = email_report.armar_mensaje(html, imagenes, email_report.asunto(fecha), para=settings.email_sender)
    (carpeta / "mail.eml").write_bytes(mensaje.as_bytes())

    # En el .html los cid: no resuelven; se apuntan a los .jpg de la misma carpeta
    navegable = html
    for i, nombre in enumerate(charts.ORDEN_EN_MAIL):
        navegable = navegable.replace(f"cid:image{i + 1}", nombre)
    (carpeta / "mail_preview.html").write_text(navegable, encoding="utf-8")
    log.info("Vista previa del mail en %s", carpeta)


class _FormatoSinSecretos(logging.Formatter):
    """Tapa secretos y destinatarios en cada línea del log, traceback incluido.

    Corriendo en GitHub Actions sobre un repo público, el log de la corrida es
    público. GitHub enmascara cada secreto completo, pero no una dirección suelta
    de la lista de destinatarios, que aparece en un SMTPRecipientsRefused.
    """

    def __init__(self, fmt: str):
        super().__init__(fmt)
        self._reemplazos = reemplazos_sensibles()

    def format(self, record: logging.LogRecord) -> str:
        texto = super().format(record)
        for secreto, reemplazo in self._reemplazos:
            texto = texto.replace(secreto, reemplazo)
        return texto


def configurar_logging(archivo: Path | None = None, nivel: int = logging.INFO) -> None:
    """Log a la consola (y opcionalmente a un archivo) para la corrida por línea de comandos.

    Cada línea pasa por _FormatoSinSecretos, así ni la consola ni el archivo
    llevan claves ni direcciones de suscriptores.
    """
    # En Windows, con la salida redirigida (Programador de tareas, subprocess), la
    # consola cae en cp1252 y un emoji en un log tira UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except (AttributeError, ValueError):
            pass

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if archivo:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(archivo, encoding="utf-8"))
    formato = _FormatoSinSecretos("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    for handler in handlers:
        handler.setFormatter(formato)
    logging.basicConfig(level=nivel, handlers=handlers, force=True)
    # httpx loguea cada request con la URL completa en INFO, y la de FRED lleva la
    # API key en la query string. El resto, solo para no tapar el log del pipeline.
    for ruidoso in ("httpx", "httpcore", "matplotlib", "PIL", "yfinance", "google_genai", "urllib3"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true",
                        help="Scrapea y arma todo, pero no escribe en Supabase, no llama a Gemini, no manda el mail ni pushea")
    parser.add_argument("--sin-mail", action="store_true", help="Corrida completa salvo el envío del reporte")
    parser.add_argument("--sin-push", action="store_true", help="No commitea ni pushea Previews/")
    parser.add_argument("--forzar", action="store_true",
                        help="Repite el día aunque la fila ya exista (pisa sus valores y vuelve a mandar el mail)")
    parser.add_argument("--enviar-a", nargs="+", metavar="MAIL",
                        help="Con --dry-run: manda el mail solo a estas direcciones, en lugar de a las listas del .env")
    parser.add_argument("--con-ia", action="store_true",
                        help="Con --dry-run: pide a Gemini los comentarios por gráfico, sin guardarlos (una consulta estructurada, con sus reintentos)")
    parser.add_argument("--salida", type=Path, help="Carpeta para los gráficos y la vista previa")
    parser.add_argument("--log-archivo", type=Path, help="Además de la consola, escribe el log en este archivo")
    parser.add_argument("--json", type=Path, help="Escribe el resultado de la corrida como JSON en este archivo")
    parser.add_argument("--origen", default="cli", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.dry_run and args.salida and args.salida.resolve().is_relative_to(PREVIEWS):
        parser.error("--salida no puede estar dentro de Previews/ en un dry-run: esa carpeta se commitea y se pushea sola")

    # Sin dry-run, --enviar-a guardaría la fila del día y mandaría el mail solo a
    # esas direcciones: la corrida programada vería la fila y la lista se quedaría sin reporte.
    if args.enviar_a and not args.dry_run:
        parser.error("--enviar-a va con --dry-run")
    if args.con_ia and not args.dry_run:
        parser.error("--con-ia va con --dry-run: en una corrida real la IA se pide sola")
    if args.enviar_a and args.sin_mail:
        parser.error("--enviar-a y --sin-mail se contradicen")

    if args.enviar_a:
        try:
            args.enviar_a = [str(m) for m in TypeAdapter(list[EmailStr]).validate_python(args.enviar_a)]
        except ValidationError as exc:
            parser.error(f"--enviar-a tiene una dirección inválida: {exc.errors()[0]['msg']}")

    configurar_logging(args.log_archivo)
    resultado = correr(
        Opciones(
            dry_run=args.dry_run,
            enviar_mail=not args.sin_mail,
            push_previews=not args.sin_push,
            forzar=args.forzar,
            enviar_a=args.enviar_a,
            salida=args.salida.resolve() if args.salida else None,
            origen=args.origen,
            probar_ia=args.con_ia,
        )
    )
    if args.json:
        args.json.write_text(redactar(json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2)), encoding="utf-8")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        _avisar_en_github(resultado)
    return 0 if resultado.exitosa else 1


def _escapar_anotacion(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _avisar_en_github(resultado: ResultadoCorrida) -> None:
    """Una anotación por etapa en advertencia o error, y el resumen de la corrida en la página del run.

    Una corrida en verde puede tener etapas en advertencia (por ejemplo, el mail salió
    sin un gráfico porque una fuente no respondió desde los servidores de GitHub).
    Sin esto, solo se vería abriendo el log. Todo pasa por redactar(): el log es público.
    """
    for etapa in resultado.etapas:
        if etapa.estado in (ADVERTENCIA, ERROR):
            nivel = "error" if etapa.estado == ERROR else "warning"
            print(f"::{nivel} title={etapa.nombre}::{_escapar_anotacion(redactar(etapa.detalle or etapa.estado))}")
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as fh:
            fh.write("```\n" + redactar(resultado.resumen()) + "\n```\n")


if __name__ == "__main__":
    sys.exit(main())
