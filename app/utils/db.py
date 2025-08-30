from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

# MySQL 연결 URL
DATABASE_URL = f"mysql+pymysql://{os.getenv('USERNAME')}:{os.getenv('PASSWORD')}@{os.getenv('HOST')}:{os.getenv('PORT')}/{os.getenv('DBNAME')}"

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    echo=True,  # 개발 시 SQL 로그 출력
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)