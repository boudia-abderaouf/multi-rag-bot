from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATA_DIR: Path = Path("./data")
    DOWNLOAD_TIMEOUT: int = 120
    FORCE_REDOWNLOAD: bool = False
    QDRANT_URL: str = "http://localhost:6333"
    OPENAI_API_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def raw_dir(self) -> Path:
        """Dossier où sont stockés les PDFs bruts téléchargés."""
        path = self.DATA_DIR / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()