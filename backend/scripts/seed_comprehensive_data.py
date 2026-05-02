import os
import sys
import random
import json
from datetime import datetime, timedelta
from passlib.context import CryptContext

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app import models

models.Base.metadata.create_all(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def seed_data():
    db = SessionLocal()
    try:
        print("Clearing old data...")
        db.query(models.InterventionRecord).delete()
        db.query(models.TreeholeAnalysis).delete()
        db.query(models.TreeholeFavorite).delete()
        db.query(models.TreeholeComment).delete()
        db.query(models.TreeholeLike).delete()
        db.query(models.TreeholePost).delete()
        db.query(models.TestResult).delete()
        db.query(models.Appointment).delete()
        db.query(models.TeacherProfile).delete()
        db.query(models.Question).delete()
        db.query(models.Article).delete()
        db.query(models.User).delete()
        db.commit()

        print("Generating Teachers...")
        teachers = []
        teacher_names = ["张敏", "李华", "王芳", "陈静", "刘洋", "赵强", "孙丽", "周伟", "吴燕", "郑超", "冯磊", "陈雪", "楚凡", "魏明", "蒋婷"]
        for i, name in enumerate(teacher_names):
            t = models.User(
                username=f"teacher{i+1}",
                password_hash=get_password_hash("123456"),
                role="teacher",
                name=name
            )
            db.add(t)
            teachers.append(t)
        
        # Add default demo teacher
        demo_t = models.User(
            username="teacher",
            password_hash=get_password_hash("123456"),
            role="teacher",
            name="王教授"
        )
        db.add(demo_t)
        teachers.append(demo_t)
        db.commit()

        for t in teachers:
            prof = models.TeacherProfile(
                user_id=t.id,
                title=random.choice(["教授", "副教授", "心理咨询师", "高级咨询师"]),
                intro=f"{t.name}老师拥有丰富的大学生心理辅导经验，擅长情绪管理和学业压力疏导。",
                location=f"心理咨询中心 {random.randint(101, 505)}室",
                time_slots=json.dumps([
                    "周一 09:00-11:00", "周二 14:00-16:00", "周四 10:00-12:00"
                ])
            )
            db.add(prof)
        db.commit()

        print("Generating 100 Students...")
        students = []
        advisors = ["辅导员A", "辅导员B", "辅导员C", "辅导员D"]
        for i in range(100):
            s = models.User(
                username=f"student{i+1}",
                password_hash=get_password_hash("123456"),
                role="student",
                student_id=f"2023{str(i+1).zfill(4)}",
                name=f"学生{i+1}",
                advisor=random.choice(advisors)
            )
            db.add(s)
            students.append(s)
            
        # Add default demo student
        demo_s = models.User(
            username="student",
            password_hash=get_password_hash("123456"),
            role="student",
            student_id="20250001",
            name="李同学",
            advisor="辅导员A"
        )
        db.add(demo_s)
        students.append(demo_s)
        db.commit()

        print("Generating Test Results (30 per student)...")
        now = datetime.now()
        for s in students:
            # Determine student's base risk tendency
            base_score = random.randint(30, 80)
            
            for i in range(30):
                test_date = now - timedelta(days=30 - i)
                # Fluctuate around base score
                score = max(20, min(100, base_score + random.randint(-15, 15)))
                
                risk_level = "green"
                if score >= 60:
                    risk_level = "red"
                elif score >= 50:
                    risk_level = "yellow"
                    
                tr = models.TestResult(
                    user_id=s.id,
                    test_type="SDS",
                    score=score,
                    standard_score=score,
                    risk_level=risk_level,
                    created_at=test_date
                )
                db.add(tr)
        db.commit()

        print("Generating 80 Appointments...")
        statuses = ["pending", "approved", "completed", "cancelled"]
        for i in range(80):
            app_date = now - timedelta(days=random.randint(0, 14))
            app = models.Appointment(
                student_id=random.choice(students).id,
                teacher_id=random.choice(teachers).id,
                time_slot=app_date.strftime("%Y-%m-%d") + " 14:00-15:00",
                status=random.choice(statuses),
                created_at=app_date - timedelta(days=1)
            )
            db.add(app)
        db.commit()

        print("Generating 200 Treehole Posts...")
        emotions = ["压力", "焦虑", "迷茫", "失眠", "开心", "难过", "孤独", "期待"]
        tags = ["学业", "情感", "生活", "求职", "人际"]
        for i in range(200):
            post_date = now - timedelta(hours=random.randint(1, 720))
            emo = random.choice(emotions)
            post = models.TreeholePost(
                anonymous_id=f"匿名{random.randint(1000,9999)}",
                content=f"最近因为{random.choice(tags)}的事情感到有些{emo}，不知道该怎么办才好...",
                tags=random.choice(tags),
                emotion_keywords=emo,
                user_id=random.choice(students).id,
                created_at=post_date
            )
            db.add(post)
        db.commit()

        print("Generating 50 Articles...")
        for i in range(50):
            art = models.Article(
                title=f"心理健康科普系列：如何应对{random.choice(emotions)}情绪 (第{i+1}期)",
                summary="这是一篇关于大学生心理健康的科普文章，帮助你更好地了解自己。",
                content="<p>在大学生活中，我们经常会遇到各种各样的挑战和压力。面对这些困难，保持积极的心态至关重要。本文将为你提供一些实用的心理学建议和技巧...</p><p>首先，要学会接纳自己的情绪。无论是积极的还是消极的，情绪都是我们内心世界的真实反映...</p>",
                source="校心理健康中心",
                views=random.randint(50, 200),
                created_at=now - timedelta(days=random.randint(1, 60))
            )
            db.add(art)
        db.commit()

        print("Generating 50 Intervention Records...")
        red_students = [s for s in students if db.query(models.TestResult).filter(models.TestResult.user_id == s.id).order_by(models.TestResult.created_at.desc()).first().standard_score >= 60]
        
        for i in range(50):
            target_student = random.choice(red_students) if red_students else random.choice(students)
            rec = models.InterventionRecord(
                student_id=target_student.id,
                teacher_id=random.choice(teachers).id,
                record_date=(now - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d"),
                notes=random.choice([
                    "已与该生进行面谈，情绪目前稳定，建议持续关注。",
                    "辅导员已介入了解情况，因近期考试压力大导致焦虑，已建议放松调节。",
                    "学生主动预约了心理咨询，评估结果为轻度抑郁倾向，已建立定期随访机制。",
                    "联系家长了解情况，近期家庭变故对学生影响较大，需重点关怀。"
                ]),
                created_at=now - timedelta(days=random.randint(0, 30))
            )
            db.add(rec)
        db.commit()

        print("Seed complete!")

    except Exception as e:
        print(f"Error seeding data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
