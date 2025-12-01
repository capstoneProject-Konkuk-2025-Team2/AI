# from sqlalchemy import create_engine, text
# from urllib.parse import quote_plus

# HOST="capstone-database.ch80usqgekm2.ap-northeast-2.rds.amazonaws.com"
# PORT="3306"
# USER="jo-eun-yeong"
# PWD="dmsdud03256022"
# DB="capstone"

# url=f"mysql+pymysql://{USER}:{quote_plus(PWD)}@{HOST}:{PORT}/{DB}"
# engine=create_engine(url)

# with engine.connect() as conn:
#     for q in [
#         "SELECT CURRENT_USER() as cur, USER() as user, DATABASE() as db;",
#         "SHOW GRANTS FOR CURRENT_USER();",
#         "SHOW TABLES;"
#     ]:
#         print("==", q)
#         for row in conn.execute(text(q)):
#             print(dict(row))

# check.py
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

HOST="capstone-database.ch80usqgekm2.ap-northeast-2.rds.amazonaws.com"
PORT="3306"
USER="jo-eun-yeong"          # 새로 만든 계정
PWD="dmsdud03256022"          # 새 비밀번호
DB ="capstone"

url = f"mysql+pymysql://{USER}:{quote_plus(PWD)}@{HOST}:{PORT}/{DB}"
engine = create_engine(url)

QUERIES = [
    "SELECT CURRENT_USER() AS cur, USER() AS user, DATABASE() AS db;",
    "SHOW GRANTS FOR CURRENT_USER();",
    "SHOW TABLES;"
]

print("== DB CONNECT TEST ==")
with engine.connect() as conn:
    for q in QUERIES:
        print("\n==", q)
        # 방법 1) mappings() 사용 (권장)
        result = conn.execute(text(q)).mappings()
        any_row = False
        for row in result:
            any_row = True
            print(dict(row))        # 안전하게 dict 변환 가능
        if not any_row:
            print("(no rows)")

print("\n✅ Done")