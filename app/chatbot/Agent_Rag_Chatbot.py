
#----------------------------------3번 고침 
#-*- coding: utf-8 -*-
# """
# Agent_Rag_Chatbot.py (refined)
# - DB(extracurricular)에서 활동 불러오기
# - 추천(검색) / 필드 단답 / 잡담 라우팅
# - '1번', '그건 …' 꼬리질문 맥락 유지
# - 추천일 경우 (보기 텍스트, [extracurricular_id ...]) 반환
# """

# import os
# import re
# import json
# import pickle
# import hashlib
# import unicodedata
# from pathlib import Path
# from datetime import datetime

# import numpy as np
# from sklearn.metrics.pairwise import cosine_similarity

# from dotenv import load_dotenv
# from sqlalchemy import text as sql_text
# from langchain.agents import initialize_agent, Tool
# from langchain.agents.agent_types import AgentType

# from app.config.llm_config import client, llm
# from app.services.user_service import load_user_profile
# from app.utils.db import engine


# # -----------------------------
# # 필드 패턴 & 키워드 (필드 키워드는 과도한 오탐 방지를 위해 '정확 지시' 위주로 축소)
# # -----------------------------
# FIELD_PATTERNS = {
#     "신청기간": r"(?:신청\s*기간|접수\s*기간)\s*:\s*([0-9.\-~\s:]+)",
#     "대상자": r"(?:대상자|대상)\s*:\s*([^\n]+)",
#     "진행기간": r"(?:진행\s*기간|일시)\s*:\s*([0-9.\-~\s:]+)",
#     "URL": r"(?:URL|링크|주소)\s*:\s*(\S+)",
#     "KUM마일리지": r"(?:KUM|쿰)\s*마일리(?:지|리지)\s*([0-9]+)\s*점",
#     "장소": r"(?:장소|위치)\s*:\s*([^\n]+)",
#     "수료증": r"(?:수료증)\s*[:\-]?\s*(있음|없음)"
# }

# # ⬇️ ‘언제/시간/일정/기간’ 같은 일반어는 오탐이 잦아 제외
# FIELD_KEYWORDS = {
#     "KUM마일리지": ["kum", "kum마일리지", "쿰마일리지", "마일리지", "점수"],
#     "신청기간": ["신청기간", "접수기간", "신청 기간", "접수 기간"],
#     "대상자": ["대상자", "대상", "누가", "몇학년", "학년"],
#     "진행기간": ["진행기간", "일시"],
#     "URL": ["url", "링크", "주소", "홈페이지", "web"],
#     "장소": ["장소", "위치", "어디서"],
#     "수료증": ["수료증", "수료"]
# }


# # -----------------------------
# # 유틸
# # -----------------------------
# def _normalize(s: str) -> str:
#     s = unicodedata.normalize("NFKC", s or "").lower()
#     s = re.sub(r"\s+", "", s)
#     s = re.sub(r"[^\w가-힣]", "", s)
#     return s

# def _which_field_from_query(query: str) -> str | None:
#     nq = _normalize(query or "")
#     for field, kws in FIELD_KEYWORDS.items():
#         for kw in kws:
#             if _normalize(kw) in nq:
#                 return field
#     return None


# # -----------------------------
# # 임베딩 캐시
# # -----------------------------
# CACHE_DIR = Path(os.getenv("CACHE_DIR", "app/.cache"))
# CACHE_DIR.mkdir(parents=True, exist_ok=True)
# CACHE_FILE = CACHE_DIR / "title_emb_cache.pkl"

# def _load_cache():
#     if CACHE_FILE.exists():
#         with open(CACHE_FILE, "rb") as f:
#             return pickle.load(f)
#     return {}

# def _save_cache(cache):
#     with open(CACHE_FILE, "wb") as f:
#         pickle.dump(cache, f)

# def get_embedding(text: str):
#     key = hashlib.md5((text + "|text-embedding-3-small").encode("utf-8")).hexdigest()
#     cache = getattr(get_embedding, "_cache", None)
#     if cache is None:
#         cache = _load_cache()
#         get_embedding._cache = cache
#     if key in cache:
#         return cache[key]
#     res = client.embeddings.create(input=[text], model="text-embedding-3-small")
#     vec = np.array(res.data[0].embedding).reshape(1, -1)
#     cache[key] = vec
#     _save_cache(cache)
#     return vec


# # -----------------------------
# # DB 로딩 & 텍스트 합성
# # -----------------------------
# def _fmt_dt(x) -> str:
#     try:
#         return x.strftime("%Y.%m.%d %H:%M") if x else ""
#     except Exception:
#         return str(x) if x else ""

# def _load_and_synthesize_text_for_extracurricular(conn):
#     """
#     extracurricular(extracurricular_id, title, url, description, activity_start/end,
#     application_start/end, location) -> 각 row를 파서 가능한 text로 합성
#     """
#     q = """
#     SELECT
#       extracurricular_id,
#       title,
#       url,
#       description,
#       activity_start,
#       activity_end,
#       application_start,
#       application_end,
#       location
#     FROM extracurricular
#     """
#     rows = []
#     for r in conn.execute(sql_text(q)).mappings():
#         apply_line = ""
#         if r.get("application_start") or r.get("application_end"):
#             apply_line = f"{_fmt_dt(r.get('application_start'))} ~ {_fmt_dt(r.get('application_end'))}"

#         event_line = ""
#         if r.get("activity_start") or r.get("activity_end"):
#             event_line = f"{_fmt_dt(r.get('activity_start'))} ~ {_fmt_dt(r.get('activity_end'))}"

#         url  = r.get("url") or ""
#         place = r.get("location") or ""
#         title = r.get("title") or ""
#         desc = (r.get("description") or "").strip()

