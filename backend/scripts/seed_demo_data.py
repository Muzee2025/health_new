import os
import sys
import bcrypt
import json
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app.models import User, TeacherProfile, Appointment, TestResult, Article, TreeholePost, Question, InterventionRecord, Base

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        if db.query(User).first():
            print("Data already exists. Dropping and recreating tables for clean seed...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("Tables did not exist, created them.")
        db.rollback()

    print("Inserting demo users...")
    teacher1 = User(
        username="teacher", password_hash=hash_password("123456"),
        role="teacher", name="王芳"
    )
    teacher2 = User(
        username="teacher2", password_hash=hash_password("123456"),
        role="teacher", name="刘洋"
    )
    teacher3 = User(
        username="teacher3", password_hash=hash_password("123456"),
        role="teacher", name="周敏"
    )
    
    student1 = User(
        username="student", password_hash=hash_password("123456"),
        role="student", student_id="20240001", name="李明", advisor="陈静", class_name="计算机1班"
    )
    student2 = User(
        username="student2", password_hash=hash_password("123456"),
        role="student", student_id="20240002", name="张伟", advisor="陈静", class_name="软件2班"
    )
    student3 = User(
        username="student3", password_hash=hash_password("123456"),
        role="student", student_id="20240003", name="赵蕾", advisor="吴强", class_name="人工智能1班"
    )
    
    db.add_all([teacher1, teacher2, teacher3, student1, student2, student3])
    db.commit()
    
    print("Inserting teacher profiles...")
    tp1 = TeacherProfile(
        user_id=teacher1.id,
        title="资深心理咨询师",
        intro="拥有10年高校心理辅导经验，擅长情绪管理和人际关系疏导。",
        location="心理健康中心 301室",
        avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Wang",
        time_slots=json.dumps(["周一 14:00-15:00", "周三 10:00-11:00", "周五 15:00-16:00"])
    )
    tp2 = TeacherProfile(
        user_id=teacher2.id,
        title="心理健康教师",
        intro="专攻大学生职业规划与学业压力管理。",
        location="心理健康中心 302室",
        avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Liu",
        time_slots=json.dumps(["周二 09:00-10:00", "周四 14:00-15:00"])
    )
    tp3 = TeacherProfile(
        user_id=teacher3.id,
        title="特聘心理专家",
        intro="国家二级心理咨询师，专注于抑郁、焦虑等常见心理问题干预。",
        location="心理健康中心 303室",
        avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=Zhou",
        time_slots=json.dumps(["周一 09:00-10:00", "周三 14:00-15:00", "周五 09:00-10:00"])
    )
    db.add_all([tp1, tp2, tp3])
    db.commit()
    
    print("Inserting articles...")
    categories = ["情绪管理", "红色心理韧性", "人际关系", "自我认知", "学业压力"]
    articles = []
    
    for i in range(1, 25):
        category = categories[i % len(categories)]
        title = f"【{category}】第{i}期：心理健康科普文章"
        summary = f"这是关于{category}的精选科普文章。了解自己，关爱他人，构建健康的心理状态。在现代快节奏生活中，我们每天都会面临各种挑战..."
        content = f"""
        <p>欢迎阅读《{title}》。</p>
        <p>在大学生活中，{category}是我们经常需要面对的课题。研究表明，良好的心理素质不仅能提高学习效率，还能改善生活质量。</p>
        <p><strong>第一，接纳自己。</strong> 很多时候压力的来源是我们对自己的要求过高。试着拥抱自己的不完美。</p>
        <p><strong>第二，合理规划。</strong> 制定可行的目标，把大任务分解成小步骤。</p>
        <p><strong>第三，寻求支持。</strong> 当你觉得撑不住的时候，记得向朋友、家人或专业的心理老师求助。</p>
        <p>希望这篇文章能给你带来一些启发和力量！</p>
        """
        cover_url = f"https://picsum.photos/300/200?random={i}"
        
        articles.append(
            Article(
                title=title,
                summary=summary,
                content=content,
                cover_url=cover_url,
                category=category,
                views=random.randint(50, 200)
            )
        )
        
    db.add_all(articles)
    db.commit()
    
    print("Inserting test records...")
    # Each person 3 records with fluctuating scores
    tests = []
    tests.append(TestResult(user_id=student1.id, test_type="SDS", score=55, standard_score=60, risk_level="yellow", created_at=datetime.now() - timedelta(days=20)))
    tests.append(TestResult(user_id=student1.id, test_type="SDS", score=65, standard_score=70, risk_level="red", created_at=datetime.now() - timedelta(days=10)))
    tests.append(TestResult(user_id=student1.id, test_type="SDS", score=60, standard_score=65, risk_level="red", created_at=datetime.now() - timedelta(days=1)))

    tests.append(TestResult(user_id=student2.id, test_type="SAS", score=45, standard_score=48, risk_level="green", created_at=datetime.now() - timedelta(days=25)))
    tests.append(TestResult(user_id=student2.id, test_type="SAS", score=52, standard_score=55, risk_level="yellow", created_at=datetime.now() - timedelta(days=12)))
    tests.append(TestResult(user_id=student2.id, test_type="SAS", score=42, standard_score=45, risk_level="green", created_at=datetime.now() - timedelta(days=2)))

    tests.append(TestResult(user_id=student3.id, test_type="SDS", score=40, standard_score=45, risk_level="green", created_at=datetime.now() - timedelta(days=15)))
    tests.append(TestResult(user_id=student3.id, test_type="SAS", score=55, standard_score=58, risk_level="yellow", created_at=datetime.now() - timedelta(days=8)))
    tests.append(TestResult(user_id=student3.id, test_type="SDS", score=58, standard_score=62, risk_level="yellow", created_at=datetime.now() - timedelta(days=3)))
    
    db.add_all(tests)
    db.commit()
    
    print("Inserting treehole posts...")
    posts = []
    posts.append(TreeholePost(anonymous_id="Anon_1", content="***，***，感觉快要崩溃了。", emotion_keywords="失眠,压力,崩溃", user_id=student1.id))
    posts.append(TreeholePost(anonymous_id="Anon_1", content="***，***，最近好烦。", emotion_keywords="烦躁,疲惫", user_id=student1.id))
    posts.append(TreeholePost(anonymous_id="Anon_1", content="***，***，还是提不起劲。", emotion_keywords="低落,无力", user_id=student1.id))

    posts.append(TreeholePost(anonymous_id="Anon_2", content="***，***，心情不错！", emotion_keywords="开心,放松", user_id=student2.id))
    posts.append(TreeholePost(anonymous_id="Anon_2", content="***，***，有点小焦虑。", emotion_keywords="焦虑", user_id=student2.id))

    posts.append(TreeholePost(anonymous_id="Anon_3", content="***，***，迷茫。", emotion_keywords="迷茫,未知", user_id=student3.id))
    posts.append(TreeholePost(anonymous_id="Anon_3", content="***，***，考试没考好。", emotion_keywords="沮丧,挫败", user_id=student3.id))
    db.add_all(posts)
    db.commit()
    
    print("Inserting appointments...")
    apps = []
    app1 = Appointment(student_id=student1.id, teacher_id=teacher1.id, time_slot="周一 14:00-15:00", status="pending")
    app2 = Appointment(student_id=student1.id, teacher_id=teacher2.id, time_slot="周三 10:00-11:00", status="completed")
    app3 = Appointment(student_id=student2.id, teacher_id=teacher1.id, time_slot="周二 09:00-10:00", status="completed")
    app4 = Appointment(student_id=student3.id, teacher_id=teacher3.id, time_slot="周五 09:00-10:00", status="pending")
    apps.extend([app1, app2, app3, app4])
    db.add_all(apps)
    db.commit()

    print("Inserting intervention records...")
    interventions = []
    interventions.append(InterventionRecord(student_id=student1.id, teacher_id=teacher1.id, record_date=datetime.now().strftime("%Y-%m-%d"), notes="约谈学生，了解近期焦虑原因，建议参加团体辅导。"))
    interventions.append(InterventionRecord(student_id=student2.id, teacher_id=teacher1.id, record_date=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"), notes="常规回访，情绪稳定。"))
    interventions.append(InterventionRecord(student_id=student3.id, teacher_id=teacher3.id, record_date=(datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"), notes="学生主动预约，解答了关于学业压力的困惑。"))
    db.add_all(interventions)
    db.commit()
    
    print("Seed complete.")
    db.close()

if __name__ == "__main__":
    seed_data()
