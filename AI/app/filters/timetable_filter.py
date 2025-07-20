import json
from datetime import datetime

# 사용자 로딩
USER_PATH = "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/users.json"
user_id = "1"  # 예시: 조은영

with open(USER_PATH, encoding="utf-8") as f:
    users = json.load(f)

user = users[user_id]

# 시간 겹침 체크
def is_time_overlap(start1, end1, start2, end2):
    fmt = "%H:%M"
    s1 = datetime.strptime(start1, fmt)
    e1 = datetime.strptime(end1, fmt)
    s2 = datetime.strptime(start2, fmt)
    e2 = datetime.strptime(end2, fmt)
    return max(s1, s2) < min(e1, e2)

# 진행기간 텍스트 파싱
def parse_schedule_from_text(text):
    for line in text.split('\n'):
        if line.startswith("진행기간:"):
            try:
                raw = line.replace("진행기간:", "").strip()
                start_raw, end_raw = raw.split("~")
                start_day, start_time = start_raw.strip().split()
                end_day, end_time = end_raw.strip().split()
                day_of_week = datetime.strptime(start_day, "%Y.%m.%d").strftime("%a")
                kor_day = {"Mon":"월", "Tue":"화", "Wed":"수", "Thu":"목", "Fri":"금", "Sat":"토", "Sun":"일"}
                return {
                    "day": kor_day[day_of_week],
                    "startTime": start_time,
                    "endTime": end_time
                }
            except:
                return None
    return None

# 활동 제목 파싱
def parse_title(text):
    for line in text.split('\n'):
        if line.startswith("제목:"):
            return line.replace("제목:", "").strip()
    return "이름 없음"

# 비교과 JSON 리스트
activity_json_paths = [
    "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/my_csv_folder/se_wein_일반비교과_정보(신청가능).json",
    "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/my_csv_folder/se_wein_취창업비교과_정보(신청가능).json"
]

# 통합 추천 결과
recommended = []

# 2개 파일 순회
for path in activity_json_paths:
    with open(path, encoding="utf-8") as f:
        activity_data = json.load(f)

    for item in activity_data:
        text = item.get("text", "")
        title = parse_title(text)
        schedule = parse_schedule_from_text(text)

        if not schedule:
            continue  # 날짜/시간 정보 없는 활동은 건너뜀

        # 사용자 시간표와 비교
        conflict = False
        for slot in user["timetable"]:
            if slot["day"] == schedule["day"]:
                if is_time_overlap(slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]):
                    conflict = True
                    break

        if not conflict:
            recommended.append(title)

# 결과 출력
print("추천 가능한 비교과 활동:")
for r in recommended:
    print("-", r)