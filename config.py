"""Configuración central del proyecto.

Todas las variables del .env se declaran acá una sola vez, con tipos estrictos.
Si falta una variable obligatoria o tiene un valor inválido, el proceso falla al
importar este módulo y no a mitad del pipeline, después de haber scrapeado todo.

Uso:
    from config import settings
    engine = create_engine(settings.supabase_db_url.get_secret_value())
"""

from pathlib import Path
from typing import Annotated

from pydantic import EmailStr, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Lista de mails separada por comas en el .env
# NoDecode evita que pydantic-settings intente parsearla como JSON
# con cualquier list[...]. Cada dirección se valida individualmente.
CommaEmails = Annotated[list[EmailStr], NoDecode]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Envío de mail ────────────────────────────────────────────────────────
    email_sender: EmailStr
    email_password: SecretStr
    email_receiver: CommaEmails
    email_receiver_csv: CommaEmails

    # ── Claves de API ────────────────────────────────────────────────────────
    gemini_api_key_1: SecretStr
    gemini_api_key_2: SecretStr | None = None
    fed_api_key: SecretStr
    supabase_db_url: SecretStr

    # ── Rutas ────────────────────────────────────────────────────────────────
    ruta_bbdd: Path
    ruta_repo: Path

    # ── Servicio / despliegue ────────────────────────────────────────────────
    # Opcionales: hoy ningún módulo las lee, así que su ausencia no debe frenar una corrida.
    service_route: str | None = None
    api_key_easy_panel: SecretStr | None = None

    @field_validator("email_receiver", "email_receiver_csv", mode="before")
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
    def gemini_keys(self) -> list[str]:
        """Las keys de Gemini en orden de rotación, descartando las ausentes."""
        keys = [self.gemini_api_key_1, self.gemini_api_key_2]
        return [k.get_secret_value() for k in keys if k is not None]


settings = Settings()
