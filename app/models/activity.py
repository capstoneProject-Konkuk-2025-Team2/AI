from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from enum import Enum

class ActivityCategory(str, Enum):
    CAREER = "진로"
    ETC = "기타"

class Activity(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    category: ActivityCategory
    start_date: datetime
    end_date: datetime
    duration_hours: float
    keywords: List[str]
    location: Optional[str] = None
    participants_count: Optional[int] = None
    created_at: datetime = datetime.now()