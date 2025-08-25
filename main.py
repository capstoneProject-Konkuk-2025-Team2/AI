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
from app.services import activity_service, report_service
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import HTTPException
from pydantic import BaseModel, Field

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
            # 여기서 url과 json에 index를 할당해놔서, 답변 활용했던 index를 반환할 수 있도록 설정 - AI
        }
    )

# 요청 바디 모델
class UserActivities(BaseModel):
    user_id: int = Field(..., alias="userId")
    activities: List[int]

class ReportRequest(BaseModel):
    users: List[UserActivities]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

@app.post(
    "/report",
    response_model=BaseResponse,
    summary="리포트 생성",
    description="사용자들에 대한 리포트를 생성해 알림을 전송합니다.",
    responses={
        400: {"model": BaseResponse, "description": ErrorCode.INVALID_ACTIVITY_DATA.message},
        500: {"model": BaseResponse, "description": ErrorCode.ACTIVITY_SAVE_FAILED.message},
    },
)
async def send_report(req: ReportRequest):
    # 검증: 중복 userId, 빈 activities, 날짜 범위
    seen = set()
    for u in req.users:
        if not u.activities:
            raise HTTPException(status_code=400, detail=ErrorCode.INVALID_ACTIVITY_DATA.message)
        if u.user_id in seen:
            raise HTTPException(status_code=400, detail=ErrorCode.INVALID_ACTIVITY_DATA.message)
        seen.add(u.user_id)
    if req.start_date and req.end_date and req.start_date > req.end_date:
        raise HTTPException(status_code=400, detail=ErrorCode.INVALID_ACTIVITY_DATA.message)

    # 기존 서비스 시그니처로 변환
    user_payloads: List[Dict] = [{"user_id": u.user_id} for u in req.users]
    user_activity_map: Dict[int, List[int]] = {u.user_id: u.activities for u in req.users}

    report_service.generate_reports_for_users(
        user_payloads=user_payloads,
        user_activity_map=user_activity_map,
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return response(message=Message.ACTIVITY_SAVE_SUCCESS)