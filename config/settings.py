import os
from pathlib import Path
from typing import get_args, get_origin

try:
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover - fallback for lightweight local envs
    class BaseSettings:
        model_config: dict = {}

        def __init__(self, **overrides):
            env_values = self._read_env_file()
            annotations = getattr(type(self), "__annotations__", {})

            for field_name, field_type in annotations.items():
                if field_name in overrides:
                    value = overrides[field_name]
                elif field_name in os.environ:
                    value = os.environ[field_name]
                elif field_name in env_values:
                    value = env_values[field_name]
                else:
                    value = getattr(type(self), field_name)
                setattr(self, field_name, self._coerce_value(field_type, value))

        def _read_env_file(self) -> dict[str, str]:
            env_file = self.model_config.get("env_file")
            if not env_file:
                return {}

            path = Path(env_file)
            if not path.exists():
                return {}

            values: dict[str, str] = {}
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
            return values

        def _coerce_value(self, field_type, value):
            origin = get_origin(field_type)
            args = get_args(field_type)
            target_type = field_type

            if origin is not None and type(None) in args:
                non_none = [arg for arg in args if arg is not type(None)]
                target_type = non_none[0] if non_none else str
                if value in {"", None}:
                    return None

            if target_type is Path:
                return Path(value)
            if target_type is bool:
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in {"1", "true", "yes", "on"}
            if target_type is int:
                return int(value)
            return value


class Settings(BaseSettings):
    DATA_DIR: Path = Path("./data")
    DOWNLOAD_TIMEOUT: int = 120
    FORCE_REDOWNLOAD: bool = False
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_DIMENSIONS: int | None = None
    RESPONSE_MODEL: str = "gpt-4.1-mini"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def data_dir(self) -> Path:
        path = self.DATA_DIR if self.DATA_DIR.is_absolute() else self.project_root / self.DATA_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def raw_dir(self) -> Path:
        path = self.data_dir / "raw"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def chunks_dir(self) -> Path:
        path = self.data_dir / "chunks"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
