import logging
from datetime import timedelta

from google.cloud import storage

from app.core.config import get_settings
from app.providers.base import StorageProvider

logger = logging.getLogger(__name__)


class GCSStorageProvider(StorageProvider):
    """Storage provider backed by Google Cloud Storage."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client = storage.Client(project=settings.GOOGLE_PROJECT_ID)
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.bucket = self.client.bucket(self.bucket_name)
        logger.info("GCSStorage: initialised bucket=%s", self.bucket_name)

    async def put_file(self, path: str, data: bytes, content_type: str) -> str:
        blob = self.bucket.blob(path)
        blob.upload_from_string(data, content_type=content_type)
        url = f"gs://{self.bucket_name}/{path}"
        logger.info("GCSStorage: put_file %s (%d bytes)", url, len(data))
        return url

    async def get_file(self, path: str) -> bytes:
        blob = self.bucket.blob(path)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: gs://{self.bucket_name}/{path}")
        return blob.download_as_bytes()

    async def get_signed_url(self, path: str, expiry_sec: int = 3600) -> str:
        blob = self.bucket.blob(path)
        if not blob.exists():
            raise FileNotFoundError(f"GCS object not found: gs://{self.bucket_name}/{path}")
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiry_sec),
            method="GET",
        )
        logger.info("GCSStorage: signed_url for %s (expiry=%ds)", path, expiry_sec)
        return url

    async def delete_file(self, path: str) -> None:
        blob = self.bucket.blob(path)
        if blob.exists():
            blob.delete()
            logger.info("GCSStorage: deleted gs://%s/%s", self.bucket_name, path)
        else:
            logger.warning("GCSStorage: delete — object not found: %s", path)
