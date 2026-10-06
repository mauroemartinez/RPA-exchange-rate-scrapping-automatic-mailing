"""Corrida diaria completa, sin Jupyter. Es el reemplazo operativo del notebook.

Etapas, en el mismo orden que el notebook:

  historico     lee Fact_Mercado_Macro (o el CSV de contingencia si Supabase no responde)
  scraping      las seis fuentes en paralelo; si una cae, alerta y corta
  validacion    arma la fila del día y la pasa por models.FilaMacro; si no cumple, alerta y corta
  persistencia  INSERT de la fila sin duplicar la fecha
  ia            párrafo de Gemini, guardado en la misma fila
  graficos      los cuatro .jpg; si Yahoo no responde, el mail sale sin el de BTC
  mail          las dos variantes del reporte (con y sin CSV)
  previews      commit y push de Previews/

Cada etapa queda registrada con estado y duración. Una etapa en "error" pone la
corrida en rojo (código de salida 1) y dispara un mail de alerta con el resumen.

Uso:
    python pipeline.py                     # corrida real: escribe, manda el mail y pushea
    python pipeline.py --dry-run           # scrapea y arma todo, sin escribir ni mandar nada
    python pipeline.py --dry-run --enviar-a yo@mail.com
                                           # igual, pero el mail te llega solo a vos
    python pipeline.py --sin-mail          # escribe en Supabase y genera todo, sin enviar
    python pipeline.py --forzar            # repite el día aunque la fila ya exista
"""

import argparse
import json
import logging
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError

import charts
import data_access
import email_report
import fechas
import ia_generator
import mailer
import preview_git
import scrapers
import transformations
from config import settings
from scrapers import btc
from scrapers.utils import ScraperError

log = logging.getLogger("pipeline")

RAIZ = Path(__file__).resolve().parent
PREVIEWS = RAIZ / "Previews"

