# The same two functions from 87a7ef7, after joinedload was applied. The gate
# must report nothing here.


# --- backend/app/routers/advanced_teacher.py (get_crisis_warnings) ---


async def get_crisis_warnings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_teacher_role(current_user)
    warnings = db.query(CrisisWarning).filter(CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).options(joinedload(CrisisWarning.student), joinedload(CrisisWarning.processor)).order_by(CrisisWarning.created_at.desc()).all()
    # One batched lookup for every triggering message instead of one per warning.
    # The join keeps the original guard: a message only counts when it belongs to the
    # student the warning names.
    message_ids = {w.chat_message_id for w in warnings if w.chat_message_id}
    trigger_messages = {}
    if message_ids:
        for message_id, content, owner in (
            db.query(AIChatMessage.id, AIChatMessage.content, AIChatSession.user_id)
            .join(AIChatSession, AIChatSession.id == AIChatMessage.session_id)
            .filter(AIChatMessage.id.in_(message_ids))
            .all()
        ):
            trigger_messages[message_id] = (content, owner)

    res = []
    for w in warnings:
        msg_content = ""
        if w.chat_message_id:
            row = trigger_messages.get(w.chat_message_id)
            if row is not None and row[1] == w.student_id:
                msg_content = row[0]
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
        .filter(models.Question.user_id.in_(assigned_student_ids(db, current_user.id)))
        .options(joinedload(models.Question.user)))
    if status:
        query = query.filter(models.Question.status == status)
    questions = query.order_by(models.Question.created_at.desc()).all()
    if not questions:
        return {"status": "success", "data": []}
    # The newest answer event per question in one query, then one lookup for every
    # actor named by those events: two statements instead of two per question.
    ranked_events = (
        db.query(
            models.SupportWorkflowEvent.id.label("event_id"),
            models.SupportWorkflowEvent.subject_id.label("subject_id"),
            func.row_number().over(
                partition_by=models.SupportWorkflowEvent.subject_id,
                order_by=models.SupportWorkflowEvent.id.desc(),
            ).label("position"),
        )
        .filter(
            models.SupportWorkflowEvent.subject_type == "question",
            models.SupportWorkflowEvent.subject_id.in_([question.id for question in questions]),
            models.SupportWorkflowEvent.action == "answer",
        )
        .subquery()
    )
    events_by_question = {
        event.subject_id: event
        for event in (
            db.query(models.SupportWorkflowEvent)
            .join(ranked_events, ranked_events.c.event_id == models.SupportWorkflowEvent.id)
            .filter(ranked_events.c.position == 1)
            .all()
        )
    }
    actor_ids = {event.actor_id for event in events_by_question.values() if event.actor_id}
    actors = {
        actor.id: actor
        for actor in db.query(models.User).filter(models.User.id.in_(actor_ids)).all()
    } if actor_ids else {}

    output = []
    for question in questions:
        event = events_by_question.get(question.id)
        actor = actors.get(event.actor_id) if event and event.actor_id else None
        output.append({"id": question.id, "student_id": question.user_id,
            "student_name": question.user.name or question.user.username,
            "question_text": question.question_text, "status": question.status,
            "created_at": question.created_at, "answer_text": question.answer_text,
            "answered_at": event.created_at if event else None,
            "answered_by": (actor.name or actor.username) if actor else None})
    return {"status": "success", "data": output}
