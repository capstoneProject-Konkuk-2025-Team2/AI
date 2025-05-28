from fastapi import FastAPI
from app.models.user import UserProfile, ChatRequest
from app.services.user_service import save_user_profile, load_user_profile
from app.services.context_builder import build_user_context
from app.config.llm_config import model, query_engine
from app.services.mvp_chatbot import (
    load_user_profile,
    load_filtered_programs_from_folder,
    filter_by_interest,
    generate_llm_prompt
)
from llmware.models import ModelCatalog
from app.models.response.base_response import response, BaseResponse
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from fastapi.exceptions import RequestValidationError
from app.utils.exception_handler import (
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler
)
import json

app = FastAPI()

# 예외 핸들러 등록
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


# TODO: 성공 응답 DTO도 정할지 고민
@app.post("/register", response_model=BaseResponse,
    responses={
        422: {
            "model": BaseResponse,
            "description": ErrorCode.VALIDATION_ERROR.message
        },
        500: {
            "model": BaseResponse,
            "description": ErrorCode.INTERNAL_SERVER_ERROR.message
        }
    })
async def register_user(profile: UserProfile):
    save_user_profile(profile.model_dump())
    return response(
        message="사용자 정보가 성공적으로 저장되었습니다.",
        data={"user_profile": profile.model_dump()})


@app.post("/chat", response_model=BaseResponse,
          responses={
        400: {
            "model": BaseResponse,
            "description": ErrorCode.USER_PROFILE_MISSING.message
        },
        404: {
            "model": BaseResponse,
            "description": ErrorCode.NO_RELEVANT_DOCUMENT.message
        },
        422: {
            "model": BaseResponse,
            "description": ErrorCode.VALIDATION_ERROR.message
        },
        500: {
            "model": BaseResponse,
            "description": ErrorCode.INTERNAL_SERVER_ERROR.message
        }
    })
async def chat_with_bot(request: ChatRequest):
    user_id = request.id
    user_question = request.question

    # 사용자 정보 로드
    user_profile = load_user_profile(user_id)
    if not user_profile:
        raise AppException(ErrorCode.USER_PROFILE_MISSING)

    # 시간 겹침 필터링
    step1_programs = load_filtered_programs_from_folder(user_profile)

    # 관심사 기반 필터링
    step2_programs = filter_by_interest(step1_programs, user_profile["interests"])

    if not step2_programs:
        raise AppException(ErrorCode.NO_RELEVANT_DOCUMENT)

    # 프롬프트 생성 및 LLM 호출
    final_prompt = generate_llm_prompt(user_profile, user_question, step2_programs)
    model = ModelCatalog().load_model("bling-answer-tool")
    response_data = model.inference(final_prompt)


    return response(
        message="사용자 정보를 반영해 성공적으로 응답했습니다.",
        data={
            "user_summary": f"{user_profile['name']}님의 관심사는 {', '.join(user_profile['interests'])}입니다. 시간표는 다음과 같습니다:\n" + "\n".join([f"{t['day']} {t['startTime']}~{t['endTime']}" for t in user_profile["timetable"]]),
            "recommendation_intro": f"위 정보를 바탕으로 시간표와 겹치지 않고 {', '.join(user_profile['interests'])}과 관련된 활동을 추천해드립니다.",
            "answer": response_data["llm_response"],
            "total_programs": len(step2_programs),
            "recommended_programs": step2_programs[:3]
        }
    )
