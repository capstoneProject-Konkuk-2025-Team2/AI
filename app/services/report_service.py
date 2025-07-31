from app.config.celery_config import celery_app
from datetime import datetime, timedelta
from app.services.activity_service import calculate_user_stats
from app.services.generator.insight_generator import (
    generate_insights, generate_recommendations
)
from app.models.activity import UserReport, ReportPeriod
from app.services.user_service import load_all_users
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException

@celery_app.task
def test_hello(): # celery 테스트 - 완료함
    print("Hello Celery")
    return "Hello"


@celery_app.task
def generate_weekly_report(): # beat 테스트 - 완료함
    print("테스트 리포트 생성됨")
    return "테스트 리포트 생성됨"


def generate_user_report(user_id: str, period: ReportPeriod) -> UserReport:
    try:
        end_date = datetime.now()
        if period == ReportPeriod.WEEKLY:
            start_date = end_date - timedelta(weeks=1)
        elif period == ReportPeriod.MONTHLY:
            start_date = end_date - timedelta(days=30)
        else:
            raise AppException(ErrorCode.VALIDATION_ERROR)
        
        # 통계
        stats = calculate_user_stats(user_id, start_date, end_date)
        
        # 인사이트와 추천사항
        insights = generate_insights(stats)
        recommendations = generate_recommendations(stats)
        
        # LLM 피드백
        feedback_message = generate_feedback(stats, insights, recommendations)
        
        report = UserReport(
            user_id=user_id,
            period=period,
            start_date=start_date,
            end_date=end_date,
            stats=stats,
            insights=insights,
            recommendations=recommendations,
            feedback_message=feedback_message
        )
        
        return report
        
    except AppException:
        raise
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)

@celery_app.task(bind=True, name='app.services.report_service.generate_weekly_report')
def generate_weekly_report(self):
    try:
        users = load_all_users()
        success_count = 0
        failed_users = []
        
        for user in users:
            try:
                user_id = user.get('id')
                if not user_id:
                    continue
                
                report = generate_user_report(user_id, ReportPeriod.WEEKLY)
                success_count += 1
                print(f"주간 리포트 생성 완료: {user_id}")
                
            except Exception as e:
                failed_users.append(user_id)
                print(f"오류 발생: {user_id} - {e}")
        
        result_message = f"주간 리포트 생성 완료: 성공 {success_count}명"
        if failed_users:
            result_message += f", 실패 {len(failed_users)}명 ({', '.join(failed_users)})"
        
        return result_message
        
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True, name='app.services.report_service.generate_monthly_report')
def generate_monthly_report(self):
    try:
        users = load_all_users()
        success_count = 0
        failed_users = []
        
        for user in users:
            try:
                user_id = user.get('id')
                if not user_id:
                    continue
                
                report = generate_user_report(user_id, ReportPeriod.MONTHLY)
                success_count += 1
                print(f"월간 리포트 생성 완료: {user_id}")
                
            except Exception as e:
                failed_users.append(user_id)
                print(f"오류 발생: {user_id} - {e}")
        
        result_message = f"월간 리포트 생성 완료: 성공 {success_count}명"
        if failed_users:
            result_message += f", 실패 {len(failed_users)}명 ({', '.join(failed_users)})"
        
        return result_message
        
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True, name='app.services.report_service.generate_single_user_report')
def generate_single_user_report(self, user_id: str, period: str):
    try:
        period_enum = ReportPeriod(period)
        report = generate_user_report(user_id, period_enum)
        
        result_message = f"사용자 {user_id}의 {period} 리포트 생성 완료"
        print(f"{result_message}")
        
        return {
            "status": "success",
            "message": result_message,
            "report_id": f"{report.user_id}_{report.period.value}_{report.created_at.strftime('%Y%m%d_%H%M%S')}"
        }
        
    except Exception as e:
        error_message = f"사용자 {user_id}의 {period} 리포트 생성 실패: {str(e)}"
        print(f"오류 발생: {error_message}")
        
        raise self.retry(exc=e, countdown=60, max_retries=3) 