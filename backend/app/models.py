from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student", index=True)
    student_id = Column(String(50), nullable=True, index=True) # 学号
    name = Column(String(50), nullable=True) # 姓名
    advisor = Column(String(50), nullable=True) # 辅导员
    class_name = Column(String(50), nullable=True) # 班级，如：计算机1班
    real_identity_flag = Column(Boolean, default=True) # 用于关联树洞
    energy_points = Column(Integer, default=0) # 红色能量积分

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TeacherStudentAssignment(Base):
    """Explicit operator-managed access, independent of display-name advisors."""
    __tablename__ = "teacher_student_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "student_id", name="uq_teacher_student_assignment"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    gender = Column(String(20), nullable=True)
    parent_phone = Column(String(50), nullable=True)
    remarks = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")

class CrisisWarning(Base):
    __tablename__ = "crisis_warnings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_message_id = Column(Integer, ForeignKey("ai_chat_messages.id", ondelete="CASCADE"), nullable=True)
    trigger_keyword = Column(String(100), nullable=False)
    risk_level = Column(String(20), nullable=False, default="high") # low, medium, high
    status = Column(String(20), nullable=False, default="pending") # pending, processed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    student = relationship("User", foreign_keys=[student_id])
    processor = relationship("User", foreign_keys=[processed_by])


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    title = Column(String(50), nullable=True) # 职称
    intro = Column(Text, nullable=True) # 简介
    location = Column(String(100), nullable=True) # 工作地点
    avatar = Column(String(255), nullable=True) # 头像
    time_slots = Column(Text, nullable=True) # 可预约时间段 (JSON)
    consultation_direction = Column(String(255), nullable=True) # 咨询方向
    
    user = relationship("User")


class TeacherAvatar(Base):
    __tablename__ = "teacher_avatars"
    __table_args__ = (
        UniqueConstraint("teacher_id", name="uq_teacher_avatar_teacher_id"),
        UniqueConstraint("image_hash", name="uq_teacher_avatar_image_hash"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    relative_path = Column(String(512), nullable=False)
    image_hash = Column(String(64), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    teacher = relationship("User", foreign_keys=[teacher_id])


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    time_slot = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending") # pending, approved, cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    test_type = Column(String(50), nullable=False, default="general") # 测试类型 (e.g. SDS, SAS)
    score = Column(Integer, nullable=False) # 粗分/总分
    standard_score = Column(Integer, nullable=True) # 标准分
    result_level = Column(String(50), nullable=True) # 结果等级
    answers = Column(Text, nullable=True) # 答案JSON
    result_json = Column(Text, nullable=True) # 详细结果JSON (可选保留兼容)
    risk_level = Column(String(20), nullable=True) # green, yellow, red (可选保留兼容)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user = relationship("User")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    summary = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    cover_url = Column(String(255), nullable=True)
    source = Column(String(100), nullable=True) # 来源
    source_url = Column(String(255), nullable=True) # 来源链接
    category = Column(String(50), nullable=True, default="心理科普") # 分类标签
    views = Column(Integer, default=0) # 阅读量
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TreeholePost(Base):
    __tablename__ = "treehole_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    anonymous_id = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(String(255), nullable=True) # 逗号分隔的标签
    is_deep = Column(Boolean, default=False) # 是否为深度好文
    emotion_keywords = Column(String(255), nullable=True)
    reply_tip = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True) # 仅供教师端追溯
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user = relationship("User")
    likes = relationship("TreeholeLike", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("TreeholeComment", back_populates="post", cascade="all, delete-orphan")
    favorites = relationship("TreeholeFavorite", back_populates="post", cascade="all, delete-orphan")

class TreeholeLike(Base):
    __tablename__ = "treehole_likes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("treehole_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    post = relationship("TreeholePost", back_populates="likes")

class TreeholeComment(Base):
    __tablename__ = "treehole_comments"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("treehole_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    anonymous_id = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("treehole_comments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    post = relationship("TreeholePost", back_populates="comments")
    parent = relationship("TreeholeComment", remote_side=[id], backref="replies")

class TreeholeFavorite(Base):
    __tablename__ = "treehole_favorites"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("treehole_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    post = relationship("TreeholePost", back_populates="favorites")

class TreeholeAnalysis(Base):
    __tablename__ = "treehole_analysis"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("treehole_posts.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    emotion_category = Column(String(50), nullable=True)
    core_values = Column(String(255), nullable=True) # 逗号分隔的价值观关键词
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    post = relationship("TreeholePost")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending") # pending, answered
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user = relationship("User")

class InterventionRecord(Base):
    __tablename__ = "intervention_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    record_date = Column(String(50), nullable=False) # e.g. 2025-04-05
    notes = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReportAnalysisCache(Base):
    __tablename__ = "report_analysis_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "report_type", name="uq_report_cache_user_type"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type = Column(String(64), nullable=False, index=True, default="student_mental_report")
    payload_json = Column(Text, nullable=False)
    data_fingerprint = Column(String(128), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PsychologicalReport(Base):
    __tablename__ = "psychological_reports"
    __table_args__ = (
        UniqueConstraint("user_id", "report_date", name="uq_psych_report_user_date"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_date = Column(String(20), nullable=False, index=True)
    risk_level = Column(String(20), nullable=True)
    analysis_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")

class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"
    id = Column(String(36), primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mode = Column(String(20), nullable=False, default="daily") # "daily" 或 "counseling"
    title = Column(String(100), nullable=True, default="新对话")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")

class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(10), nullable=False) # "user", "ai", "system"
    content = Column(Text, nullable=False)
    emotion_tags = Column(Text, nullable=True) # JSON
    is_crisis = Column(Boolean, default=False)
    heatmap = Column(Text, nullable=True) # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("AIChatSession", backref="messages")


class ChatHistoryArchive(Base):
    """
    结构化历史对话归档表（面向深度思考与检索）。
    """
    __tablename__ = "chat_history_archive"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_message_id = Column(Integer, ForeignKey("ai_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    ai_message_id = Column(Integer, ForeignKey("ai_chat_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    user_input = Column(Text, nullable=False)
    ai_reply = Column(Text, nullable=False)
    context_json = Column(Text, nullable=True)  # JSON: 历史上下文快照
    topic_tags = Column(String(255), nullable=True, index=True)  # 逗号分隔，支持快速 like 检索
    sentiment_score = Column(Integer, nullable=True)  # 0-100，便于趋势分析
    semantic_summary = Column(String(500), nullable=True)  # 一句话语义摘要，便于预览
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User")
