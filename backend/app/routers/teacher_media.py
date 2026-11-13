import hashlib
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..upload_security import (
    DOCUMENT_TYPES,
    IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    read_bounded_upload,
    read_image_upload,
    validate_document_content,
    validate_image_content,
)
from .auth import get_current_user
from .teacher_shared import _build_avatar_url, check_teacher_role

router = APIRouter(prefix="/api/teacher")

TEACHER_AVATAR_SUBDIR = "teacher_avatars"

TEACHER_AVATAR_DIR = Path("uploads") / TEACHER_AVATAR_SUBDIR

PICTURE_SOURCE_DIR = Path(r"D:\Muzee\develop\IDEA_code\health_new\picture")

ALLOWED_AVATAR_EXT = set(IMAGE_TYPES)

def _safe_remove_file(path: Path):
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        # 文件清理失败不影响主流程
        pass

def _upsert_teacher_avatar_content(
    *,
    request: Request,
    db: Session,
    teacher_id: int,
    content: bytes,
    ext: str,
):
    image_hash = hashlib.sha256(content).hexdigest()
    conflict = (
        db.query(models.TeacherAvatar)
        .filter(
            models.TeacherAvatar.image_hash == image_hash,
            models.TeacherAvatar.teacher_id != teacher_id,
        )
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="该头像已被其他教师使用，禁止共用图片")

    TEACHER_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"teacher_{teacher_id}_{uuid.uuid4().hex}{ext}"
    relative_path = f"{TEACHER_AVATAR_SUBDIR}/{filename}"
    abs_path = Path("uploads") / relative_path

    with abs_path.open("wb") as f:
        f.write(content)

    old_abs_path: Path | None = None
    avatar = db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id == teacher_id).first()
    if avatar:
        old_abs_path = Path("uploads") / avatar.relative_path
        avatar.file_name = filename
        avatar.relative_path = relative_path
        avatar.image_hash = image_hash
        avatar.file_size = len(content)
    else:
        avatar = models.TeacherAvatar(
            teacher_id=teacher_id,
            file_name=filename,
            relative_path=relative_path,
            image_hash=image_hash,
            file_size=len(content),
        )
        db.add(avatar)

    profile = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == teacher_id).first()
    avatar_url = _build_avatar_url(request, relative_path)
    if profile:
        profile.avatar = avatar_url
    else:
        db.add(models.TeacherProfile(user_id=teacher_id, avatar=avatar_url, time_slots="[]"))
    try:
        db.commit()
    except Exception:
        # The file was written before the row: roll it back so a failed commit cannot
        # leave an unreferenced image on disk. Only the file written just above is
        # removed; the previous avatar is untouched.
        db.rollback()
        _safe_remove_file(abs_path)
        raise

    if old_abs_path and old_abs_path != abs_path:
        _safe_remove_file(old_abs_path)

    return {
        "message": "头像上传成功",
        "teacher_id": teacher_id,
        "avatar_url": avatar_url,
        "relative_path": relative_path,
        "image_hash": image_hash,
        "file_size": len(content),
    }

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    content = await read_bounded_upload(file)
    requested_ext = Path(file.filename or "").suffix.lower()
    is_document = requested_ext in DOCUMENT_TYPES
    if is_document:
        ext = validate_document_content(content, file.filename or "", file.content_type)
        directory = _article_document_directory()
    else:
        ext = validate_image_content(content, file.filename or "", file.content_type)
        directory = Path("uploads") / "public_images"
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise HTTPException(status_code=503, detail="Upload storage is unavailable")
    filename = f"{uuid.uuid4().hex}{ext}"
    try:
        with (directory / filename).open("xb") as stream:
            stream.write(content)
    except OSError:
        raise HTTPException(status_code=503, detail="Upload storage is unavailable") from None
    if is_document:
        return {"url": str(request.url_for("download_article_document", filename=filename))}
    return {"url": str(request.base_url).rstrip("/") + f"/static/public_images/{filename}"}

def _article_document_directory() -> Path:
    base = Path("uploads").resolve()
    directory = base / "article_documents"
    if directory.is_symlink():
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.resolve().parent != base:
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    return directory

@router.get("/documents/{filename}")
def download_article_document(filename: str, current_user: models.User = Depends(get_current_user)):
    if current_user.role not in {"student", "teacher"}:
        raise HTTPException(status_code=403, detail="Sign in to download this document")
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|docx)", filename):
        raise HTTPException(status_code=404, detail="Document not found")
    directory = _article_document_directory()
    path = directory / filename
    if path.is_symlink() or not path.is_file() or path.resolve().parent != directory.resolve():
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(path, media_type=DOCUMENT_TYPES[path.suffix], filename=f"document{path.suffix}",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'", "Cache-Control": "private, no-store"})

@router.post("/avatar")
async def upload_teacher_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    教师头像上传（严格一对一）：
    1) teacher_id 在 teacher_avatars 唯一；
    2) image_hash 全局唯一，禁止共用同一张图；
    3) 上传新头像时自动删除旧头像文件并更新记录。
    """
    check_teacher_role(current_user)
    content, ext = await read_image_upload(file)

    return _upsert_teacher_avatar_content(
        request=request,
        db=db,
        teacher_id=current_user.id,
        content=content,
        ext=ext,
    )

class AvatarFromPictureRequest(BaseModel):
    filename: str

@router.post("/avatar/from-picture")
def set_teacher_avatar_from_picture(
    payload: AvatarFromPictureRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    filename = os.path.basename((payload.filename or "").strip())
    if not filename:
        raise HTTPException(status_code=400, detail="filename 不能为空")
    source_path = PICTURE_SOURCE_DIR / filename
    ext = source_path.suffix.lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail=f"仅支持 {sorted(ALLOWED_AVATAR_EXT)} 格式")
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=404, detail="指定图片不存在")
    if source_path.stat().st_size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be at most 5 MiB")
    content = source_path.read_bytes()
    ext = validate_image_content(content, filename)
    return _upsert_teacher_avatar_content(
        request=request,
        db=db,
        teacher_id=current_user.id,
        content=content,
        ext=ext,
    )
