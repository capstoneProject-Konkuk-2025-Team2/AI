from pydantic import BaseModel
from typing import List

class UserActivityRequest(BaseModel):
    userId: int
    activities: List[int]

class ReportRequest(BaseModel):
    users: List[UserActivityRequest]
    start_date: str
    end_date: str