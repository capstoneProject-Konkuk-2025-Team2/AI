from pydantic import BaseModel
from typing import List, Optional

class TimeSlot(BaseModel):
    day: Optional[str] = None # 요일
    startTime: Optional[str] = None # 시작시간
    endTime: Optional[str] = None # 종료시간

class UserProfile(BaseModel):
    name: Optional[str] = None # 이름
    major: Optional[str] = None # 학과
    year: Optional[str] = None # 학년
    interestes: Optional[List[str]] = None # 관심사
    timetable: Optional[List[TimeSlot]] = None #시간표

class ChatRequest(BaseModel):
    id: str
    question: str