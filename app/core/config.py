import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_KEY: str = 'sk-0644acae22b64c389e55a6e3eea54f15'
    TESSERACT_CMD: str = r'E:\others\Tesseract-OCR'
    
    class Config:
        env_file = ".env"

settings = Settings() 