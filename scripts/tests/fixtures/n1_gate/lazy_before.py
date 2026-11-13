# Snapshot from ec7b920, before the backend added joinedload. Both functions
# read a relationship per row (w.student, w.processor, question.user) while the
# query gate was already green. In-repo so the regression test needs no git
# history: a shallow CI checkout has only one commit.


# --- backend/app/routers/advanced_teacher.py (get_crisis_warnings) ---


async def get_crisis_warnings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_teacher_role(current_user)
    warnings = db.query(CrisisWarning).filter(CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).order_by(CrisisWarning.created_at.desc()).all()
    res = []
    for w in warnings:
        msg_content = ""
        if w.chat_message_id:
            msg = db.query(AIChatMessage).join(AIChatSession).filter(AIChatMessage.id == w.chat_message_id, AIChatSession.user_id == w.student_id).first()
            if msg:
                msg_content = msg.content
        res.append({
            "id": w.id,
            "student_id": w.student_id,
            "student_name": w.student.name or w.student.username if w.student else "未知",
            "class_name": w.student.class_name if w.student else "未知",
            "trigger_keyword": w.trigger_keyword,
            "risk_level": w.risk_level,
            "status": w.status,
            "trigger_msg": msg_content,
            "created_at": w.created_at.strftime("%Y-%m-%d %H:%M:%S") if w.created_at else None,
            "processed_at": w.processed_at.strftime("%Y-%m-%d %H:%M:%S") if w.processed_at else None,
            "processed_by": w.processor.name or w.processor.username if w.processor else None
        })
    return {"status": "success", "data": res}


# --- backend/app/routers/teacher.py (list_assigned_questions) ---


def list_assigned_questions(status: str | None = None, db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    if status not in (None, "pending", "answered"):
        raise HTTPException(status_code=422, detail="status must be pending or answered")
    query = (db.query(models.Question).join(models.User, models.User.id == models.Question.user_id)
        .filter(models.Question.user_id.in_(assigned_student_ids(db, current_user.id))))
    if status:
        query = query.filter(models.Question.status == status)
    questions = query.order_by(models.Question.created_at.desc()).all()
    output = []
    for question in questions:
        event = (db.query(models.SupportWorkflowEvent)
            .filter_by(subject_type="question", subject_id=question.id, action="answer")
            .order_by(models.SupportWorkflowEvent.id.desc()).first())
        output.append({"id": question.id, "student_id": question.user_id,
            "student_name": question.user.name or question.user.username,
            "question_text": question.question_text, "status": question.status,
            "created_at": question.created_at, "answer_text": question.answer_text,
            "answered_at": event.created_at if event else None,
            "answered_by": _support_actor_name(db, event.actor_id) if event else None})
    return {"status": "success", "data": output}
