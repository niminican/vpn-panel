from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Panel
    panel_host: str = "0.0.0.0"
    panel_port: int = 8080
    secret_key: str = "change-this-to-a-random-secret-key"
    admin_username: str = "admin"
    admin_password: str = "admin"

    # Database
    database_url: str = "sqlite:///./data/vpnpanel.db"

    # WireGuard
    wg_interface: str = "wg0"
    wg_port: int = 51820
    wg_subnet: str = "10.8.0.0/24"
    wg_dns: str = "1.1.1.1,8.8.8.8"
    wg_server_ip: str = ""
    wg_config_dir: str = "/etc/wireguard"

    # Encryption
    encryption_key: str = "change-this-to-a-fernet-key"

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""

    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # Demo mode (skip actual WireGuard/iptables commands)
    demo_mode: bool = False

    # JWT
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    @property
    def data_dir(self) -> Path:
        path = Path("data")
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def check_security_defaults():
    """Warn about insecure default values at startup."""
    import logging
    logger = logging.getLogger(__name__)
    warnings = []

    if settings.secret_key == "change-this-to-a-random-secret-key":
        warnings.append("SECRET_KEY is using the default value! Set a random value in .env")

    if settings.admin_password == "admin":
        warnings.append("ADMIN_PASSWORD is 'admin'! Change it immediately after first login")

    if settings.encryption_key == "change-this-to-a-fernet-key":
        warnings.append("ENCRYPTION_KEY is using the default value! Set a Fernet key in .env")

    for w in warnings:
        logger.critical(f"SECURITY WARNING: {w}")