#         text = "\n".join([
#             f"제목: {title}".strip(),
#             f"신청기간: {apply_line}".strip() if apply_line else "",
#             f"진행기간: {event_line}".strip() if event_line else "",
#             f"URL: {url}".strip() if url else "",
#             f"장소: {place}".strip() if place else "",
#             desc
#         ]).strip()

#         rows.append({"id": r["extracurricular_id"], "text": text})
#     return rows

# def load_activities_from_db():
#     with engine.connect() as conn:
#         rows = _load_and_synthesize_text_for_extracurricular(conn)
#         if rows:
#             return rows
#     raise RuntimeError("DB에서 비교과 데이터를 찾지 못했습니다. (extracurricular 테이블이 비었을 수 있음)")


# # -----------------------------
# # 파서/스코어링
# # -----------------------------
# def parse_title(text: str) -> str:
#     for line in text.splitlines():
#         if line.startswith("제목:"):
#             return line.replace("제목:", "", 1).strip()
#     return "이름 없음"

# def extract_fields(text: str) -> dict:
#     out = {"제목": parse_title(text)}
#     nums = re.findall(r"(?:KUM|쿰)\s*마일리(?:지|리지)[^\d]{0,8}(\d{1,3})", text)
#     if nums:
#         out["KUM마일리지"] = str(max(int(n) for n in nums))
#     for k, pat in FIELD_PATTERNS.items():
#         if k == "KUM마일리지":
#             continue
#         m = re.search(pat, text)
#         if m:
#             out[k] = m.group(1).strip()
#     return out

# def parse_schedule(text: str):
#     # "진행기간: 2025.05.27 14:00 ~ 2025.05.27 16:00" 형식 가정
#     for line in text.splitlines():
#         if line.startswith("진행기간:"):
#             try:
#                 raw = line.replace("진행기간:", "", 1).strip()
#                 start_raw, end_raw = raw.split("~")
#                 start_day, start_time = start_raw.strip().split()
#                 end_day, end_time = end_raw.strip().split()
#                 dow = datetime.strptime(start_day, "%Y.%m.%d").strftime("%a")
#                 kor_day = {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}
#                 return {"day": kor_day.get(dow, ""), "startTime": start_time, "endTime": end_time}
#             except:
#                 return None
#     return None

# def _parse_user_time_constraint(q: str):
#     """
#     예) '수요일 12시~5시', '수요일 12:00~17:00' → {"day":"수","start":"12:00","end":"17:00"}
#         '수요일 추천해줘' → {"day":"수"}
#     """
#     day_map = {"월":"월","화":"화","수":"수","목":"목","금":"금","토":"토","일":"일"}
#     out = {}
#     for d in day_map:
#         if d in q:
#             out["day"] = d
#             break
#     m = re.search(r"(\d{1,2})\s*[:시]\s*(\d{0,2})?\s*~\s*(\d{1,2})\s*[:시]\s*(\d{0,2})?", q)
#     if m:
#         s_h = int(m.group(1)); s_m = int(m.group(2) or 0)
#         e_h = int(m.group(3)); e_m = int(m.group(4) or 0)
#         out["start"] = f"{s_h:02d}:{s_m:02d}"
#         out["end"]   = f"{e_h:02d}:{e_m:02d}"
#     return out or None

# def _time_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
#     fmt = "%H:%M"
#     s1, e1 = datetime.strptime(a_start, fmt), datetime.strptime(a_end, fmt)
#     s2, e2 = datetime.strptime(b_start, fmt), datetime.strptime(b_end, fmt)
#     return max(s1, s2) < min(e1, e2)


# # -----------------------------
# # 글로벌 상태
# # -----------------------------
# load_dotenv()
# USER_PATH = Path(os.getenv("DATA_DIR"))

# activities = []
# title_embeddings = []

# recent_num_to_title: dict[int, str] = {}
# recent_num_to_id: dict[int, int] = {}
# last_queried_title: str | None = None

# def initialize_activities():
#     """DB에서 활동 로드 + 타이틀 임베딩 캐시 생성"""
#     global activities, title_embeddings
#     activities = load_activities_from_db()
#     title_embeddings = []
#     for item in activities:
#         title = parse_title(item.get("text", ""))
#         title_embeddings.append(get_embedding(title))


# # -----------------------------
# # 검색(추천)
# # -----------------------------
# def _filter_by_user_time(q: str, schedule: dict | None, user_profile: dict) -> bool:
#     """
#     사용자가 질의에 요일/시간대를 명시한 경우 그 조건과 맞는지 체크.
#     user_profile의 timetable과 겹치지 않는지도 체크.
#     """
#     if not schedule:
#         return False  # 진행시간이 없는 항목은 추천에서 제외 (질 좋은 추천만)
#     cons = _parse_user_time_constraint(q)
#     if cons:
#         if cons.get("day") and cons["day"] != schedule["day"]:
#             return False
#         if cons.get("start") and cons.get("end"):
#             if not _time_overlap(schedule["startTime"], schedule["endTime"], cons["start"], cons["end"]):
#                 return False
#     if (user_profile.get("timetable") or []):
#         for slot in user_profile["timetable"]:
#             if slot.get("day") == schedule["day"]:
#                 if _time_overlap(slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]):
#                     return False
#     return True

# def _lead_for_query(query: str) -> str:
#     ql = _normalize(query)
#     if "창업" in query:
#         return "다음은 창업 프로그램 추천 목록입니다:\n\n"
#     if "ai" in ql or "인공지능" in ql or "데이터" in ql:
#         return "AI 관련 비교과 추천 결과입니다:\n\n"
#     if "취업" in query or "진로" in query:
#         return "취업·진로 관련 추천 프로그램입니다:\n\n"
#     if "캡스톤" in query or "캡스톤디자인" in ql:
#         return "캡스톤디자인 관련 프로그램을 찾았어요:\n\n"
#     if "어울리" in query or "추천" in query:
#         return "당신과 어울리는 비교과 Top5를 골라봤어요:\n\n"
#     return "다음 프로그램들을 추천드려요:\n\n"

