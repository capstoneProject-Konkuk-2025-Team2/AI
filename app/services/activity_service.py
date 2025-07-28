import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict, Counter
from app.models.activity import Activity, ActivityStats, ActivityCategory
import uuid

class ActivityService:
    def __init__(self):
        self.data_dir = "app/data"
        self.activities_file = os.path.join(self.data_dir, "activities.json")
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """데이터 디렉토리 생성"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        if not os.path.exists(self.activities_file):
            with open(self.activities_file, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False)
    
    def save_activity(self, activity: Activity) -> str:
        """활동 저장"""
        activities = self.load_all_activities()
        activity.id = str(uuid.uuid4())
        activities.append(activity.model_dump())
        
        with open(self.activities_file, 'w', encoding='utf-8') as f:
            json.dump(activities, f, ensure_ascii=False, indent=2, default=str)
        
        return activity.id