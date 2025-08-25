from datetime import datetime
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.services.generator.insight_generator import (
    generate_insights, generate_recommendations
)
from app.chatbot.llm_feedback_chatbot import generate_feedback
from app.models.activity import UserReport
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from app.services.activity_service import get_activity_service, SessionLocal  # 주신 코드 기준
from app.services.pdf_service import create_report_pdf_bytes    
from app.services.send_service import send_email_with_pdf_attachment

# ----------------------------------------------------------------------
# 단일 사용자 리포트 생성 함수
# ----------------------------------------------------------------------
def generate_user_report(
    db: Session,
    user_id: int,
    activity_id_list: List[int],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> UserReport:
    """
    주어진 사용자/활동/기간으로 리포트를 생성합니다.
    ActivityService.calculate_user_stats 시그니처를 준수합니다.
    """
    try:
        activity_service = get_activity_service(db)

        # 통계
        stats = activity_service.calculate_user_stats(
            user_id=user_id,
            activity_id_list=activity_id_list,
            start_date=start_date,
            end_date=end_date,
        )

        # 인사이트 & 추천
        insights = generate_insights(stats)
        recommendations = generate_recommendations(stats)

        # LLM 피드백
        feedback_message = generate_feedback(stats, insights, recommendations)

        # 모델(UserReport)은 주어진 것을 그대로 사용
        report = UserReport(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            stats=stats,
            insights=insights,
            recommendations=recommendations,
            feedback_message=feedback_message,
        )
        return report

    except AppException:
        # 내부 정의된 예외는 그대로 전파
        raise
    except Exception as e:
        print("[리포트 생성 오류]", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)
    

# ----------------------------------------------------------------------
# 배치 리포트 생성 (스프링 서버 입력 포맷 반영)
# ----------------------------------------------------------------------
def generate_reports_for_users(
    user_payloads: List[Dict],
    # 각 사용자별 활동목록 매핑: {user_id: [activity_id, ...]}
    user_activity_map: Dict[int, List[int]],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> Tuple[str, List[int]]:
    """
    스프링 서버가 제공하는 사용자 리스트와 (user_id -> activity_id_list) 매핑을 이용해 배치 리포트를 생성합니다.

    Parameters
    ----------
    user_payloads : List[Dict]
        예: [{"id": 1, "name": "...", ...}, {"id": 2, ...}]
        알림 발송 등 부가정보를 포함한 사용자 페이로드(스프링에서 전달받은 원소)
    user_activity_map : Dict[int, List[int]]
        예: {1: [101,102], 2: [201,202,203]}
    period : ReportPeriod
        리포트 주기 (기본 월간)
    start_date, end_date : Optional[datetime]
        통계 산출 기간
    Returns
    -------
    result_message : str
        처리 요약 메시지
    failed_users : List[int]
        실패한 사용자 id 목록
    """
    db: Optional[Session] = None
    success_count = 0
    failed_users: List[int] = []

    try:
        db = SessionLocal()

        for user in user_payloads:
            user_id = user.get("id") #여기서 db를 접근하면 좋겠는데
            if not user_id:
                continue

            try:
                activity_id_list = user_activity_map.get(user_id, [])
                # 활동 아이디가 없다면 통계는 0으로 나올 수 있으나, 리포트는 생성 가능
                report = generate_user_report(
                    db=db,
                    user_id=user_id,
                    activity_id_list=activity_id_list,
                    start_date=start_date,
                    end_date=end_date,
                )

                print(f"[리포트 생성 완료] user_id={user_id}, activities={len(activity_id_list)}")

                pdf_bytes = create_report_pdf_bytes(report)
                
                out_dir = Path("reports")
                out_dir.mkdir(parents=True, exist_ok=True)
                filename = f"report_user_{user_id}_{start_date:%Y%m%d}-{end_date:%Y%m%d}.pdf"
                (out_dir / filename).write_bytes(pdf_bytes)

                print(f"[PDF 저장] {out_dir/filename}")

                # 알림 전송
                email_sent = send_email_with_pdf_attachment(
                    to_email="pyeonk@konkuk.ac.kr",
                    subject="[리포트] 활동 리포트가 도착했습니다",
                    body=f"{user['name']}님,\n\n{start_date:%Y-%m-%d}부터 {end_date:%Y-%m-%d}까지의 활동 리포트를 첨부합니다.",
                    pdf_bytes=pdf_bytes,
                    filename=filename
                )

                if not email_sent:
                    failed_users.append(user_id)

                # 성공 카운트는 한 번만 증가
                success_count += 1

            except Exception as e:
                failed_users.append(user_id)
                print(f"[오류] user_id={user_id} - {e}")

        # 결과 메시지
        result_message = f"월간 리포트 생성 완료: 성공 {success_count}명"
        if failed_users:
            failed_str = ", ".join(str(uid) for uid in failed_users)
            result_message += f", 실패 {len(failed_users)}명 ({failed_str})"

        return result_message, failed_users

    except Exception as e:
        print("[배치 처리 오류]", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)
    finally:
        if db:
            db.close()