from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PROJECT_NAME: str = "AeroInspect AI"
    VERSION: str = "2.0.0"

    DATABASE_URL: str

    ALLOWED_ORIGINS: str = "*"

    COMPLIANCE_BASE_SCORE: float = 100.0
    VIOLATION_PENALTY_POINTS: float = 5.0

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    ROUTERBENCH_API_KEY: str = ""

    class Config:
        env_file = ".env"

    @property
    def cors_origins_list(self):
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()