# app/services/generator/insight_generator.py

from typing import List, Any, Mapping
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from app.utils.format.insights_format import (
    INSIGHTS_CONFIG, RECOMMENDATIONS_CONFIG, THRESHOLDS
)

def _get(obj: Any, key: str, default=None):
    # 객체의 속성 또는 dict 키를 동일하게 읽기
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return default

def generate_insights(stats: Any) -> List[str]:
    try:
        insights: List[str] = []

        total_activities = _get(stats, "total_activities", 0)
        if total_activities == 0:
            insights.append(INSIGHTS_CONFIG["no_activity"])
            return insights

        activity_insight = get_activity_count_insight(total_activities)
        if activity_insight:
            insights.append(activity_insight)

        total_hours = _get(stats, "total_hours", 0.0)
        time_insight = get_time_investment_insight(total_hours)
        if time_insight:
            insights.append(time_insight)

        return insights
    except Exception as e:
        print("오류 발생:", e)
        # ↓ ErrorCode 수정은 2)에서 설명
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)

def generate_recommendations(stats: Any) -> List[str]:
    try:
        recommendations: List[str] = []

        total_activities = _get(stats, "total_activities", 0)
        if total_activities == 0:
            return RECOMMENDATIONS_CONFIG["no_activity"]

        if total_activities < THRESHOLDS["activity_count"]["medium"]:
            recommendations.append(RECOMMENDATIONS_CONFIG["low_activity"])

        if is_evening_active(stats):
            recommendations.append(RECOMMENDATIONS_CONFIG["time_pattern"])

        if not recommendations:
            recommendations.append(RECOMMENDATIONS_CONFIG["default"])

        return recommendations
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)
    

def get_activity_count_insight(total_activities: int) -> str:
    if total_activities >= THRESHOLDS["activity_count"]["high"]:
        return INSIGHTS_CONFIG["activity_count"]["high"]
    elif total_activities >= THRESHOLDS["activity_count"]["medium"]:
        return INSIGHTS_CONFIG["activity_count"]["medium"]
    elif total_activities >= 1:
        return INSIGHTS_CONFIG["activity_count"]["low"]
    return ""

def get_time_investment_insight(total_hours: float) -> str:
    if total_hours >= THRESHOLDS["time_investment"]["high"]:
        return INSIGHTS_CONFIG["time_investment"]["high"]
    elif total_hours >= THRESHOLDS["time_investment"]["medium"]:
        return INSIGHTS_CONFIG["time_investment"]["medium"]
    return ""

def is_evening_active(stats: Any) -> bool:
    time_pattern = _get(stats, "time_pattern", {}) or {}
    most_active_hour = time_pattern.get("most_active_hour", 9)
    return most_active_hour > THRESHOLDS["evening_hour"]
