"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env."""

    instance_name: str = "local-image-search"

    qdrant_url: str = "http://127.0.0.1:6335"
    qdrant_grpc_port: int = 6336
    qdrant_prefer_grpc: bool = True
    qdrant_path: str = str(PROJECT_ROOT / "data" / "qdrant")
    qdrant_collection: str = "local_image_search_images"

    redis_url: str = ""
    redis_queue_key: str = "image_search:local:task_queue"

    model_name: str = "google/siglip2-so400m-patch14-384"
    model_local_files_only: bool = False
    device: str = "cuda"
    batch_size: int = 64
    vector_dimension: int = 1152

    queue_wait_timeout: float = 0.5

    host: str = "127.0.0.1"
    port: int = 4568

    error_db_path: str = str(PROJECT_ROOT / "data" / "errors.db")

    class Config:
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
