
import json
import os
import uuid
from datetime import datetime, timedelta
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
