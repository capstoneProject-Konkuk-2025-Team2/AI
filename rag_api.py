from fastapi import FastAPI, HTTPException
from models.user import UserProfile, ChatRequest
from services.user_service import save_user_profile, load_user_profile
from services.context_builder import build_user_context
from config.llm_config import model, query_engine

# FastAPI 초기화
app = FastAPI()

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
    user_profile = load_user_profile(user_id)
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
