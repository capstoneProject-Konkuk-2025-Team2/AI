import json
import re
import os
from datetime import datetime
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")  # 환경변수에서 API 키 가져오기!! -> 졸프 2 예정

def load_user_profile(name, path="users.json"):
    with open(path, "r", encoding="utf-8") as f:
        users = json.load(f)
    for user in users:
        if user["이름"] == name:
            return user
    return None

def get_weekday_korean(date_str):
    dt = datetime.strptime(date_str, "%Y.%m.%d")
    weekdays = ['월', '화', '수', '목', '금', '토', '일']
    return weekdays[dt.weekday()]

def extract_schedule_from_text(text):
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
        return False
    return start1 < end2 and start2 < end1

def load_filtered_programs_from_folder(user_profile, folder_path="my_csv_folder"):
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
                for user_time in user_profile["시간표"]:
                    if is_time_conflict(user_time, program_schedule):
                        conflict = True
                        break
                if not conflict:
                    all_programs.append(item)
    return all_programs

def filter_by_interest(programs, interests):
    filtered = []
    for item in programs:
        text = item["text"]
        if any(interest.lower() in text.lower() for interest in interests):
            filtered.append(item)
    return filtered

def generate_llm_prompt(user, question, programs):
    profile_summary = f"{user['이름']}님은 {user['학년']} {user['학과']} 소속이며, 관심사는 {', '.join(user['관심사'])}입니다."
    timetable_summary = "시간표는 다음과 같습니다:\n" + "\n".join(user["시간표"])
    program_summaries = []
    for i, prog in enumerate(programs[:5], 1):
        lines = prog["text"].split("\n")
        title = next((line for line in lines if line.startswith("제목:")), "제목 정보 없음")
        summary = f"{i}. {title.strip()}"
        program_summaries.append(summary)
    programs_block = "\n".join(program_summaries)
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

# 사용자 로그인
name = input("당신의 이름을 입력하세요: ")
user = load_user_profile(name)
if not user:
    print(f"{name}이라는 이름을 가진 사용자를 찾을 수 없습니다.")
    exit()

print(f"{name}님, 챗봇을 시작합니다. 종료하려면 'exit'을 입력하세요.\n")

while True:
    question = input("질문: ")
    if question.lower() in ["exit", "quit", "종료"]:
        print("챗봇을 종료합니다.")
        break

    step1_programs = load_filtered_programs_from_folder(user, folder_path="my_csv_folder")
    step2_programs = filter_by_interest(step1_programs, user["관심사"])

    if not step2_programs:
        print("추천할 비교과 프로그램이 없습니다.\n")
        continue

    final_prompt = generate_llm_prompt(user, question, step2_programs)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 건국대학교의 친절한 비교과 추천 챗봇입니다."},
            {"role": "user", "content": final_prompt}
        ]
    )

    print("\n LLM 추천 결과:\n", response["choices"][0]["message"]["content"], "\n")

    print(f"총 추천된 프로그램 수: {len(step2_programs)}")
    for idx, prog in enumerate(step2_programs[:3], start=1):
        print(f"\n 추천 {idx}:\n{prog['text'][:300]}\n---")
    print()
