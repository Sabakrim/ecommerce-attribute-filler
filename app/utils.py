import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AttributeFiller.Utils")

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")

# Ensure temporary working directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_EXCEL_BYTES = int(os.environ.get("MAX_EXCEL_MB", 20)) * 1024 * 1024
MAX_PDF_BYTES = int(os.environ.get("MAX_PDF_MB", 50)) * 1024 * 1024

def generate_session_id() -> str:
    return str(uuid.uuid4())[:8]

def validate_file_size(file_bytes: bytes, max_bytes: int, file_type: str) -> None:
    if len(file_bytes) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValueError(f"{file_type} file size exceeds maximum permitted limit of {max_mb} MB.")

def save_temp_upload(file_bytes: bytes, filename: str) -> Path:
    session_id = generate_session_id()
    safe_name = f"{session_id}_{Path(filename).name}"
    target_path = UPLOAD_DIR / safe_name
    with open(target_path, "wb") as f:
        f.write(file_bytes)
    logger.info(f"Saved temporary upload: {target_path}")
    return target_path

def cleanup_file(path: Path) -> None:
    try:
        if path and path.exists():
            path.unlink()
            logger.info(f"Cleaned up temporary file: {path}")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {path}: {e}")

def sanitize_filename(name: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip()
