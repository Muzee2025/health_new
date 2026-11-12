import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, engine


def init_db():
    print("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    print("Creating new tables...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete.")

if __name__ == "__main__":
    init_db()
