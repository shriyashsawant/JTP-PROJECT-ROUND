from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://auramatch:auramatch_secret@db:5432/auramatch"
    model_name: str = "all-MiniLM-L6-v2"
    app_name: str = "AuraMatch AI"
    debug: bool = True

    class Config:
        env_file = ".env"

settings = Settings()
