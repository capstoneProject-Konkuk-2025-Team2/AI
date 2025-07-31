
import json
import os
from datetime import datetime
from typing import List, Optional, Dict
from collections import defaultdict, Counter
from app.models.activity import Activity, ActivityStats
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(os.getenv("DATA_DIR")).resolve()
ACTIVITIES_FILE = BASE_DIR / os.getenv("ACTIVITY_FILENAME")

def save_activity(activity: Activity) -> int:
    try:
        check_data_dir()
        activities = load_all_activities()

        activity_data = activity.model_dump()

        for field in ["start_date", "end_date", "created_at"]:
            if isinstance(activity_data.get(field), datetime):
                activity_data[field] = activity_data[field].isoformat()

        activities.append(activity_data)

        with open(ACTIVITIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(activities, f, ensure_ascii=False, indent=2)

        return activity_data["id"]
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.ACTIVITY_SAVE_FAILED)
    

def check_data_dir():
    try:
        BASE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise AppException(ErrorCode.DIRECTORY_CREATE_ERROR)
    
def load_all_activities() -> List[dict]:
    try:
        if not ACTIVITIES_FILE.exists():
            return []

        if os.path.getsize(ACTIVITIES_FILE) == 0:
            return []

        with open(ACTIVITIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.ACTIVITY_LOAD_FAILED)
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.FILE_READ_ERROR)

def calculate_user_stats(user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> ActivityStats:
    try:
        activities = get_user_activities(user_id, start_date, end_date)
        
        if not activities:
            return ActivityStats(
                user_id=user_id,
                total_activities=0,
                total_hours=0.0,
                category_distribution={},
                most_active_category="",
                diversity_score=0.0,
                monthly_trend=[],
                time_pattern={}
            )
        
        total_activities = len(activities)
        total_hours = sum(activity.duration for activity in activities)
        
        category_counts = Counter(activity.category.value for activity in activities)
        category_distribution = dict(category_counts)
        most_active_category = category_counts.most_common(1)[0][0] if category_counts else ""
        
        unique_categories = len(category_counts)
        total_categories = 2  # career, etc 두개밖에 없음
        diversity_score = min(unique_categories / total_categories, 1.0) if total_categories > 0 else 0.0
        
        monthly_trend = calculate_monthly_trend(activities)
        
        time_pattern = calculate_time_pattern(activities)
        
        return ActivityStats(
            user_id=user_id,
            total_activities=total_activities,
            total_hours=total_hours,
            category_distribution=category_distribution,
            most_active_category=most_active_category,
            diversity_score=diversity_score,
            monthly_trend=monthly_trend,
            time_pattern=time_pattern
        )
        
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.DATA_ACCESS_ERROR)
    
def get_user_activities(user_id: str, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Activity]:
    try:
        all_activities = load_all_activities()
        user_activities = []
        
        for activity_data in all_activities:
            if activity_data.get('user_id') == user_id:
                if start_date or end_date:
                    activity_date = datetime.fromisoformat(activity_data['date'].replace('Z', '+00:00'))
                    if start_date and activity_date < start_date:
                        continue
                    if end_date and activity_date > end_date:
                        continue
                # 객체 변환하기
                activity_data_copy = activity_data.copy()
                activity_data_copy['date'] = datetime.fromisoformat(activity_data['date'].replace('Z', '+00:00'))
                user_activities.append(Activity(**activity_data_copy))
        
        return user_activities
        
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.ACTIVITY_LOAD_FAILED)
    
def calculate_monthly_trend(activities: List[Activity]) -> List[Dict]:
    monthly_data = defaultdict(lambda: {"activities": 0, "hours": 0.0})
    
    for activity in activities:
        month_key = activity.date.strftime('%Y-%m')
        monthly_data[month_key]["activities"] += 1
        monthly_data[month_key]["hours"] += activity.duration
    
    return [
        {"month": month, **data}
        for month, data in sorted(monthly_data.items())
    ]

def calculate_time_pattern(activities: List[Activity]) -> Dict:
    hours = [activity.date.hour for activity in activities]
    weekdays = [activity.date.weekday() for activity in activities]
    
    most_active_hour = Counter(hours).most_common(1)[0][0] if hours else 0
    most_active_weekday = Counter(weekdays).most_common(1)[0][0] if weekdays else 0
    
    return {
        "most_active_hour": most_active_hour,
        "most_active_weekday": most_active_weekday
    } 