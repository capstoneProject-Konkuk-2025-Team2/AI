import os

# 리포트 관련 설정
REPORT_DIR = os.getenv("REPORT_DIR", "reports")

# 이메일 템플릿
EMAIL_SUBJECT_TEMPLATE = "[리포트] {user_name}님의 활동 리포트가 도착했습니다"

EMAIL_BODY_TEMPLATE = """안녕하세요 {user_name}님,

{start_date}부터 {end_date}까지의 활동 리포트를 첨부합니다.
리포트를 통해 활동 현황을 확인하시고, 개선 방향을 참고해 보세요.

감사합니다.
"""

# 로깅 설정
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'app.log',
            'formatter': 'detailed',
            'level': 'INFO',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'level': 'INFO',
        }
    },
    'loggers': {
        '': {  # root logger
            'handlers': ['file', 'console'],
            'level': 'INFO',
        }
    }
}