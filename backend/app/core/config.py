import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Vellei AI Mock Interview Platform"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # AI / Model Config
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # DB Config
    DATABASE_URL: str = "sqlite:///./mock_interviews.db"
    
    # App Config
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = "*"

settings = Settings()
