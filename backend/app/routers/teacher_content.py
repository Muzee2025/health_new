import sys
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.services.article_catalog import page_articles
from app.services.rag_service import (
    add_document_to_rag as _add_document_to_rag_impl,
)
from app.services.rag_service import (
    delete_document_from_rag as _delete_document_from_rag_impl,
)
from app.services.rag_service import (
    get_rag_status as _get_rag_status_impl,
)

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
from .teacher_shared import check_teacher_role

router = APIRouter(prefix="/api/teacher", tags=["Teacher"])


def _legacy_teacher_rag_dependency(name: str, fallback):
    """Respect the old teacher module's monkeypatchable service entry points."""
    legacy_module = sys.modules.get(f"{__package__}.teacher")
    if legacy_module is None:
        return fallback
    return getattr(legacy_module, name, fallback)


def add_document_to_rag(*args, **kwargs):
    dependency = _legacy_teacher_rag_dependency("add_document_to_rag", _add_document_to_rag_impl)
    return dependency(*args, **kwargs)


def delete_document_from_rag(*args, **kwargs):
    dependency = _legacy_teacher_rag_dependency("delete_document_from_rag", _delete_document_from_rag_impl)
    return dependency(*args, **kwargs)


def get_rag_status():
    dependency = _legacy_teacher_rag_dependency("get_rag_status", _get_rag_status_impl)
    return dependency()


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
