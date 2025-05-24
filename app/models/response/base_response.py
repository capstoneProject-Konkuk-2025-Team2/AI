from pydantic import BaseModel
from typing import Optional, Any
from app.utils.constants.error_codes import ErrorCode

class BaseResponse(BaseModel):
    code: int
    message: Optional[str] = None
    data: Optional[Any] = None

def response(
    message: Optional[str] = None,
    data: Any = None
) -> BaseResponse:
    return BaseResponse(
        code=200,
        message=message,
        data=data
    )

def error_response(error: ErrorCode) -> tuple[int, dict]:
    res = BaseResponse(
        code=error.http_status,
        message=error.message
    )
    return error.http_status, res.model_dump()
