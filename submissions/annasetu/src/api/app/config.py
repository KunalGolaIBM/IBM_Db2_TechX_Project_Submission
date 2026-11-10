from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AnnaSetu"
    environment: str = "development"
    db2_host: str = "127.0.0.1"
    db2_port: int = 50000
    db2_name: str = "ANNASETU"
    db2_user: str = "db2inst1"
    db2_password: str = ""
    jwt_secret: str = ""
    demo_password: str = ""
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_demo_data: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def db2_dsn(self) -> str:
        return (
            f"DATABASE={self.db2_name};HOSTNAME={self.db2_host};"
            f"PORT={self.db2_port};PROTOCOL=TCPIP;UID={self.db2_user};"
            f"PWD={self.db2_password};"
        )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
