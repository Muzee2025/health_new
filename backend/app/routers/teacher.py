from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.services.article_catalog import page_articles
from app.services.rag_service import (
    add_document_to_rag,
    delete_document_from_rag,
    get_rag_status,
)

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
from .teacher_crisis import (
    CrisisDecisionRequest as CrisisDecisionRequest,
)
from .teacher_crisis import (
    CrisisReviewRequest as CrisisReviewRequest,
)
from .teacher_crisis import (
    FollowUpCancel as FollowUpCancel,
)
from .teacher_crisis import (
    FollowUpComplete as FollowUpComplete,
)
from .teacher_crisis import (
    FollowUpCreate as FollowUpCreate,
)
from .teacher_crisis import (
    _follow_up_dict as _follow_up_dict,
)
from .teacher_crisis import (
    _serialize_real_warning_row as _serialize_real_warning_row,
)
from .teacher_crisis import (
    _transition_follow_up as _transition_follow_up,
)
from .teacher_crisis import (
    cancel_follow_up as cancel_follow_up,
)
from .teacher_crisis import (
    complete_follow_up as complete_follow_up,
)
from .teacher_crisis import (
    create_follow_up as create_follow_up,
)
from .teacher_crisis import (
    follow_up_router as _teacher_follow_up_router,
)
from .teacher_crisis import (
    get_crisis_review_history as get_crisis_review_history,
)
from .teacher_crisis import (
    get_pending_crisis_records as get_pending_crisis_records,
)
from .teacher_crisis import (
    list_follow_ups as list_follow_ups,
)
from .teacher_crisis import (
    review_pending_crisis as review_pending_crisis,
)
from .teacher_crisis import (
    router as _teacher_crisis_router,
)
from .teacher_dashboard import (
    create_teacher_profile as create_teacher_profile,
)
from .teacher_dashboard import (
    delete_teacher_profile as delete_teacher_profile,
)
from .teacher_dashboard import (
    get_appointments as get_appointments,
)
from .teacher_dashboard import (
    get_dashboard_stats as get_dashboard_stats,
)
from .teacher_dashboard import (
    get_teachers_profiles as get_teachers_profiles,
)
from .teacher_dashboard import (
    profiles_router as _teacher_profiles_router,
)
from .teacher_dashboard import (
    router as _teacher_dashboard_router,
)
from .teacher_dashboard import (
    update_appointment_status as update_appointment_status,
)
from .teacher_media import (
    ALLOWED_AVATAR_EXT as ALLOWED_AVATAR_EXT,
)
from .teacher_media import (
    PICTURE_SOURCE_DIR as PICTURE_SOURCE_DIR,
)
from .teacher_media import (
    TEACHER_AVATAR_DIR as TEACHER_AVATAR_DIR,
)
from .teacher_media import (
    TEACHER_AVATAR_SUBDIR as TEACHER_AVATAR_SUBDIR,
)
from .teacher_media import (
    AvatarFromPictureRequest as AvatarFromPictureRequest,
)
from .teacher_media import (
    _article_document_directory as _article_document_directory,
)
from .teacher_media import (
    _safe_remove_file as _safe_remove_file,
)
from .teacher_media import (
    _upsert_teacher_avatar_content as _upsert_teacher_avatar_content,
)
from .teacher_media import (
    download_article_document as download_article_document,
)
from .teacher_media import (
    router as _teacher_media_router,
)
from .teacher_media import (
    set_teacher_avatar_from_picture as set_teacher_avatar_from_picture,
)
from .teacher_media import (
    upload_file as upload_file,
)
from .teacher_media import (
    upload_teacher_avatar as upload_teacher_avatar,
)
from .teacher_shared import (
    _build_avatar_url as _build_avatar_url,
)
from .teacher_shared import (
    check_teacher_role as check_teacher_role,
)
from .teacher_students import (
    _support_actor_name as _support_actor_name,
)
from .teacher_students import (
    add_intervention as add_intervention,
)
from .teacher_students import (
    answer_assigned_question as answer_assigned_question,
)
from .teacher_students import (
    create_student as create_student,
)
from .teacher_students import (
    get_interventions as get_interventions,
)
from .teacher_students import (
    get_student_detail as get_student_detail,
)
from .teacher_students import (
    get_students as get_students,
)
from .teacher_students import (
    list_assigned_questions as list_assigned_questions,
)
from .teacher_students import (
    questions_router as _teacher_student_questions_router,
)
from .teacher_students import (
    router as _teacher_students_router,
)

router = APIRouter(prefix="/api/teacher", tags=["Teacher"])


router.routes.extend(_teacher_crisis_router.routes)




router.routes.extend(_teacher_student_questions_router.routes)





router.routes.extend(_teacher_follow_up_router.routes)


router.routes.extend(_teacher_media_router.routes)


router.routes.extend(_teacher_dashboard_router.routes)




router.routes.extend(_teacher_students_router.routes)







# Content Management: Articles
@router.get("/articles/page", response_model=schemas.ArticlePage)
def get_articles_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    q: str = Query("", max_length=100),
    category: str = Query("", max_length=50),
    sort: str = Query("newest", pattern="^(newest|most-read)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    return page_articles(db, page=page, page_size=page_size, q=q.strip(),
                         category=category.strip(), sort=sort)


@router.get("/articles")
def get_articles(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    return db.query(models.Article).order_by(models.Article.created_at.desc()).all()

@router.get("/articles/{article_id}")
def get_article_detail(article_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("/articles")
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    payload = article.model_dump()
    payload["views"] = 0
    new_article = models.Article(**payload)
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return new_article

@router.delete("/articles/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
    return {"message": "Deleted"}

# Content Management: Knowledge Base

@router.get("/knowledge", response_model=List[schemas.KnowledgeBaseResponse])
def get_knowledge_base(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    return db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.created_at.desc()).all()

@router.post("/knowledge", response_model=schemas.KnowledgeBaseResponse)
def create_knowledge(knowledge: schemas.KnowledgeBaseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    new_knowledge = models.KnowledgeBase(**knowledge.model_dump())
    db.add(new_knowledge)
    # Index before committing: the SQL row stays authoritative, so a half-written
    # pair (row without vectors) must never be committed silently. flush() assigns
    # the primary key without ending the transaction, so the row can still be
    # rolled back if the optional index refuses the document.
    db.flush()
    if get_rag_status()["enabled"]:
        if not add_document_to_rag(new_knowledge.id, new_knowledge.title, new_knowledge.content):
            db.rollback()
            raise HTTPException(status_code=503, detail="Knowledge indexing is unavailable")
    db.commit()
    db.refresh(new_knowledge)
    return new_knowledge

@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    knowledge = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    # Remove the vectors first. If that fails, the row is kept so the record stays
    # visible and retryable -- a deleted row with surviving vectors would still be
    # retrievable by students, which is a disclosure rather than a dirty row.
    if get_rag_status()["enabled"]:
        if not delete_document_from_rag(knowledge_id):
            raise HTTPException(status_code=503, detail="Knowledge index removal is unavailable")
    db.delete(knowledge)
    db.commit()
    return {"message": "Deleted"}
router.routes.extend(_teacher_profiles_router.routes)
