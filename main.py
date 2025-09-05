from fastapi import FastAPI
from app.models.user import UserProfile, ChatRequest
from app.services.user_service import save_user_profile, load_user_profile
from app.chatbot.Agent_Rag_Chatbot import run_query, initialize_activities, activities
from app.services.report_service import generate_reports_for_users
from app.utils.constants.message import Message
from app.models.response.base_response import response, BaseResponse
from app.models.request.report_request import ReportRequest
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException
from fastapi.exceptions import RequestValidationError
from app.utils.exception_handler import app_exception_handler, generic_exception_handler, validation_exception_handler
from datetime import datetime
import os, glob
from datetime import datetime, timedelta
from fastapi.staticfiles import StaticFiles   

app = FastAPI()

app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

REPORT_DIR = os.getenv("REPORT_DIR", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
app.mount("/reports", StaticFiles(directory=REPORT_DIR, html=False), name="reports")

# @app.get("/error-test") - 에러 핸들러 테스트용(해봄)
# def test_error():
#     raise AppException(ErrorCode.USER_PROFILE_MISSING)


@app.post("/register", response_model=BaseResponse,
    summary="사용자 등록",
    description="사용자 정보를 등록하고 프로필을 저장합니다.",
    tags=["사용자 정보"],
    responses={
        422: {"model": BaseResponse, "description": ErrorCode.VALIDATION_ERROR.message},
        500: {"model": BaseResponse, "description": ErrorCode.INTERNAL_SERVER_ERROR.message}
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
        400: {"model": BaseResponse, "description": ErrorCode.USER_PROFILE_MISSING.message},
        404: {"model": BaseResponse, "description": ErrorCode.NO_RELEVANT_DOCUMENT.message},
        422: {"model": BaseResponse, "description": ErrorCode.VALIDATION_ERROR.message},
        500: {"model": BaseResponse, "description": ErrorCode.INTERNAL_SERVER_ERROR.message}
    })
async def chat_with_bot(request: ChatRequest):
    user_id = request.id
    user_question = request.question

    user_profile = load_user_profile(user_id)
    if not user_profile:
        raise AppException(ErrorCode.USER_PROFILE_MISSING)

    if not activities:
        initialize_activities()

    # agent = make_agent(user_profile)
    # query = resolve_followup_question(user_question);
    # result = agent.run(query)
    result = run_query(user_profile, user_question)
    # from app.chatbot.Agent_Rag_Chatbot import chat_reply
    # result = chat_reply(user_profile, user_question)

    return response(
        message=Message.CHAT_RESPONSE_SUCCESS,
        data={
            "answer": result
            # 여기서 url과 json에 index를 할당해놔서, 답변 활용했던 index를 반환할 수 있도록 설정 - AI
        }
    )

@app.post(
    "/report",
    response_model=BaseResponse,
    summary="리포트 생성",
    description="사용자들에 대한 리포트를 생성해 알림을 전송합니다.",
    tags=["리포트 전송"],
    responses={
        400: {"model": BaseResponse, "description": ErrorCode.INVALID_ACTIVITY_DATE_DATA.message},
        400: {"model": BaseResponse, "description": ErrorCode.INVALID_ACTIVITY_DATA.message},
        422: {"model": BaseResponse, "description": ErrorCode.VALIDATION_ERROR.message},
        500: {"model": BaseResponse, "description": ErrorCode.REPORT_GENERATION_FAILED.message},
        500: {"model": BaseResponse, "description": ErrorCode.ACTIVITY_LOAD_FAILED.message},
        500: {"model": BaseResponse, "description": ErrorCode.DATA_ACCESS_ERROR.message},
    },
)
async def create_report(request: ReportRequest):
    
    # 기본 검증
    if not request.users:
        raise AppException(ErrorCode.INVALID_ACTIVITY_DATA)

    # 날짜 파싱
    try:
        start_date = datetime.fromisoformat(request.start_date)
        end_date = datetime.fromisoformat(request.end_date)
    except ValueError:
        raise AppException(ErrorCode.INVALID_ACTIVITY_DATE_DATA)

    if end_date < start_date:
        raise AppException(ErrorCode.VALIDATION_ERROR)


    try:
        user_activity_map = {u.userId: u.activities for u in request.users}
    except Exception:
        raise AppException(ErrorCode.INVALID_ACTIVITY_DATA)


    try:
        msg, failed = generate_reports_for_users(
            user_activity_map=user_activity_map,
            start_date=start_date,
            end_date=end_date,
        )
    except AppException:
        raise
    except Exception:
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)

    if failed:
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)

    return BaseResponse(success=True, code = 200, message=msg, failed=failed)

