"""
Storage abstraction for uploaded files.

Currently backed by the local filesystem (./storage/documents/) so the
project runs with zero external setup. To move to S3/GCS later, only this
file needs to change — everywhere else calls upload/download/delete and
doesn't care where the bytes actually live.
"""

import uuid
from pathlib import Path

STORAGE_ROOT = Path("storage/documents")
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def upload_file(file_bytes: bytes, original_filename: str) -> str:
    """
    Save file bytes to storage and return a unique storage_key that can be
    used later to retrieve or delete it. Never trust original_filename for
    the actual save path (avoids path traversal); we only use it for the extension.
    """
    extension = Path(original_filename).suffix
    storage_key = f"{uuid.uuid4()}{extension}"
    destination = STORAGE_ROOT / storage_key
    destination.write_bytes(file_bytes)
    return storage_key


def download_file(storage_key: str) -> bytes:
    path = STORAGE_ROOT / storage_key
    if not path.exists():
        raise FileNotFoundError(f"No file found for storage_key={storage_key}")
    return path.read_bytes()


def delete_file(storage_key: str) -> None:
    path = STORAGE_ROOT / storage_key
    if path.exists():
        path.unlink()
