from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Répertoire racine des données (PDFs téléchargés)
    # Local  : ./data  (relatif au projet)
    # Prod   : /app/data  (volume Docker monté)
    DATA_DIR: Path = Path("./data")

    # Timeout HTTP pour le téléchargement des PDFs (secondes)
    DOWNLOAD_TIMEOUT: int = 120

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def raw_dir(self) -> Path:
        """Dossier où sont stockés les PDFs bruts téléchargés."""
        path = self.DATA_DIR / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()