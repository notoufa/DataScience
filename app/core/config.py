import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_KEY: str = "sk-0644acae22b64c389e55a6e3eea54f15"
    TESSERACT_CMD: str = "E:\\others\\Tesseract-OCR\\tesseract.exe"
    DB_HOST: str = "222.20.96.38"
    DB_NAME: str = "SiemensHarden_DB"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "Liu_123456"
    DB_PORT: str = "5432"
    VANNA_API_KEY: str = "6b837c6bf630461eab556b4223ed8c22"
    VANNA_MODEL: str = "test2820"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 