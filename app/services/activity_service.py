import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker
from app.utils.db import engine
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException

# Automap 설정
Base = automap_base()
Base.prepare(autoload_with=engine)
Extracurricular = Base.classes.extracurricular
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class ActivityService:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_user_stats(self, user_id: int, activity_id_list: List[int], 
                           start_date: Optional[datetime] = None, 
                           end_date: Optional[datetime] = None) -> Dict:
        """사용자의 비교과 활동 통계 계산"""
        try:
            activities = self.get_user_activities(activity_id_list, start_date, end_date)
            
            if not activities:
                return {
                    "user_id": user_id,
                    "total_activities": 0,
                    "total_hours": 0.0,
                    "monthly_trend": [],
                    "time_pattern": {}
                }
            
            total_activities = len(activities)
            total_hours = sum(self._calculate_duration_hours(activity) for activity in activities)
            monthly_trend = self._calculate_monthly_trend(activities)
            time_pattern = self._calculate_time_pattern(activities)
            
            return {
                "user_id": user_id,
                "total_activities": total_activities,
                "total_hours": round(total_hours, 2),
                "monthly_trend": monthly_trend,
                "time_pattern": time_pattern
            }
            
        except Exception as e:
            print(f"통계 계산 오류: {e}")
            raise AppException(ErrorCode.DATA_ACCESS_ERROR)
    
    def get_user_activities(self, activity_id_list: List[int],
                          start_date: Optional[datetime] = None, 
                          end_date: Optional[datetime] = None) -> List:
        """사용자의 비교과 활동 목록 조회"""
        try:
            # 기본 쿼리: activity_id_list에 있는 활동들만 조회
            query = self.db.query(Extracurricular).filter(
                Extracurricular.extracurricular_id.in_(activity_id_list),
                Extracurricular.is_deleted == 0  # 삭제되지 않은 활동만
            )
            
            # 날짜 필터링 (활동 시작일 기준)
            if start_date:
                query = query.filter(Extracurricular.activity_start >= start_date)
            if end_date:
                query = query.filter(Extracurricular.activity_start <= end_date)
            
            activities = query.all()
            
            return activities
            
        except Exception as e:
            print(f"활동 조회 오류: {e}")
            raise AppException(ErrorCode.ACTIVITY_LOAD_FAILED)
    
    def _calculate_duration_hours(self, activity) -> float:
        """활동 지속 시간을 시간 단위로 계산"""
        if not activity.activity_start or not activity.activity_end:
            return 0.0
        
        try:
            duration = activity.activity_end - activity.activity_start
            return duration.total_seconds() / 3600.0  # 시간으로 변환
        except Exception:
            return 0.0
    
    def _calculate_monthly_trend(self, activities: List) -> List[Dict]:
        """월별 활동 트렌드 계산"""
        monthly_data = defaultdict(lambda: {"activities": 0, "hours": 0.0})
        
        for activity in activities:
            if activity.activity_start:
                month_key = activity.activity_start.strftime('%Y-%m')
                monthly_data[month_key]["activities"] += 1
                monthly_data[month_key]["hours"] += self._calculate_duration_hours(activity)
        
        return [
            {
                "month": month, 
                "activities": data["activities"],
                "hours": round(data["hours"], 2)
            }
            for month, data in sorted(monthly_data.items())
        ]
    
    def _calculate_time_pattern(self, activities: List) -> Dict:
        """활동 시간 패턴 분석"""
        hours = []
        weekdays = []
        
        for activity in activities:
            if activity.activity_start:
                hours.append(activity.activity_start.hour)
                weekdays.append(activity.activity_start.weekday())
        
        most_active_hour = Counter(hours).most_common(1)[0][0] if hours else 0
        most_active_weekday = Counter(weekdays).most_common(1)[0][0] if weekdays else 0
        
        # 요일 이름 매핑
        weekday_names = ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']
        
        return {
            "most_active_hour": most_active_hour,
            "most_active_weekday": most_active_weekday,
            "most_active_weekday_name": weekday_names[most_active_weekday] if weekdays else "없음"
        }

# 서비스 팩토리 함수
def get_activity_service(db: Session) -> ActivityService:
    """ActivityService 인스턴스 생성"""
    return ActivityService(db)