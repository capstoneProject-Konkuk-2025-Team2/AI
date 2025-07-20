import json
import re
import os
from datetime import datetime
from llmware.models import ModelCatalog


def load_user_profile(user_id, path="app/data/users.json"):
    """사용자 ID에 해당하는 사용자 정보를 JSON 파일에서 불러옵니다."""
    # 스크립트의 절대 경로를 기준으로 파일 경로를 설정합니다.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    user_file_path = os.path.join(base_dir, "..", "data", "users.json")

    try:
        with open(user_file_path, "r", encoding="utf-8") as f:
            users = json.load(f)
        # ID를 문자열로 변환하여 검색
        user_id = str(user_id)
        return users.get(user_id)
    except FileNotFoundError:
        print(f"오류: 사용자 정보 파일이 없습니다: {user_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"오류: 사용자 정보 파일 형식이 잘못되었습니다: {user_file_path}")
        return None

def get_weekday_korean(date_str):
    """2025.05.29 → '목'"""
    try:
        dt = datetime.strptime(date_str, "%Y.%m.%d")
        weekdays = ['월', '화', '수', '목', '금', '토', '일']
        return weekdays[dt.weekday()]
    except ValueError:
        return None

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
        if weekday:
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
            # datetime.time 객체로 변환하여 비교
            start = datetime.strptime(start_str, "%H:%M").time()
            end = datetime.strptime(end_str, "%H:%M").time()
            return day, start, end
        except Exception as e:
            # print(f"스케줄 파싱 오류: {schedule}, 오류: {e}")
            return None, None, None

    day1, start1, end1 = parse(schedule1)
    day2, start2, end2 = parse(schedule2)

    if not all([day1, start1, end1, day2, start2, end2]):
        # 파싱 실패 시 겹치지 않는 것으로 간주 (안전하게)
        return False

    if day1 != day2:
        return False  # 요일 다르면 무조건 안 겹침

    # 시간이 겹치는 경우: A 시작 < B 끝 and B 시작 < A 끝
    # 종료 시간이 시작 시간보다 이르거나 같으면 겹치지 않는 것으로 판단
    if start1 >= end1 or start2 >= end2:
         return False # 올바른 시간 범위가 아님

    return start1 < end2 and start2 < end1

def load_filtered_programs_from_folder(user_profile, folder_path="app/data/my_csv_folder"):
    """폴더 내 모든 JSON 비교과 파일을 읽고, 사용자 시간표와 겹치지 않는 프로그램만 필터링"""
    # 스크립트의 절대 경로를 기준으로 폴더 경로를 설정합니다.
    base_dir = os.path.dirname(os.path.abspath(__file__))
    abs_folder_path = os.path.join(base_dir, "..", "data", "my_csv_folder")

    all_programs = []
    filtered_programs = []
    programs_with_schedule = []
    programs_without_schedule = []

    if not os.path.exists(abs_folder_path):
        print(f"오류: 비교과 프로그램 폴더가 없습니다: {abs_folder_path}")
        return []

    for filename in os.listdir(abs_folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(abs_folder_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    programs = json.load(f)
                    if not isinstance(programs, list):
                         print(f"경고: 파일 형식이 리스트가 아닙니다: {file_path}")
                         continue
                    all_programs.extend(programs)
            except json.JSONDecodeError:
                print(f"오류: JSON 파일 파싱 실패: {file_path}")
            except Exception as e:
                print(f"파일 읽기 오류: {file_path}, 오류: {e}")


    for item in all_programs:
        if "text" not in item:
            # print(f"경고: 'text' 필드가 없는 프로그램 항목이 있습니다: {item}")
            programs_without_schedule.append(item)
            continue

        program_schedule = extract_schedule_from_text(item["text"])

        if not program_schedule:
            # 일정이 없는 프로그램은 시간표 필터링 대상이 아님
            programs_without_schedule.append(item)
            continue

        # 일정이 있는 프로그램만 시간 겹침 확인 대상
        programs_with_schedule.append(item)

        conflict = False
        if "timetable" in user_profile and isinstance(user_profile["timetable"], list):
            for time_slot in user_profile["timetable"]:
                if isinstance(time_slot, dict) and "day" in time_slot and "startTime" in time_slot and "endTime" in time_slot:
                    user_time = f"{time_slot['day']} {time_slot['startTime']}~{time_slot['endTime']}"
                    if is_time_conflict(user_time, program_schedule):
                        conflict = True
                        break
                # else:
                     # print(f"경고: 잘못된 시간표 항목 형식: {time_slot}")

        if not conflict:
            filtered_programs.append(item)

    # 일정이 없는 프로그램은 필터링된 목록에 합칩니다.
    return filtered_programs + programs_without_schedule

def filter_by_interest(programs, interests):
    """
    관심사 리스트(예: ["AI", "데이터"])가 텍스트에 포함된 프로그램만 필터링
    """
    if not interests:
        return programs # 관심사가 없으면 필터링하지 않음

    filtered = []
    for item in programs:
        if "text" in item:
            text = item["text"]
            if any(interest.lower() in text.lower() for interest in interests):
                filtered.append(item)
    return filtered

def generate_llm_prompt(user, question, programs):
    """
    사용자 정보, 질문, 필터링된 프로그램들을 바탕으로 LLM에게 전달할 프롬프트를 생성.
    """
    # 1. 사용자 정보 요약
    name = user.get('name', '사용자')
    year = user.get('year', '정보 없음')
    major = user.get('major', '정보 없음')
    interests = user.get('interests', [])
    timetable = user.get('timetable', [])

    profile_summary = f"{name}님은 {year} {major} 소속이며, 관심사는 {', '.join(interests) if interests else '없음'}입니다."
    timetable_summary = "시간표는 다음과 같습니다:\n" + "\n".join([f"{t.get('day','?')} {t.get('startTime','?')}~{t.get('endTime','?')}" for t in timetable]) if timetable else "시간표 정보 없음."


    # 2. 프로그램 리스트 요약 (최대 10개 - LLM이 볼 수 있도록 좀 더 제공)
    program_summaries = []
    for i, prog in enumerate(programs[:10], 1): # 최대 10개 프로그램 정보 제공
        lines = prog.get("text", "내용 없음").split("\n")
        title = next((line for line in lines if line.startswith("제목:")), "제목 정보 없음").strip()
        schedule = next((line for line in lines if line.startswith("진행기간:")), "일정 정보 없음").strip()
        summary = f"{i}. {title} - {schedule}"
        program_summaries.append(summary)

    programs_block = "\n".join(program_summaries) if program_summaries else "제안할 프로그램이 없습니다."


    # 3. 최종 프롬프트 구성
    prompt = f"""
당신은 건국대학교의 비교과 추천 챗봇입니다. 제공된 사용자 정보, 질문, 그리고 필터링된 비교과 프로그램 목록을 바탕으로 응답하세요. 추천할 비교과 프로그램을 선정할 때는 반드시 아래 [후보 비교과 프로그램] 목록 내에서 골라야 하며, 추천 이유에 사용자의 관심사와 시간표 조건을 고려했음을 명시해주세요.

[사용자 정보]
{profile_summary}
{timetable_summary}

[사용자 질문]
"{question}"

[후보 비교과 프로그램]
{programs_block}

위의 정보들을 바탕으로, 사용자의 시간표와 관심사, 질문을 가장 잘 반영하는 비교과 2~3개를 골라 추천 이유와 함께 설명해주세요. 추천할 프로그램이 없다면 없다고 명확히 답변해주세요.
"""
    return prompt.strip()

# --- 평가 로직 시작 ---

# 이 부분을 주석 처리하거나 삭제하여 CLI 챗봇 실행을 비활성화합니다。
# if __name__ == "__main__":
#     # 사용자 로그인
#     name = input("당신의 이름을 입력하세요: ")
#     user = load_user_profile(name)
#
#     if not user:
#         print(f"{name}이라는 이름을 가진 사용자를 찾을 수 없습니다.")
#         exit()
#
#     print(f"{name}님, 챗봇을 시작합니다. 종료하려면 'exit'을 입력하세요.\n")
#
#     while True:
#         question = input("질문: ")
#         if question.lower() in ["exit", "quit", "종료"]:
#             print("챗봇을 종료합니다.")
#             break
#
#         # Step 1: 시간 겹침 필터링
#         step1_programs = load_filtered_programs_from_folder(user, folder_path="app/data/my_csv_folder")
#
#         # Step 2: 관심사 기반 필터링
#         step2_programs = filter_by_interest(step1_programs, user["interests"])
#
#         if not step2_programs:
#             print("추천할 비교과 프로그램이 없습니다.\n")
#             continue
#
#         final_prompt = generate_llm_prompt(user, question, step2_programs)
#         model = ModelCatalog().load_model("bling-answer-tool")
#         response = model.inference(final_prompt)
#
#         print("\n LLM 추천 결과:\n", response["llm_response"], "\n")
#
#         print(f"\n총 추천된 프로그램 수: {len(step2_programs)}")
#         for idx, prog in enumerate(step2_programs[:3], start=1):
#             print(f"\n 추천 {idx}:\n{prog['text'][:300]}\n---")
#         print()


def evaluate_chatbot_response(user_id, question, users_file="app/data/users.json", programs_folder="app/data/my_csv_folder"):
    """
    챗봇 응답의 정확성을 평가하는 함수.
    """
    print(f"--- 평가 시작 (사용자: {user_id}, 질문: \"{question}\") ---")

    # 1. 사용자 정보 로드
    user_profile = load_user_profile(user_id, users_file)
    if not user_profile:
        print(f"오류: 사용자 {user_id} 정보를 찾을 수 없습니다.")
        return

    print("\n[사용자 정보]")
    print(f"이름: {user_profile.get('name', '정보 없음')}")
    print(f"관심사: {', '.join(user_profile.get('interests', [])) if user_profile.get('interests') else '없음'}")
    print("시간표:")
    if "timetable" in user_profile and isinstance(user_profile["timetable"], list):
        for t in user_profile["timetable"]:
            print(f"  - {t.get('day','?')} {t.get('startTime','?')}~{t.get('endTime','?')}")
    else:
        print("  시간표 정보 없음.")

    # 2. 시간 겹침 필터링
    print("\n[시간 겹침 필터링 적용]")
    time_filtered_programs = load_filtered_programs_from_folder(user_profile, programs_folder)
    print(f"시간표 필터링 후 프로그램 수: {len(time_filtered_programs)}")

    # 시간 겹침 필터링 정확성 추가 검증
    print("\n[시간 겹침 필터링 정확성 검증]")
    conflict_found_in_filtered = False
    user_timetable_str = [f"{t.get('day','?')} {t.get('startTime','?')}~{t.get('endTime','?')}" for t in user_profile.get('timetable', []) if isinstance(t, dict)]

    if not time_filtered_programs:
        print("  필터링된 프로그램이 없어 시간 겹침 검증을 수행할 수 없습니다.")
    else:
        for idx, prog in enumerate(time_filtered_programs[:10], start=1): # 상위 10개만 검증 예시
             prog_schedule = extract_schedule_from_text(prog.get("text", ""))
             if prog_schedule:
                 is_conflict = False
                 for user_time in user_timetable_str:
                      if is_time_conflict(user_time, prog_schedule):
                           is_conflict = True
                           break
                 print(f"  {idx}. 프로그램 일정: {prog_schedule} -> 시간 겹침: {'발견됨' if is_conflict else '없음'}")
                 if is_conflict:
                     conflict_found_in_filtered = True
             else:
                  print(f"  {idx}. 프로그램 일정 정보 없음")

        if not conflict_found_in_filtered:
             print("  [종합]: 필터링된 상위 10개 프로그램에서 시간 겹침이 발견되지 않았습니다.")
        else:
             print("  [종합]: 필터링된 상위 10개 프로그램 중 시간 겹침이 발견된 항목이 있습니다. 확인이 필요합니다.")


    # 3. 관심사 기반 필터링
    print("\n[관심사 기반 필터링 적용]")
    interest_filtered_programs = filter_by_interest(time_filtered_programs, user_profile.get("interests", []))
    print(f"관심사 필터링 후 프로그램 수: {len(interest_filtered_programs)}")

    # 관심사 필터링 정확성 추가 검증
    print("\n[관심사 필터링 정확성 검증]")
    interests = [interest.lower() for interest in user_profile.get("interests", [])]
    if not interests:
        print("  사용자 관심사 없음: 관심사 필터링 검증을 건너뛰었습니다.")
    elif not interest_filtered_programs:
         print("  관심사 필터링 후 프로그램이 없어 검증을 수행할 수 없습니다.")
    else:
        for idx, prog in enumerate(interest_filtered_programs[:10], start=1): # 상위 10개만 검증 예시
            if "text" in prog:
                text = prog["text"].lower()
                found_interests = [interest for interest in interests if interest in text]
                if found_interests:
                    print(f"  {idx}. 포함된 관심사: {', '.join(found_interests)}")
                else:
                    print(f"  {idx}. 포함된 관심사 없음")
            else:
                 print(f"  {idx}. 프로그램 내용(text) 정보 없음")


    # 4. LLM 프롬프트 생성 및 호출
    print("\n[LLM 응답 생성]")
    if not interest_filtered_programs:
        print("후보 프로그램이 없어 LLM에 질문하지 않습니다.")
        llm_response_text = "추천할 비교과 프로그램이 없습니다."
        programs_for_llm = [] # LLM에게 전달한 프로그램 목록 (평가용)
    else:
        final_prompt = generate_llm_prompt(user_profile, question, interest_filtered_programs)
        print("--- LLM에게 전달할 프롬프트 ---")
        print(final_prompt)
        print("------------------------------")

        try:
            # LLM 모델 로드 및 추론
            model = ModelCatalog().load_model("bling-answer-tool") # 모델 이름 확인 필요
            response = model.inference(final_prompt)
            llm_response_text = response.get("llm_response", "LLM 응답 없음")
            programs_for_llm = interest_filtered_programs # LLM에게 전달된 실제 프로그램 목록
        except Exception as e:
            print(f"오류: LLM 모델 로드 또는 추론 실패 - {e}")
            llm_response_text = f"LLM 응답 생성 중 오류 발생: {e}"
            programs_for_llm = []


    print("\n[LLM 추천 결과]")
    print(llm_response_text)


    # 5. LLM 추천 결과 분석 (후보 프로그램 내에 있는지 확인)
    print("\n[LLM 추천 프로그램 검증]")
    if not programs_for_llm:
        print("LLM에게 전달된 후보 프로그램이 없습니다. LLM 응답 내용을 수동으로 확인하세요.")
    else:
        # LLM 응답에서 프로그램 제목을 추출하는 간단한 시도
        # LLM 응답 형식이 다양할 수 있으므로 정확도는 떨어질 수 있습니다.
        # 예시: "1. 제목: [제목]" 패턴 검색 또는 프로그램 이름 패턴 검색
        # 여기서는 간단히 LLM 응답 텍스트에 후보 프로그램 제목이 포함되어 있는지 확인합니다.
        print("LLM 응답 텍스트에 후보 프로그램 제목이 포함되어 있는지 확인합니다.")
        print("(참고: LLM이 프로그램 이름을 다르게 표현할 수 있어 완벽한 검증은 어렵습니다.)")

        llm_recommended_titles_found_in_candidates = []
        candidate_titles = [prog.get('text', '').splitlines()[0].replace("제목: ", "").strip() for prog in programs_for_llm if prog.get('text')]

        for candidate_title in candidate_titles:
            if candidate_title and candidate_title.lower() in llm_response_text.lower():
                 llm_recommended_titles_found_in_candidates.append(candidate_title)

        if llm_recommended_titles_found_in_candidates:
            print(f"  LLM 응답에서 후보 프로그램 목록의 제목 {len(llm_recommended_titles_found_in_candidates)}개를 찾았습니다:")
            for title in llm_recommended_titles_found_in_candidates:
                print(f"  - {title}")
        else:
            print("  LLM 응답에서 후보 프로그램 목록의 제목을 찾기 어렵습니다. LLM 응답 내용을 직접 검토해주세요.")


    print("\n--- 평가 종료 ---")
    print("시간 겹침 필터링과 관심사 필터링 정확성 검증 결과를 확인해주세요.")
    print("LLM 응답에서 실제로 추천하는 프로그램들이 '관심사 필터링 후 프로그램 수' 목록에 있는 프로그램들인지 수동으로 검토하는 것이 가장 정확합니다.")


# --- 평가 실행 예시 ---
if __name__ == "__main__":
    # 평가할 사용자 ID와 질문 설정
    #test_user_id = "1" # app/data/users.json 파일에 있는 사용자 ID 중 하나
    test_user_id = "2" 
    #test_question = "이번 학기 들을 만한 비교과 추천해줘"
    test_question = "AI 관련 프로그램 알려줘"

    # 평가 실행
    #evaluate_chatbot_response(test_user_id, test_question)
    evaluate_chatbot_response("2", "AI 관련 프로그램 알려줘")

    # 다른 사용자나 질문으로 평가를 반복할 수 있습니다。
    # evaluate_chatbot_response("2", "AI 관련 프로그램 알려줘")

