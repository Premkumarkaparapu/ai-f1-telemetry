"""Storage provider abstractions — local, S3, and GCS.

Caches remote cloud files locally on the container filesystem to minimize
external download latency and billing.
"""

from abc import ABC, abstractmethod
import os
from pathlib import Path
from backend.app.core.config import RAW_DIR
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class StorageProvider(ABC):
    """Abstract interface defining the get_file capability."""

    @abstractmethod
    def get_file(self, slug: str) -> Path:
        """Download file and return absolute path on filesystem."""
        pass


class LocalStorageProvider(StorageProvider):
    """Retrieves cached files directly from local storage."""

    def get_file(self, slug: str) -> Path:
        local_path = RAW_DIR / slug
        if not local_path.exists():
            raise FileNotFoundError(f"Local file {slug} not found in RAW_DIR.")
        logger.info("LocalStorageProvider: file %s found", slug)
        return local_path


class S3StorageProvider(StorageProvider):
    """Downloads files on-demand from Amazon S3, caching them locally."""

    def __init__(self, bucket_name: str | None = None):
        self.bucket = bucket_name or os.getenv("S3_BUCKET_NAME", "f1-telemetry-pickles")

    def get_file(self, slug: str) -> Path:
        local_path = RAW_DIR / slug
        if local_path.exists():
            logger.info("S3StorageProvider: file %s found in local cache", slug)
            return local_path

        logger.info("S3StorageProvider: downloading %s from S3 bucket '%s'", slug, self.bucket)

        # Ensure directories exist
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        # Dynamic import of boto3 to prevent server crash if not installed
        try:
            import boto3
            from botocore.exceptions import ClientError

            s3 = boto3.client("s3")
            s3.download_file(self.bucket, slug, str(local_path))
            logger.info("S3StorageProvider: download of %s completed successfully", slug)
            return local_path
        except ImportError:
            logger.warning("boto3 is not installed. Simulating local stub download for %s", slug)
            raise FileNotFoundError(f"boto3 library missing; cannot download {slug} from S3.")
        except ClientError as exc:
            logger.error("Failed to download %s from S3: %s", slug, exc)
            raise FileNotFoundError(f"File {slug} not found in S3 bucket {self.bucket}: {exc}")


class GCSStorageProvider(StorageProvider):
    """Downloads files on-demand from Google Cloud Storage, caching them locally."""

    def __init__(self, bucket_name: str | None = None):
        self.bucket = bucket_name or os.getenv("GCS_BUCKET_NAME", "f1-telemetry-pickles")

    def get_file(self, slug: str) -> Path:
        local_path = RAW_DIR / slug
        if local_path.exists():
            logger.info("GCSStorageProvider: file %s found in local cache", slug)
            return local_path

        logger.info("GCSStorageProvider: downloading %s from GCS bucket '%s'", slug, self.bucket)

        RAW_DIR.mkdir(parents=True, exist_ok=True)

        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(self.bucket)
            blob = bucket.blob(slug)
            blob.download_to_filename(str(local_path))
            logger.info("GCSStorageProvider: download of %s completed successfully", slug)
            return local_path
        except ImportError:
            logger.warning(
                "google-cloud-storage not installed. "
                "Simulating local stub download for %s", slug
            )
            raise FileNotFoundError(
                f"google-cloud-storage library missing; "
                f"cannot download {slug} from GCS."
            )
        except Exception as exc:
            logger.error("Failed to download %s from GCS: %s", slug, exc)
            raise FileNotFoundError(f"File {slug} not found in GCS bucket {self.bucket}: {exc}")


# ── Storage Factory ───────────────────────────────────────────────────────────

def get_storage_provider() -> StorageProvider:
    """Instantiate the active storage provider based on env configuration."""
    provider_name = os.getenv("STORAGE_PROVIDER", "local").lower().strip()

    if provider_name == "s3":
        return S3StorageProvider()
    elif provider_name == "gcs":
        return GCSStorageProvider()
    else:
        return LocalStorageProvider()
