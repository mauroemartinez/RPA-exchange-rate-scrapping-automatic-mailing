"""Envío de mails de alerta cuando algo del pipeline falla.

Separado del notebook para que cualquier módulo pueda avisar sin depender de que
la celda 33 esté definida. El reporte diario sigue armándose en el notebook.
"""

import smtplib
import ssl
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def enviar_alerta(asunto: str, cuerpo: str) -> bool:
    """Mail de texto plano a EMAIL_RECEIVER_CSV. Devuelve si pudo enviarlo.

    Nunca propaga: si el SMTP también está caído, se avisa por consola y se sigue.
    Una alerta que rompe el proceso que intentaba reportar no sirve de nada.
    """
    destinatarios = list(settings.email_receiver_csv)
    em = MIMEMultipart()
    em["From"] = settings.email_sender
    em["To"] = ", ".join(destinatarios)
    em["Subject"] = asunto
    em.attach(MIMEText(cuerpo, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.login(settings.email_sender, settings.email_password.get_secret_value())
            smtp.sendmail(settings.email_sender, destinatarios, em.as_string())
        print(f"📧 Alerta enviada: {asunto}")
        return True
    except Exception as exc:
        print(f"⚠️ No se pudo enviar la alerta por mail: {exc}")
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
