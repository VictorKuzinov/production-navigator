from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str
    app_version: str
    debug: bool

    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

settings = Settings()  # pyright: ignore[reportCallIssue]