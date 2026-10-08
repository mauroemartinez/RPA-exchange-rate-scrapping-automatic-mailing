"""Envío de mails de alerta cuando algo del pipeline falla.

Separado del reporte para que cualquier módulo pueda avisar sin depender del resto.
Las alertas van en texto plano a EMAIL_ALERTAS, o a EMAIL_RECEIVER_CSV si no está
configurada, y pasan por config.redactar: un traceback puede arrastrar una clave.
"""

import logging
import smtplib
import ssl
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from reporte.config import redactar, settings

log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def enviar_smtp(mensaje, destinatarios: list[str]) -> None:
    """Un sendmail por Gmail con TLS. Levanta ante cualquier fallo, incluidos los rechazos parciales.

    Es el único lugar que habla SMTP: lo usan las alertas y el reporte.
    """
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.email_sender, settings.email_password.get_secret_value())
        rechazados = smtp.sendmail(settings.email_sender, destinatarios, mensaje.as_string())
    if rechazados:
        raise smtplib.SMTPRecipientsRefused(rechazados)


def enviar_alerta(asunto: str, cuerpo: str) -> bool:
    """Mail de texto plano a la lista de alertas. Devuelve si pudo enviarlo.

    Nunca propaga: si el SMTP también está caído, se avisa en el log y se sigue.
    Una alerta que rompe el proceso que intentaba reportar no sirve de nada.
    """
    destinatarios = settings.destinatarios_alertas
    asunto, cuerpo = redactar(asunto), redactar(cuerpo)
    em = MIMEMultipart()
    em["From"] = settings.email_sender
    em["To"] = ", ".join(destinatarios)
    em["Subject"] = asunto
    em.attach(MIMEText(cuerpo, "plain"))

    try:
        enviar_smtp(em, destinatarios)
        log.info("Alerta enviada: %s", asunto)
        return True
    except Exception as exc:
        log.error("No se pudo enviar la alerta por mail (%s): %s", asunto, exc)
        return False


def alertar_scraper_caido(exc: BaseException) -> bool:
    """Alerta para un ScraperError, con sitio y paso si vienen en la excepción."""
    sitio = getattr(exc, "site", "desconocido")
    paso = getattr(exc, "step", "desconocido")
    causa = getattr(exc, "cause", exc)

    cuerpo = (
        f"Una fuente falló y el reporte no se pudo armar.\n\n"
        f"Fuente : {sitio}\n"
        f"Paso   : {paso}\n"
        f"Causa  : {type(causa).__name__}: {causa}\n\n"
        f"--- traceback ---\n"
        f"{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}"
    )
    return enviar_alerta(f"⚠️ Scraper caído: {sitio}", cuerpo)


def alertar_validacion(error: BaseException) -> bool:
    """La fila del día no pasó models.FilaMacro: no se guardó ni se mandó nada."""
    return enviar_alerta("Atención: Error en el mailing automático", str(error))
