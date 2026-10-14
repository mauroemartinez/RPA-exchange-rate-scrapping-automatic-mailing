"""Configuración central del proyecto.

Todas las variables del .env se declaran acá una sola vez, con tipos estrictos.
Si falta una variable obligatoria o tiene un valor inválido, el proceso falla al
importar este módulo y no a mitad del pipeline, después de haber scrapeado todo.

Uso:
    from reporte.config import settings
    engine = create_engine(settings.supabase_db_url.get_secret_value())
"""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import EmailStr, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# La carpeta del proyecto, deducida de dónde está este archivo. Sirve para
# resolver rutas relativas del .env sin depender del directorio de trabajo.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent  # este archivo vive en reporte/

# Lista de mails separada por comas en el .env
# NoDecode evita que pydantic-settings intente parsearla como JSON
# con cualquier list[...]. Cada dirección se valida individualmente.
CommaEmails = Annotated[list[EmailStr], NoDecode]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ_PROYECTO / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Envío de mail ────────────────────────────────────────────────────────
    email_sender: EmailStr
    email_password: SecretStr
    email_receiver: CommaEmails
    email_receiver_csv: CommaEmails
    # Opcional: a quién van las alertas técnicas (tracebacks, errores de SMTP).
    # Vacía, van a EMAIL_RECEIVER_CSV como siempre.
    email_alertas: CommaEmails = Field(default_factory=list)

    # ── Claves de API ────────────────────────────────────────────────────────
    gemini_api_key_1: SecretStr
    gemini_api_key_2: SecretStr | None = None
    fed_api_key: SecretStr
    supabase_db_url: SecretStr

    # ── Rutas ────────────────────────────────────────────────────────────────
    ruta_bbdd: Path
    ruta_repo: Path

    @field_validator("ruta_bbdd", "ruta_repo")
    @classmethod
    def _resolver_relativa(cls, v: Path) -> Path:
        """Una ruta relativa se resuelve contra la carpeta del proyecto.

        Así el mismo .env sirve en cualquier máquina: 'data/archivo.csv' apunta
        siempre al lugar correcto sin importar dónde esté clonado el repo. Una
        ruta absoluta se respeta tal cual, para no romper los .env que ya existen.
        """
        return v if v.is_absolute() else (RAIZ_PROYECTO / v).resolve()

    @field_validator("gemini_api_key_2", mode="before")
    @classmethod
    def _key_vacia_es_sin_key(cls, v):
        """GEMINI_API_KEY_2= (vacía) cuenta como no configurada.

        pydantic-settings la leería como SecretStr(""), y una key vacía
        entraría a la rotación de Gemini como si fuera una key más.
        """
        if v is None:
            return None
        texto = v.get_secret_value() if isinstance(v, SecretStr) else str(v)
        return texto if texto.strip() else None

    @field_validator("email_receiver", "email_receiver_csv", "email_alertas", mode="before")
    @classmethod
    def _split_emails(cls, v: str | list[str]) -> list[str] | str:
        """Convierte 'a@x.com, b@y.com' en ['a@x.com', 'b@y.com'].

        Reemplaza a parse_env_email_list() del notebook. Corre en modo 'before',
        o sea antes de que pydantic valide el tipo list[str].
        """
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v

    @field_validator("email_receiver")
    @classmethod
    def _al_menos_un_destinatario(cls, v: list[EmailStr]) -> list[EmailStr]:
        if not v:
            raise ValueError("EMAIL_RECEIVER no puede estar vacío: el reporte no tendría a quién ir")
        return v

    @property
    def destinatarios_alertas(self) -> list[str]:
        """EMAIL_ALERTAS si está, si no EMAIL_RECEIVER_CSV."""
        return [str(m) for m in (self.email_alertas or self.email_receiver_csv)]

    @property
    def gemini_keys(self) -> list[str]:
        """Las keys de Gemini en orden de rotación, descartando las ausentes."""
        keys = [self.gemini_api_key_1, self.gemini_api_key_2]
        return [k.get_secret_value() for k in keys if k is not None]


settings = Settings()


def reemplazos_sensibles() -> list[tuple[str, str]]:
    """(texto, reemplazo) para cada secreto del .env y cada dirección de destinatario.

    Los más largos primero: una URL de conexión se tapa entera antes de que su
    contraseña se reemplace sola.
    """
    secretos = [
        settings.email_password, settings.gemini_api_key_1, settings.gemini_api_key_2,
        settings.fed_api_key, settings.supabase_db_url,
    ]
    pares = [(s.get_secret_value(), "***") for s in secretos if s is not None]
    url = urlparse(settings.supabase_db_url.get_secret_value())
    # La clave, y también el usuario del pooler (postgres.<id del proyecto>) y el host
    for parte in (url.password, url.username if url.username != "postgres" else None, url.hostname):
        if parte:
            pares.append((parte, "***"))
    destinatarios = {str(m) for m in [*settings.email_receiver, *settings.email_receiver_csv, *settings.email_alertas]}
    pares += [(m, "[destinatario]") for m in destinatarios]
    return sorted((p for p in pares if p[0]), key=lambda p: len(p[0]), reverse=True)


def redactar(texto: str) -> str:
    """El texto sin secretos ni direcciones de destinatarios: para logs, JSON y alertas."""
    for secreto, reemplazo in reemplazos_sensibles():
        texto = texto.replace(secreto, reemplazo)
    return texto