# def _format_reco_item_line(i: int, title: str, kum: str | None) -> str:
#     miles = f" - KUM마일리지: {kum}점" if kum else ""
#     return f"{i}. {title}{miles}"

# def search_top5_programs_with_explanation(query: str, user_profile: dict):
#     """
#     반환: (보기용 텍스트, [추천된 extracurricular_id ...])
#     (리스트는 자연어 톤; 점수/유사도 수치는 출력 제거)
#     """
#     global recent_num_to_title, recent_num_to_id, last_queried_title

#     query_emb = get_embedding(query)
#     interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
#     interest_emb = get_embedding(interest_text)

#     # 숫자 마일리지 필터
#     mileage_filter = None
#     m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)\s*([0-9]+)\s*점", query)
#     if m:
#         mileage_filter = int(m.group(1))

#     scored = []
#     for idx, item in enumerate(activities):
#         text = item.get("text", "")
#         fields = extract_fields(text)
#         schedule = parse_schedule(text)
#         if not _filter_by_user_time(query, schedule, user_profile):
#             continue

#         if mileage_filter is not None:
#             v = fields.get("KUM마일리지")
#             if not v or int(v) != mileage_filter:
#                 continue

#         title = fields.get("제목", parse_title(text))
#         title_emb = title_embeddings[idx]
#         qsim = float(cosine_similarity(title_emb, query_emb)[0][0])
#         isim = float(cosine_similarity(title_emb, interest_emb)[0][0]) if interest_text else 0.0
#         if qsim < 0.30 and isim < 0.30:
#             continue

#         score = 0.8 * qsim + 0.2 * isim
#         scored.append((idx, item["id"], title, score, fields.get("KUM마일리지")))

#     if not scored:
#         return ("조건에 맞는 프로그램을 찾지 못했습니다.", [])

#     top5 = sorted(scored, key=lambda x: x[3], reverse=True)[:5]

#     recent_num_to_title = {i+1: top5[i][2] for i in range(len(top5))}
#     recent_num_to_id    = {i+1: top5[i][1] for i in range(len(top5))}
#     last_queried_title  = top5[0][2]

#     lines = [
#         _format_reco_item_line(i, title, kum)
#         for i, (_idx, _id, title, _score, kum) in enumerate(top5, start=1)
#     ]

#     lead = _lead_for_query(query)
#     tail = "\n\n원하는 프로그램이 있으시면 번호로 말씀해 주세요. 자세한 정보를 바로 알려드릴게요."
#     return (lead + "\n".join(lines) + tail, [t[1] for t in top5])


# # -----------------------------
# # 필드 단답 & 자유 요약
# # -----------------------------
# def _short_field_answer(query: str, fields: dict) -> str | None:
#     field = _which_field_from_query(query)
#     if not field:
#         return None
#     val = fields.get(field)
#     if field == "KUM마일리지" and val:
#         m = re.search(r"\d+", val)
#         val = m.group(0) if m else val
#         return f"{field}: {val}점"
#     return f"{field}: {val if val else '자료에 없음'}"

# def answer_program_question_by_title(query: str) -> str:
#     """
#     제목 포함/유사도 기반으로 1개 선택 → 필드 단답 우선, 아니면 description 요약
#     """
#     global last_queried_title

#     # 1) 제목 포함 일치
#     best_idx = -1
#     for i, item in enumerate(activities):
#         title_i = parse_title(item.get("text", ""))
#         if title_i and title_i in query:
#             best_idx = i
#             break

#     # 2) 임베딩 유사도로 최다 유사 제목
#     if best_idx == -1:
#         q_emb = get_embedding(query)
#         best_score = -1.0
#         for idx, title_emb in enumerate(title_embeddings):
#             sim = float(cosine_similarity(title_emb, q_emb)[0][0])
#             if sim > best_score:
#                 best_score, best_idx = sim, idx
#         if best_score < 0.55:
#             # 최근 맥락 + 필드질문이면 최근 항목으로
#             if last_queried_title and _which_field_from_query(query):
#                 for it in activities:
#                     if last_queried_title in it.get("text", ""):
#                         fields = extract_fields(it.get("text", ""))
#                         ans = _short_field_answer(query, fields)
#                         if ans:
#                             return ans
#             return "입력하신 질문에서 어떤 프로그램을 지칭하는지 찾을 수 없습니다."

#     item = activities[best_idx]
#     text = item.get("text", "")
#     fields = extract_fields(text)
#     last_queried_title = fields.get("제목", parse_title(text))

#     # 3) 필드 단답
#     short = _short_field_answer(query, fields)
#     if short:
#         return short

#     # 4) 간단 요약 (description 포함된 합성 텍스트의 앞부분만 사용)
#     brief_text = text[:1600]
#     prompt = (
#         f"[활동정보]\n{brief_text}\n\n"
#         f"[질문]\n{query}\n\n"
#         "자료에 있는 내용만 근거로 한국어로 1~2문장으로 친근하게 답하세요. "
#         "자료에 없으면 '자료에 없음'이라고만 답하세요."
#     )
#     response = client.chat.completions.create(
#         model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
#         temperature=0.2,
#         max_tokens=160,
#         messages=[
#             {"role": "system", "content": "친근하고 정확한 비교과 안내 도우미."},
#             {"role": "user", "content": prompt}
#         ]
#     )
#     return response.choices[0].message.content.strip()


# # -----------------------------
# # 후속질의 치환 & 의도 분류
# # -----------------------------
# def resolve_followup_question(user_question: str) -> str:
#     """
#     '2번 URL', '2번 활동 KUM 마일리지' → '〈제목〉 URL' 형태로 치환
#     '그건 …' → 최근 제목으로 치환
#     """
#     global recent_num_to_title, last_queried_title

