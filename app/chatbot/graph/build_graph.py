from pathlib import Path
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from neo4j import GraphDatabase

# ---------- Neo4j ----------
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
if not NEO4J_PASSWORD:
    raise RuntimeError("NEO4J_PASSWORD 가 .env에 없습니다.")

# ---------- MySQL (RDS) ----------
HOST = os.getenv("HOST")
PORT = os.getenv("PORT", "3306")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DBNAME = os.getenv("DBNAME")
missing = [k for k, v in {"HOST": HOST, "USERNAME": USERNAME, "PASSWORD": PASSWORD, "DBNAME": DBNAME}.items() if not v]
if missing:
    raise RuntimeError(f".env 누락: {', '.join(missing)}")

PASSWORD_Q = quote_plus(str(PASSWORD))
DATABASE_URL = f"mysql+pymysql://{USERNAME}:{PASSWORD_Q}@{HOST}:{PORT}/{DBNAME}"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

# ---------- Neo4j loaders ----------
def load_programs(tx, rows):
    """
    Program 노드 upsert
    - id: program_id (extracurricular.extracurricular_id)
    - program_pk: 내부 PK (extracurricular_pk_id) - 필요시 추적용
    """
    for r in rows:
        tx.run("""
        MERGE (p:Program {id: $program_id})
          ON CREATE SET p.title=$title,
                        p.url=$url,
                        p.description=$description,
                        p.keywords=$keywords,
                        p.app_start=$app_start, p.app_end=$app_end,
                        p.act_start=$act_start, p.act_end=$act_end,
                        p.program_pk=$program_pk,
                        p.target_audience=$target_audience,
                        p.kum_mileage=$kum_mileage,
                        p.has_certificate=$has_certificate,
                        p.selection_method=$selection_method,
                        p.purpose=$purpose,
                        p.benefits=$benefits,
                        p.procedure=$procedure
          ON MATCH  SET p.title=$title,
                        p.url=$url,
                        p.description=$description,
                        p.keywords=$keywords,
                        p.app_start=$app_start, p.app_end=$app_end,
                        p.act_start=$act_start, p.act_end=$act_end,
                        p.program_pk=$program_pk,
                        p.target_audience=$target_audience,
                        p.kum_mileage=$kum_mileage,
                        p.has_certificate=$has_certificate,
                        p.selection_method=$selection_method,
                        p.purpose=$purpose,
                        p.benefits=$benefits,
                        p.procedure=$procedure
        """, **r)

def load_members_and_interests(tx, rows):
    for r in rows:
        # Member upsert (그대로)
        tx.run("""
        MERGE (m:Member {id: $member_id})
          ON CREATE SET m.email=$email, m.role=$role,
                        m.academic_status=$academic_status,
                        m.grade=$grade, m.college=$college, m.department=$department,
                        m.name=$name
          ON MATCH  SET m.email=$email, m.role=$role,
                        m.academic_status=$academic_status,
                        m.grade=$grade, m.college=$college, m.department=$department,
                        m.name=$name
        """, **r)

        # 관심사 연결: 빈 문자열/NULL 방지
        interest = (r.get("interest") or "").strip()
        if interest:
            tx.run("""
            MATCH (m:Member {id:$member_id})
            MERGE (t:Topic {name: $interest})
            MERGE (m)-[:INTERESTS]->(t)
            """, member_id=r["member_id"], interest=interest)

def load_timetable(tx, rows):
    """
    BusyBlock upsert + (Member)-[:HAS_BUSY]->(BusyBlock)
    """
    for r in rows:
        tx.run("""
        MERGE (m:Member {id:$member_id})
        MERGE (b:BusyBlock { id: $timetable_id })
        SET b.day=$day, b.start_time=$start_time, b.end_time=$end_time,
            b.event_name=$event_name, b.event_detail=$event_detail, b.color=$color
        MERGE (m)-[:HAS_BUSY]->(b)
        """, **r)

