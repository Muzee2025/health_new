"""Bounded raster uploads; SVG/HTML and client paths are never accepted."""
import io
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
DOCUMENT_TYPES = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}


def validate_image_content(content: bytes, filename: str, content_type: str | None = None) -> str:
    if not content:
        raise HTTPException(status_code=400, detail="Image must not be empty")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be at most 5 MiB")
    if not filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise HTTPException(status_code=400, detail="Invalid image filename")
    ext = Path(filename).suffix.lower()
    if ext not in IMAGE_TYPES or (content_type is not None and content_type != IMAGE_TYPES[ext]):
        raise HTTPException(status_code=415, detail="Use a PNG, JPEG or WebP image with a matching media type")
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 33 and content[12:16] == b"IHDR"
    is_jpeg = content.startswith(b"\xff\xd8\xff") and content.endswith(b"\xff\xd9")
    is_webp = len(content) >= 16 and content[:4] == b"RIFF" and content[8:12] == b"WEBP" and int.from_bytes(content[4:8], "little") + 8 == len(content)
    if not ((ext == ".png" and is_png) or (ext in (".jpg", ".jpeg") and is_jpeg) or (ext == ".webp" and is_webp)):
        raise HTTPException(status_code=415, detail="Image content does not match its format")
    if is_png:
        width, height = struct.unpack(">II", content[16:24])
        if not 0 < width <= 4096 or not 0 < height <= 4096:
            raise HTTPException(status_code=413, detail="PNG dimensions must be at most 4096 by 4096")
    return ".jpg" if ext == ".jpeg" else ext


async def read_image_upload(file: UploadFile) -> tuple[bytes, str]:
    content = await read_bounded_upload(file)
    return content, validate_image_content(content, file.filename or "", file.content_type)


async def read_bounded_upload(file: UploadFile) -> bytes:
    chunks = []
    size = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image must be at most 5 MiB")
        chunks.append(chunk)
    content = b"".join(chunks)
    return content


def validate_document_content(content: bytes, filename: str, content_type: str | None) -> str:
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Document must be nonempty and at most 5 MiB")
    if not filename or any(char in filename for char in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="Invalid document filename")
    ext = Path(filename).suffix.lower()
    if ext not in DOCUMENT_TYPES or content_type != DOCUMENT_TYPES[ext]:
        raise HTTPException(status_code=415, detail="Use a PDF or non-macro DOCX with a matching media type")
    if ext == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
            raise HTTPException(status_code=415, detail="Invalid PDF document")
        return ext
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if len(entries) > 200 or len(names) != len(entries) or sum(entry.file_size for entry in entries) > 20 * 1024 * 1024:
                raise ValueError("Archive bounds")
            if not {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}.issubset(names):
                raise ValueError("Not a DOCX package")
            for entry in entries:
                name = entry.filename
                parts = name.replace("\\", "/").split("/")
                if (name.startswith(("/", "\\")) or "\\" in name or ":" in name or ".." in parts
                        or entry.flag_bits & 1 or (entry.external_attr >> 16) & 0o170000 == 0o120000
                        or entry.file_size > 8 * 1024 * 1024
                        or entry.file_size > max(1, entry.compress_size) * 200
                        or any(word in name.lower() for word in ("vbaproject", "activex", "embeddings/"))):
                    raise ValueError("Unsafe DOCX entry")
                if name.endswith(".xml") or name.endswith(".rels"):
                    raw = archive.read(entry)
                    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"macroenabled" in raw.lower():
                        raise ValueError("Unsafe XML")
                    ElementTree.fromstring(raw)
            # Consume every member to check CRC and declared decompression sizes.
            if archive.testzip() is not None:
                raise ValueError("Invalid CRC")
    except (zipfile.BadZipFile, ValueError, RuntimeError, OSError, ElementTree.ParseError):
        raise HTTPException(status_code=415, detail="Invalid or unsupported DOCX document") from None
    return ext
