"""Shared, summary-only article catalog queries for paged endpoints."""
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models import Article


CATEGORY_TRIM_CHARS = " \t\r\n\v\f"
NORMALIZED_CATEGORY = func.trim(Article.category, CATEGORY_TRIM_CHARS)


NORMALIZED_VIEWS = case(
    (func.coalesce(Article.views, 0) < 0, 0),
    else_=func.coalesce(Article.views, 0),
).label("views")

SUMMARY_COLUMNS = (
    Article.id,
    Article.title,
    Article.summary,
    Article.cover_url,
    Article.category,
    Article.source,
    NORMALIZED_VIEWS,
    Article.created_at,
    Article.source_url,
)


def page_articles(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 12,
    q: str = "",
    category: str = "",
    sort: str = "newest",
) -> dict:
    """Return one bounded page; never select the article body column."""
    query = db.query(*SUMMARY_COLUMNS)
    if q:
        # Escape SQL LIKE metacharacters so q is always literal user text.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.filter(or_(
            Article.title.like(pattern, escape="\\"),
            Article.summary.like(pattern, escape="\\"),
            Article.source.like(pattern, escape="\\"),
        ))
    if category:
        query = query.filter(NORMALIZED_CATEGORY == category)

    total = query.order_by(None).count()
    effective_page = max(1, min(page, ((total - 1) // page_size + 1) if total else 1))
    if sort == "most-read":
        query = query.order_by(NORMALIZED_VIEWS.desc(),
                               Article.created_at.desc(), Article.id.desc())
    else:
        query = query.order_by(Article.created_at.desc(), Article.id.desc())
    rows = query.offset((effective_page - 1) * page_size).limit(page_size).all()
    categories = [row[0] for row in db.query(NORMALIZED_CATEGORY)
                  .filter(Article.category.isnot(None), NORMALIZED_CATEGORY != "")
                  .distinct().order_by(NORMALIZED_CATEGORY.asc()).all()]
    return {
        "items": [dict(zip((column.key for column in SUMMARY_COLUMNS), row)) for row in rows],
        "total": total,
        "page": effective_page,
        "page_size": page_size,
        "categories": categories,
    }
