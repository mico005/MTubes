from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "YouTube Music Clone API"

    # Defaulting to SQLite for local MVP testing.
    # Override this in your .env file with a PostgreSQL URI when deploying (e.g., Supabase).
    DATABASE_URL: str = "sqlite:///./music_clone.db"

    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
