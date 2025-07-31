from fastapi import FastAPI
from app.models.user import UserProfile, ChatRequest
from app.services.user_service import save_user_profile, load_user_profile
from app.chatbot.agent_rag_chatbot import (
    make_agent,
    initialize_activities,
    resolve_followup_question,
    activities
)
from app.utils.constants.message import Message
from app.models.response.base_response import response, BaseResponse
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from fastapi.exceptions import RequestValidationError
from app.utils.exception_handler import (
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler
)
from app.models.activity import Activity
from app.services import activity_service

app = FastAPI()

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# @app.get("/error-test") - 에러 핸들러 테스트용(해봄)
# def test_error():
#     raise AppException(ErrorCode.USER_PROFILE_MISSING)


@app.post("/register", response_model=BaseResponse,
    summary="사용자 등록",
    description="사용자 정보를 등록하고 프로필을 저장합니다.",
    tags=["사용자 정보"],
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
        message=Message.USER_REGISTER_SUCCESS,
        data={
            "user_profile": profile.model_dump()
            }
        )


@app.post("/chat", response_model=BaseResponse,
    summary="챗봇과 대화 요청",
    description="사용자 프로필을 기반으로 챗봇과 자연어로 대화를 수행합니다.",
    tags=["챗봇 통신"],
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

    user_profile = load_user_profile(user_id)
    if not user_profile:
        raise AppException(ErrorCode.USER_PROFILE_MISSING)

    if not activities:
        initialize_activities()

    agent = make_agent(user_profile)
    query = resolve_followup_question(user_question);
    result = agent.run(query)

    return response(
        message=Message.CHAT_RESPONSE_SUCCESS,
        data={
            "answer": result
        }
    )

# 필요없는것 같은데
@app.post("/activities", response_model=BaseResponse,
    summary="사용자 활동 정보 저장",
    description=
        """
        사용자의 활동(Activity) 정보를 서버에 저장합니다.  
        활동에는 제목, 설명, 카테고리, 시작/종료 시간, 키워드, 위치 등의 정보가 포함됩니다.  
        저장이 완료되면 고유한 활동 ID를 반환합니다.
        """,
    tags=["사용자 정보"],
    responses={
        400: {
            "model": BaseResponse,
            "description": ErrorCode.INVALID_ACTIVITY_DATA.message
        },
        500: {
            "model": BaseResponse,
            "description": ErrorCode.ACTIVITY_SAVE_FAILED.message
        }
    })
async def add_activity(activity: Activity):
    activity_id = activity_service.save_activity(activity)
    return response(
        message=Message.ACTIVITY_SAVE_SUCCESS,
        data={"activity_id": activity_id}
    )