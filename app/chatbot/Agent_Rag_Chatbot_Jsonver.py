import json
import re
import os
# proxy to keep lowercase import stable
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from app.config.llm_config import client, llm
from app.services.user_service import load_user_profile
import pickle, hashlib
from pathlib import Path
from dotenv import load_dotenv
import unicodedata

# (기존 FIELD_PATTERNS 유지) + 장소/수료증도 시도
FIELD_PATTERNS = {
    "신청기간": r"(?:신청\s*기간|접수\s*기간)\s*:\s*([0-9.\-~\s:]+)",
    "대상자": r"(?:대상자|대상)\s*:\s*([^\n]+)",
    "진행기간": r"(?:진행\s*기간|일시)\s*:\s*([0-9.\-~\s:]+)",
    "URL": r"(?:URL|링크|주소)\s*:\s*(\S+)",
    "KUM마일리지": r"(?:KUM|쿰)\s*마일리(?:지|리지)\s*([0-9]+)\s*점",
    "장소": r"(?:장소|위치)\s*:\s*([^\n]+)",
    "수료증": r"(?:수료증)\s*[:\-]?\s*(있음|없음)"
}

# 질문에서 필드 의도를 판별할 때 쓸 느슨한 키워드 매핑
FIELD_KEYWORDS = {
    "KUM마일리지": ["kum", "kum 마일리지", "kum마일리지", "쿰마일리지", "마일리지", "점수", "스코어"],
    "신청기간": ["신청기간", "신청 기간", "접수기간", "접수 기간", "언제까지 신청", "데드라인", "마감"],
    "대상자": ["대상자", "대상", "누가", "몇학년", "학년", "참여대상"],
    "진행기간": ["진행기간", "일시", "언제", "시간", "날짜", "일정", "기간"],
    "URL": ["url", "링크", "주소", "사이트", "홈페이지"],
    "장소": ["장소", "위치", "어디서", "장소가"],
    "수료증": ["수료증", "수료", "수료증주", "수료증 있"]
}


def _normalize(s: str) -> str:
    # 소문자, 공백/구두점 제거, NFKC 정규화
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^\w가-힣]", "", s)
    return s

def _which_field_from_query(query: str) -> str | None:
    nq = _normalize(query)
    for field, kws in FIELD_KEYWORDS.items():
        for kw in kws:
            if _normalize(kw) in nq:
                return field
    return None


# def extract_fields(text: str) -> dict:
#     out = {"제목": parse_title(text)}
#     for k, pat in FIELD_PATTERNS.items():
#         m = re.search(pat, text)
#         if m:
#             out[k] = m.group(1).strip()
#     return out
# def extract_fields(text: str) -> dict:
#     out = {"제목": parse_title(text)}
#     # KUM마일리지는 다중 매칭 → 최대값 선택
#     nums = re.findall(r"(?:KUM|쿰)\s*마일리(?:지|리지)\s*([0-9]+)\s*점", text)
#     if nums:
#         try:
#             out["KUM마일리지"] = str(max(int(n) for n in nums))
#         except:
#             pass

#     for k, pat in FIELD_PATTERNS.items():
#         if k == "KUM마일리지":
#             continue  # 위에서 처리했음
#         m = re.search(pat, text)
#         if m:
#             out[k] = m.group(1).strip()
#     return out
# 1) extract_fields 교체
def extract_fields(text: str) -> dict:
    out = {"제목": parse_title(text)}

    # KUM 마일리지는 여러 숫자가 나올 수 있으니 모두 수집 → 최댓값(숫자만)
    nums = nums = re.findall(r"(?:KUM|쿰)\s*마일리(?:지|리지)[^\d]{0,8}(\d{1,3})", text)
    if nums:
        out["KUM마일리지"] = str(max(int(n) for n in nums))

    # 나머지 필드 1개만 매칭
    for k, pat in FIELD_PATTERNS.items():
        if k == "KUM마일리지":
            continue
        m = re.search(pat, text)
        if m:
            out[k] = m.group(1).strip()
    return out

# === intent 라우터 ===
def _looks_like_field_question(q: str) -> bool:
    ql = q.lower()
    # 숫자 지시("1번", "그건 …") 또는 필드 키워드 포함 시 필드질문으로 간주
    if re.search(r"\b\d+\s*번", q) or q.strip().startswith("그건"):
        return True
    # 우리가 정의한 FIELD_KEYWORDS 활용
    for kws in FIELD_KEYWORDS.values():
        if any(kw.replace(" ", "").lower() in ql.replace(" ", "") for kw in kws):
            return True
    return False

def run_query(user_profile: dict, user_question: str) -> str:
    # 후속 질의치환(1번→제목, 그건→최근제목 …)
    q = resolve_followup_question(user_question)

    # 필드형이면 규칙기반 단답 바로 실행 (툴/에이전트 우회)
    if re.search(r"\b\d+\s*번", q) or q.strip().startswith("그건") or _which_field_from_query(q):
        return answer_program_question_by_title(q)

    # 추천/검색은 기존 함수로
    return search_top5_programs_with_explanation(q, user_profile)

