import json
import random
import string
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
from .student_shared import _invalidate_user_report_cache, check_student_role

router = APIRouter(prefix="/api/student")
search_router = APIRouter(prefix="/api/student")

EMOTION_KEYWORDS = ["焦虑", "失眠", "压力", "崩溃", "难过", "抑郁", "想哭"]

def generate_anonymous_id():
    return "深海旅人_" + ''.join(random.choices(string.digits, k=4))

def _rule_based_treehole_summary(content: str, tags: list):
    emotion = "平静"
    if any(kw in content for kw in ["焦虑", "压力", "紧张"]):
        emotion = "焦虑"
    elif any(kw in content for kw in ["难过", "崩溃", "哭"]):
        emotion = "低落"
    elif any(kw in content for kw in ["开心", "希望", "美好"]):
        emotion = "积极"
    elif any(kw in content for kw in ["迷茫", "不知道", "未来"]):
        emotion = "迷茫"

    keywords = []
    if "人生意义" in tags or "意义" in content:
        keywords.append("人生意义")
    if "自我成长" in tags or "成长" in content or "学习" in content:
        keywords.append("成长")
    if "红色精神与我" in tags or "责任" in content:
        keywords.append("责任与担当")
    if "人际关系" in tags or "朋友" in content or "室友" in content:
        keywords.append("人际关系")
    if "未来规划" in tags or "未来" in content:
        keywords.append("未来探索")

    if not keywords:
        keywords = ["日常随想", "自我探索"]

    return emotion, ",".join(keywords)

@router.post("/treehole/post", response_model=schemas.TreeholeResponse)
def create_treehole_post(post_data: schemas.TreeholeCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)

    content = post_data.content
    matched_keywords = [kw for kw in EMOTION_KEYWORDS if kw in content]

    reply_tip = None
    if matched_keywords:
        reply_tip = "看到你提到了一些不容易的感受。关键词提示仅供参考，不代表风险判断；如果你需要支持，可以通过学校公布的官方渠道联系心理服务人员。"

    tags_str = ",".join(post_data.tags) if post_data.tags else ""
    is_deep = len(content) > 100 or ("#人生意义" in tags_str) or ("#自我成长" in tags_str) or ("#红色精神与我" in tags_str)

    prior_energy = current_user.energy_points
    if is_deep:
        current_user.energy_points += 5

    post = models.TreeholePost(
        anonymous_id=generate_anonymous_id(),
        content=content,
        tags=tags_str,
        is_deep=is_deep,
        emotion_keywords=",".join(matched_keywords) if matched_keywords else None,
        reply_tip=reply_tip,
        user_id=current_user.id if current_user.real_identity_flag else None
    )
    db.add(post)
    try:
        db.flush()
        emotion, core_values = _rule_based_treehole_summary(content, post_data.tags or [])
        analysis = models.TreeholeAnalysis(post_id=post.id, user_id=current_user.id,
            emotion_category=emotion, core_values=core_values)
        db.add(analysis)
        db.commit()
        db.refresh(post)
    except Exception:
        db.rollback()
        current_user.energy_points = prior_energy
        raise
    _invalidate_user_report_cache(db, current_user.id)

    return schemas.TreeholeResponse(
        id=post.id,
        anonymous_id=post.anonymous_id,
        content=post.content,
        tags=post.tags,
        is_deep=post.is_deep,
        emotion_keywords=post.emotion_keywords,
        reply_tip=post.reply_tip,
        created_at=post.created_at,
        likes_count=0,
        comments_count=0,
        favorites_count=0,
        is_liked=False,
        is_favorited=False
    )

def _treehole_id_scope(post_ids):
    """Bind an already-read id set as one JSON parameter instead of N ``IN`` values.

    Two properties are needed at once and each fix alone breaks the other:

    * The id set must be *fixed* before the aggregates run. Referencing the filter
      query as a live subquery re-evaluated it per statement, so a concurrent
      unfavourite changed which ids the later aggregates saw: the post stayed in the
      response (it was already loaded) while its counts silently became 0. Passing the
      ids that were actually loaded keeps every aggregate looking at the same posts.
      (The values themselves are still read per statement, not under one snapshot.)
    * The id set must not cost one bound variable per row. ``get_treehole_posts`` has
      no pagination, so it reads the whole table; a materialised ``IN (...)`` list
      raised "too many SQL variables" at 32766 posts. ``json_each`` binds the whole
      list as a single TEXT parameter regardless of length.

    ``json_each`` is part of SQLite's built-in JSON support (compiled in by default;
    verified present on the 3.53.1 build this project uses).
    """
    payload = json.dumps([int(post_id) for post_id in post_ids])
    return select(func.json_each(payload).column_valued("value"))

