from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str
    role: Literal["student"] = "student"
    student_id: Optional[str] = None
    name: Optional[str] = None
    advisor: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    student_id: Optional[str] = None
    name: Optional[str] = None
    advisor: Optional[str] = None
    energy_points: int = 0
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class AppointmentCreate(BaseModel):
    teacher_id: int
    time_slot: str

class AppointmentResponse(BaseModel):
    id: int
    student_id: int
    teacher_id: int
    time_slot: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TestSubmit(BaseModel):
    test_type: str = "general"
    score: int
    standard_score: Optional[int] = None
    result_level: Optional[str] = None
    answers: Optional[str] = None
    result_json: Optional[str] = None
    risk_level: Optional[str] = None
    
class TestResponse(BaseModel):
    id: int
    user_id: int
    test_type: str
    score: int
    standard_score: Optional[int]
    result_level: Optional[str]
    answers: Optional[str]
    result_json: Optional[str]
    risk_level: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TeacherProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    title: Optional[str]
    intro: Optional[str]
    location: Optional[str]
    avatar: Optional[str]
    time_slots: Optional[List[str]]

class ArticleResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str]
    content: str
    cover_url: Optional[str]
    category: Optional[str]
    source: Optional[str]
    source_url: Optional[str]
    views: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ArticleViewTrackRequest(BaseModel):
    viewer_id: Optional[str] = None


class ArticleViewTrackResponse(BaseModel):
    article_id: int
    views: int
    counted: bool
    dedup_window_seconds: int

class TreeholeCreate(BaseModel):
    content: str
    tags: Optional[List[str]] = None

class TreeholeCommentResponse(BaseModel):
    id: int
    anonymous_id: str
    content: str
    parent_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TreeholeResponse(BaseModel):
    id: int
    anonymous_id: str
    content: str
    tags: Optional[str] = None
    is_deep: bool = False
    emotion_keywords: Optional[str]
    reply_tip: Optional[str]
    created_at: datetime
    likes_count: int = 0
    comments_count: int = 0
    favorites_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False
    
    class Config:
        from_attributes = True

class TreeholeCommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None

class QuestionCreate(BaseModel):
    question_text: str

    @field_validator("question_text")
    @classmethod
    def normalize_question_text(cls, value: str) -> str:
        normalized = value.strip()
        if not 1 <= len(normalized) <= 2000:
            raise ValueError("Question text must contain 1 to 2000 non-whitespace characters")
        return normalized

class QuestionResponse(BaseModel):
    id: int
    user_id: int
    question_text: str
    answer_text: Optional[str]
    status: str
    created_at: datetime
    response_state: Optional[str] = None
    assigned_teacher_count: Optional[int] = None
    answered_at: Optional[datetime] = None
    answered_by: Optional[str] = None
    
    class Config:
        from_attributes = True

class TeacherStudentList(BaseModel):
    id: int
    student_id: Optional[str]
    name: Optional[str]
    class_name: Optional[str]
    advisor: Optional[str]
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    remarks: Optional[str] = None
    risk_level: Optional[str]
    latest_test_time: Optional[datetime] = None
    latest_test_score: Optional[int] = None
    has_pending_crisis: bool = False
    pending_crisis_count: int = 0
    latest_crisis_warning_at: Optional[datetime] = None

class QuestionAnswer(BaseModel):
    answer_text: str

class InterventionRecordCreate(BaseModel):
    student_id: int
    record_date: str
    notes: str


class TeacherStudentCreate(BaseModel):
    initial_password: str = Field(min_length=8, max_length=72)
    name: str
    student_id: str
    class_name: Optional[str] = None
    gender: Optional[str] = None
    parent_phone: Optional[str] = None
    remarks: Optional[str] = None

class InterventionRecordResponse(BaseModel):
    id: int
    student_id: int
    teacher_id: int
    record_date: str
    notes: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArticleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=500)
    content: str = Field(min_length=1, max_length=100_000)
    cover_url: Optional[str] = Field(default=None, max_length=255)
    category: Optional[str] = Field(default="心理科普", max_length=50)
    source: Optional[str] = Field(default=None, max_length=100)

    @field_validator("title", "summary", "content", "cover_url", "category", "source", mode="before")
    @classmethod
    def trim_article_fields(cls, value):
        # SQLite does not enforce VARCHAR lengths. Validate all creation paths
        # before a transaction, retaining interior whitespace in the article.
        return value.strip() if isinstance(value, str) else value

class TeacherProfileCreateUpdate(BaseModel):
    user_id: int
    title: Optional[str] = None
    intro: Optional[str] = None
    location: Optional[str] = None
    avatar: Optional[str] = None
    time_slots: Optional[List[str]] = None
    consultation_direction: Optional[str] = None

class KnowledgeBaseCreate(BaseModel):
    title: str
    content: str

class KnowledgeBaseResponse(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    
    class Config:
        from_attributes = True
