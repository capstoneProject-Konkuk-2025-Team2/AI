import json
from datetime import datetime
import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity
from langchain.agents import initialize_agent, Tool
from langchain_openai import ChatOpenAI
from langchain.agents.agent_types import AgentType
import re

USER_PATH = "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/users.json"
ACTIVITY_JSON_PATHS = [
    "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/my_csv_folder/se_wein_일반비교과_정보(신청가능).json",
    "/Users/jo-eun-yeong/RAG_Agent/AI/app/data/my_csv_folder/se_wein_취창업비교과_정보(신청가능).json"
]

client = OpenAI(api_key="OPENAI_API_KEY")
llm = ChatOpenAI(openai_api_key="OPENAI_API_KEY", temperature=0)

# === 글로벌 상태 ===
recent_top5_idx_title_map = {}
last_queried_title = None

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
                kor_day = {"Mon":"월", "Tue":"화", "Wed":"수", "Thu":"목", "Fri":"금", "Sat":"토", "Sun":"일"}
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

def generate_summary_gpt(title, content):
    prompt = f"""다음은 비교과 프로그램에 대한 상세 설명입니다:\n\n{content}\n\n이 프로그램의 핵심 내용을 3줄 이내로 요약해주세요. 제목은 '{title}'입니다."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 친절한 비교과 안내 도우미입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# 사용자 정보 로딩
with open(USER_PATH, encoding="utf-8") as f:
    users = json.load(f)
name = input("사용자 이름을 입력하세요: ")
user = next((u for u in users.values() if u["name"] == name), None)
if not user:
    print("사용자를 찾을 수 없습니다.")
    exit()
interest_emb = get_embedding(" ".join(user.get("interests", [])))

# 활동과 제목 임베딩 선계산
activities, title_embeddings = [], []
for path in ACTIVITY_JSON_PATHS:
    with open(path, encoding="utf-8") as f:
        for item in json.load(f):
            title = parse_title(item.get("text", ""))
            title_emb = get_embedding(title)
            activities.append(item)
            title_embeddings.append(title_emb)

# 추천 함수
def search_top5_programs_with_explanation(query):
    global recent_top5_idx_title_map
    query_emb = get_embedding(query)
    scored = []
    for idx, item in enumerate(activities):
        schedule = parse_schedule(item.get("text", ""))
        if not schedule: continue
        if any(slot["day"] == schedule["day"] and is_time_overlap(slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]) for slot in user["timetable"]):
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
    best_score = -1
    best_idx = -1
    for idx, title_emb in enumerate(title_embeddings):
        sim = cosine_similarity(title_emb, query_emb)[0][0]
        if sim > best_score:
            best_score = sim
            best_idx = idx
    if best_score < 0.70:
        return "입력하신 질문에서 어떤 프로그램을 지칭하는지 찾을 수 없습니다. 제목 일부 또는 내용을 다시 입력해주세요."

    item = activities[best_idx]
    last_queried_title = parse_title(item.get("text", ""))
    prompt = f"""비교과 활동 내용은 다음과 같습니다:\n\n{item.get('text', '')}\n\n사용자가 다음과 같은 질문을 했습니다:\n{query.strip()}\n\n이 질문에 대해 비교과 활동 내용을 바탕으로 정확하고 간결하게 한국어로 답변해주세요."""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 친절한 비교과 안내 도우미입니다."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# LangChain Agent 설정
tools = [
    Tool(name="search_program", func=search_top5_programs_with_explanation, description="유사한 비교과 활동 Top 5 추천"),
    Tool(name="ask_program_by_title", func=answer_program_question_by_title, description="활동 제목을 포함한 자연어 질문에 응답")
]
agent = initialize_agent(tools=tools, llm=llm, agent=AgentType.OPENAI_FUNCTIONS, verbose=True)

# 실행
while True:
    query = input("\n궁금한 내용을 입력하세요 ('종료' 입력 시 종료): ")
    if query.strip() == "종료":
        print("대화를 종료합니다.")
        break

    # 번호 기반 질문인지 확인
    match = re.match(r"(\d+)번", query)
    if match:
        num = int(match.group(1))
        if num in recent_top5_idx_title_map:
            query = recent_top5_idx_title_map[num]

    # "그건"으로 시작하는 질문이면 직전 활동 제목과 결합
    elif query.strip().startswith("그건") and last_queried_title:
        query = last_queried_title + " " + query.strip()

    result = agent.run(query)
    print("\n 답변:")
    print(result)
