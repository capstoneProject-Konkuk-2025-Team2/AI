from app.config.celery_config import celery_app

@celery_app.task
def test_hello(): # celery 테스트 - 완료함
    print("Hello Celery")
    return "Hello"


@celery_app.task
def generate_weekly_report(): # beat 테스트 - 완료함
    print("테스트 리포트 생성됨")
    return "테스트 리포트 생성됨"