def load_member_program_edges(tx, rows):
    """
    (Member)-[:HAS_SCHEDULE]->(Program)
    - schedule 테이블 중 extracurricular_id NOT NULL만
    """
    for r in rows:
        tx.run("""
        MERGE (m:Member {id:$member_id})
        MERGE (p:Program {id:$program_id})
        MERGE (m)-[r:HAS_SCHEDULE {schedule_id:$schedule_id}]->(p)
        SET r.start_date=$start_date, r.end_date=$end_date, r.title=$title
        """, **r)

def load_reviews(tx, rows):
    """
    (Member)-[:REVIEWED]->(Program)
    """
    for r in rows:
        tx.run("""
        MERGE (m:Member {id:$member_id})
        MERGE (p:Program {id:$program_id})
        MERGE (m)-[rv:REVIEWED {id:$review_id}]->(p)
        SET rv.star=$star, rv.content=$content
        """, **r)

# ---------- MAIN ----------
if __name__ == "__main__":
    print("DATABASE_URL =", engine.url.render_as_string(hide_password=True))

    # 1) MySQL 연결 확인
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅ MySQL OK")

    # 2) 데이터 SELECT (현재 스키마에 맞춤)
    with engine.connect() as conn:
            # --- Program ---
        programs = conn.execute(text("""
            SELECT
              extracurricular_id       AS program_id,
              extracurricular_pk_id    AS program_pk,
              title,
              url,
              description,
              keywords,
              application_start        AS app_start,
              application_end          AS app_end,
              activity_start           AS act_start,
              activity_end             AS act_end,
              target_audience,
              kum_mileage,
              has_certificate,
              selection_method,
              purpose,
              benefits,
              `procedure`
            FROM extracurricular
            WHERE is_deleted = 0
        """)).mappings().all()

        # --- Member + Interests (row 당 관심사 0~1개; 관심사 여러개면 여러 row) ---
        members = conn.execute(text("""
            SELECT
              m.member_id              AS member_id,
              m.email                  AS email,
              m.role                   AS role,
              m.academic_status        AS academic_status,
              m.college                AS college,
              m.department             AS department,
              m.grade                  AS grade,
              m.name                   AS name,
              i.content                AS interest
            FROM member m
            LEFT JOIN interest i ON i.member_id = m.member_id
        """)).mappings().all()

        # --- Timetable (Busy) ---
        times = conn.execute(text("""
            SELECT
              t.timetable_id           AS timetable_id,
              t.member_id              AS member_id,
              t.day_of_week            AS day,
              t.start_time             AS start_time,
              t.end_time               AS end_time,
              t.event_name             AS event_name,
              t.event_detail           AS event_detail,
              t.color                  AS color
            FROM timetable t
        """)).mappings().all()

        # --- Schedule → Member-Program edge (extracurricular만) ---
        scheds = conn.execute(text("""
            SELECT
              s.schedule_id            AS schedule_id,
              s.member_id              AS member_id,
              s.extracurricular_id     AS program_id,
              s.start_date_time        AS start_date,
              s.end_date_time          AS end_date,
              s.title                  AS title
            FROM schedule s
            WHERE s.extracurricular_id IS NOT NULL
        """)).mappings().all()

        # --- Review ---
        reviews = conn.execute(text("""
            SELECT
              r.review_id              AS review_id,
              r.member_id              AS member_id,
              r.extracurricular_id     AS program_id,
              r.star                   AS star,
              r.content                AS content
            FROM review r
        """)).mappings().all()

    # 3) Neo4j 연결 확인 및 적재
    with driver.session() as s:
        s.run("RETURN 1").consume()
    print("✅ Neo4j OK")

    with driver.session() as s:
        s.execute_write(load_programs, programs)
        s.execute_write(load_members_and_interests, members)
        s.execute_write(load_timetable, times)
        s.execute_write(load_member_program_edges, scheds)
        s.execute_write(load_reviews, reviews)

    print("🎉 그래프 적재 완료")