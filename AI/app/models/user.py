from pydantic import BaseModel
from typing import List, Optional

class TimeSlot(BaseModel):
    day: Optional[str] = None # 요일
    startTime: Optional[str] = None # 시작시간
    endTime: Optional[str] = None # 종료시간

class UserProfile(BaseModel):
    id: int
    name: Optional[str] = None # 이름
    major: Optional[str] = None # 학과
    grade: Optional[str] = None # 학년
    interests: Optional[List[str]] = None # 관심사
    timetable: Optional[List[TimeSlot]] = None #시간표

class ChatRequest(BaseModel):
    id: int # 사용자 아이디
    question: str # 검색