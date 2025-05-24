from fastapi import FastAPI
from models.user import UserProfile, ChatRequest
from services.user_service import save_user_profile, load_user_profile
from services.context_builder import build_user_context
from config.llm_config import model, query_engine
from models.response import response
from models.response import BaseResponse
from utils.constants.error_codes import ErrorCode
from utils.app_exception import AppException
from utils.exception_handler import (
    app_exception_handler,
    generic_exception_handler
)
app = FastAPI()

# 에외 핸들러 등록
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


# TODO: 성공 응답 DTO도 정할지 고민
@app.post("/register/{user_id}", response_model=BaseResponse)
def register_user(user_id: str, profile: UserProfile):
    save_user_profile(user_id, profile.model_dump())
    return response(
        success = True,
        message = "사용자 정보가 성공적으로 저장되었습니다.",
        data = {"user_id": user_id})


@app.post("/chat", response_model=BaseResponse)
async def chat_with_bot(request: ChatRequest):
    user_id = request.id
    user_question = request.question

    # 사용자 정보 로드
    user_profile = load_user_profile(user_id)
    if not user_profile:
        raise AppException(ErrorCode.USER_PROFILE_MISSING)

    # 사용자 context 생성
    user_context = build_user_context(user_profile)
    
    # semantic query
    search_results = query_engine.semantic_query(user_question, result_count=3)

    if not search_results:
        raise AppException(ErrorCode.NO_RELEVANT_DOCUMENT)

    # context 결합
    combined_context = " ".join([res["text"] for res in search_results])

    # 최종 context 조합
    final_context = user_context + "\n" + combined_context

    # 모델 추론
    answer = model.inference(user_question, add_context=final_context)

    return response(
            success = True,
            message = "사용자 정보를 반영해 성공적으로 응답했습니다.",
            data = {"answer": answer}
        )
