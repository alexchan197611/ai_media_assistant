from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(ROOT / 'storage' / 'projects' / 'app.sqlite3').as_posix()}"
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    upload_dir: Path = ROOT / "storage" / "uploads"
    output_dir: Path = ROOT / "storage" / "outputs"
    tts_cache_dir: Path = ROOT / "storage" / "projects" / "tts"
    model_config = SettingsConfigDict(env_prefix="AMA_", env_file=".env", extra="ignore")

settings = Settings()
