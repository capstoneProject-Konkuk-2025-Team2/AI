from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class Category(str, Enum):
    CAREER = "career"
    ETC = "etc"

class ReportPeriod(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class Activity(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    category: Category
    start_date: datetime
    end_date: datetime
    duration_hours: float
    keywords: List[str]
    location: Optional[str] = None
    participants_count: Optional[int] = None
    created_at: datetime = datetime.now()

class ActivityStats(BaseModel):
    user_id: str
    total_activities: int
    total_hours: float
    category_distribution: dict
    most_active_category: str
    diversity_score: float 
    monthly_trend: List[dict]
    time_pattern: dict

class UserReport(BaseModel):
    user_id: str
    period: ReportPeriod
    start_date: datetime
    end_date: datetime
    stats: ActivityStats
    insights: List[str]
    recommendations: List[str]
    feedback_message: str
    created_at: datetime = datetime.now() 