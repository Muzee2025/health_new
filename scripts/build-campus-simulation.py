"""Build an isolated, reproducible 2025–2026 campus simulation (stdlib only)."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from math import ceil
from pathlib import Path
import random
import sqlite3
import sys


SEED = 20261104
BASE_HASH = "3f8931f627eebeb4c0514e580fa3b62516d73eed9d619e3eadaaaf781d388d20"
COHORTS = {2022: 4700, 2023: 4850, 2024: 5050, 2025: 5400}
TZ = timezone(timedelta(hours=8))
SOURCES = {
    "calendar": "https://jw.whxy.edu.cn/info/1031/10464.htm",
    "departments": "https://www.whxy.edu.cn/ybsz.htm",
    "cohort_programs": "https://cw.whxy.edu.cn/__local/4/58/CD/37215CC85CDF2D2F5756BF5E200_34E7C2C0_1A5B4B.pdf",
    "tracks": "https://xxgk.whxy.edu.cn/info/1010/3529.htm",
}
TERMS = (
    (1, "第一学期", "2025-09-06", "2025-09-08", "2026-01-18", "2026-01-05"),
    (2, "第二学期", "2026-03-07", "2026-03-09", "2026-07-12", "2026-06-29"),
)
DEPARTMENTS = {
    1: "会计学院", 2: "信息工程学院", 3: "金融与经济学院", 4: "管理学院",
    5: "法学院", 6: "艺术与传媒学院", 7: "外国语学院", 8: "通识教育课部",
}
# Department, simulation code, major, track, allocation weight, first/last cohort.
# Weights and internal codes are scenario inputs. The fee catalogue scopes cohort eligibility.
PROGRAMS = (
    (1, 1, "会计学", "ACA班", 17, 2022, 2025),
    (1, 2, "会计学", "", 25, 2022, 2024),
    (1, 3, "会计学", "数智会计", 27, 2025, 2025),
    (1, 4, "财务管理", "CIMA班", 11, 2022, 2025),
    (1, 5, "财务管理", "数智财务实验班", 14, 2023, 2025),
    (1, 6, "审计学", "", 13, 2022, 2024),
    (1, 7, "审计学", "智能审计", 13, 2025, 2025),
    (2, 11, "软件工程", "腾讯班", 25, 2022, 2025),
    (2, 12, "软件工程", "中软卓越工程师班", 27, 2022, 2025),
    (2, 13, "网络工程", "", 23, 2022, 2024),
    (2, 14, "网络工程", "华为班", 19, 2022, 2025),
    (2, 15, "物联网工程", "", 15, 2022, 2025),
    (2, 16, "数据科学与大数据技术", "", 18, 2022, 2025),
    (2, 17, "智能科学与技术", "", 10, 2022, 2025),
    (2, 18, "智能视觉工程", "", 8, 2025, 2025),
    (3, 1, "金融学", "", 20, 2022, 2024),
    (3, 2, "金融学", "数字金融方向", 20, 2025, 2025),
    (3, 3, "国际经济与贸易", "", 12, 2022, 2024),
    (3, 4, "国际经济与贸易", "数字贸易方向", 12, 2025, 2025),
    (3, 5, "跨境电子商务", "", 11, 2022, 2025),
    (3, 6, "税收学", "", 8, 2022, 2025),
    (3, 7, "数字经济", "商务分析方向", 10, 2025, 2025),
    (4, 1, "工商管理", "", 14, 2022, 2025),
    (4, 2, "供应链管理", "", 13, 2022, 2024),
    (4, 3, "供应链管理", "智能制造供应链方向", 12, 2025, 2025),
    (4, 4, "大数据管理与应用", "", 18, 2024, 2025),
    (4, 5, "旅游管理", "", 9, 2022, 2025),
    (4, 6, "工程管理", "", 10, 2022, 2025),
    (5, 1, "法学", "", 28, 2022, 2025),
    (5, 2, "国际经贸规则", "", 8, 2022, 2025),
    (6, 1, "网络与新媒体", "", 18, 2022, 2025),
    (6, 2, "新闻学", "", 11, 2022, 2025),
    (6, 3, "视觉传达设计", "", 17, 2022, 2025),
    (6, 4, "数字媒体艺术", "", 17, 2022, 2025),
    (6, 5, "影视摄影与制作", "", 10, 2022, 2025),
    (6, 6, "工艺美术", "", 8, 2022, 2025),
    (6, 7, "环境设计", "", 10, 2022, 2024),
    (7, 1, "英语", "", 14, 2022, 2025),
    (7, 2, "商务英语", "", 11, 2022, 2025),
    (8, 1, "社会体育指导与管理", "", 10, 2022, 2025),
    (8, 2, "社会体育指导与管理", "中帆协帆船特色班", 7, 2022, 2025),
)
KINDS = (
    "platform_visit", "article_view", "mood_checkin", "demo_assessment",
    "chat_session", "appointment", "treehole_post", "teacher_message",
)
TOPICS = ("学业安排", "作息", "人际相处", "校园适应", "生涯规划", "平台操作")

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE sim_batch (
 id TEXT PRIMARY KEY, academic_year TEXT NOT NULL, timezone TEXT NOT NULL,
 seed INTEGER NOT NULL, population INTEGER NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic=1),
 sources_json TEXT NOT NULL CHECK(json_valid(sources_json))
);
CREATE TABLE sim_terms (
 term_id INTEGER PRIMARY KEY CHECK(term_id IN (1,2)), name TEXT NOT NULL,
 activity_start TEXT NOT NULL, teaching_start TEXT NOT NULL, activity_end TEXT NOT NULL,
 simulated_exam_start TEXT NOT NULL
);
CREATE TABLE sim_departments (department_code INTEGER PRIMARY KEY, department TEXT NOT NULL UNIQUE);
CREATE TABLE sim_programs (
 department_code INTEGER NOT NULL REFERENCES sim_departments, program_code INTEGER NOT NULL,
 major TEXT NOT NULL, track TEXT NOT NULL, weight INTEGER NOT NULL CHECK(weight>0),
 first_cohort INTEGER NOT NULL, last_cohort INTEGER NOT NULL,
 PRIMARY KEY(department_code,program_code)
);
CREATE TABLE sim_classes (
 class_id INTEGER PRIMARY KEY, department_code INTEGER NOT NULL, program_code INTEGER NOT NULL,
 cohort INTEGER NOT NULL, class_number INTEGER NOT NULL CHECK(class_number BETWEEN 1 AND 99),
 class_label TEXT NOT NULL,
 UNIQUE(department_code,program_code,cohort,class_number),
 FOREIGN KEY(department_code,program_code) REFERENCES sim_programs
);
CREATE TABLE sim_students (
 student_id INTEGER PRIMARY KEY, student_no TEXT NOT NULL UNIQUE,
 class_id INTEGER NOT NULL REFERENCES sim_classes,
 class_sequence INTEGER NOT NULL CHECK(class_sequence BETWEEN 1 AND 99),
 synthetic INTEGER NOT NULL DEFAULT 1 CHECK(synthetic=1),
 CHECK(student_no GLOB 'SIM-[0-9][0-9]9[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'),
 UNIQUE(class_id,class_sequence)
);
CREATE TABLE sim_student_terms (
 student_id INTEGER NOT NULL REFERENCES sim_students, term_id INTEGER NOT NULL REFERENCES sim_terms,
 grade_year INTEGER NOT NULL CHECK(grade_year BETWEEN 1 AND 4),
 active_from TEXT NOT NULL, active_until TEXT NOT NULL CHECK(active_until>=active_from),
 PRIMARY KEY(student_id,term_id)
);
CREATE TABLE sim_events (
 event_id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, term_id INTEGER NOT NULL,
 occurred_at TEXT NOT NULL CHECK(substr(occurred_at,20)='+08:00'),
 event_type TEXT NOT NULL CHECK(event_type IN (
  'platform_visit','article_view','mood_checkin','demo_assessment','chat_session',
  'appointment','treehole_post','teacher_message')),
 topic TEXT, score INTEGER, scheduled_at TEXT, status TEXT,
 FOREIGN KEY(student_id,term_id) REFERENCES sim_student_terms,
 CHECK(CASE event_type
   WHEN 'mood_checkin' THEN score IS NOT NULL AND score BETWEEN 1 AND 5
   WHEN 'demo_assessment' THEN score IS NOT NULL AND score BETWEEN 0 AND 100
   ELSE score IS NULL END),
 CHECK(CASE event_type WHEN 'appointment' THEN
   scheduled_at IS NOT NULL AND scheduled_at>occurred_at AND substr(scheduled_at,20)='+08:00'
   AND status IS NOT NULL AND status IN ('completed','cancelled','no_show')
   ELSE scheduled_at IS NULL AND status IS NULL END)
);
CREATE INDEX ix_sim_events_student_term ON sim_events(student_id,term_id,occurred_at);
CREATE INDEX ix_sim_events_term_time ON sim_events(term_id,occurred_at,event_type);
CREATE VIEW sim_roster AS
 SELECT s.student_id,s.student_no,c.cohort,d.department_code,d.department,
        p.program_code,p.major,p.track,c.class_id,c.class_number,c.class_label,s.class_sequence,s.synthetic
 FROM sim_students s JOIN sim_classes c USING(class_id) JOIN sim_departments d USING(department_code)
 JOIN sim_programs p ON p.department_code=c.department_code AND p.program_code=c.program_code;
CREATE VIEW sim_term_activity AS
 SELECT r.*,st.term_id,st.grade_year,st.active_from,st.active_until,
        COUNT(e.event_id) AS event_count,
        COUNT(CASE WHEN e.event_type='mood_checkin' THEN 1 END) AS checkins,
        COUNT(CASE WHEN e.event_type='demo_assessment' THEN 1 END) AS assessments,
        COUNT(CASE WHEN e.event_type='chat_session' THEN 1 END) AS chat_sessions,
        COUNT(CASE WHEN e.event_type='appointment' THEN 1 END) AS appointments
 FROM sim_roster r JOIN sim_student_terms st USING(student_id)
 LEFT JOIN sim_events e ON e.student_id=st.student_id AND e.term_id=st.term_id
 GROUP BY st.student_id,st.term_id;
"""


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def allocate(total, programs):
    """Allocate exactly total seats by largest remainder, with stable tie order."""
    weight = sum(p[4] for p in programs)
    seats = [total * p[4] // weight for p in programs]
    order = sorted(range(len(programs)), key=lambda i: -(total * programs[i][4] % weight))
    for index in order[:total - sum(seats)]:
        seats[index] += 1
    return zip(programs, seats)


def add_roster(db):
    classes, students, enrollments = [], [], []
    for cohort, total in COHORTS.items():
        eligible = [p for p in PROGRAMS if p[5] <= cohort <= p[6]]
        for program, seats in allocate(total, eligible):
            department, code = program[:2]
            class_count = ceil(seats / 46)
            size, extra = divmod(seats, class_count)
            for number in range(1, class_count + 1):
                class_id = len(classes) + 1
                label = f"{cohort % 100:02d}{number:02d}班"
                classes.append((class_id, department, code, cohort, number, label))
                for sequence in range(1, size + (number <= extra) + 1):
                    student_id = len(students) + 1
                    student_no = f"SIM-{cohort % 100:02d}9{department:02d}{code:02d}{number:02d}{sequence:02d}"
                    students.append((student_id, student_no, class_id, sequence))
                    for term, _, start, _, end, _ in TERMS:
                        active = "2025-09-13" if cohort == 2025 and term == 1 else start
                        enrollments.append((student_id, term, 2026 - cohort, active, end))
    db.executemany("INSERT INTO sim_classes VALUES (?,?,?,?,?,?)", classes)
    db.executemany("INSERT INTO sim_students(student_id,student_no,class_id,class_sequence) VALUES (?,?,?,?)", students)
    db.executemany("INSERT INTO sim_student_terms VALUES (?,?,?,?,?)", enrollments)
    return enrollments


def day_profile(start, end, exam_start):
    start, end, exam_start = map(date.fromisoformat, (start, end, exam_start))
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    weights = [(.68 if d.weekday() >= 5 else 1) *
               (1.6 if (d - start).days < 16 or d >= exam_start else 1)
               for d in days]
    return days, weights


def stamp(day, minute):
    return datetime.combine(day, time(minute // 60, minute % 60), TZ).isoformat()


def add_activity(db, enrollments, seed):
    rng = random.Random(seed)
    profiles = {(term, start): day_profile(start, end, exam)
                for term, _, first, _, end, exam in TERMS
                for start in ({first, "2025-09-13"} if term == 1 else {first})}
    rng_by_student = {}
    rows = []
    for student, term, _, start, end in enrollments:
        if student not in rng_by_student:
            rng_by_student[student] = (rng.betavariate(2.4, 2.2), rng.gauss(0, 0.60))
        engagement, tendency = rng_by_student[student]
        if rng.random() > .28 + .64 * engagement + .03 * (term - 1):
            continue
        days, weights = profiles[term, start]
        end_date = date.fromisoformat(end)
        events = []
        for kind, likelihood, limit in (
            ("article_view", .78, 5), ("mood_checkin", .64, 8),
            ("demo_assessment", .67, 3), ("chat_session", .53, 5),
            ("appointment", .10, 1), ("treehole_post", .18, 3), ("teacher_message", .22, 2),
        ):
            if rng.random() >= likelihood * (.58 + .63 * engagement):
                continue
            for day in rng.choices(days, weights, k=rng.randint(1, limit)):
                occurred = stamp(day, rng.randint(8 * 60, 22 * 60 + 59))
                topic, score, scheduled, status = rng.choice(TOPICS), None, None, None
                if kind == "mood_checkin":
                    score = max(1, min(5, round(rng.gauss(3.2 + tendency, .9))))
                elif kind == "demo_assessment":
                    score = max(0, min(100, round(rng.gauss(64 + tendency * 10, 15))))
                elif kind == "appointment":
                    if day == end_date:
                        day -= timedelta(days=1)
                        occurred = stamp(day, rng.randint(8 * 60, 22 * 60 + 59))
                    appointment_day = min(day + timedelta(days=rng.randint(1, 7)), end_date)
                    scheduled = stamp(appointment_day, rng.choice((540, 600, 660, 840, 900, 960)))
                    status = rng.choices(("completed", "cancelled", "no_show"), (75, 18, 7))[0]
                events.append((student, term, occurred, kind, topic, score, scheduled, status))
        first_visit = min((e[2] for e in events), default=None)
        if first_visit is None:
            first_visit = stamp(rng.choices(days, weights)[0], rng.randint(480, 1379))
        events.append((student, term, first_visit, "platform_visit", None, None, None, None))
        rows.extend(sorted(events, key=lambda row: row[2]))
        if len(rows) >= 4000:
            insert_events(db, rows)
            rows.clear()
    insert_events(db, rows)


def insert_events(db, rows):
    db.executemany(
        "INSERT INTO sim_events(student_id,term_id,occurred_at,event_type,topic,score,scheduled_at,status) "
        "VALUES (?,?,?,?,?,?,?,?)", rows,
    )


def verify(db):
    def scalar(sql):
        return db.execute(sql).fetchone()[0]

    counts = {table: scalar(f"SELECT COUNT(*) FROM {table}") for table in (
        "sim_students", "sim_student_terms", "sim_departments", "sim_programs", "sim_classes",
        "sim_events", "reference_records", "training_examples",
    )}
    term_counts = [list(row) for row in db.execute("""
        SELECT st.term_id,COUNT(*),SUM(EXISTS(
            SELECT 1 FROM sim_events e WHERE e.student_id=st.student_id AND e.term_id=st.term_id))
        FROM sim_student_terms st GROUP BY st.term_id ORDER BY st.term_id
    """)]
    problems = {
        "id_mismatch": scalar("""SELECT COUNT(*) FROM sim_roster WHERE student_no<>
            printf('SIM-%02d9%02d%02d%02d%02d',cohort%100,department_code,program_code,class_number,class_sequence)
            OR class_label<>printf('%02d%02d班',cohort%100,class_number)"""),
        "cohort_or_calendar_mismatch": scalar("""SELECT COUNT(*) FROM sim_student_terms st
            JOIN sim_roster r USING(student_id) JOIN sim_terms t USING(term_id)
            JOIN sim_programs p ON p.department_code=r.department_code AND p.program_code=r.program_code
            WHERE grade_year<>2026-r.cohort OR r.cohort NOT BETWEEN p.first_cohort AND p.last_cohort
            OR active_from<>CASE WHEN r.cohort=2025 AND st.term_id=1 THEN '2025-09-13' ELSE t.activity_start END
            OR active_until<>t.activity_end"""),
        "event_outside_window": scalar("""SELECT COUNT(*) FROM sim_events JOIN sim_student_terms USING(student_id,term_id)
            WHERE substr(occurred_at,1,10) NOT BETWEEN active_from AND active_until
            OR (scheduled_at IS NOT NULL AND substr(scheduled_at,1,10) NOT BETWEEN active_from AND active_until)"""),
        "group_without_both_terms": scalar("""SELECT COUNT(*) FROM (
            SELECT s.student_id FROM sim_students s LEFT JOIN sim_student_terms st USING(student_id)
            GROUP BY s.student_id HAVING COUNT(st.term_id)<>2)"""),
        "inconsistent_class_roster": scalar("""SELECT COUNT(*) FROM (
            SELECT c.class_id FROM sim_classes c LEFT JOIN sim_students s USING(class_id)
            GROUP BY c.class_id HAVING COUNT(s.student_id)=0 OR MAX(s.class_sequence)<>COUNT(s.student_id)
                OR COUNT(s.student_id)>46)"""),
    }
    assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert not any(problems.values()), problems
    assert counts["sim_students"] == 20_000 and counts["sim_student_terms"] == 40_000
    assert (counts["training_examples"], counts["reference_records"]) == (96, 476)
    assert dict(db.execute("SELECT cohort,COUNT(*) FROM sim_roster GROUP BY cohort")) == COHORTS
    assert {r[0] for r in db.execute("SELECT DISTINCT event_type FROM sim_events")} == set(KINDS)
    assert all(total == 20_000 and 0 < active < total for _, total, active in term_counts)
    event_counts = [list(row) for row in db.execute(
        "SELECT term_id,event_type,COUNT(*) FROM sim_events GROUP BY term_id,event_type ORDER BY term_id,event_type"
    )]
    return {"table_counts": counts, "term_enrollment_and_active_counts": term_counts,
            "event_counts": event_counts, "checks": problems, "integrity": "ok", "foreign_key_errors": 0}


def export_csv(db, target, query):
    cursor = db.execute(query)
    with target.open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([column[0] for column in cursor.description])
        writer.writerows(cursor)


def build(source, output):
    source, output = Path(source).resolve(strict=True), Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output must be a new directory")
    if sha256(source) != BASE_HASH:
        raise ValueError("Expected the verified synthetic Q&A database")
    with sqlite3.connect(source.as_uri() + "?mode=ro&immutable=1", uri=True) as old, sqlite3.connect(":memory:") as db:
        old.execute("PRAGMA query_only=ON")
        old.backup(db)
        db.executescript(DDL)
        db.execute("INSERT INTO sim_batch VALUES (?,?,?,?,?,1,?)",
                   ("campus-2025-2026-v1", "2025-2026", "Asia/Shanghai", SEED, sum(COHORTS.values()),
                    json.dumps(SOURCES, ensure_ascii=False)))
        db.executemany("INSERT INTO sim_terms VALUES (?,?,?,?,?,?)", TERMS)
        db.executemany("INSERT INTO sim_departments VALUES (?,?)", DEPARTMENTS.items())
        db.executemany("INSERT INTO sim_programs VALUES (?,?,?,?,?,?,?)", PROGRAMS)
        enrollments = add_roster(db)
        add_activity(db, enrollments, SEED)
        db.commit()
        summary = verify(db)
        if sha256(source) != BASE_HASH:
            raise ValueError("Reference database changed during simulation")
        output.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(output / "campus-simulation.sqlite3") as destination:
            db.backup(destination)
        export_csv(db, output / "student-semesters.csv", "SELECT * FROM sim_term_activity ORDER BY student_id,term_id")
        export_csv(db, output / "platform-events.csv", """
            SELECT s.student_no,e.term_id,e.occurred_at,e.event_type,e.topic,e.score,e.scheduled_at,e.status
            FROM sim_events e JOIN sim_students s USING(student_id) ORDER BY e.term_id,e.occurred_at,e.event_id
        """)
        export_csv(db, output / "monthly-activity.csv", """
            SELECT term_id,substr(occurred_at,1,7) AS month,event_type,
                   COUNT(*) AS events,COUNT(DISTINCT student_id) AS students
            FROM sim_events GROUP BY term_id,month,event_type ORDER BY term_id,month,event_type
        """)
    summary.update({"seed": SEED, "source_sha256": BASE_HASH, "cohorts": COHORTS,
                    "sources": SOURCES, "synthetic": True,
                    "files": {p.name: {"sha256": sha256(p), "bytes": p.stat().st_size}
                              for p in sorted(output.iterdir()) if p.is_file()}})
    (output / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.source, args.output)
    print(json.dumps({k: result[k] for k in ("table_counts", "term_enrollment_and_active_counts", "checks")},
                     ensure_ascii=False))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
