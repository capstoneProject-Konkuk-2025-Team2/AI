from typing import List
from app.models.activity import ActivityStats
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from app.utils.format.insights_format import (
    INSIGHTS_CONFIG, RECOMMENDATIONS_CONFIG, THRESHOLDS
)
from app.models.activity import CATEGORY_NAMES

def generate_insights(stats: ActivityStats) -> List[str]:
    try:
        insights = []
        
        if stats.total_activities == 0:
            insights.append(INSIGHTS_CONFIG["no_activity"])
            return insights
        
        if stats.most_active_category:
            category_name = CATEGORY_NAMES.get(stats.most_active_category, stats.most_active_category)
            insights.append(INSIGHTS_CONFIG["category_activity"].format(category_name=category_name))
        
        diversity_insight = get_diversity_insight(stats.diversity_score)
        if diversity_insight:
            insights.append(diversity_insight)
        
        activity_insight = get_activity_count_insight(stats.total_activities)
        if activity_insight:
            insights.append(activity_insight)
        
        time_insight = get_time_investment_insight(stats.total_hours)
        if time_insight:
            insights.append(time_insight)
        
        return insights
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)

def generate_recommendations(stats: ActivityStats) -> List[str]:
    try:
        recommendations = []
        
        if stats.total_activities == 0:
            return RECOMMENDATIONS_CONFIG["no_activity"]
        
        missing_recommendation = get_missing_category_recommendation(stats)
        if missing_recommendation:
            recommendations.append(missing_recommendation)
        
        if stats.total_activities < THRESHOLDS["activity_count"]["medium"]:
            recommendations.append(RECOMMENDATIONS_CONFIG["low_activity"])
        
        if is_evening_active(stats):
            recommendations.append(RECOMMENDATIONS_CONFIG["time_pattern"])
        
        if not recommendations:
            recommendations.append(RECOMMENDATIONS_CONFIG["default"])
        
        return recommendations
    except Exception as e:
        print("오류 발생:", e)
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)
    


def get_diversity_insight(diversity_score: float) -> str:
    if diversity_score == 1.0:
        return INSIGHTS_CONFIG["diversity"][1.0]
    elif diversity_score >= 0.5:
        return INSIGHTS_CONFIG["diversity"][0.5]
    else:
        return INSIGHTS_CONFIG["diversity"][0.0]

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

def get_missing_category_recommendation(stats: ActivityStats) -> str:
    if stats.diversity_score < 1.0:
        if "career" not in stats.category_distribution:
            return RECOMMENDATIONS_CONFIG["missing_category"]["career"]
        elif "etc" not in stats.category_distribution:
            return RECOMMENDATIONS_CONFIG["missing_category"]["etc"]
    return ""

def is_evening_active(stats: ActivityStats) -> bool:
    most_active_hour = stats.time_pattern.get("most_active_hour", 9)
    return most_active_hour > THRESHOLDS["evening_hour"] 