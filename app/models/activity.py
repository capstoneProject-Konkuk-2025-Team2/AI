from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class Activity(BaseModel):
    id: str
    user_id: int
    title: str
    description: str
    start_date: datetime
    end_date: datetime
    keywords: List[str]
    location: Optional[str] = None

class ActivityStats(BaseModel):
    user_id: int
    total_activities: int
    total_hours: float
    monthly_trend: List[dict]
    time_pattern: dict

class UserReport(BaseModel):
    user_id: int
    start_date: datetime
    end_date: datetime
    stats: ActivityStats
    insights: List[str]
    recommendations: List[str]
    feedback_message: str
    created_at: datetime = datetime.now() 