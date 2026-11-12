"""Fail-closed teacher/student access using explicit database assignments only."""
from fastapi import HTTPException
from sqlalchemy.orm import Session, aliased

from app import models


def assigned_student_ids(db: Session, teacher_id: int):
    teacher = aliased(models.User)
    return (db.query(models.TeacherStudentAssignment.student_id)
            .join(models.User, models.User.id == models.TeacherStudentAssignment.student_id)
            .join(teacher, teacher.id == models.TeacherStudentAssignment.teacher_id)
            .filter(models.TeacherStudentAssignment.teacher_id == teacher_id, models.User.role == "student", teacher.role == "teacher"))


def require_assigned_student(db: Session, teacher_id: int, student_id: int) -> models.User:
    student = (db.query(models.User)
               .filter(models.User.id == student_id, models.User.role == "student",
                       models.User.id.in_(assigned_student_ids(db, teacher_id))).first())
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def assigned_teacher_ids(db: Session, student_id: int) -> set[int]:
    if not db.query(models.User.id).filter(models.User.id == student_id, models.User.role == "student").first():
        return set()
    rows = (db.query(models.TeacherStudentAssignment.teacher_id)
            .join(models.User, models.User.id == models.TeacherStudentAssignment.teacher_id)
            .filter(models.TeacherStudentAssignment.student_id == student_id, models.User.role == "teacher").all())
    return {row[0] for row in rows}
