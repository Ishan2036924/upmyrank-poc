from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql://upmyrank:upmyrank@localhost:5432/upmyrank"
    redis_url: str = "redis://localhost:6379"
    openai_api_key: str = Field(default="", min_length=0)  # validated at startup if blank
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"  # kept for backwards compat

    # Tiered model routing
    model_cheap: str = "gpt-4o-mini"      # classification, summarization
    model_quality: str = "gpt-4.1-mini"   # Socratic responses, solutions

    # Admin access gate
    admin_student_id: str = ""             # legacy: UUID of admin student (kept for backward compat)
    admin_emails: str = ""                 # preferred: comma-separated admin email addresses

    # Supabase
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_secret_key: str = ""


settings = Settings()
