import os
from dotenv import load_dotenv
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta

load_dotenv()

redis_url = os.getenv('REDIS_URL')


celery_app = Celery(
    'report_generator',
    broker=redis_url,
    backend=redis_url,
    include=['app.services.report_service'],
)


celery_app.conf.update(
    timezone='Asia/Seoul',
    enable_utc=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_time_limit=30 * 60, # 30분
    task_soft_time_limit=25 * 60, # 25분
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

celery_app.conf.beat_schedule = {
    'test-every-30-seconds': {
        'task': 'app.services.report_service.generate_weekly_report',
        'schedule': timedelta(seconds=30), # 테스트용 - 확인함
    },
    'weekly-report-generation': {
        'task': 'app.services.report_service.generate_weekly_report',
        'schedule': crontab(hour=9, minute=0, day_of_week=1), # 월요일 9시(오전)
    },
    'monthly-report-generation': {
        'task': 'app.services.report_service.generate_monthly_report',
        'schedule': crontab(hour=9, minute=0, day_of_month=1), # 월 1일 9시(오전)
    },
}
