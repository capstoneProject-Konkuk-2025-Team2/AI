from sqlalchemy import inspect
from app.utils.db import engine

insp = inspect(engine)
cols = insp.get_columns("extracurricular")  # 테이블 이름
for col in cols:
    print(col["name"], col["type"])