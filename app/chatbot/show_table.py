# # # # ▶ 임시 스니펫: 테이블/컬럼 이름 덤프 (build_graph.py 최상단에 두지 말고, 일단 별도 파일로 빠르게 실행)
# # # from sqlalchemy import create_engine, text
# # # import os
# # # from urllib.parse import quote_plus

# # # HOST=os.getenv("HOST"); PORT=os.getenv("PORT") or "3306"
# # # USERNAME=os.getenv("USERNAME"); PASSWORD=os.getenv("PASSWORD")
# # # DBNAME=os.getenv("DBNAME")
# # # DATABASE_URL=f"mysql+pymysql://{USERNAME}:{quote_plus(PASSWORD)}@{HOST}:{PORT}/{DBNAME}"

# # # engine=create_engine(DATABASE_URL)

# # # with engine.connect() as conn:
# # #     print("=== SHOW TABLES ===")
# # #     for (t,) in conn.exec_driver_sql("SHOW TABLES").fetchall():
# # #         print("-", t)

# # #     # 후보 테이블들만 찍어보기
# # #     print("\n=== LIKE 'extra%' 후보 ===")
# # #     for (t,) in conn.exec_driver_sql("SHOW TABLES LIKE 'extra%'").fetchall():
# # #         print("-", t)

# # #     # 테이블 결정 후 컬럼 보기 (아래 이름은 출력 보고 바꿔넣자)
# # #     # 예: extracurricular / Extracurricular / EXTRA_CURRICULAR 등 실제 이름 대체
# # #     print("\n=== DESCRIBE extracurricular ===")
# # #     for row in conn.exec_driver_sql("DESCRIBE `extracurricular`").fetchall():
# # #         print(row)

# # # show_table.py
# # from pathlib import Path
# # from dotenv import load_dotenv
# # load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")  # <-- 프로젝트 .env

# # import os
# # from urllib.parse import quote_plus
# # from sqlalchemy import create_engine, text

# # HOST = os.getenv("HOST")
# # PORT = os.getenv("PORT") or "3306"
# # USERNAME = os.getenv("USERNAME")
# # PASSWORD = os.getenv("PASSWORD")
# # DBNAME = os.getenv("DBNAME")

# # missing = [k for k,v in {
# #     "HOST":HOST, "USERNAME":USERNAME, "PASSWORD":PASSWORD, "DBNAME":DBNAME
# # }.items() if not v]
# # if missing:
# #     raise SystemExit(f".env 누락: {', '.join(missing)}")

# # DATABASE_URL = f"mysql+pymysql://{USERNAME}:{quote_plus(PASSWORD)}@{HOST}:{PORT}/{DBNAME}"
# # print("DATABASE_URL =", DATABASE_URL)

# # engine = create_engine(DATABASE_URL)

# # with engine.connect() as conn:
# #     print("\n=== SHOW TABLES ===")
# #     for (t,) in conn.exec_driver_sql("SHOW TABLES").fetchall():
# #         print("-", t)

# #     print("\n=== DESCRIBE extracurricular ===")
# #     for row in conn.exec_driver_sql("DESCRIBE `extracurricular`").fetchall():
# #         print(row)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `extracurricular` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== DESCRIBE interest ===")
# #     # for row in conn.exec_driver_sql("DESCRIBE `interest`").fetchall():
# #     #     print(row)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `interest` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== DESCRIBE emember ===")
# #     # for row in conn.exec_driver_sql("DESCRIBE `member`").fetchall():
# #     #     print(row)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `member` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== DESCRIBE review ===")
# #     # for row in conn.exec_driver_sql("DESCRIBE `review`").fetchall():
# #     #     print(row)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `review` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== DESCRIBE schedule ===")
# #     # for row in conn.exec_driver_sql("DESCRIBE `schedule`").fetchall():
# #     #     print(row)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `schedule` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== DESCRIBE timetable ===")
# #     # for row in conn.exec_driver_sql("DESCRIBE `timetable`").fetchall():
# #     #     print(row)
# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `timetable` LIMIT 1").mappings().all()
# #     # print(res)

