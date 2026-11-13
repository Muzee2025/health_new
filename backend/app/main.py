import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.security import cors_origins, validate_security_configuration
from app.upload_body_limit import UploadBodyLimitMiddleware
from app.upload_security import IMAGE_TYPES

# Fail before startup callbacks when security settings are invalid.
validate_security_configuration()

# Imported after the security check on purpose: importing app.database opens the
# configured engine and app.models registers every mapped table on Base.metadata,
# so both must stay below validate_security_configuration().
from app import models  # noqa: E402, F401 - register mapped tables in Base.metadata
from app.database import engine  # noqa: E402, F401 - open the engine after the security check
from app.routers import (  # noqa: E402
    advanced_chat,
    advanced_teacher,
    assistant_v1,
    auth,
    health,
    llm_gateway,
    report_v1,
    student,
    student_dashboard,
    teacher,
    websocket,
)
from app.services.multi_model_orchestrator import orchestrator  # noqa: E402

# 创建数据库表
# Schema creation/migration is an explicit operator action, never an import side effect.

app = FastAPI(
    title="心域智链 - 心理健康系统 API",
    description="高校大学生心理健康测评、大模型AI辅导与树洞社区",
    version="1.0.0",
)

# 配置 CORS
origins = cors_origins()

app.add_middleware(UploadBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# 挂载静态文件目录
upload_dir = "uploads"
if not os.path.exists(upload_dir):
    os.makedirs(upload_dir)
class PublicImageFiles(StaticFiles):
    async def get_response(self, path, scope):
        if Path(path).suffix.lower() not in IMAGE_TYPES:
            raise HTTPException(status_code=404, detail="Image not found")
        response = await super().get_response(path, scope)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
        return response


# Only intentionally public raster assets are static. Arbitrary historical
# uploads, chat material and article documents cannot be reached via /static.
for public_subdir in ("public_images", "teacher_avatars"):
    public_path = Path(upload_dir) / public_subdir
    if public_path.is_symlink():
        raise RuntimeError("Public image directory must not be a symbolic link")
    public_path.mkdir(parents=True, exist_ok=True)
    app.mount(f"/static/{public_subdir}", PublicImageFiles(directory=public_path), name=f"static-{public_subdir}")

# 注册路由模块
app.include_router(auth.router)
app.include_router(student_dashboard.router, prefix="/api/student", tags=["Student"])
app.include_router(student.router)
app.include_router(teacher.router)
app.include_router(advanced_chat.router, prefix="/api/advanced-ai", tags=["advanced-ai"])
app.include_router(advanced_teacher.router, prefix="/api/advanced-teacher", tags=["advanced-teacher"])
app.include_router(report_v1.router)
app.include_router(assistant_v1.router)
app.include_router(llm_gateway.router)
app.include_router(websocket.router, prefix="/api", tags=["websocket"])
app.include_router(health.router)


@app.on_event("startup")
def init_article_views_on_startup():
    """Compatibility hook: never manufacture or rewrite stored view counts."""
    return None

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
