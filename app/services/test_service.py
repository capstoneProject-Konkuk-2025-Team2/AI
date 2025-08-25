# from app.utils.db import engine

# def check_db_connection():
#     try:
#         with engine.connect() as conn:
#             res = conn.exec_driver_sql("SELECT 1")
#             print("DB 연결 성공:", res.scalar_one())
#     except Exception as e:
#         print("DB 연결 실패:", e)

# if __name__ == "__main__":
#     check_db_connection()

from datetime import datetime
from app.services.report_service import generate_reports_for_users

user_payloads = [
    {"id": 1, "name": "홍길동", "email": "hong@test.com"},
    {"id": 2, "name": "김철수", "email": "kim@test.com"}
]
user_activity_map = {
    1: [1, 2, 3],
    2: [1, 2]
}

msg, failed = generate_reports_for_users(
    user_payloads=user_payloads,
    user_activity_map=user_activity_map,
    start_date=datetime(2025, 8, 1),
    end_date=datetime(2025, 8, 25),
)

print(msg, failed)

# send_hello_email.py
# import smtplib
# from email.mime.text import MIMEText

# # Gmail SMTP 서버 정보
# SMTP_SERVER = "smtp.gmail.com"
# SMTP_PORT = 587

# # 로그인 정보
# SMTP_USER = "final4end@gmail.com"
# SMTP_PASSWORD = "xlsc hzuq husd hqvp"  # 앱 비밀번호 사용

# # 수신자 및 메일 내용
# to_email = "pyeonk@konkuk.ac.kr"
# subject = "SMTP 테스트 메일"
# body = "안녕하세요, 이 메일은 Gmail SMTP 설정 테스트입니다."

# # 메일 생성
# msg = MIMEText(body)
# msg['Subject'] = subject
# msg['From'] = SMTP_USER
# msg['To'] = to_email

# # SMTP 서버에 연결하여 메일 보내기
# try:
#     server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
#     server.starttls()
#     server.login(SMTP_USER, SMTP_PASSWORD)
#     server.sendmail(SMTP_USER, to_email, msg.as_string())
#     print("메일 전송 성공!")
# except Exception as e:
#     print(f"메일 전송 실패: {e}")
# finally:
#     server.quit()