# #     # print("\n=== 예시 1행 미리보기 ===")
# #     # res = conn.exec_driver_sql("SELECT * FROM `extracurricular` LIMIT 1").mappings().all()
# #     # print(res)

# from sqlalchemy import create_engine, text
# import os
# from urllib.parse import quote_plus

# HOST = "capstone-database.ch80usqgekm2.ap-northeast-2.rds.amazonaws.com"
# PORT = "3306"
# USERNAME = "admin"
# PASSWORD = "qxJRQHsIWfEZCbBXnJ5r"
# DBNAME = "capstone"

# url = f"mysql+pymysql://{USERNAME}:{quote_plus(PASSWORD)}@{HOST}:{PORT}/{DBNAME}"
# engine = create_engine(url)

# with engine.connect() as conn:
#     # result = conn.execute(text("SHOW TABLES;"))
#     for row in conn.exec_driver_sql("DESCRIBE `extracurricular`").fetchall():
#         print(row)
#     # for r in result:
#     #     print(r)

# -*- coding: utf-8 -*-
"""
테이블들을 순회하며 DESCRIBE와 SAMPLE(SELECT * LIMIT 5)을 출력
- SQLAlchemy + PyMySQL만 사용
- 접속 되면 테이블별로 하나하나 시도하며 실패해도 계속 진행
"""

import os
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# ===== 연결 정보: env 또는 직접 기입 =====
HOST = "capstone-database.ch80usqgekm2.ap-northeast-2.rds.amazonaws.com"
PORT = "3306"
USERNAME = "admin"
PASSWORD = "qxJRQHsIWfEZCbBXnJ5r"
DBNAME = "capstone"

# 테이블 목록: 필요시 수정
TABLES = ["extracurricular", "member", "timetable", "schedule", "review", "interest"]

# ===== 엔진 생성 =====
url = f"mysql+pymysql://{USERNAME}:{quote_plus(str(PASSWORD))}@{HOST}:{PORT}/{DBNAME}"
engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)

def print_hr():
    print("-" * 60)

def describe_table(conn, table):
    print_hr()
    print(f"== DESCRIBE `{table}` ==")
    try:
        rows = conn.exec_driver_sql(f"DESCRIBE `{table}`").fetchall()
        if not rows:
            print("(empty)")
            return
        # rows는 튜플; 컬럼: Field, Type, Null, Key, Default, Extra
        print("Field | Type | Null | Key | Default | Extra")
        for r in rows:
            # r가 튜플일 경우 인덱스로 접근
            Field, Type, Null, Key, Default, Extra = r
            print(f"{Field} | {Type} | {Null} | {Key} | {Default} | {Extra}")
    except SQLAlchemyError as e:
        print(f"(DESCRIBE 실패) {e}")

def sample_table(conn, table, limit=5):
    print_hr()
    print(f"== SAMPLE `{table}` (LIMIT {limit}) ==")
    try:
        result = conn.execute(text(f"SELECT * FROM `{table}` LIMIT {limit}"))
        rows = result.mappings().all()
        if not rows:
            print("(no rows)")
            return
        # \G 스타일 세로 출력
        for i, row in enumerate(rows, start=1):
            print(f"*************************** {i}. row ***************************")
            for k, v in row.items():
                print(f"{k}: {v}")
    except SQLAlchemyError as e:
        print(f"(SAMPLE 실패) {e}")

def main():
    print(f"[연결 시도] {engine.url.render_as_string(hide_password=True)}")
    try:
        with engine.connect() as conn:
            # 연결 확인
            conn.execute(text("SELECT 1"))
            print("✅ DB 연결 OK")
            print_hr()

            # SHOW TABLES (참고)
            try:
                show = conn.exec_driver_sql("SHOW TABLES;").fetchall()
                print("== SHOW TABLES ==")
                for t in show:
                    # ('table_name',) 형태
                    print("-", t[0])
            except SQLAlchemyError as e:
                print(f"(SHOW TABLES 실패) {e}")
            print_hr()

            # 대상 테이블 순회
            for t in TABLES:
                describe_table(conn, t)
                sample_table(conn, t)
                print_hr()

    except SQLAlchemyError as e:
        print(f"[DB 연결/쿼리 오류] {e}")

if __name__ == "__main__":
    main()