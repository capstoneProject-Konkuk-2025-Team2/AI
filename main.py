from fastapi import FastAPI
from app.models.user import UserProfile, ChatRequest
from app.services.user_service import save_user_profile, load_user_profile
from app.chatbot.Agent_Rag_Chatbot import (
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
from app.services.activity_service import ActivityService

app = FastAPI()
activity_service = ActivityService()

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# @app.get("/error-test") - 에러 핸들러 테스트용(해봄)
# def test_error():
#     raise AppException(ErrorCode.USER_PROFILE_MISSING)


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
        message=Message.USER_REGISTER_SUCCESS,
        data={
            "user_profile": profile.model_dump()
            }
        )


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

# 사용자가 활동 데이터를 activities.json에 저장한다 - 형식 상의하기
@app.post("/activities", response_model=BaseResponse)
async def add_activity(activity: Activity):
    try:
        activity_id = activity_service.save_activity(activity)
        return response(
            message=Message.USER_ADD_ACTIVITY_SUCCESS,
            data={"activity_id": activity_id}
        )
    except Exception as e:
        raise AppException(ErrorCode.INTERNAL_SERVER_ERROR)

