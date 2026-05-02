import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 从 .env 文件中获取数据库连接 URL
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# 创建 SQLAlchemy 引擎
# pool_pre_ping=True 可以防止连接池中的连接失效导致错误
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}
)

# 创建本地 Session 类
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类，用于后续所有的模型继承
Base = declarative_base()

# 依赖项，用于获取数据库 session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
