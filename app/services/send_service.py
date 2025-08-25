import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()  # .env 파일 로드

def send_email_with_pdf_attachment(to_email, subject, body, pdf_bytes, filename):
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))

    if not all([smtp_user, smtp_password, smtp_server, smtp_port]):
        print("[환경변수 오류] SMTP 설정을 확인하세요.")
        return False

    # 이메일 메시지 생성
    message = MIMEMultipart()
    message['From'] = smtp_user
    message['To'] = to_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    # PDF 첨부
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(attachment)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)
        server.quit()
        print(f"[메일 전송 완료] {to_email}에게 {filename} 전송")
        return True
    except Exception as e:
        print(f"[메일 전송 실패] {to_email}: {e}")
        return False
