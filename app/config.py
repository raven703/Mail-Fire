from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://mailfire:mailfire@localhost:5432/mailfire"
    admin_password: str = ""
    cookie_secure: bool = True
    max_message_bytes: int = 50 * 1024 * 1024
    max_objects: int = 200
    max_expanded_bytes: int = 100 * 1024 * 1024
    max_archive_depth: int = 3
    import_root: str = "/imports"
    import_stability_seconds: int = 15
    import_recursive: bool = True
    import_policy: str = "leave"
    internal_domains: str = ""
    smtp_networks: str = "127.0.0.1/32"
    smtp_host: str = "0.0.0.0"
    smtp_port: int = 2525
    session_hours: int = 8
    analysis_timeout: int = 120
    job_lease_seconds: int = 60
    job_heartbeat_seconds: int = 15


@lru_cache
def settings():
    return Settings()
