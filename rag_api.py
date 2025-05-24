from fastapi import FastAPI, Request
from pydantic import BaseModel
from llmware.library import Library
from llmware.retrieval import Query
from llmware.models import ModelCatalog
from llmware.configs import LLMWareConfig, MilvusConfig
import json
import os

# 초기 설정
LLMWareConfig().set_active_db("sqlite")
MilvusConfig().set_config("lite", True)
LLMWareConfig().set_vector_db("chromadb")
USER_TABLE_PATH = "user.json"

# 라이브러리 및 모델 로딩
library_name = "my_library"
embedding_model = "mini-lm-sbert"
llm_model_name = "bling-answer-tool"

lib = Library().load_library(library_name)
query_engine = Query(lib)
model = ModelCatalog().load_model(llm_model_name)

# FastAPI 초기화
app = FastAPI()

class ChatRequest(BaseModel):
    id: str
    question: str


@app.post("/register/{user_id}")
def register_user(user_id: str, profile: UserProfile):
    try:
        save_user_profile(user_id, profile.dict()) # 함수 구성
        return {"message": f"{user_id}의 정보가 성공적으로 저장되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) # 예외처리 어떻게 할지


@app.post("/chat")
async def chat_with_bot(request: ChatRequest):
    user_id = request.id
    user_question = request.question

    # 사용자 정보 로드
    user_profile = load_user_table(user_id)
    if not user_profile:
        return {"answer": "사용자 정보가 없습니다. 먼저 입력해 주세요."}

    # 사용자 context 생성
    user_context = build_user_context(user_profile)
    # semantic query
    search_results = query_engine.semantic_query(user_question, result_count=3)

    if not search_results:
        return {"answer": "관련 정보를 찾지 못했습니다."}

    # context 결합
    combined_context = " ".join([res["text"] for res in search_results])

    # 최종 context 조합
    final_context = user_context + "\n" + combined_context
    
    # 모델 추론
    answer = model.inference(user_question, add_context=final_context)

    return {"answer": answer}


# user.json에서 특정 사용자의 정보를 불러옴
def load_user_table(user_id: str) -> dict | None:
    if not os.path.exists(USER_TABLE_PATH):
        return None

    try:
        with open(USER_TABLE_PATH, "r") as f:
            users = json.load(f)
        return users.get(user_id)
    except Exception:
        return None
    
def build_user_context(user_profile: dict) -> str:
    parts = []

    name = user_profile.get("이름", "알 수 없음")
    major = user_profile.get("학과", "")
    year = user_profile.get("학년", "")
    interests = user_profile.get("관심사", [])
    timetable = user_profile.get("시간표", [])

    # 기본 정보
    if name or major or year:
        parts.append(f"{name}은(는) {major} {year}입니다.")

    # 관심사
    if interests:
        interest_str = ", ".join(interests)
        parts.append(f"관심사는 {interest_str}입니다.")

    # 시간표 요약
    if timetable:
        schedule_str = "; ".join(
            [f"{item['요일']} {item['시작시간']}~{item['종료시간']}" for item in timetable]
        )
        parts.append(f"수업 시간은 다음과 같습니다: {schedule_str}.")

    return " ".join(parts)
