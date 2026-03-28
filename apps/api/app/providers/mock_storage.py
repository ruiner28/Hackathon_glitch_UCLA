import logging
import os
from pathlib import Path

from app.providers.base import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorageProvider(StorageProvider):
    """Stores files on the local filesystem under a configurable base path."""

    def __init__(self, base_path: str = "./storage"):
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("LocalStorage: base_path=%s", self.base_path)

    def _full_path(self, path: str) -> Path:
        # Prevent path traversal
        safe = Path(path).as_posix().lstrip("/")
        return self.base_path / safe

    async def put_file(self, path: str, data: bytes, content_type: str) -> str:
        full = self._full_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        logger.info("LocalStorage: put_file %s (%d bytes, %s)", full, len(data), content_type)
        return f"file://{full}"

    async def get_file(self, path: str) -> bytes:
        full = self._full_path(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {full}")
        return full.read_bytes()

    async def get_signed_url(self, path: str, expiry_sec: int = 3600) -> str:
        full = self._full_path(path)
        if not full.exists():
            raise FileNotFoundError(f"File not found: {full}")
        return f"file://{full}"

    async def delete_file(self, path: str) -> None:
        full = self._full_path(path)
        if full.exists():
            os.remove(full)
            logger.info("LocalStorage: deleted %s", full)
        else:
            logger.warning("LocalStorage: delete_file — file not found: %s", full)
