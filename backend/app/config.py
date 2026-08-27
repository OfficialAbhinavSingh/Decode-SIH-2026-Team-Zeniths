from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field("postgresql+psycopg://neer:neer@localhost:5432/neerdrishti", validation_alias="DATABASE_URL")
    ingest_token: str = Field("dev-ingest-token", validation_alias="INGEST_TOKEN")
    city_default: str = Field("Jaipur", validation_alias="CITY_DEFAULT")
    cors_origins: str = Field("http://localhost:5173", validation_alias="CORS_ORIGINS")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