CACHE_DIR = Path(os.getenv("CACHE_DIR", "app/.cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "title_emb_cache.pkl"

def _load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "rb") as f:
            return pickle.load(f)
    return {}

def _save_cache(cache):
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)

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
    key = hashlib.md5((text + "|text-embedding-3-small").encode("utf-8")).hexdigest()
    cache = getattr(get_embedding, "_cache", None)
    if cache is None:
        cache = _load_cache()
        get_embedding._cache = cache
    if key in cache:
        return cache[key]
    res = client.embeddings.create(input=[text], model="text-embedding-3-small")
    vec = np.array(res.data[0].embedding).reshape(1, -1)
    cache[key] = vec
    _save_cache(cache)
    return vec

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
    interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    interest_emb = get_embedding(interest_text)

    # (1) 'KUM 마일리지 20점' 같은 숫자 필터 감지
    mileage_filter = None
    m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)\s*([0-9]+)\s*점", query)
    if m:
        mileage_filter = int(m.group(1))

    scored = []
    for idx, item in enumerate(activities):
        text = item.get("text", "")
        schedule = parse_schedule(text)
        if not schedule:
            continue

        # (2) 유저 시간표 충돌 제외
        for slot in (user_profile.get("timetable") or []):
            if slot["day"] == schedule["day"] and is_time_overlap(
                slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]
            ):
                break
        else:
            # (3) 마일리지 숫자 필터
            fields = extract_fields(text)
            if mileage_filter is not None:
                v = fields.get("KUM마일리지")
                if not v or int(v) != mileage_filter:
                    continue

            # (4) 유사도 점수 계산 + 낮은 항목 컷
            title_emb = title_embeddings[idx]
            query_sim = cosine_similarity(title_emb, query_emb)[0][0]
            interest_sim = cosine_similarity(title_emb, interest_emb)[0][0]
            if query_sim < 0.30 and interest_sim < 0.30:
                continue

            title = fields.get("제목", parse_title(text))
            score = 0.8 * query_sim + 0.2 * interest_sim
            scored.append((idx, title, score, query_sim, interest_sim, fields.get("KUM마일리지")))

    top5 = sorted(scored, key=lambda x: x[2], reverse=True)[:5]
    recent_top5_idx_title_map = {i+1: top5[i][1] for i in range(len(top5))}

    if not top5:
        return "조건에 맞는 프로그램을 찾지 못했습니다."

    # (5) 출력: KUM마일리지도 함께 표기
    lines = []
    for i, (_, title, score, qsim, isim, kum) in enumerate(top5, start=1):
        miles = f" — KUM마일리지: {kum}점" if kum else ""
        lines.append(f"{i}. {title}{miles}\n    - 종합 점수: {score:.3f} (질문 유사도: {qsim:.3f}, 관심사 유사도: {isim:.3f})")

    # 리스트가 있으면 '1번'을 최근 타이틀로 저장해 후속 '그건 …/1번 …' 안정화
    from_text = top5[0][1]  # 1등 제목
    globals()["last_queried_title"] = from_text    
    return "\n\n".join(lines)

# def _short_field_answer(query: str, fields: dict) -> str | None:
#     field = _which_field_from_query(query)
#     if not field:
#         return None
#     val = fields.get(field)
#     return f"{field}: {val if val else '자료에 없음'}"
# 2) _short_field_answer 내 숫자 정규화
def _short_field_answer(query: str, fields: dict) -> str | None:
    field = _which_field_from_query(query)
    if not field:
        return None
    val = fields.get(field)

    # 평가용 포맷 고정: "KUM마일리지: 20" (점 제거)
    if field == "KUM마일리지" and val:
        m = re.search(r"\d+", val)
        val = m.group(0) if m else val

    return f"{field}: {val if val else '자료에 없음'}"