#     m = re.match(r"^\s*(\d+)\s*번(?:\s*활동)?\s*(.*)$", user_question)
#     if m:
#         num = int(m.group(1))
#         tail = (m.group(2) or "").strip()
#         if num in recent_num_to_title:
#             title = recent_num_to_title[num]
#             last_queried_title = title
#             return f"{title} {tail}".strip()

#     if user_question.strip().startswith("그건"):
#         tail = user_question.strip()[2:].strip()
#         if last_queried_title and tail:
#             return f"{last_queried_title} {tail}".strip()

#     return user_question

# def _classify_intent(original_q: str) -> str:
#     """
#     의도 판단 규칙:
#     - '추천/어울리/…'가 있으면 무조건 추천 우선
#     - 숫자 시작('1번', '2번') 또는 '그건 …' 또는 명시 필드 키워드 → 필드
#     - 그 외 → 추천
#     """
#     q = original_q or ""
#     nq = _normalize(q)

#     # 1) 추천 트리거 우선
#     reco_trigs = ["추천", "어울리", "비교과", "프로그램", "활동", "컨설팅", "워크숍", "특강", "ai", "인공지능", "데이터", "취업", "창업", "캡스톤", "디자인"]
#     if any(_normalize(t) in nq for t in reco_trigs):
#         return "reco"

#     # 2) 숫자/그건/필드키워드 → 필드
#     if re.search(r"^\s*\d+\s*번", q) or q.strip().startswith("그건") or _which_field_from_query(q):
#         return "field"

#     # 3) 기본값
#     return "reco"


# # -----------------------------
# # 에이전트(툴) 구성 (원하면 사용)
# # -----------------------------
# def _tool_search_wrapper(user_profile):
#     def _run(query: str):
#         txt, ids = search_top5_programs_with_explanation(query, user_profile)
#         return json.dumps({"text": txt, "ids": ids}, ensure_ascii=False)
#     return _run

# def _tool_field_answer(query: str):
#     return answer_program_question_by_title(query)

# def make_agent(user_profile):
#     tools = [
#         Tool(
#             name="search_program",
#             func=_tool_search_wrapper(user_profile),
#             description="관심사/시간표/사용자 요청에 맞는 비교과 프로그램 Top5를 추천(검색)한다. 결과는 JSON({text, ids})."
#         ),
#         Tool(
#             name="ask_program_by_title",
#             func=_tool_field_answer,
#             description="특정 프로그램에 대해 '신청기간/진행기간/대상자/URL/장소/수료증/KUM마일리지' 등 필드 질문을 받으면 단답 또는 짧은 요약으로 답한다."
#         )
#     ]
#     return initialize_agent(
#         tools=tools,
#         llm=llm,
#         agent=AgentType.OPENAI_FUNCTIONS,
#         verbose=False,
#         max_iterations=2,
#         early_stopping_method="generate",
#         handle_parsing_errors=True
#     )


# # -----------------------------
# # 최상위 진입점
# # -----------------------------
# def run_query(user_profile: dict, user_question: str):
#     """
#     외부에서 호출하는 단일 엔트리.
#     - 추천 intent: (응답텍스트, [id...])
#     - 필드/요약 intent: (응답텍스트, [])
#     - 잡담은 현재 경로에서 거의 발생하지 않도록 하되, 필요시 자연어 한두 문장으로 대응
#     """
#     intent = _classify_intent(user_question)    # 원문 기준
#     q = resolve_followup_question(user_question) # 후속질의 보정

#     if intent == "field":
#         return (answer_program_question_by_title(q), [])

#     # 기본은 추천 경로
#     txt, ids = search_top5_programs_with_explanation(q, user_profile)
#     return (txt, ids)


# # -----------------------------
# # CLI 테스트 진입 (선택)
# # -----------------------------
# if __name__ == "__main__":
#     load_dotenv()
#     initialize_activities()
#     user_id = input("사용자 ID를 입력하세요: ").strip()
#     user_profile = load_user_profile(user_id)
#     if not user_profile:
#         print("사용자 정보를 찾을 수 없습니다.")
#         exit()

#     while True:
#         q = input("\n궁금한 내용을 입력하세요 ('종료' 입력 시 종료): ").strip()
#         if q == "종료":
#             break
#         text, ids = run_query(user_profile, q)
#         print("\n답변:\n", text)
#         if ids:
#             print("\n[추천된 extracurricular_id]:", ids)


# # ---------------------------------------
# # (평가/디버깅용) 상위 k개 구조화 반환
# # ---------------------------------------
# def ranked_programs(query: str, user_profile: dict, k: int = 5):
#     query_emb = get_embedding(query)
#     interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
#     interest_emb = get_embedding(interest_text)

#     mileage_filter = None
#     m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)\s*([0-9]+)\s*점?", query)
#     if m:
#         mileage_filter = int(m.group(1))

#     rows = []
#     for idx, item in enumerate(activities):
#         text = item.get("text", "")
#         schedule = parse_schedule(text)
#         if not schedule:
#             continue

#         # 유저 시간표 충돌 제외
#         fields = extract_fields(text)
#         cons_ok = _filter_by_user_time(query, schedule, user_profile)
#         if not cons_ok:
#             continue

#         if mileage_filter is not None:
#             v = fields.get("KUM마일리지")
#             if not v or int(v) != mileage_filter:
#                 continue

#         title_emb = title_embeddings[idx]
#         qsim = float(cosine_similarity(title_emb, query_emb)[0][0])
#         isim = float(cosine_similarity(title_emb, interest_emb)[0][0]) if interest_text else 0.0
#         if qsim < 0.30 and isim < 0.30:
#             continue

#         rows.append({
#             "idx": idx,
#             "id": item["id"],
#             "title": fields.get("제목", parse_title(text)),
#             "score": float(0.8 * qsim + 0.2 * isim),
#             "query_sim": float(qsim),
#             "interest_sim": float(isim),
#             "fields": fields,
#         })

