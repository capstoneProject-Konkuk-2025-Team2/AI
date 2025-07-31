import json
import re
import os
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from app.config.llm_config import client, llm
from app.services.user_service import load_user_profile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

USER_PATH = Path(os.getenv("DATA_DIR"))
ACTIVITY_JSON_PATHS = [
    Path(p.strip()) for p in os.getenv("ACTIVITY_JSON_PATHS", "").split(",") if p.strip()
]

recent_top5_idx_title_map = {}
last_queried_title = None
activities, title_embeddings = [], []

def is_time_overlap(start1, end1, start2, end2):
    fmt = "%H:%M"
    s1, e1 = datetime.strptime(start1, fmt), datetime.strptime(end1, fmt)
    s2, e2 = datetime.strptime(start2, fmt), datetime.strptime(end2, fmt)
    return max(s1, s2) < min(e1, e2)

def parse_schedule(text):
    for line in text.split('\n'):
        if line.startswith("진행기간:"):
            try:
                raw = line.replace("진행기간:", "").strip()
                start_raw, end_raw = raw.split("~")
                start_day, start_time = start_raw.strip().split()
                end_day, end_time = end_raw.strip().split()
                day_of_week = datetime.strptime(start_day, "%Y.%m.%d").strftime("%a")
                kor_day = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
                return {"day": kor_day[day_of_week], "startTime": start_time, "endTime": end_time}
            except:
                return None
    return None

def parse_title(text):
    for line in text.split('\n'):
        if line.startswith("제목:"):
            return line.replace("제목:", "").strip()
    return "이름 없음"

def get_embedding(text):
    res = client.embeddings.create(input=[text], model="text-embedding-3-small")
    return np.array(res.data[0].embedding).reshape(1, -1)

def initialize_activities():
    global activities, title_embeddings
    for path in ACTIVITY_JSON_PATHS:
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                title = parse_title(item.get("text", ""))
                title_emb = get_embedding(title)
                activities.append(item)
                title_embeddings.append(title_emb)

def search_top5_programs_with_explanation(query, user_profile):
    global recent_top5_idx_title_map
    query_emb = get_embedding(query)
    interest_emb = get_embedding(" ".join(user_profile.get("interests", [])))

    scored = []
    for idx, item in enumerate(activities):
        schedule = parse_schedule(item.get("text", ""))
        if not schedule:
            continue
        if any(
            slot["day"] == schedule["day"] and
            is_time_overlap(slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"])
            for slot in user_profile["timetable"]
        ):
            continue
        title_emb = title_embeddings[idx]
        query_sim = cosine_similarity(title_emb, query_emb)[0][0]
        interest_sim = cosine_similarity(title_emb, interest_emb)[0][0]
        score = 0.8 * query_sim + 0.2 * interest_sim
        title = parse_title(item.get("text", ""))
        scored.append((idx, title, score, query_sim, interest_sim))
    top5 = sorted(scored, key=lambda x: x[2], reverse=True)[:5]
    recent_top5_idx_title_map = {i+1: top5[i][1] for i in range(len(top5))}

    return "\n\n".join([
        f"{i+1}. {title}\n    - 종합 점수: {score:.3f} (질문 유사도: {qsim:.3f}, 관심사 유사도: {isim:.3f})"
        for i, (_, title, score, qsim, isim) in enumerate(top5)
    ])

def answer_program_question_by_title(query):
    global last_queried_title
    query_emb = get_embedding(query)
    best_score, best_idx = -1, -1
    for idx, title_emb in enumerate(title_embeddings):
        sim = cosine_similarity(title_emb, query_emb)[0][0]
        if sim > best_score:
            best_score, best_idx = sim, idx
    if best_score < 0.70:
        return "입력하신 질문에서 어떤 프로그램을 지칭하는지 찾을 수 없습니다."

    item = activities[best_idx]
    last_queried_title = parse_title(item.get("text", ""))
    prompt = f"""비교과 활동 내용은 다음과 같습니다:\n\n{item.get('text', '')}\n\n사용자가 다음과 같은 질문을 했습니다:\n{query.strip()}\n\n이 질문에 대해 정확하고 간결하게 답변해주세요."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "친절한 비교과 안내 도우미입니다."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

def make_agent(user_profile):
    def wrapped_search(query: str):
        return search_top5_programs_with_explanation(query, user_profile)

    tools = [
        Tool(name="search_program", func=wrapped_search, description="관심사와 시간표에 맞는 비교과 프로그램 Top5 추천"),
        Tool(name="ask_program_by_title", func=answer_program_question_by_title, description="특정 프로그램에 대해 질문하면 답변")
    ]
    return initialize_agent(tools=tools, llm=llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)


def resolve_followup_question(user_question):
    global recent_top5_idx_title_map, last_queried_title

    match = re.match(r"(\d+)번", user_question)
    if match:
        num = int(match.group(1))
        if num in recent_top5_idx_title_map:
            return recent_top5_idx_title_map[num]

    if user_question.startswith("그건") and last_queried_title:
        return f"{last_queried_title} {user_question}"

    return user_question


if __name__ == "__main__":
    initialize_activities()
    user_id = input("사용자 ID를 입력하세요: ").strip()
    user_profile = load_user_profile(user_id)
    if not user_profile:
        print("사용자 정보를 찾을 수 없습니다.")
        exit()

    agent = make_agent(user_profile)

    while True:
        question = input("\n궁금한 내용을 입력하세요 ('종료' 입력 시 종료): ")
        if question.strip() == "종료":
            break

        query = resolve_followup_question(question);

        result = agent.run(query)
        print("\n 답변:\n", result)
