import json
import re
import os
from datetime import datetime
from llmware.models import ModelCatalog


def load_user_profile(user_id, path="app/data/users.json"):
    """사용자 ID에 해당하는 사용자 정보를 JSON 파일에서 불러옵니다."""
    with open(path, "r", encoding="utf-8") as f:
        users = json.load(f)
    
    # ID를 문자열로 변환하여 검색
    user_id = str(user_id)
    return users.get(user_id)

def get_weekday_korean(date_str):
    """2025.05.29 → '목'"""
    dt = datetime.strptime(date_str, "%Y.%m.%d")
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    return weekdays[dt.weekday()]

def extract_schedule_from_text(text):
    """
    '진행기간: 2025.05.29 15:00~2025.05.29 17:00' → '목 15:00~17:00'
    """
    pattern = r"진행기간:\s*(\d{4}\.\d{2}\.\d{2})\s*(\d{2}:\d{2})~\d{4}\.\d{2}\.\d{2}\s*(\d{2}:\d{2})"
    match = re.search(pattern, text)
    if match:
        date_str = match.group(1)
        start_time = match.group(2)
        end_time = match.group(3)
        weekday = get_weekday_korean(date_str)
        return f"{weekday} {start_time}~{end_time}"
    return None

def is_time_conflict(schedule1, schedule2):
    """
    두 스케줄 문자열이 요일과 시간에서 겹치는지 판단
    예: "수 13:00~15:00", "수 14:00~16:00" → True (겹침)
    """
    def parse(schedule):
        try:
            day, time_range = schedule.split()
            start_str, end_str = time_range.split("~")
            start = datetime.strptime(start_str, "%H:%M").time()
            end = datetime.strptime(end_str, "%H:%M").time()
            return day, start, end
        except:
            return None, None, None

    day1, start1, end1 = parse(schedule1)
    day2, start2, end2 = parse(schedule2)

    if day1 != day2:
        return False  # 요일 다르면 무조건 안 겹침

    # 시간이 겹치는 경우: A 시작 < B 끝 and B 시작 < A 끝
    return start1 < end2 and start2 < end1

def load_filtered_programs_from_folder(user_profile, folder_path="app/data/my_csv_folder"):
    """폴더 내 모든 JSON 비교과 파일을 읽고, 사용자 시간표와 겹치지 않는 프로그램만 필터링"""
    all_programs = []

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                programs = json.load(f)

            for item in programs:
                text = item["text"]
                program_schedule = extract_schedule_from_text(text)

                if not program_schedule:
                    all_programs.append(item)
                    continue

                conflict = False
                # 시간표 형식 변경에 따른 수정
                for time_slot in user_profile["timetable"]:
                    user_time = f"{time_slot['day']} {time_slot['startTime']}~{time_slot['endTime']}"
                    if is_time_conflict(user_time, program_schedule):
                        conflict = True
                        break

                if not conflict:
                    all_programs.append(item)

    return all_programs

def filter_by_interest(programs, interests):
    """
    관심사 리스트(예: ["AI", "데이터"])가 텍스트에 포함된 프로그램만 필터링
    """
    filtered = []
    for item in programs:
        text = item["text"]
        if any(interest.lower() in text.lower() for interest in interests):
            filtered.append(item)
    return filtered

def generate_llm_prompt(user, question, programs):
    """
    사용자 정보, 질문, 필터링된 프로그램들을 바탕으로 LLM에게 전달할 프롬프트를 생성.
    """
    # 1. 사용자 정보 요약
    profile_summary = f"{user['name']}님은 {user['grade']} {user['major']} 소속이며, 관심사는 {', '.join(user['interests'])}입니다."
    timetable_summary = "시간표는 다음과 같습니다:\n" + "\n".join([f"{t['day']} {t['startTime']}~{t['endTime']}" for t in user["timetable"]])

    # 2. 프로그램 리스트 요약 (최대 5개)
    program_summaries = []
    for i, prog in enumerate(programs[:5], 1):
        lines = prog["text"].split("\n")
        title = next((line for line in lines if line.startswith("제목:")), "제목 정보 없음")
        summary = f"{i}. {title.strip()}"
        program_summaries.append(summary)
    programs_block = "\n".join(program_summaries)

    # 3. 최종 프롬프트 구성
    prompt = f"""
당신은 건국대학교의 비교과 추천 챗봇입니다.
아래는 사용자 정보와 질문입니다:

[사용자 정보]
{profile_summary}
{timetable_summary}

[사용자 질문]
"{question}"

[후보 비교과 프로그램]
{programs_block}

위의 정보들을 바탕으로, 사용자의 시간표와 관심사, 질문을 고려하여
추천할 만한 비교과 2개를 골라 이유와 함께 설명해주세요.
"""
    return prompt.strip()

# # 사용자 로그인
# name = input("당신의 이름을 입력하세요: ")
# user = load_user_profile(name)

# if not user:
#     print(f"{name}이라는 이름을 가진 사용자를 찾을 수 없습니다.")
#     exit()

# print(f"{name}님, 챗봇을 시작합니다. 종료하려면 'exit'을 입력하세요.\n")

# while True:
#     question = input("질문: ")
#     if question.lower() in ["exit", "quit", "종료"]:
#         print("챗봇을 종료합니다.")
#         break

#     # Step 1: 시간 겹침 필터링
#     step1_programs = load_filtered_programs_from_folder(user, folder_path="app/data/my_csv_folder")

#     # Step 2: 관심사 기반 필터링
#     step2_programs = filter_by_interest(step1_programs, user["interests"])

#     if not step2_programs:
#         print("추천할 비교과 프로그램이 없습니다.\n")
#         continue

#     # 여기서 프롬프트 생성 + LLM 호출
#     final_prompt = generate_llm_prompt(user, question, step2_programs)
#     model = ModelCatalog().load_model("bling-answer-tool")
#     response = model.inference(final_prompt)

#     # 결과 출력
#     print("\n LLM 추천 결과:\n", response["llm_response"], "\n")

#     # 출력
#     print(f"\n총 추천된 프로그램 수: {len(step2_programs)}")
#     for idx, prog in enumerate(step2_programs[:3], start=1):
#         print(f"\n 추천 {idx}:\n{prog['text'][:300]}\n---")

#     print()

