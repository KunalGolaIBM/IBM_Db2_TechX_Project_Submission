import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    db2_host: str = "db2"
    db2_port: int = 50000
    db2_database: str = "FINDB"
    db2_user: str = "db2inst1"
    db2_password: str = ""
    db2_schema: str = "FINSIGHT"

    # AI Service Host & Security
    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 8000
    ai_service_internal_token: str = "dev_internal_secret_token"

    # LLM & Embeddings
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # Demo default user
    demo_user_id: str = "usr_demo_synthetic_01"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
