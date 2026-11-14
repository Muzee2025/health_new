
from fastapi import APIRouter

from app.services.rag_service import (
    add_document_to_rag as add_document_to_rag,
)
from app.services.rag_service import (
    delete_document_from_rag as delete_document_from_rag,
)
from app.services.rag_service import (
    get_rag_status as get_rag_status,
)

from .teacher_content import (
    create_article as create_article,
)
from .teacher_content import (
    create_knowledge as create_knowledge,
)
from .teacher_content import (
    delete_article as delete_article,
)
from .teacher_content import (
    delete_knowledge as delete_knowledge,
)
from .teacher_content import (
    get_article_detail as get_article_detail,
)
from .teacher_content import (
    get_articles as get_articles,
)
from .teacher_content import (
    get_articles_page as get_articles_page,
)
from .teacher_content import (
    get_knowledge_base as get_knowledge_base,
)
from .teacher_content import (
    router as _teacher_content_router,
)
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







router.routes.extend(_teacher_content_router.routes)


router.routes.extend(_teacher_profiles_router.routes)
