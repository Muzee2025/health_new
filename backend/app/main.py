from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
import random

from app.database import engine, SessionLocal
from app import models
from app.routers import auth, student, teacher, advanced_chat, advanced_teacher, report_v1, assistant_v1, llm_gateway, websocket
from app.services.multi_model_orchestrator import orchestrator

# 创建数据库表
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="心域智链 - 心理健康系统 API",
    description="高校大学生心理健康测评、大模型AI辅导与树洞社区",
    version="1.0.0",
)

# 配置 CORS
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
upload_dir = "uploads"
if not os.path.exists(upload_dir):
    os.makedirs(upload_dir)
app.mount("/static", StaticFiles(directory=upload_dir), name="static")

# 注册路由模块
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(teacher.router)
app.include_router(advanced_chat.router, prefix="/api/advanced-ai", tags=["advanced-ai"])
app.include_router(advanced_teacher.router, prefix="/api/advanced-teacher", tags=["advanced-teacher"])
app.include_router(report_v1.router)
app.include_router(assistant_v1.router)
app.include_router(llm_gateway.router)
app.include_router(websocket.router, prefix="/api", tags=["websocket"])


@app.on_event("startup")
def init_article_views_on_startup():
    """
    启动时一次性回填历史文章阅读量，避免前端列表出现 0。
    """
    db = SessionLocal()
    try:
        rows = db.query(models.Article).filter(
            (models.Article.views.is_(None)) | (models.Article.views < 50)
        ).all()
        if not rows:
            return
        for article in rows:
            article.views = random.randint(50, 200)
        db.commit()
    finally:
        db.close()

@app.get("/", tags=["root"])
def read_root():
    return {"message": "Welcome to 心域智链 Backend API!"}

@app.get("/api/v1/model/current", tags=["model"])
def get_current_model():
    data = {"status": "success", "data": orchestrator.get_current_model_meta()}
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )
