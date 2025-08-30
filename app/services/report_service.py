from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import logging
from contextlib import contextmanager

from sqlalchemy.orm import Session
from app.services.generator.insight_generator import generate_insights, generate_recommendations
from app.chatbot.llm_feedback_chatbot import generate_feedback
from app.models.activity import UserReport
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from app.services.activity_service import get_activity_service, SessionLocal 
from app.services.pdf_service import create_report_pdf_bytes    
from app.services.send_service import send_email_with_pdf_attachment
from app.services.user_service import load_all_users
from app.utils.format.report_format import REPORT_DIR, EMAIL_SUBJECT_TEMPLATE, EMAIL_BODY_TEMPLATE

logger = logging.getLogger(__name__)

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def generate_user_report(
    db: Session,
    user_id: int,
    user_name: str,
    activity_id_list: List[int],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> UserReport:
    try:
        activity_service = get_activity_service(db)

        # 통계 계산
        stats = activity_service.calculate_user_stats(
            user_id=user_id,
            activity_id_list=activity_id_list
        )

        # 인사이트 & 추천 생성
        insights = generate_insights(stats)
        recommendations = generate_recommendations(stats)

        # LLM 피드백 생성
        feedback_message = generate_feedback(stats, insights, recommendations)

        # UserReport 객체 생성
        report = UserReport(
            user_id=user_id,
            user_name=user_name,
            start_date=start_date,
            end_date=end_date,
            stats=stats,
            insights=insights,
            recommendations=recommendations,
            feedback_message=feedback_message,
        )
        
        logger.info(f"리포트 생성 성공: user_id={user_id}, activities={len(activity_id_list)}")
        return report

    except AppException:
        logger.warning(f"앱 예외 발생: user_id={user_id}")
        raise
    except Exception as e:
        logger.error(f"리포트 생성 오류: user_id={user_id}, error={e}", exc_info=True)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)


def _generate_filename(user_name: str, start_date: Optional[datetime], end_date: Optional[datetime]) -> str:
    if not start_date or not end_date:
        return f"report_user_{user_name}_no_date.pdf"
    
    # 파일명에 안전하지 않은 문자 제거
    safe_name = "".join(c for c in user_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    return f"report_user_{safe_name}_{start_date:%Y%m%d}-{end_date:%Y%m%d}.pdf"


def _process_single_user(
    user: dict, 
    user_activity_map: Dict[int, List[int]], 
    start_date: Optional[datetime], 
    end_date: Optional[datetime],
    db: Session
) -> Tuple[bool, Optional[str]]:
    user_id = user.get("id")
    user_name = user.get("name", f"User_{user_id}")
    user_email = user.get("email")
    
    if not user_id:
        return False, "사용자 ID가 없음"
    
    if not user_email:
        logger.warning(f"사용자 이메일이 없음: user_id={user_id}")
        return False, "이메일 주소가 없음"

    try:
        activity_id_list = user_activity_map.get(user_id, [])
        
        # 리포트 생성
        report = generate_user_report(
            db=db,
            user_id=user_id,
            user_name=user_name,
            activity_id_list=activity_id_list,
            start_date=start_date,
            end_date=end_date,
        )

        # PDF 생성
        pdf_bytes = create_report_pdf_bytes(report)
        
        # 파일 저장
        # out_dir = Path(REPORT_DIR)
        # out_dir.mkdir(parents=True, exist_ok=True)
        filename = _generate_filename(user_name, start_date, end_date)
        # pdf_path = out_dir / filename
        # pdf_path.write_bytes(pdf_bytes)
        
        # logger.info(f"PDF 저장 완료: {pdf_path}")

        # 이메일 전송
        email_subject = EMAIL_SUBJECT_TEMPLATE.format(user_name=user_name)
        email_body = EMAIL_BODY_TEMPLATE.format(
            user_name=user_name,
            start_date=start_date.strftime('%Y-%m-%d') if start_date else '시작일 미정',
            end_date=end_date.strftime('%Y-%m-%d') if end_date else '종료일 미정'
        )
        
        email_sent = send_email_with_pdf_attachment(
            to_email=user_email,
            subject=email_subject,
            body=email_body,
            pdf_bytes=pdf_bytes,
            filename=filename
        )

        if not email_sent:
            logger.warning(f"이메일 전송 실패: user_id={user_id}")
            return False, "이메일 전송 실패"

        return True, None

    except Exception as e:
        error_msg = f"사용자 처리 중 오류: {str(e)}"
        logger.error(f"user_id={user_id}, error={error_msg}", exc_info=True)
        return False, error_msg


def generate_reports_for_users(
    user_activity_map: Dict[int, List[int]],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[str, List[int]]:
    success_count = 0
    failed_users: List[int] = []
    
    if not user_activity_map:
        logger.warning("처리할 사용자가 없습니다")
        return "처리할 사용자가 없습니다", []

    try:
        with get_db_session() as db:
            # 사용자 데이터 로딩
            target_user_ids = set(user_activity_map.keys())
            user_dict = load_all_users()
            
            # 필요한 사용자만 필터링
            user_payloads = [
                user for user in user_dict.values() 
                if user.get("id") in target_user_ids
            ]
            
            if not user_payloads:
                logger.warning(f"유효한 사용자를 찾을 수 없습니다: {target_user_ids}")
                return "유효한 사용자를 찾을 수 없습니다", list(target_user_ids)

            logger.info(f"리포트 생성 시작: {len(user_payloads)}명 처리 예정")

            # 각 사용자별 처리
            for user in user_payloads:
                user_id = user.get("id")
                success, error_msg = _process_single_user(
                    user, user_activity_map, start_date, end_date, db
                )
                
                if success:
                    success_count += 1
                else:
                    failed_users.append(user_id)
                    logger.error(f"사용자 처리 실패: user_id={user_id}, reason={error_msg}")

        # 결과 메시지 생성
        result_message = f"월간 리포트 생성 완료: 성공 {success_count}명"
        if failed_users:
            failed_str = ", ".join(str(uid) for uid in failed_users)
            result_message += f", 실패 {len(failed_users)}명 (user_ids: {failed_str})"
            
        logger.info(result_message)
        return result_message, failed_users

    except Exception as e:
        logger.error(f"배치 처리 중 치명적 오류: {e}", exc_info=True)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)