#     rows.sort(key=lambda r: r["score"], reverse=True)
#     return rows[:k]

## ------------------------------------------일단 여기까지 Sat Sep 6

# 파일: app/chatbot/Agent_Rag_Chatbot.py
"""
DB-backed Agent (JSON 성능 이식판)
- DB(extracurricular)에서 로드하지만, JSON 기반 코드의 검색/필드응답/후속질의 UX와 점수표시를 그대로 재현
- 특징:
  1) 추천 리스트에 종합점수/질문유사도/관심사유사도 표기 (JSON 버전과 동일)
  2) '1번', '숫자만(4)', '그건 …' 후속질의 안정 동작
  3) KUM 마일리지 다중 매칭 → 최댓값 사용
  4) 시간표 충돌 배제 + (선택) 질의 내 요일/시간대 제약 반영
  5) 필드 질문(신청기간/진행기간/대상자/URL/장소/수료증/KUM마일리지) 단답 우선
"""

import os
import re
import json
import pickle
import hashlib
import unicodedata
from pathlib import Path
from datetime import datetime

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from dotenv import load_dotenv
from sqlalchemy import text as sql_text
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType

from app.config.llm_config import client, llm
from app.services.user_service import load_user_profile
from app.utils.db import engine


# -----------------------------
# 필드 패턴 & 키워드 (JSON 버전과 동일/확장)
# -----------------------------
FIELD_PATTERNS = {
    "신청기간": r"(?:신청\s*기간|접수\s*기간)\s*:\s*([0-9.\-~\s:()]+)",
    "대상자": r"(?:대상자|대상)\s*:\s*([^\n]+)",
    "진행기간": r"(?:진행\s*기간|일시)\s*:\s*([0-9.\-~\s:()]+)",
    "URL": r"(?:URL|링크|주소)\s*:\s*(\S+)",
    "KUM마일리지": r"(?:KUM|쿰)\s*마일리(?:지|리지)\s*([0-9]+)\s*점",
    "장소": r"(?:장소|위치)\s*:\s*([^\n]+)",
    "수료증": r"(?:수료증)\s*[:\-]?\s*(있음|없음)"
}

# JSON 버전의 느슨한 키워드 + 약간 확장 (오탐 허용)
FIELD_KEYWORDS = {
    "KUM마일리지": ["kum", "kum 마일리지", "kum마일리지", "쿰마일리지", "마일리지", "점수", "스코어"],
    "신청기간": ["신청기간", "신청 기간", "접수기간", "접수 기간", "언제까지 신청", "데드라인", "마감"],
    "대상자": ["대상자", "대상", "누가", "몇학년", "학년", "참여대상"],
    "진행기간": ["진행기간", "일시", "언제", "시간", "날짜", "일정", "기간"],
    "URL": ["url", "링크", "주소", "사이트", "홈페이지", "web"],
    "장소": ["장소", "위치", "어디서", "장소가"],
    "수료증": ["수료증", "수료", "수료증주", "수료증 있"]
}


# -----------------------------
# 유틸
# -----------------------------
def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^\w가-힣]", "", s)
    return s

def _which_field_from_query(query: str) -> str | None:
    nq = _normalize(query or "")
    for field, kws in FIELD_KEYWORDS.items():
        for kw in kws:
            if _normalize(kw) in nq:
                return field
    return None


# -----------------------------
# 임베딩 캐시
# -----------------------------
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

def get_embedding(text: str):
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


# -----------------------------
# DB 로딩 & 텍스트 합성 (JSON 스키마와 유사한 텍스트로 표준화)
# -----------------------------
def _fmt_dt(x) -> str:
    """
    DB는 datetime 또는 'YYYY-MM-DD HH:MM:SS' 문자열일 수 있음.
    합성 텍스트는 'YYYY.MM.DD HH:MM'로 통일 (JSON 텍스트와 최대한 유사)
    """
    if not x:
        return ""
    try:
        if isinstance(x, str):
            x = x[:16]  # 'YYYY-MM-DD HH:MM'
            dt = datetime.strptime(x, "%Y-%m-%d %H:%M")
        else:
            dt = x
        return dt.strftime("%Y.%m.%d %H:%M")
    except Exception:
        return str(x)

def _load_and_synthesize_text_for_extracurricular(conn):
    """
    extracurricular(extracurricular_id, title, url, description,
                    activity_start/end, application_start/end, location)
    → JSON-text와 최대한 비슷한 라인 구성으로 합성
    """
    q = """
    SELECT
      extracurricular_id,
      title,
      url,
      description,
      activity_start,
      activity_end,
      application_start,
      application_end,
      location
    FROM extracurricular
    """
    rows = []
    for r in conn.execute(sql_text(q)).mappings():
        title = (r.get("title") or "").strip()
        url   = (r.get("url") or "").strip()

        apply_line = ""
        if r.get("application_start") or r.get("application_end"):
            # JSON은 종종 날짜 사이 공백 없이 ~ 연결 → 여긴 공백 최소화
            a1 = _fmt_dt(r.get("application_start"))
            a2 = _fmt_dt(r.get("application_end"))
            apply_line = f"{a1}~{a2}".replace("  ", " ")

        event_line = ""
        if r.get("activity_start") or r.get("activity_end"):
            e1 = _fmt_dt(r.get("activity_start"))
            e2 = _fmt_dt(r.get("activity_end"))
            # "YYYY.MM.DD HH:MM~YYYY.MM.DD HH:MM"
            event_line = f"{e1}~{e2}".replace("  ", " ")

        place = (r.get("location") or "").strip()
        desc  = (r.get("description") or "").strip()

        # JSON의 text 형식을 최대한 모사
        text = "\n".join(filter(None, [
            f"제목: {title}",
            f"URL: {url}" if url else "",
            f"신청기간: {apply_line}" if apply_line else "",
            f"진행기간: {event_line}" if event_line else "",
            f"장소: {place}" if place else "",
            desc
        ])).strip()

        rows.append({"id": r["extracurricular_id"], "text": text})
    return rows