def answer_program_question_by_title(query):
    global last_queried_title

    # (A) 정확 제목 포함 매칭 먼저
    best_idx = -1
    for i, item in enumerate(activities):
        title_i = parse_title(item.get("text",""))
        if title_i and title_i in query:
            best_idx = i
            break

    # (B) 없으면 임베딩 유사도
    if best_idx == -1:
        query_emb = get_embedding(query)
        best_score = -1
        for idx, title_emb in enumerate(title_embeddings):
            sim = cosine_similarity(title_emb, query_emb)[0][0]
            if sim > best_score:
                best_score, best_idx = sim, idx
        if best_score < 0.55:  # ★ 0.65 -> 0.55로 완화 (제목+질문 섞인 질의 대응)
            # 최근 맥락 + 필드질문이면 최근 항목으로 단답 시도
            if last_queried_title and _which_field_from_query(query):
                for i, it in enumerate(activities):
                    if last_queried_title in it.get("text",""):
                        fields = extract_fields(it.get("text",""))
                        ans = _short_field_answer(query, fields)
                        if ans: return ans
            return "입력하신 질문에서 어떤 프로그램을 지칭하는지 찾을 수 없습니다."

    # (C) 선택된 항목에서 필드 추출/단답
    item = activities[best_idx]
    text = item.get("text", "")
    fields = extract_fields(text)
    last_queried_title = fields.get("제목", parse_title(text))

    short = _short_field_answer(query, fields)
    if short:
        return short

    # (D) 나머지는 LLM으로 간단 답변
    brief_text = text[:1500]
    prompt = (
        f"[활동정보]\n{brief_text}\n\n"
        f"[질문]\n{query}\n\n"
        "자료에 있는 내용만 근거로 한국어로 1~2문장으로 간단히 답하세요. "
        "자료에 없으면 '자료에 없음'이라고 답하세요."
    )
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
        temperature=0,
        max_tokens=160,
        messages=[
            {"role": "system", "content": "간결하고 정확한 비교과 안내 도우미."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def make_agent(user_profile):
    def wrapped_search(query: str):
        return search_top5_programs_with_explanation(query, user_profile)

    tools = [
        Tool(name="search_program", func=wrapped_search, description="관심사와 시간표에 맞는 비교과 프로그램 Top5 추천"),
        Tool(name="ask_program_by_title", func=answer_program_question_by_title, description="특정 프로그램에 대해 질문하면 답변")
    ]
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=False,              # 로그 오버헤드 줄이기
        max_iterations=1,           # 왕복 1회로 고정
        early_stopping_method="generate",
        handle_parsing_errors=True
    )


# def resolve_followup_question(user_question):
#     global recent_top5_idx_title_map, last_queried_title

#     match = re.match(r"(\d+)번", user_question)
#     if match:
#         num = int(match.group(1))
#         if num in recent_top5_idx_title_map:
#             return recent_top5_idx_title_map[num]

#     if user_question.startswith("그건") and last_queried_title:
#         return f"{last_queried_title} {user_question}"

#     return user_question
def resolve_followup_question(user_question):
    global recent_top5_idx_title_map, last_queried_title

    # 예: "2번 활동 KUM 마일리지 얼마줘?" → "해당제목 KUM 마일리지 얼마줘?"
    m = re.match(r"^\s*(\d+)\s*번(?:\s*활동)?\s*(.*)$", user_question)
    if m:
        num = int(m.group(1)); tail = (m.group(2) or "").strip()
        if num in recent_top5_idx_title_map:
            title = recent_top5_idx_title_map[num]
            last_queried_title = title     
            return f"{title} {tail}".strip()

    # 예: "그건 대상자는?" → "최근제목 대상자는?"
    if user_question.startswith("그건"):
        tail = user_question.replace("그건", "", 1).strip()
        if last_queried_title and tail:
            return f"{last_queried_title} {tail}".strip()

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

# 파일: app/chatbot/Agent_Rag_Chatbot.py  (아무 데나 아래 함수 하나 추가)
def ranked_programs(query: str, user_profile: dict, k: int = 5):
    """내부 검색 로직을 재사용해 상위 k개를 구조화된 형태로 반환 (평가용)"""
    query_emb = get_embedding(query)
    interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    interest_emb = get_embedding(interest_text)

    # 마일리지 필터 (질문에 '20점' 같은게 있으면 적용)
    mileage_filter = None
    m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)\s*([0-9]+)\s*점?", query)
    if m:
        mileage_filter = int(m.group(1))

    rows = []
    for idx, item in enumerate(activities):
        text = item.get("text", "")
        schedule = parse_schedule(text)
        if not schedule:
            continue

        # 유저 시간표 충돌 제외
        conflict = False
        for slot in (user_profile.get("timetable") or []):
            if slot["day"] == schedule["day"] and is_time_overlap(
                slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]
            ):
                conflict = True
                break
        if conflict:
            continue

        fields = extract_fields(text)
        if mileage_filter is not None:
            v = fields.get("KUM마일리지")
            if not v or int(v) != mileage_filter:
                continue

        title_emb = title_embeddings[idx]
        query_sim = cosine_similarity(title_emb, query_emb)[0][0]
        interest_sim = cosine_similarity(title_emb, interest_emb)[0][0]
        if query_sim < 0.30 and interest_sim < 0.30:
            continue

        title = fields.get("제목", parse_title(text))
        score = 0.8 * query_sim + 0.2 * interest_sim
        rows.append({
            "idx": idx,
            "title": title,
            "score": float(score),
            "query_sim": float(query_sim),
            "interest_sim": float(interest_sim),
            "fields": fields,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:k]