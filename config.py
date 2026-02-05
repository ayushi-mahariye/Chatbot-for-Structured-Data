from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = ""
    
    # JWT
    jwt_secret_key: str = ""  # Default value, overridden by env var
    jwt_algorithm: str = ""
    
    # POS API
    pos_api_url: str = "http://localhost:5000"
    pos_api_jwt_public_key: Optional[str] = None
    
    # OpenAI
    openai_api_key: Optional[str] = None
    
    # Redis
    redis_url: Optional[str] = None
    
    # Application
    debug: bool = True
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()