def load_activities_from_db():
    with engine.connect() as conn:
        rows = _load_and_synthesize_text_for_extracurricular(conn)
        if rows:
            return rows
    raise RuntimeError("DB에서 비교과 데이터를 찾지 못했습니다. (extracurricular 테이블이 비었을 수 있음)")


# -----------------------------
# 파서/스코어링 (JSON 버전과 동일한 규칙)
# -----------------------------
def parse_title(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("제목:"):
            return line.replace("제목:", "", 1).strip()
    return "이름 없음"

def extract_fields(text: str) -> dict:
    out = {"제목": parse_title(text)}
    # KUM 마일리지: 다중 매칭 → 최댓값(숫자만)
    nums = re.findall(r"(?:KUM|쿰)\s*마일리(?:지|리지)[^\d]{0,8}(\d{1,3})", text)
    if nums:
        out["KUM마일리지"] = str(max(int(n) for n in nums))
    for k, pat in FIELD_PATTERNS.items():
        if k == "KUM마일리지":
            continue
        m = re.search(pat, text)
        if m:
            out[k] = m.group(1).strip()
    return out

def _weekday_kor_from_date_str(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y.%m.%d")
        return {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}[dt.strftime("%a")]
    except:
        return ""

def parse_schedule(text: str):
    """
    JSON 텍스트 포맷을 기준:
    - "진행기간: 2025.05.27 14:00~2025.05.27 16:00"
    - 괄호 요일이 껴도 허용
    """
    def _clean(s: str) -> str:
        return re.sub(r"\([^)]+\)", "", s).strip()

    for line in text.splitlines():
        if line.startswith("진행기간:"):
            raw = _clean(line.replace("진행기간:", "", 1).strip())

            # 1) 서로 다른 날짜
            m = re.match(
                r"(\d{4}\.\d{1,2}\.\d{1,2})\s+(\d{1,2}:\d{2})\s*[~\-]\s*(\d{4}\.\d{1,2}\.\d{1,2})\s+(\d{1,2}:\d{2})",
                raw
            )
            # 2) 같은 날짜 (두 번째 날짜 생략)
            n = re.match(
                r"(\d{4}\.\d{1,2}\.\d{1,2})\s+(\d{1,2}:\d{2})\s*[~\-]\s*(\d{1,2}:\d{2})",
                raw
            )
            if not (m or n):
                return None

            if m:
                start_day, start_time, end_day, end_time = m.groups()
            else:
                start_day, start_time, end_time = n.groups()
                end_day = start_day

            day = _weekday_kor_from_date_str(start_day)
            return {"day": day, "startTime": start_time, "endTime": end_time}
    return None

def _parse_user_time_constraint(q: str):
    """
    '수요일 12시~5시', '수요일 12:00~17:00', '수요일 추천해줘' → {"day": "...", "start": "...", "end": "..."} or {"day": "..."}
    """
    day_map = {"월":"월","화":"화","수":"수","목":"목","금":"금","토":"토","일":"일"}
    out = {}
    for d in day_map:
        if d in q:
            out["day"] = d
            break
    # 느슨한 시각 범위
    pat = r"(\d{1,2})\s*(?:시|:)?\s*(\d{0,2})?\s*[~\-]\s*(\d{1,2})\s*(?:시|:)?\s*(\d{0,2})?"
    m = re.search(pat, q)
    if m:
        s_h = int(m.group(1)); s_m = int(m.group(2) or 0)
        e_h = int(m.group(3)); e_m = int(m.group(4) or 0)
        if e_h < s_h:
            e_h += 12 if s_h <= 12 else 0
        out["start"] = f"{s_h:02d}:{s_m:02d}"
        out["end"]   = f"{e_h:02d}:{e_m:02d}"
    return out or None

def _time_overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    fmt = "%H:%M"
    s1, e1 = datetime.strptime(a_start, fmt), datetime.strptime(a_end, fmt)
    s2, e2 = datetime.strptime(b_start, fmt), datetime.strptime(b_end, fmt)
    return max(s1, s2) < min(e1, e2)


# -----------------------------
# 글로벌 상태/캐시
# -----------------------------
load_dotenv()

activities = []                 # [{"id": int, "text": str}, ...]
title_embeddings = []           # [np.array(1,d), ...]
recent_top5_idx_title_map = {}  # {1: "제목", ...}
recent_top5_idx_id_map = {}     # {1: id, ...}
last_queried_title: str | None = None

def initialize_activities():
    """DB에서 활동 로드 + 타이틀 임베딩 캐시 생성"""
    global activities, title_embeddings
    activities = load_activities_from_db()
    title_embeddings = []
    for item in activities:
        title = parse_title(item.get("text", ""))
        title_embeddings.append(get_embedding(title))


# -----------------------------
# 검색(추천): JSON 버전의 동작 & 출력 재현
# -----------------------------
def _schedule_ok_for_user(schedule: dict | None, user_profile: dict) -> bool:
    if not schedule:
        return False
    # 유저 시간표 충돌 제외
    for slot in (user_profile.get("timetable") or []):
        if slot.get("day") == schedule["day"] and _time_overlap(
            slot["startTime"], slot["endTime"], schedule["startTime"], schedule["endTime"]
        ):
            return False
    return True

def search_top5_programs_with_explanation(query: str, user_profile: dict):
    """
    반환: (텍스트, [id...])
    - 텍스트: JSON 버전처럼 각 항목에 점수 3종 표시
    """
    global recent_top5_idx_title_map, recent_top5_idx_id_map, last_queried_title

    if not activities or not title_embeddings:
        initialize_activities()

    query_emb = get_embedding(query)
    interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    interest_emb = get_embedding(interest_text)

    # (1) KUM 마일리지 숫자 필터
    mileage_filter = None
    m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)[^\d]{0,3}(\d{1,3})", query)
    if m:
        mileage_filter = int(m.group(1))

    scored = []
    for idx, item in enumerate(activities):
        text = item.get("text", "")
        schedule = parse_schedule(text)
        if not _schedule_ok_for_user(schedule, user_profile):
            continue

        fields = extract_fields(text)

        # (2) 마일리지 숫자 필터
        if mileage_filter is not None:
            v = fields.get("KUM마일리지")
            if not v or int(v) != mileage_filter:
                continue

        # (3) 유사도 점수 계산 + 낮은 항목 컷(JSON과 동일 임계)
        title_emb = title_embeddings[idx]
        qsim = float(cosine_similarity(title_emb, query_emb)[0][0])
        isim = float(cosine_similarity(title_emb, interest_emb)[0][0]) if interest_text else 0.0
        if qsim < 0.30 and isim < 0.30:
            continue

        title = fields.get("제목", parse_title(text))
        score = 0.8 * qsim + 0.2 * isim
        scored.append((idx, item["id"], title, score, qsim, isim, fields.get("KUM마일리지")))

    if not scored:
        return ("조건에 맞는 프로그램을 찾지 못했습니다.", [])

    top5 = sorted(scored, key=lambda x: x[3], reverse=True)[:5]

    # 숫자 선택용 맵 (제목/ID 모두 저장)
    recent_top5_idx_title_map = {i+1: top5[i][2] for i in range(len(top5))}
    recent_top5_idx_id_map    = {i+1: top5[i][1] for i in range(len(top5))}
    globals()["recent_top5_idx_title_map"] = recent_top5_idx_title_map
    globals()["recent_top5_idx_id_map"] = recent_top5_idx_id_map

    # 후속 '그건...' 안정화를 위해 1등 제목 보관
    last_queried_title = top5[0][2]

    # (4) 출력 포맷: JSON 버전과 동일하게 점수 노출
    lines = []
    for i, (_idx, _id, title, score, qsim, isim, kum) in enumerate(top5, start=1):
        miles = f" — KUM마일리지: {kum}점" if kum else ""
        lines.append(f"{i}. {title}{miles}\n    - 종합 점수: {score:.3f} (질문 유사도: {qsim:.3f}, 관심사 유사도: {isim:.3f})")

    text_out = "\n\n".join(lines)
    ids_out = [t[1] for t in top5]
    return (text_out, ids_out)


# -----------------------------
# 필드 단답 & 자유 요약 (JSON 버전과 동일 논리)
# -----------------------------
def _short_field_answer(query: str, fields: dict) -> str | None:
    field = _which_field_from_query(query)
    if not field:
        return None
    val = fields.get(field)

    # JSON 평가 포맷: "KUM마일리지: 20" (점 제거)
    if field == "KUM마일리지" and val:
        m = re.search(r"\d+", val)
        val = m.group(0) if m else val

    return f"{field}: {val if val else '자료에 없음'}"

def answer_program_question_by_title(query: str) -> str:
    """
    제목 포함/유사도 기반으로 1개 선택 → 필드 단답 우선, 아니면 간단 요약
    (JSON 버전의 임계/맥락 fallback 유지)
    """
    global last_queried_title

    if not activities or not title_embeddings:
        initialize_activities()

    # (A) 정확 제목 포함 매칭
    best_idx = -1
    for i, item in enumerate(activities):
        title_i = parse_title(item.get("text", ""))
        if title_i and title_i in query:
            best_idx = i
            break

    # (B) 임베딩 유사도
    if best_idx == -1:
        q_emb = get_embedding(query)
        best_score = -1.0
        for idx, title_emb in enumerate(title_embeddings):
            sim = float(cosine_similarity(title_emb, q_emb)[0][0])
            if sim > best_score:
                best_score, best_idx = sim, idx
        if best_score < 0.55:
            # 최근 맥락 + 필드질문 → 최근 항목으로 단답 시도
            if last_queried_title and _which_field_from_query(query):
                for it in activities:
                    if last_queried_title in it.get("text", ""):
                        fields = extract_fields(it.get("text", ""))
                        ans = _short_field_answer(query, fields)
                        if ans:
                            return ans
            return "입력하신 질문에서 어떤 프로그램을 지칭하는지 찾을 수 없습니다."

    item = activities[best_idx]
    text = item.get("text", "")
    fields = extract_fields(text)
    last_queried_title = fields.get("제목", parse_title(text))

    # (C) 필드 단답 우선
    short = _short_field_answer(query, fields)
    if short:
        return short

    # (D) 간단 요약 (자료에만 근거)
    brief_text = text[:1500]
    prompt = (
        f"[활동정보]\n{brief_text}\n\n"
        f"[질문]\n{query}\n\n"
        "자료에 있는 내용만 근거로 한국어로 1~2문장으로 간단히 답하세요. "
        "자료에 없으면 '자료에 없음'이라고 답하세요."
    )
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=0.0,
        max_tokens=160,
        messages=[
            {"role": "system", "content": "간결하고 정확한 비교과 안내 도우미."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()


# -----------------------------
# 후속질의 치환 & 의도 분류 (JSON UX 충실)
# -----------------------------
def resolve_followup_question(user_question: str) -> str:
    """
    '2번 URL', '2', '2: URL', '그건 …' → '〈제목〉 …' 치환
    - 앞머리 자모/부호 제거 허용 ('ㄱ그건', 'ㅋㅋ 2번 URL')
    """
    global recent_top5_idx_title_map, last_queried_title

    s = user_question.strip()
    s_clean = re.sub(r"^[ㄱ-ㅎㅏ-ㅣ\W_]+", "", s)

    # 숫자만/숫자+번/숫자:tail 모두 지원
    m = re.match(r"^\s*(\d+)\s*(?:번|\.|:)?\s*(.*)$", s_clean)
    if m:
        num = int(m.group(1)); tail = (m.group(2) or "").strip()
        if num in recent_top5_idx_title_map:
            title = recent_top5_idx_title_map[num]
            last_queried_title = title
            return f"{title} {tail}".strip()

    if s_clean.startswith("그건"):
        tail = s_clean[2:].strip()
        if last_queried_title and tail:
            return f"{last_queried_title} {tail}".strip()

    return user_question

def _classify_intent(original_q: str) -> str:
    """
    - (우선) 숫자 시작('1', '1번') 또는 '그건 …' 또는 필드 키워드 → 'field'
    - 그 외에 '추천/어울리/비교과/프로그램/특강/AI/창업/캡스톤…' 포함 → 'reco'
    - 기본 → 'reco'
    (숫자만을 필드로 처리하는 점이 JSON UX 핵심)
    """
    q = original_q or ""
    nq = _normalize(q)
    head = re.sub(r"^[ㄱ-ㅎㅏ-ㅣ\W_]+", "", q.strip())

    if re.search(r"^\s*\d+\s*(?:번)?\s*(?:$|\S)", head) or head.startswith("그건") or _which_field_from_query(q):
        return "field"

    reco_trigs = ["추천", "어울리", "비교과", "프로그램", "활동", "컨설팅", "워크숍", "특강",
                  "ai", "인공지능", "데이터", "취업", "창업", "캡스톤", "디자인"]
    if any(_normalize(t) in nq for t in reco_trigs):
        return "reco"
    return "reco"


# -----------------------------
# LangChain Tool 래핑 (JSON 스타일)
# -----------------------------
def _tool_search_wrapper(user_profile):
    def _run(query: str):
        txt, ids = search_top5_programs_with_explanation(query, user_profile)
        return json.dumps({"text": txt, "ids": ids}, ensure_ascii=False)
    return _run

def _tool_field_answer(query: str):
    return answer_program_question_by_title(query)

def make_agent(user_profile):
    tools = [
        Tool(
            name="search_program",
            func=_tool_search_wrapper(user_profile),
            description="관심사/시간표/사용자 요청에 맞는 비교과 프로그램 Top5를 추천(검색)한다. 결과는 JSON({text, ids})."
        ),
        Tool(
            name="ask_program_by_title",
            func=_tool_field_answer,
            description="특정 프로그램에 대해 '신청기간/진행기간/대상자/URL/장소/수료증/KUM마일리지' 등 필드 질문을 받으면 단답 또는 짧은 요약으로 답한다."
        )
    ]
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=False,
        max_iterations=1,  # JSON 버전과 동일하게 왕복 1회
        early_stopping_method="generate",
        handle_parsing_errors=True
    )


# -----------------------------
# 최상위 진입점 (JSON 라우팅 유지)
# -----------------------------
def run_query(user_profile: dict, user_question: str):
    """
    외부에서 호출하는 단일 엔트리.
    - 추천 intent: (텍스트, [id...])  ← 텍스트 안에 점수표시 포함
    - 필드/요약 intent: (텍스트, [])
    """
    if not activities or not title_embeddings:
        initialize_activities()

    # 후속 치환 먼저 (숫자/그건)
    q = resolve_followup_question(user_question)
    intent = _classify_intent(user_question)

    if intent == "field":
        return (answer_program_question_by_title(q), [])

    txt, ids = search_top5_programs_with_explanation(q, user_profile)
    return (txt, ids)


# -----------------------------
# CLI 테스트
# -----------------------------
if __name__ == "__main__":
    load_dotenv()
    initialize_activities()
    user_id = input("사용자 ID를 입력하세요: ").strip()
    user_profile = load_user_profile(user_id)
    if not user_profile:
        print("사용자 정보를 찾을 수 없습니다.")
        exit()

    agent = make_agent(user_profile)

    while True:
        question = input("\n궁금한 내용을 입력하세요 ('종료' 입력 시 종료): ").strip()
        if question == "종료":
            break
        # JSON UX처럼: agent로 래핑하되, 내부 라우팅은 run_query 사용
        # (툴만 쓸 수도 있지만, 여기선 run_query로 바로)
        text, ids = run_query(user_profile, question)
        print("\n답변:\n", text)
        if ids:
            print("\n[추천된 extracurricular_id]:", ids)


# ---------------------------------------
# (평가/디버깅용) 상위 k개 구조화 반환 (JSON 버전과 동일)
# ---------------------------------------
def ranked_programs(query: str, user_profile: dict, k: int = 5):
    if not activities or not title_embeddings:
        initialize_activities()

    query_emb = get_embedding(query)
    interest_text = " ".join(user_profile.get("interests", [])) if user_profile.get("interests") else ""
    interest_emb = get_embedding(interest_text)

    m = re.search(r"(?:KUM|쿰)?\s*마일리(?:지|리지)[^\d]{0,3}(\d{1,3})", query)
    mileage_filter = int(m.group(1)) if m else None

    rows = []
    for idx, item in enumerate(activities):
        text = item.get("text", "")
        schedule = parse_schedule(text)
        if not schedule:
            continue
        # 유저 시간표 충돌 제외
        conflict = False
        for slot in (user_profile.get("timetable") or []):
            if slot.get("day") == schedule["day"] and _time_overlap(
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
        qsim = float(cosine_similarity(title_emb, query_emb)[0][0])
        isim = float(cosine_similarity(title_emb, interest_emb)[0][0]) if interest_text else 0.0
        if qsim < 0.30 and isim < 0.30:
            continue

        title = fields.get("제목", parse_title(text))
        score = 0.8 * qsim + 0.2 * isim
        rows.append({
            "idx": idx,
            "id": item["id"],
            "title": title,
            "score": float(score),
            "query_sim": float(qsim),
            "interest_sim": float(isim),
            "fields": fields,
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:k]