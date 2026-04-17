"""
File upload service — secure file handling for DMS, IT Support,
Facility, and Announcements modules.

Files are stored under app/static/uploads/<module>/<random_hex>/
"""

import os
import uuid
import logging

logger = logging.getLogger(__name__)

UPLOAD_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "uploads")

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "jpg", "jpeg", "png", "gif", "bmp", "zip", "rar",
}

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage, module: str) -> dict | None:
    """
    Save an uploaded file securely.

    Args:
        file_storage: Flask FileStorage object (from request.files).
        module: Sub-folder name (e.g. 'dms', 'facility', 'announcements').

    Returns:
        dict with 'filename', 'original_name', 'path', 'url' on success,
        None on failure.
    """
    if not file_storage or not file_storage.filename:
        return None

    original = file_storage.filename
    if not _allowed_file(original):
        logger.warning("Upload rejected — disallowed extension: %s", original)
        return None

    # Generate unique path
    random_hex = uuid.uuid4().hex[:12]
    ext = original.rsplit(".", 1)[1].lower()
    safe_name = f"{random_hex}.{ext}"

    module_dir = os.path.join(UPLOAD_BASE, module)
    os.makedirs(module_dir, exist_ok=True)

    full_path = os.path.join(module_dir, safe_name)
    file_storage.save(full_path)

    logger.info("File uploaded: %s → %s", original, full_path)

    return {
        "filename": safe_name,
        "original_name": original,
        "path": full_path,
        "url": f"/static/uploads/{module}/{safe_name}",
    }


def delete_upload(module: str, filename: str) -> bool:
    """Delete an uploaded file. Returns True if deleted."""
    full_path = os.path.join(UPLOAD_BASE, module, filename)
    if os.path.exists(full_path):
        os.remove(full_path)
        logger.info("File deleted: %s", full_path)
        return True
    return False