OK, ADVERTENCIA, ERROR, OMITIDA = "ok", "advertencia", "error", "omitida"


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

    def como_dict(self, con_detalle: bool = True) -> dict:
        """Serializable a JSON. Sin detalle, para respuestas HTTP: un mensaje de error
        puede arrastrar datos de conexión."""
        datos = asdict(self)
        datos["fecha"] = self.fecha.isoformat()
        datos["salida"] = str(self.salida) if self.salida else None
        datos["exitosa"] = self.exitosa
        if not con_detalle:
            for etapa in datos["etapas"]:
                etapa.pop("detalle")
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
    enviar_mail: Callable = email_report.enviar
    leer_csv: Callable = email_report.leer_csv_adjunto
    actualizar_previews: Callable = preview_git.actualizar_previews
    alertar: Callable = mailer.enviar_alerta
    alertar_scraper: Callable = mailer.alertar_scraper_caido
    alertar_validacion: Callable = mailer.alertar_validacion
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
        deps = Dependencias(**{**deps.__dict__, "alertar": _solo_log, "alertar_scraper": _solo_log, "alertar_validacion": _solo_log})

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

    # ── Histórico ────────────────────────────────────────────────────────────
    with registro.etapa("historico") as e:
        historico, origen = deps.leer_historico(engine)
        e.detalle = f"{len(historico)} filas desde {origen}"
        if origen != "supabase":
            e.estado = ADVERTENCIA

    hoy_iso = str(fecha)
    existente = historico[historico["Fecha"] == hoy_iso]
    ya_existe = not existente.empty
    parrafo_existente = None
    if ya_existe:
        if "ai_paragraph" in existente.columns and isinstance(existente["ai_paragraph"].iloc[0], str):
            parrafo_existente = existente["ai_paragraph"].iloc[0]
        if not (opciones.forzar or opciones.dry_run):
            registro.omitir(
                "control",
                f"la fila del {fecha} ya existe, así que la corrida de hoy ya se hizo. "
                "Para repetirla: --forzar. Para reenviar el mail: scripts/reenvio_manual.py",
            )
            resultado.estado = OMITIDA
            return
        log.warning("La fila del %s ya existe; se rehace el día sin duplicarla", fecha)
        historico = historico[historico["Fecha"] != hoy_iso].reset_index(drop=True)

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

    df = transformations.sumar_al_historico(fila, historico)
    fwd_oficial, fwd_blue = transformations.forwards_fisher(df)
    df = transformations.agregar_brechas_y_variaciones(df)

    # ── Persistencia ─────────────────────────────────────────────────────────
    persistida = False
    if opciones.dry_run:
        registro.omitir("persistencia", "dry-run")
    else:
        with registro.etapa("persistencia", critica=False) as e:
            escrita = deps.guardar_fila(engine, fila, sobrescribir=ya_existe)
            persistida = True
            if escrita:
                e.detalle = "fila actualizada" if ya_existe else "fila insertada"
            else:
                # Solo pasa si otra corrida sin candado (el notebook, por ejemplo) la
                # insertó entre la lectura del histórico y este INSERT.
                e.estado = ADVERTENCIA
                e.detalle = "la fila apareció mientras corría; se conservan los valores guardados"

    # ── Párrafo de IA ────────────────────────────────────────────────────────
    parrafo = ia_generator.MENSAJE_FALLA
    if opciones.dry_run:
        parrafo = parrafo_existente or "[dry-run] Acá va el párrafo de Gemini, que en una prueba no se pide."
        registro.omitir("ia", "dry-run: no se llama a Gemini")
    elif not persistida:
        registro.omitir("ia", "la fila del día no quedó guardada")
    else:
        with registro.etapa("ia", critica=False) as e:
            texto = deps.generar_parrafo(engine, fecha_esperada=fecha)
            if texto and texto != ia_generator.MENSAJE_FALLA:
                parrafo = texto
            else:
                e.estado = ADVERTENCIA
                e.detalle = "Gemini no devolvió párrafo; el mail lleva el mensaje de reemplazo"

    # ── Gráficos ─────────────────────────────────────────────────────────────
    inflacion = transformations.serie_inflacion(res.bcra["inflacion_mensual"], res.bcra["bcra_tea"])
    inflacion_12 = transformations.ultimos_meses(inflacion)

    carpeta = opciones.salida or (Path(tempfile.mkdtemp(prefix="macro_dryrun_")) if opciones.dry_run else PREVIEWS)
    carpeta.mkdir(parents=True, exist_ok=True)
    if opciones.dry_run or carpeta != PREVIEWS:
        resultado.salida = carpeta

    generados: dict[str, Path] = {}
    with registro.etapa("graficos", critica=False) as e:
        data = charts.preparar_datos(df)
        pendientes = [
            (charts.TIPOS_DE_CAMBIO, lambda: charts.grafico_tipos_de_cambio(data, carpeta)),
            (charts.VARIACIONES, lambda: charts.grafico_variaciones(
                charts.preparar_variaciones(data, inflacion), carpeta)),
            (charts.INFLACION, lambda: charts.grafico_inflacion(charts.preparar_inflacion(inflacion_12), carpeta)),
        ]
        fallas = []
        for nombre, generar in pendientes:
            try:
                generados[nombre] = generar()
            except Exception as exc:
                log.exception("No se pudo generar %s", nombre)
                fallas.append(f"{nombre}: {type(exc).__name__}: {exc}")

        try:
            desde, hasta = charts.rango_btc(deps.ahora())
            crudo = deps.descargar_btc(desde, hasta)
            generados[charts.BTC] = charts.grafico_btc(charts.preparar_btc(crudo, hasta), carpeta)
        except Exception as exc:
            log.warning("Sin gráfico de BTC: %s", exc)
            e.estado = ADVERTENCIA
            e.detalle = f"sin gráfico de BTC ({type(exc).__name__}: {exc})"

        if fallas:
            # A diferencia de BTC, estos no dependen de un tercero: si fallan, es un bug
            e.estado = ERROR
            e.detalle = "; ".join(fallas + ([e.detalle] if e.detalle else []))

    # ── Mail ─────────────────────────────────────────────────────────────────
    with registro.etapa("mail", critica=False) as e:
        # Solo los gráficos generados en esta corrida: si uno falló, en Previews/
        # sigue el de ayer y no tiene que viajar en el mail de hoy.
        imagenes = {nombre: generados[nombre].read_bytes() for nombre in charts.ORDEN_EN_MAIL if nombre in generados}
        html = email_report.renderizar(
            df, inflacion_12, fwd_oficial, fwd_blue, parrafo,
            performance_segundos=time.perf_counter() - comienzo,
            graficos=email_report.cids_disponibles(imagenes),
        )
        if resultado.salida:
            _guardar_vista_previa(resultado.salida, html, imagenes, fecha)

        if opciones.enviar_a:
            errores = email_report.enviar_reporte_diario(
                html, imagenes, fecha, deps.leer_csv(), receptores=[], receptores_csv=opciones.enviar_a,
                enviar_fn=deps.enviar_mail,
            )
        elif opciones.dry_run or not opciones.enviar_mail:
            errores = None
            e.estado = OMITIDA
            e.detalle = "dry-run" if opciones.dry_run else "--sin-mail"
        else:
            errores = email_report.enviar_reporte_diario(html, imagenes, fecha, deps.leer_csv(), enviar_fn=deps.enviar_mail)

        if errores is not None:
            fallidos = {variante: error for variante, error in errores.items() if error}
            if fallidos:
                e.estado = ERROR
                e.detalle = "; ".join(f"{variante}: {error}" for variante, error in fallidos.items())
            else:
                e.detalle = "enviado" + (f" solo a {', '.join(opciones.enviar_a)}" if opciones.enviar_a else "")

    # ── Previews en GitHub ───────────────────────────────────────────────────
    if opciones.dry_run or not opciones.push_previews:
        registro.omitir("previews", "dry-run" if opciones.dry_run else "--sin-push")
    elif carpeta != PREVIEWS:
        registro.omitir("previews", f"los gráficos se generaron en {carpeta}, no en Previews/")
    elif Path(settings.ruta_repo).resolve() != RAIZ:
        registro.omitir("previews", f"RUTA_REPO ({settings.ruta_repo}) no es la carpeta de este código ({RAIZ})")
    else:
        with registro.etapa("previews", critica=False) as e:
            hecho, e.detalle = deps.actualizar_previews(RAIZ)
            if not hecho:
                e.estado = OMITIDA


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


def configurar_logging(archivo: Path | None = None, nivel: int = logging.INFO) -> None:
    """Log a la consola (y opcionalmente a un archivo) para la corrida por línea de comandos."""
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
    logging.basicConfig(
        level=nivel, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s", handlers=handlers, force=True
    )
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
                        help="Manda el mail solo a estas direcciones, en lugar de a las listas del .env")
    parser.add_argument("--salida", type=Path, help="Carpeta para los gráficos y la vista previa")
    parser.add_argument("--log-archivo", type=Path, help="Además de la consola, escribe el log en este archivo")
    parser.add_argument("--json", type=Path, help="Escribe el resultado de la corrida como JSON en este archivo")
    parser.add_argument("--origen", default="cli", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

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
        )
    )
    if args.json:
        args.json.write_text(json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if resultado.exitosa else 1


if __name__ == "__main__":
    sys.exit(main())