def _get_treehole_responses(posts, user_id, db):
    """Build the list responses with five batched lookups instead of five per post.

    The per-post helper issued three COUNTs plus two existence checks, so a page of N
    posts cost 5N+1 statements. Each of the five values is now one GROUP BY (or one
    IN over the same post set), so both the statement count and the bound-parameter
    count are flat.

    The post set is the ids of the posts actually loaded by the caller, bound through
    ``_treehole_id_scope``: the *same* post ids are used by every aggregate, and they
    cost exactly one bound parameter at any size.

    Scope of that guarantee: it fixes which posts the aggregates cover, so a post that
    was loaded cannot lose its counts when a concurrent request changes the filter. It
    does not open a read transaction, so the aggregate VALUES themselves are still read
    per statement; a like or comment added between two statements is simply not counted
    by the earlier one. Consistent per-post values under concurrent writes would need a
    transaction or a single joined query, which this change deliberately does not add.

    The per-post values are unchanged: a post with no likes/comments/favourites still
    gets 0, and is_liked/is_favorited stay False when no user is given.
    """
    if not posts:
        return []
    id_scope = _treehole_id_scope(post.id for post in posts)
    likes = dict(db.query(models.TreeholeLike.post_id, func.count(models.TreeholeLike.id))
                 .filter(models.TreeholeLike.post_id.in_(id_scope))
                 .group_by(models.TreeholeLike.post_id).all())
    comments = dict(db.query(models.TreeholeComment.post_id, func.count(models.TreeholeComment.id))
                    .filter(models.TreeholeComment.post_id.in_(id_scope))
                    .group_by(models.TreeholeComment.post_id).all())
    favorites = dict(db.query(models.TreeholeFavorite.post_id, func.count(models.TreeholeFavorite.id))
                     .filter(models.TreeholeFavorite.post_id.in_(id_scope))
                     .group_by(models.TreeholeFavorite.post_id).all())
    liked_ids, favorited_ids = set(), set()
    if user_id:
        liked_ids = {row[0] for row in db.query(models.TreeholeLike.post_id).filter(
            models.TreeholeLike.post_id.in_(id_scope),
            models.TreeholeLike.user_id == user_id).all()}
        favorited_ids = {row[0] for row in db.query(models.TreeholeFavorite.post_id).filter(
            models.TreeholeFavorite.post_id.in_(id_scope),
            models.TreeholeFavorite.user_id == user_id).all()}

    return [
        schemas.TreeholeResponse(
            id=post.id,
            anonymous_id=post.anonymous_id,
            content=post.content,
            tags=post.tags,
            is_deep=post.is_deep,
            emotion_keywords=post.emotion_keywords,
            reply_tip=post.reply_tip,
            created_at=post.created_at,
            likes_count=likes.get(post.id, 0),
            comments_count=comments.get(post.id, 0),
            favorites_count=favorites.get(post.id, 0),
            is_liked=post.id in liked_ids,
            is_favorited=post.id in favorited_ids,
        )
        for post in posts
    ]

@router.get("/treehole/posts", response_model=List[schemas.TreeholeResponse])
def get_treehole_posts(tab: str = "home", tag: str = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.TreeholePost)

    if tab == "my":
        query = query.filter(models.TreeholePost.user_id == current_user.id)
    elif tab == "favorites":
        fav_post_ids = db.query(models.TreeholeFavorite.post_id).filter(models.TreeholeFavorite.user_id == current_user.id)
        query = query.filter(models.TreeholePost.id.in_(fav_post_ids))
    elif tab == "hot":
        query = query.order_by(models.TreeholePost.is_deep.desc())

    if tag:
        query = query.filter(models.TreeholePost.tags.like(f"%{tag}%"))

    if tab != "hot":
        query = query.order_by(models.TreeholePost.created_at.desc())

    # Load the posts first, then hand their ids to the response builder. The ids are
    # the ones actually returned, so the aggregates below cannot disagree with the list
    # even if a concurrent request changes the filter (e.g. unfavourites a post).
    posts = query.all()
    return _get_treehole_responses(posts, current_user.id, db)

@router.post("/treehole/{post_id}/like")
def toggle_like(post_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.TreeholeLike).filter(models.TreeholeLike.post_id == post_id, models.TreeholeLike.user_id == current_user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unliked"}
    else:
        like = models.TreeholeLike(post_id=post_id, user_id=current_user.id)
        db.add(like)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent tap already inserted this like. The desired end state is
            # "liked", so report it instead of surfacing a constraint error.
            db.rollback()
            return {"status": "liked"}
        return {"status": "liked"}

@router.post("/treehole/{post_id}/favorite")
def toggle_favorite(post_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.TreeholeFavorite).filter(models.TreeholeFavorite.post_id == post_id, models.TreeholeFavorite.user_id == current_user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unfavorited"}
    else:
        fav = models.TreeholeFavorite(post_id=post_id, user_id=current_user.id)
        db.add(fav)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {"status": "favorited"}
        return {"status": "favorited"}

@router.post("/treehole/{post_id}/comment", response_model=schemas.TreeholeCommentResponse)
def add_comment(post_id: int, comment_data: schemas.TreeholeCommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    comment = models.TreeholeComment(
        post_id=post_id,
        user_id=current_user.id,
        anonymous_id=generate_anonymous_id(),
        content=comment_data.content,
        parent_id=comment_data.parent_id
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.get("/treehole/{post_id}/comments", response_model=List[schemas.TreeholeCommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    return db.query(models.TreeholeComment).filter(models.TreeholeComment.post_id == post_id).order_by(models.TreeholeComment.created_at.asc()).all()

@search_router.get("/treehole/search_by_word")
def get_treehole_by_word(
    word: str = Query(..., min_length=1, max_length=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    posts = db.query(models.TreeholePost).filter(
        models.TreeholePost.user_id == current_user.id,
        models.TreeholePost.content.like(f"%{word}%")
    ).order_by(models.TreeholePost.created_at.desc()).limit(20).all()
    return [
        {
            "id": post.id,
            "content": post.content,
            "created_at": post.created_at,
        } for post in posts
    ]
